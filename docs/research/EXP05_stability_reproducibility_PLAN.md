# PLAN — EXP-05 Stability & Reproducibility (Revision 1)

> **Mục đích:** Tài liệu này là **implementation PLAN** cho EXP-05,
> không phải Mentor document hoàn chỉnh.
>
> **Revision history:**
> - Revision 0: bản draft ban đầu.
> - Revision 1: sửa theo mentor review — điều chỉnh Block R/S/N, bổ
>   sung EPIC-08 boundary, schema label artifact, scope guards (xem
>   §15 cho diff chi tiết).
>
> **TUYỆT ĐỐI KHÔNG** chạy code / tạo file / sửa file / commit /
> push / PR trong bước này ngoài implementation phase đã được thực
> hiện.

---

## 1. Phạm vi EXP-05

### 1.1. Mục tiêu

EXP-05 generate raw **stability evidence** và **reproducibility
evidence** cho 5 thuật toán EPIC-06 trên FE-06 final clustering
matrix, bằng cách chạy ba khối thực nghiệm độc lập:

- **Block R — Reproducibility**: 5 thuật toán × `n_repeat=5` × seed=42.
  Verify `labels_hash` và metric values deterministic. Đây là
  **reproducibility evidence**, không phải stability analysis.
- **Block S — Random Seed Stability**: K-Means + GMM + FCM (3 thuật
  toán có random axis) × seeds = [42, 7, 123, 2024, 1729] ×
  `n_repeat=1`. Fixed hyperparameters. Ghi nhận metrics + cluster
  sizes + `labels_hash`. KHÔNG ranking algorithm. Agglomerative và
  DBSCAN không cần seed sweep (deterministic).
- **Block N — Feature Perturbation**: In-memory perturbation trên
  FE-06 final clustering matrix. `sigma` = 0, 0.01, 0.05 × feature
  std. `sigma=0` chỉ cần 1 sanity run / algorithm để đối chiếu
  EXP-01. `sigma=1%` và `sigma=5%`: 3 perturbation seeds
  [42, 43, 44]. KHÔNG persist perturbed dataset. KHÔNG assert trước
  rằng labels phải thay đổi. Verify input FE-06 SHA unchanged.

EXP-05 xuất raw labels artifact (label-level) thay vì chỉ
`labels_hash`. Artifact này là đầu vào cần thiết cho EPIC-08 tính
ARI / AMI, Hungarian matching, statistical tests, confidence
intervals.

### 1.2. Ranh giới EXP-05

| EXP-05 LÀM | EXP-05 KHÔNG LÀM |
|------------|------------------|
| Generate reproducibility evidence (Block R) | Stability analysis (EPIC-08) |
| Generate random-seed stability evidence (Block S) | ARI / AMI computation (EPIC-08) |
| Generate feature-perturbation evidence (Block N) | Hungarian matching (EPIC-08) |
| Xuất raw labels artifact (`exp05_cluster_labels.parquet`) | Statistical tests (EPIC-08) |
| Aggregate metrics (mean/std/min/max/CV) | Confidence intervals (EPIC-08) |
| Variation statistics (labels_hash_unique_count, ...) | Cross-algorithm ranking |
| Pre/post SHA check cho FE-06 input | Composite score |
| Provenance metadata cho mỗi run | "Best" / "winner" / "optimal" / "recommended" / "final" claim |
| CustomerID alignment với FE-06 metadata | Sampling / subsampling |
| | Re-sweep hyperparameters (EXP-03) |
| | Re-sweep preprocessing (EXP-04) |
| | K sweep (EXP-02) |
| | Persist perturbed datasets |

### 1.3. Tiêu chí "thành công" của EXP-05

EXP-05 TECHNICALLY_IMPLEMENTED khi:

1. **Block R**: 5 algorithms × 5 repeats = 25 runs; `labels_hash`
   deterministic across repeats per algorithm.
2. **Block S**: 3 algorithms (K-Means, GMM, FCM) × 5 seeds × 1
   repeat = 15 runs.
3. **Block N**: 5 algorithms × 1 sigma=0 run + 5 algorithms × 2
   sigma (1%, 5%) × 3 perturbation seeds = 35 runs.
4. **Total runs**: 25 + 15 + 35 = 75 runs.
5. **Labels artifact** `reports/exp05/exp05_cluster_labels.parquet`
   đúng schema (run_id, block, algorithm, seed, sigma,
   perturbation_seed, repeat_index, CustomerID, cluster_label).
6. **CustomerID alignment** với FE-06 metadata.
7. **Pre/post SHA check** cho FE-06 input (NO mutation).
8. **Tất cả tests** pass (unit + integration).
9. **Lint + format** pass.
10. **Không có** "best/optimal/winner/recommended/final" claim.

---

## 2. Hiện trạng EPIC-06/07 (gap analysis)

### 2.1. Tái sử dụng từ EXP-01 → EXP-04

| Component | Tái sử dụng? |
|-----------|--------------|
| `ExperimentRunner` (`runner.py`) | **CÓ** — gọi trực tiếp, không sửa |
| `FrameworkConfig` + `load_framework_config` | **CÓ** |
| 5 algorithm adapters | **CÓ** — registry không sửa |
| `ClusterResult` / `ExperimentResult` schema | **CÓ** — không sửa |
| `metrics.py` (`attach_metrics_with_status`, `compute_runtime_stats`) | **CÓ** |
| `baseline.py` (`BaselineRunner`, `BaselineSpec`, `BaselineResult`) | **CÓ** — pattern reused |
| `validation.py` (`validate_clustering_matrix`, `validate_customer_alignment`) | **CÓ** |
| `config.py` (`compute_text_sha256`, `load_framework_config`) | **CÓ** |
| `preprocessing_feature_sensitivity.py` (`compute_labels_hash`, `ScenarioSpec` pattern) | **CÓ** — pattern reused cho label artifact |
| Working defaults từ `configs/exp01_baseline.yaml` | **CÓ** — mirror |
| `configs/clustering.yaml` framework block | **CÓ** |

### 2.2. Thành phần MỚI

| Path | Mô tả |
|------|-------|
| `configs/exp05_stability_reproducibility.yaml` | EXP-05 config riêng (seeds, sigma, blocks) |
| `src/customer_segmentation/clustering/stability.py` | EXP-05 orchestrator: Block R/S/N runners + label writer + aggregators |
| `scripts/run_exp05_stability.py` | CLI entry point |
| `tests/test_exp05_stability.py` | Behavioral tests |
| `reports/exp05/*` | Output reports & label artifact |

### 2.3. Có sửa EPIC-06 framework không?

**KHÔNG.** EXP-05 chỉ:

- Đọc `FrameworkConfig` từ `configs/clustering.yaml`.
- Gọi `ExperimentRunner.run()` không qua modification.
- Reuse `metrics.attach_metrics_with_status` không qua modification.
- Reuse `AlgorithmRegistry` không qua modification.

Mọi EPIC-06 framework files (`runner.py`, `result.py`, `metrics.py`,
`baseline.py`, adapters, ...) không bị sửa.

---

## 4. Block R — Reproducibility

### 4.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans |
| Hyperparameters | EXP-01 working defaults |
| Seed | 42 (fixed) |
| n_repeat | 5 |
| Total runs | 5 × 5 = 25 |
| Determinism expectation | labels_hash identical across 5 repeats; metric values identical |

### 4.2. Output per (algorithm, repeat_index)

| Field | Type | Description |
|-------|------|-------------|
| `scenario_id` | str | "EXP05-R-REP-{algorithm}-r{repeat_index}" |
| `block` | str | "R" |
| `algorithm` | str | algorithm name |
| `seed` | int | 42 |
| `sigma` | float \| None | None (no perturbation) |
| `perturbation_seed` | int \| None | None (no perturbation) |
| `repeat_index` | int | 0..4 |
| `feature_set_sha256` | str | FE-06 input SHA |
| `hyperparameters` | dict | from EXP-01 working defaults |
| `silhouette`, `silhouette_status` | float \| None, str | from metrics layer |
| `davies_bouldin`, `davies_bouldin_status` | float \| None, str | |
| `calinski_harabasz`, `calinski_harabasz_status` | float \| None, str | |
| `wcss`, `wcss_status` | float \| None, str | |
| `runtime_seconds` | float | algorithm execution only |
| `labels_hash` | str | SHA-256 of int64 labels |
| `n_clusters_realized` | int \| None | |
| `noise_count`, `noise_ratio` | int \| None, float \| None | |
| `cluster_sizes` | dict[str, int] | per-cluster customer counts |

### 4.3. Aggregate per algorithm

- silhouette mean/std/min/max/CV
- DBI mean/std/min/max/CV
- CH mean/std/min/max/CV
- WCSS mean/std/min/max/CV
- runtime mean/std/min/max
- `labels_hash_unique_count` (expected = 1 if deterministic)
- `metric_unique_count_silhouette` etc.
- `n_clusters_unique_count`
- decision_status: `REPRODUCIBILITY_VERIFIED` nếu all identical,
 `REPRODUCIBILITY_FAILED` nếu có variation.

---

## 5. Block S — Random Seed Stability

### 5.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, gmm, fuzzy_cmeans (3 algorithms có random axis) |
| Agglomerative | KHÔNG seed sweep (deterministic trong n_clusters mode) |
| DBSCAN | KHÔNG seed sweep (deterministic) |
| Hyperparameters | EXP-01 working defaults (fixed) |
| Seeds | [42, 7, 123, 2024, 1729] |
| n_repeat per seed | 1 |
| Total runs | 3 × 5 = 15 |

### 5.2. Output per (algorithm, seed)

Same schema as Block R but:

- `scenario_id` = "EXP05-S-{algorithm}-seed{seed}"
- `seed` ∈ {42, 7, 123, 2024, 1729}
- `repeat_index` = 0
- `labels_hash` varies across seeds (this is **expected** evidence,
  not failure).

### 5.3. Aggregate per algorithm

- For each metric: mean / std / min / max / CV across 5 seeds.
- `labels_hash_unique_count` (= 5 nếu labels phụ thuộc seed; = 1
  nếu algorithm robust tới seed; both are valid evidence).
- `n_clusters_unique_count`.
- `cluster_size_distribution` per seed.

### 5.4. Phân biệt với EXP-01

EXP-01 chạy 1 seed (42) × n_repeat=5 — đó là runtime variance +
determinism verification.

EXP-05 Block S chạy 5 seeds × n_repeat=1 — đó là seed-axis evidence
để EPIC-08 tính ARI/AMI sau.

---

## 6. Block N — Feature Perturbation

### 6.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans |
| Hyperparameters | EXP-01 working defaults |
| sigma_grid | [0.0, 0.01, 0.05] (× feature std) |
| sigma=0 | 1 sanity run per algorithm (đối chiếu EXP-01) |
| sigma=0.01, 0.05 | 3 perturbation seeds [42, 43, 44] |
| n_repeat per (sigma, perturbation_seed) | 1 |
| Total runs | 5 + 5 × 2 × 3 = 5 + 30 = 35 |

### 6.2. Perturbation semantics

For each (sigma, perturbation_seed):

```
rng = np.random.default_rng(seed=perturbation_seed)
noise = rng.normal(loc=0.0, scale=1.0, size=X.shape)
X_perturbed = X + sigma * noise * feature_std
```

Trong đó `feature_std` = column-wise std của `X` (FE-06 final
clustering matrix). sigma=0.01 nghĩa là 1% noise × std; sigma=0.05
nghĩa là 5% noise × std.

### 6.3. Constraints

- Perturbation **in-memory only**. KHÔNG persist perturbed dataset
  ra disk.
- KHÔNG assert rằng labels phải thay đổi với sigma=1% hoặc 5%.
  Việc labels thay đổi hay không là **kết quả thực nghiệm**, không
  phải assumption.
- `sigma=0` chỉ là sanity check: phải reproduce EXP-01 baseline
  trong tolerance (cluster_labels identical ở library version hiện
  tại).
- Verify input FE-06 SHA unchanged (pre/post).

### 6.4. Output per (algorithm, sigma, perturbation_seed)

Same schema as Block R but:

- `scenario_id` = "EXP05-N-{algorithm}-sigma{sigma}-pseed{perturbation_seed}"
- `sigma` ∈ {0.0, 0.01, 0.05}
- `perturbation_seed` ∈ {42, 43, 44} (or None for sigma=0)
- `seed` = baseline seed (42) for algorithm

### 6.5. Aggregate per (algorithm, sigma)

- Per metric: mean / std / min / max / CV across perturbation seeds.
- `labels_hash_unique_count`.
- `metric_unique_count_silhouette`.
- `n_clusters_unique_count`.
- `baseline_labels_hash_match` (sigma=0 vs EXP-01): bool.

---

## 7. Labels Artifact — `exp05_cluster_labels.parquet`

### 7.1. Schema (REQUIRED)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | str | Unique identifier per (block, algorithm, seed, sigma, perturbation_seed, repeat_index) |
| `block` | str | "R" / "S" / "N" |
| `algorithm` | str | algorithm name |
| `seed` | int | random seed for algorithm |
| `sigma` | float \| None | None for R/S; float for N |
| `perturbation_seed` | int \| None | None for R/S; int for N |
| `repeat_index` | int | 0..4 for R; 0 for S/N |
| `CustomerID` | int64 | From FE-06 customer_metadata |
| `cluster_label` | int64 | Hard label (argmax for GMM/FCM, raw for others) |

### 7.2. CustomerID alignment

`CustomerID` MUST come from FE-06 `customer_metadata.parquet`. The
FE-06 final clustering matrix và customer metadata có cùng row
order (validation đã verify trong EPIC-06 framework). EXP-05
re-verifies alignment via `validate_customer_alignment` trước khi
ghi artifact.

### 7.3. Why a separate label artifact?

EPIC-08 cần raw labels để:

- Tính ARI/AMI across seeds (Block S).
- Hungarian matching (Block N).
- Statistical tests (Block S vs Block N).
- Confidence intervals.

`labels_hash` chỉ cho biết labels identical hay khác, không cho
biết cách chúng khác nhau thế nào. EPIC-08 cần label-level data.

---

## 8. Metrics Policy

### 8.1. Reuse metrics layer

EXP-05 reuses `metrics.attach_metrics_with_status` verbatim:

- silhouette, DBI, CH, WCSS
- WCSS uses arithmetic centroid from hard labels (GMM/FCM: argmax)
- DBSCAN noise excluded
- Status semantics: VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR
  / MISSING

### 8.2. Recorded per-run metrics

| Field | Type |
|-------|------|
| silhouette + silhouette_status | float \| None, str |
| davies_bouldin + davies_bouldin_status | float \| None, str |
| calinski_harabasz + calinski_harabasz_status | float \| None, str |
| wcss + wcss_status | float \| None, str |
| runtime_seconds | float |
| labels_hash | str |
| n_clusters_realized | int \| None |
| noise_count | int \| None |
| noise_ratio | float \| None |
| cluster_sizes | dict[str, int] |

### 8.3. Variation statistics (aggregate)

Khi phù hợp (depends on context):

- mean / std / min / max / CV
- `labels_hash_unique_count`
- `metric_unique_count_silhouette`
- `metric_unique_count_davies_bouldin`
- `metric_unique_count_calinski_harabasz`
- `metric_unique_count_wcss`
- `n_clusters_unique_count`

**KHÔNG dùng** variation statistics để tự kết luận algorithm nào
  "tốt hơn". Variation chỉ là evidence để EPIC-08 phân tích.

---

## 9. Configuration

### 9.1. EXP-05 config file

Path: `configs/exp05_stability_reproducibility.yaml`

Sections (top-level):

- `exp05.name`, `exp05.description`
- `exp05.dataset`: FE-06 final_clustering_dataset_path,
  customer_metadata_path, customer_key.
- `exp05.algorithms`: canonical order.
- `exp05.working_defaults`: mirror EXP-01.
- `exp05.block_r`: reproducibility block (algorithms, n_repeat, seed).
- `exp05.block_s`: seed stability block (algorithms, seeds, n_repeat).
- `exp05.block_n`: perturbation block (algorithms, sigma_grid,
  perturbation_seeds, sigma_zero_sanity_runs_per_algo).
- `exp05.metrics`: internal metrics list, status policy, wcss centroid.
- `exp05.decision_status`: permitted, forbidden labels.
- `exp05.output`: reports dir, labels_artifact_filename.

### 9.2. Decision status taxonomy

**Permitted**:

- `REPRODUCIBILITY_VERIFIED` (Block R, all metrics deterministic).
- `REPRODUCIBILITY_FAILED` (Block R, any metric varies).
- `STABILITY_EVIDENCE_GENERATED` (Block S, evidence recorded).
- `PERTURBATION_EVIDENCE_GENERATED` (Block N, evidence recorded).
- `PENDING_REVIEW` (any unexpected state).
- `SIGMA_ZERO_BASELINE_MATCH` (Block N sigma=0 sanity check).

**Forbidden** (case-insensitive): BEST, OPTIMAL, WINNER, SUPERIOR,
RECOMMENDED, FINAL.

---

## 10. Implementation strategy

### 10.1. Architecture

```
scripts/run_exp05_stability.py
        │
        v
StabilityReproducibilityRunner (stability.py)
        │
        ├── run_block_r()
        │     5 algorithms × n_repeat=5 → 25 records
        │     For each: ExperimentRunner.run() × 5 (determinism verify)
        │     attach_metrics_with_status()
        │     labels_hash
        │
        ├── run_block_s()
        │     3 algorithms (kmeans, gmm, fuzzy_cmeans) × 5 seeds
        │     For each: ExperimentRunner.run() with seed_override
        │     attach_metrics_with_status()
        │     labels_hash
        │
        ├── run_block_n()
        │     5 algorithms × (1 sigma=0 + 2 sigma × 3 perturbation seeds)
        │     For each: in-memory perturb + ExperimentRunner.run()
        │     attach_metrics_with_status()
        │     labels_hash
        │     SHA verify FE-06 input unchanged
        │
        ├── collect_labels_artifact()
        │     build DataFrame (run_id, block, algorithm, seed, sigma,
        │     perturbation_seed, repeat_index, CustomerID, cluster_label)
        │     write exp05_cluster_labels.parquet
        │
        └── write_reports()
                reports/exp05/exp05_manifest.json
                reports/exp05/exp05_run_summary.json
                reports/exp05/exp05_reproducibility_results.csv
                reports/exp05/exp05_reproducibility_aggregate.csv
                reports/exp05/exp05_seed_sweep_results.csv
                reports/exp05/exp05_seed_sweep_aggregate.csv
                reports/exp05/exp05_noise_perturbation_results.csv
                reports/exp05/exp05_noise_perturbation_aggregate.csv
                reports/exp05/exp05_cluster_size_consistency.csv
                reports/exp05/exp05_cluster_labels.parquet
                reports/exp05/exp05_pending_review.json
                reports/exp05/exp05_analysis.md
```

### 10.2. Reuse vs New

| Component | Source | Modified? |
|-----------|--------|-----------|
| `ExperimentRunner.run()` | EPIC-06 | NO |
| `ExperimentSpec` | EPIC-06 | NO |
| `attach_metrics_with_status()` | EXP-01 metrics.py | NO |
| `compute_runtime_stats()` | EXP-01 metrics.py | NO |
| `ClusterResult` / `ExperimentResult` | EPIC-06 | NO |
| `compute_labels_hash()` (used in EXP-04) | EXP-04 / EPIC-07 | REUSE |
| `StabilityReproducibilityRunner`, `BlockRRecord`, `BlockSRecord`, `BlockNRecord`, `LabelArtifactRow`, `BlockRAggregate`, `BlockSAggregate`, `BlockNAggregate` | NEW | YES |
| `run_exp05_stability.py` | NEW | YES |
| `configs/exp05_stability_reproducibility.yaml` | NEW | YES |

### 10.3. Public API of `stability.py`

```python
class StabilityReproducibilityRunner:
    def __init__(self, framework_cfg, exp05_config, *, framework_config_text=None, exp05_config_text=None)
    def run(
        self,
        matrix_df,
        customer_metadata_df,
        *,
        input_sha256,
        metadata_sha256,
    ) -> StabilityResult:
        # 1. Verify SHAs.
        # 2. Run Block R, S, N sequentially.
        # 3. Collect labels artifact.
        # 4. SHA verify post-run (no mutation).
        # 5. Return aggregated result.
```

### 10.4. Module-level helpers

- `compute_labels_hash(labels)`: reused from EXP-04
  (`preprocessing_feature_sensitivity.compute_labels_hash`).
- `generate_perturbation(X, sigma, perturbation_seed)`:
  in-memory Gaussian noise scaled by column std.
- `aggregate_block_r(records)`, `aggregate_block_s(records)`,
  `aggregate_block_n(records)`: pure functions returning
  aggregate dataclasses.

---

## 11. File Plan

### 11.1. MỚI

| Path | Type | Mô tả |
|------|------|-------|
| `configs/exp05_stability_reproducibility.yaml` | Config | EXP-05 source of truth |
| `src/customer_segmentation/clustering/stability.py` | Module | Orchestrator + record dataclasses |
| `scripts/run_exp05_stability.py` | Script | CLI entry point |
| `tests/test_exp05_stability.py` | Tests | Behavioral tests |
| `reports/exp05/*` | Directory | Output artifacts |

### 11.2. KHÔNG sửa

- `src/customer_segmentation/clustering/runner.py`
- `src/customer_segmentation/clustering/result.py`
- `src/customer_segmentation/clustering/metrics.py`
- `src/customer_segmentation/clustering/baseline.py`
- `src/customer_segmentation/clustering/preprocessing_feature_sensitivity.py`
- `src/customer_segmentation/clustering/{kmeans,agglomerative,dbscan,gmm,fuzzy_cmeans}.py`
- `configs/clustering.yaml`
- `configs/experiment.yaml`
- `configs/exp01_baseline.yaml`
- `configs/exp02_cluster_number.yaml`
- `configs/exp03_hyperparameter_search.yaml`
- `configs/exp04_preprocessing_feature_set.yaml`

### 11.3. Output (under `reports/exp05/`)

| File | Format | Mô tả |
|------|--------|-------|
| `exp05_manifest.json` | JSON | Top-level manifest: blocks + provenance + scope boundaries |
| `exp05_run_summary.json` | JSON | Machine-readable summary |
| `exp05_reproducibility_results.csv` | CSV (long) | Per-(algorithm × repeat) Block R records |
| `exp05_reproducibility_aggregate.csv` | CSV | Per-algorithm Block R aggregate |
| `exp05_seed_sweep_results.csv` | CSV (long) | Per-(algorithm × seed) Block S records |
| `exp05_seed_sweep_aggregate.csv` | CSV | Per-algorithm Block S aggregate |
| `exp05_noise_perturbation_results.csv` | CSV (long) | Per-(algorithm × sigma × perturbation_seed) Block N records |
| `exp05_noise_perturbation_aggregate.csv` | CSV | Per-(algorithm × sigma) Block N aggregate |
| `exp05_cluster_size_consistency.csv` | CSV | Cross-block cluster size distribution snapshot |
| `exp05_cluster_labels.parquet` | Parquet | **REQUIRED** — label-level artifact for EPIC-08 |
| `exp05_pending_review.json` | JSON | PENDING_REVIEW items |
| `exp05_analysis.md` | Markdown | Vietnamese narrative report |

---

## 12. Tests

### 12.1. Required test categories

| Category | Tests |
|----------|-------|
| Config YAML loads | 2 |
| Block matrix correctness (R: 5 algorithms × n_repeat=5; S: 3 algorithms × 5 seeds; N: 5 + 5×2×3) | 6 |
| Seed set correctness for Block S | 2 |
| Sigma set correctness for Block N | 2 |
| Fixed hyperparameters (mirror EXP-01) | 2 |
| Block R determinism (same seed → identical labels_hash) | 4 |
| sigma=0 reproduces baseline within tolerance | 2 |
| Input SHA unchanged after run | 2 |
| Labels artifact schema + CustomerID alignment | 4 |
| Aggregate mean/std/min/max/CV computation | 4 |
| **No ranking/composite/best terminology** in outputs | 3 |
| **No ARI/AMI values** in outputs | 2 |
| **No assertion** that sigma=1%/5% MUST change labels | 2 |
| Perturbation in-memory only (no perturbed dataset on disk) | 2 |

### 12.2. Coverage

- Block R: K-Means deterministic; Agglomerative deterministic;
  DBSCAN deterministic; GMM deterministic with `n_init=1, init_params='kmeans'`
  + seed; FCM deterministic with fixed seed.
- Block S: K-Means + GMM + FCM labels_hash thay đổi across seeds
  (evidence); metrics have variation.
- Block N: sigma=0 reproduces EXP-01 baseline; sigma=0.01/0.05
  produces variations (or not — both valid).

### 12.3. Test isolation

Tests MUST NOT require running on real FE-06 dataset (which is
gated by SHA verification). Use synthetic DataFrames (similar to
EXP-04 tests). The tests verify behavior on synthetic data; the
real-data run is gated behind `data/processed/` existence.

---

## 13. Assumptions

1. **FE-06 final clustering matrix** (Extended RFM, 14 features,
   SHA-256 = `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`)
   là input duy nhất của EXP-05.
2. **CustomerID** nằm trong customer metadata (4371 rows), không
   nằm trong matrix.
3. **EXP-01 working defaults** mirror từ
   `configs/exp01_baseline.yaml` được chấp nhận làm
   WORKING_ASSUMPTION.
4. **Block S seed list** = [42, 7, 123, 2024, 1729] là
   WORKING_ASSUMPTION.
5. **Block N sigma list** = [0.0, 0.01, 0.05] và perturbation seeds
   = [42, 43, 44] là WORKING_ASSUMPTION.
6. **Perturbation distribution** = Gaussian (normal) with column-wise
   std scaling. WORKING_ASSUMPTION.
7. **GMM/FCM hard label derivation** = `argmax` of soft outputs (not
   GMM Gaussian means or FCM fuzzy centroids).
8. **DBSCAN noise handling** mirror EXP-01 (exclude noise from
   internal metrics + WCSS).
9. **Random seed protocol**: Block R uses seed=42; Block S uses 5
   seeds; Block N uses seed=42 for algorithm + perturbation_seeds for
   noise.
10. **`n_repeat`**: Block R = 5; Block S = 1; Block N = 1.

---

## 14. PENDING_REVIEW decisions

| ID | Decision | Status | Cần mentor |
|----|----------|--------|-----------|
| EXP05-BLK-01 | Block R = reproducibility verification, NOT stability analysis | WORKING_ASSUMPTION | Có |
| EXP05-BLK-02 | Block S chỉ cho 3 algorithms có random axis (K-Means + GMM + FCM) | WORKING_ASSUMPTION | Có |
| EXP05-BLK-03 | Block N = in-memory perturbation; sigma=[0, 0.01, 0.05]×std | WORKING_ASSUMPTION | Có |
| EXP05-SEED-01 | Seeds for Block S = [42, 7, 123, 2024, 1729] | WORKING_ASSUMPTION | Có |
| EXP05-PERT-01 | Perturbation distribution = Gaussian, column-wise std scaled | WORKING_ASSUMPTION | Có |
| EXP05-PERT-02 | sigma=0 sanity run: must reproduce EXP-01 baseline (cluster_labels identical) | WORKING_ASSUMPTION | Có |
| EXP05-ART-01 | Labels artifact schema (run_id, block, algorithm, seed, sigma, perturbation_seed, repeat_index, CustomerID, cluster_label) | WORKING_ASSUMPTION | Có |
| EXP05-AGG-01 | Aggregate uses mean/std/min/max/CV; no composite scoring | TECHNICALLY_IMPLEMENTED | Không |
| EXP05-DEC-01 | Decision status taxonomy: REPRODUCIBILITY_VERIFIED / REPRODUCIBILITY_FAILED / STABILITY_EVIDENCE_GENERATED / PERTURBATION_EVIDENCE_GENERATED / PENDING_REVIEW / SIGMA_ZERO_BASELINE_MATCH | WORKING_ASSUMPTION | Có |
| EXP05-EPIC-08 | ARI/AMI, Hungarian matching, statistical tests, confidence intervals thuộc EPIC-08 | TECHNICALLY_IMPLEMENTED | Không |

---

## 15. Những gì KHÔNG nằm trong scope EXP-05

| Nội dung | Lý do | Thuộc EPIC |
|----------|-------|--------|
| ARI / AMI computation | EXP-05 generates raw labels; EPIC-08 computes ARI/AMI | EPIC-08 |
| Hungarian matching | EPIC-08 owns algorithm-level matching | EPIC-08 |
| Statistical tests across seeds | EXP-05 records; EPIC-08 analyzes | EPIC-08 |
| Confidence intervals | EPIC-08 owns | EPIC-08 |
| Stability analysis (qualitative) | EXP-05 is evidence, not analysis | EPIC-08 |
| Algorithm comparison / ranking | EPIC-08 owns | EPIC-08 |
| Composite score | AGENTS.md §2.6 cấm | — |
| "Best algorithm" / "winner" claim | AGENTS.md §2.5 cấm | — |
| Sampling / subsampling | EXP-05 uses full FE-06 matrix | — |
| K sweep | EXP-02 owns | EXP-02 |
| Re-sweep hyperparameters | EXP-03 owns | EXP-03 |
| Re-sweep preprocessing | EXP-04 owns | EXP-04 |
| Persistence of perturbed dataset | In-memory only | — |
| Customer profiling / segment naming | EPIC-09 owns | EPIC-09 |
| Visualization | Out of scope; Factual numerical tables only | EPIC-08 |

---

## 16. Workflow thực thi

```
Step 1: Tạo configs/exp05_stability_reproducibility.yaml ✅
Step 2: Tạo src/customer_segmentation/clustering/stability.py ✅
Step 3: Tạo scripts/run_exp05_stability.py ✅
Step 4: Tạo tests/test_exp05_stability.py ✅
Step 5: pytest test_exp05_stability.py pass
Step 6: pytest full pass
Step 7: ruff check pass
Step 8: black --check pass
Step 9: Smoke run với synthetic data (output_dir=...) — verify reports
Step 10: Generate reports/exp05/* artifacts qua smoke run
Step 11: Viết docs/research/EXP05_stability_reproducibility.md
```

---

## 17. Danh sách thay đổi so với PLAN Revision 0

| # | Review point | Thay đổi |
|---|-------------|----------|
| 1 | Block R — Reproducibility | §4: sửa từ "5 algorithms × seed sweep" thành "5 algorithms × n_repeat=5, seed=42, determinism verification". Không phải stability analysis. |
| 2 | Block S — Random Seed Stability | §5: thêm explicit list 3 algorithms có random axis (K-Means + GMM + FCM); Agglomerative + DBSCAN deterministic nên KHÔNG seed sweep. |
| 3 | Block N — Feature Perturbation | §6: sửa — sigma=0 chỉ cần 1 sanity run/algorithm; sigma=1% và 5% × 3 perturbation seeds. Perturbation in-memory only. Không assert labels phải thay đổi. |
| 4 | EPIC-08 boundary | §1.2, §7, §15: thêm bảng rõ ràng EPIC-08 owns ARI/AMI/Hungarian/statistical tests/CI. EXP-05 chỉ generate raw labels artifact. |
| 5 | Labels artifact schema | §7: REQUIRED schema (run_id, block, algorithm, seed, sigma, perturbation_seed, repeat_index, CustomerID, cluster_label). |
| 6 | Decision status taxonomy | §9.2: thêm REPRODUCIBILITY_VERIFIED / REPRODUCIBILITY_FAILED / STABILITY_EVIDENCE_GENERATED / PERTURBATION_EVIDENCE_GENERATED / PENDING_REVIEW / SIGMA_ZERO_BASELINE_MATCH. |
| 7 | Không sampling/subsampling | §1.2, §15: explicit "NO sampling / subsampling". |
| 8 | Không K sweep | §1.2, §15: explicit "NO K sweep" (EXP-02 owns). |
| 9 | Không lặp EXP-03/04 | §1.2, §15: explicit "DO NOT rerun EXP-03/04". |
| 10 | CustomerID alignment | §7.2: MUST come from FE-06 metadata; verify via validate_customer_alignment. |

---

*Plan Revision 1. Implementation theo các điểm đã sửa ở §17.*