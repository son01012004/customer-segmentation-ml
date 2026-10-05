# ML-04 — DBSCAN (Density-Based Spatial Clustering of Applications with Noise)

> **Mentor Document cho EPIC-06 / ML-04.**
> Adapter version: `sklearn_1.9.1` (ghi trong `DBSCANAdapter.version`).
> Trạng thái implementation: `TECHNICALLY_IMPLEMENTED`.
> Ngôn ngữ tài liệu: tiếng Việt. Code / file name / config key / class
> name: English theo convention hiện tại của repository.

Tài liệu này phân biệt rõ giữa **đã implement** (`TECHNICALLY_IMPLEMENTED`),
**working assumption** (`WORKING_ASSUMPTION`), **pending mentor review**
(`PENDING_REVIEW`) và **out of scope** (`OUT_OF_SCOPE`).

---

## 1. Tên task và vai trò trong nghiên cứu

| Trường | Nội dung |
|--------|----------|
| **Task ID** | `ML-04` |
| **Tên task** | Density-Based Spatial Clustering of Applications with Noise (DBSCAN) |
| **Mục tiêu** | Triển khai DBSCAN như một concrete `BaseClusterAlgorithm` adapter, plug vào ML-01 framework. Adapter là thin wrapper quanh `sklearn.cluster.DBSCAN`; nó chỉ expose các hyperparameter đã được quy ước trong ML-04 task contract (`eps`, `min_samples`, `metric`). KHÔNG compute evaluation metrics, KHÔNG so sánh algorithm, KHÔNG chọn best `eps` / `min_samples`, KHÔNG mutate input. Bảo toàn noise label `-1` verbatim theo sklearn convention. |
| **Vị trí trong research pipeline** | ML-04 nằm sau ML-01 (framework) và sau FE-06 (dataset). ML-04 là density-based clustering family (cùng với K-Means / Agglomerative / GMM / FCM); ML-04 là một trong bốn benchmark algorithms cố định bởi methodology (theo AGENTS.md §2.1). Output của ML-04 (`cluster_labels_*.parquet`, `experiment_log_*.json`) là input cho EPIC-07 (controlled sweep), EPIC-08 (evaluation), EPIC-09 (segment analysis). |
| **Input** | `data/processed/final_clustering_dataset.parquet` (FE-06 output; SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`); `data/processed/customer_metadata.parquet` (FE-06 output; SHA-256 `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`); `configs/clustering.yaml` (DBSCAN section: `clustering.algorithms.dbscan.*`). |
| **Output** | `data/processed/clustering_experiments/cluster_labels_ML-04-DBSCAN-*.parquet` (CustomerID + ClusterLabel + IsNoise); `data/processed/clustering_experiments/experiment_log_ML-04-DBSCAN-*.json`; `reports/ml04/ml04_run_summary.json`; `reports/ml04/ml04_initial_diagnostic.md`; `reports/ml04/ml04_parameter_diagnostic.csv`. |
| **Quan hệ với task trước/sau** | Trước: ML-01 framework. Sau: EPIC-07 sẽ sweep `(eps, min_samples, metric)`; EPIC-08 sẽ compute silhouette/DBI/CH (silhouette KHÔNG áp dụng cho density-based clusters có noise — xem AGENTS.md §3 Evaluation row); EPIC-09 sẽ phân tích segment dựa trên cluster labels (loại trừ noise). |
| **Algorithm family** | `density_based` (hard labels + dedicated noise label `-1`). |

---

## 2. Mục tiêu nghiên cứu

ML-04 trả lời một phần câu hỏi nghiên cứu về **tính khả thi kỹ thuật** của
việc chạy DBSCAN trên FE-06 dataset với framework thống nhất:

- "DBSCAN phát hiện được bao nhiêu cluster trên FE-06 dataset với
  `eps=0.5`, `min_samples=5`, `metric='euclidean'`? Noise ratio là bao nhiêu?"
- "Có thể thay đổi `metric` (`euclidean`, `manhattan`, `cosine`) mà vẫn giữ
  schema output thống nhất của ML-01 framework không?"
- "DBSCAN có deterministic không? Noise label `-1` được bảo toàn verbatim
  trong cluster_labels_*.parquet và algorithm-specific diagnostics (`noise_count`,
  `noise_ratio`, `core_sample_count`) không?"

**Phạm vi nghiên cứu:**

- ML-04 là technical implementation, KHÔNG phải evaluation.
- ML-04 KHÔNG sweep `(eps, min_samples)`; `working_eps=0.5`,
  `working_min_samples=5` là **WORKING_ASSUMPTION**.
- ML-04 KHÔNG chọn `best eps` / `best min_samples`; 3 per-metric diagnostic
  runs (`euclidean`, `manhattan`, `cosine`) chỉ để verify adapter hỗ trợ đầy
  đủ các metric và thu diagnostics.
- ML-04 KHÔNG làm business interpretation: noise là kết quả của density-based
  clustering, KHÔNG phải outlier flag cần loại bỏ.
- ML-04 KHÔNG tạo k-distance plot trong EPIC-06; đó là diagnostic viz
  optional.

**Mối liên hệ với đặc thù dữ liệu FE-06:**

- DBSCAN phụ thuộc mạnh vào `eps` và `min_samples`. Với standardized feature
  scale (FE-06 đã dùng RobustScaler), `eps=0.5` có nghĩa "bán kính 0.5 đơn
  vị scale". Trên FE-06 dataset, working default cho `n_clusters=17` và
  `noise_ratio=0.7268` (tức ~73% customer bị DBSCAN label là noise).
- ML-04 KHÔNG đánh giá đây là "good" hay "bad"; đó là behavior của DBSCAN
  với working hyperparameters, và EPIC-07 sẽ sweep để tìm vùng tham số
  khác nếu cần.

**Mối liên hệ với EPIC-07/08/09:**

- EPIC-07 sẽ sweep `(eps, min_samples, metric)`. Vì DBSCAN không có
  `n_clusters`, EPIC-07 sẽ đo `n_clusters`, `noise_ratio`, `core_sample_ratio`,
  và các diagnostic tương tự để explore parameter space.
- EPIC-08 sẽ compute silhouette / DBI / CH. The AGENTS.md §3 (Evaluation row)
  ghi "Reporting internal metrics without stability and runtime; ignoring
  silhouette for density-based clusters" — silhouette KHÔNG áp dụng cho
  density-based clusters (vì noise label `-1` không có ground truth cluster
  centroid).
- EPIC-09 sẽ phân tích segment. Noise points sẽ cần được xử lý riêng trong
  EPIC-09 (loại trừ hoặc gom vào một "noise segment") — đó là scope của
  EPIC-09, KHÔNG phải ML-04.

---

## 3. Cơ sở lý thuyết

### 3.1. Density-based clustering

**DBSCAN** (Ester et al., 1996) groups points close to each other vào
clusters và mark isolated points là noise. Thuật toán parameterized bởi
hai hyperparameters:

- `eps` — neighborhood radius (epsilon).
- `min_samples` — minimum số points để form dense region.

### 3.2. Epsilon neighborhood

Epsilon-neighborhood của point `x`:

    N_eps(x) = {x_j | d(x, x_j) <= eps}

Trong đó `d` là chosen pairwise distance metric.

### 3.3. Core point

Point `x` là **core point** nếu:

    |N_eps(x)| >= min_samples

Trong sklearn convention (mà adapter kế thừa), point itself **được include
trong count**, nên point có đúng `min_samples` neighbors (kể cả chính nó)
là core point.

### 3.4. Border point

Point **không phải core** nhưng nằm trong epsilon-neighborhood của một core
point.

### 3.5. Noise (outlier) point

Point **không phải core**, **không phải border** → label `-1` (sklearn
convention). ML-04 BẢO TOÀN noise label `-1` verbatim.

### 3.6. Density reachability

- Point `p` *directly density-reachable* từ `q` nếu `p ∈ N_eps(q)` và `q` là
  core point.
- Point `p` *density-reachable* từ `q` nếu tồn tại chain of points
  `p_1, p_2, ..., p_n` với `p_1 = q` và `p_n = p`, mỗi `p_{i+1}` directly
  density-reachable từ `p_i`.

### 3.7. Density connectivity

Hai points `p` và `q` *density-connected* nếu tồn tại một point `o` sao
cho cả `p` và `q` đều density-reachable từ `o`.

### 3.8. Cluster

Một **cluster** là một maximal set of density-connected points mà không
phải noise.

### 3.9. Sensitivity to eps và min_samples

- `eps` nhỏ → nhiều noise.
- `eps` lớn → ít cluster (có thể 1 cluster duy nhất nếu `eps` đủ lớn).
- `min_samples` nhỏ → nhiều cluster nhỏ (nhiều core points).
- `min_samples` lớn → ít core points → nhiều noise.

EPIC-07 sẽ sweep hai hyperparameters này.

### 3.10. k-distance plot

Diagnostic để chọn `eps`: sort distance từ mỗi point đến `k`-th nearest
neighbor, tìm "elbow". ML-04 chưa tạo k-distance plot trong EPIC-06 (xem
Section 9).

### 3.11. Noise ratio

Tỷ lệ points được label `-1`:

    noise_ratio = noise_count / n_samples

Phản ánh mức độ tách biệt của data. Trên FE-06 working default,
`noise_ratio ≈ 0.7268` (cao) → DBSCAN cho rằng phần lớn customers không
thuộc dense region nào với `eps=0.5`.

### 3.12. Hard clustering

Mỗi point thuộc 1 cluster HOẶC là noise. **KHÔNG có soft probability**;
đó là đặc trưng của GMM (xem ML-05) và FCM (xem ML-06).

### 3.13. Determinism

DBSCAN trong `n_clusters`-free mode là deterministic trong sklearn — không
có internal RNG. ML-04 advertise `supports_random_state() == False` và
runner KHÔNG inject seed.

---

## 4. Phương pháp / Methodology

### 4.1. Dữ liệu sử dụng

| File | Vai trò | SHA-256 | Shape |
|------|---------|---------|-------|
| `data/processed/final_clustering_dataset.parquet` | Numeric feature matrix | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `(4371, 14)` |
| `data/processed/customer_metadata.parquet` | CustomerID mapping | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `(4371, 1)` |

Dataset version: `FE06-v1.0`.

**Feature set (14 features):** giống ML-02 / ML-03.

### 4.2. Preprocessing

ML-04 KHÔNG thực hiện preprocessing. Verify input đã qua FE-06 pipeline
(giống ML-02 / ML-03).

### 4.3. Algorithm / configuration

| Hyperparameter | Working default | Nguồn |
|----------------|-----------------|--------|
| `eps` | `0.5` | `configs/clustering.yaml` → `clustering.algorithms.dbscan.working_eps` |
| `min_samples` | `5` | `configs/clustering.yaml` → `clustering.algorithms.dbscan.working_min_samples` |
| `metric` | `"euclidean"` | `configs/clustering.yaml` → `clustering.algorithms.dbscan.working_metric` |
| `noise_label` | `-1` (sklearn convention; preserved verbatim) | `configs/clustering.yaml` → `clustering.algorithms.dbscan.noise_label` |
| `random_state` | KHÔNG dùng (DBSCAN deterministic) | n/a |

`eps_range` và `min_samples_range` được note là `TODO` trong YAML, dành cho
EPIC-07 sweep.

**Metric options supported by adapter** (`SUPPORTED_METRICS`):
`euclidean`, `manhattan`, `cityblock`, `cosine`, `chebyshev`, `l1`, `l2`.

**Library version:** `sklearn 1.9.1`.

### 4.4. Cách chạy

Script entry point: `scripts/run_ml04_dbscan.py`.

Lệnh này chạy:

1. **Primary run**: `eps=0.5`, `min_samples=5`, `metric='euclidean'`.
2. **3 per-metric diagnostic runs**: cùng `eps` và `min_samples` nhưng thay
   `metric` thành `euclidean`, `manhattan`, `cosine`. Đây KHÔNG phải
   controlled sweep — chỉ để verify adapter hỗ trợ đầy đủ các metric và
   thu diagnostics.

Mỗi run ghi artifact riêng với `experiment_id` khác nhau.

### 4.5. Cách lưu kết quả

Artifact paths theo `framework.output` config:

- `cluster_labels_ML-04-DBSCAN-{variant}-*.parquet` — CustomerID + ClusterLabel
  + IsNoise (với `IsNoise = (ClusterLabel == -1)`).
- `experiment_log_ML-04-DBSCAN-{variant}-*.json` — full `ExperimentResult.to_dict()`.
- KHÔNG có `algorithm_output_*.parquet` (DBSCAN không có soft probability
  / membership).

### 4.6. Cách đảm bảo reproducibility

- DBSCAN deterministic → không cần seed.
- Framework runner KHÔNG inject seed vì `adapter.supports_random_state()
  == False`. Experiment log ghi `random_seed = 42` (requested) nhưng
  `random_seed_used = None`.
- `experiment_log` ghi input SHA, config SHA, library versions.

### 4.7. Bảng phân loại decision (BẮT BUỘC)

| Loại decision | Nội dung | Status | Bằng chứng / Nguồn |
|---------------|----------|--------|---------------------|
| TECHNICALLY_IMPLEMENTED | `DBSCANAdapter` class | Implemented | `src/customer_segmentation/clustering/dbscan.py` |
| TECHNICALLY_IMPLEMENTED | Adapter registered in `AlgorithmRegistry` as `"dbscan"` | Implemented | `dbscan.py` → `@AlgorithmRegistry.register("dbscan")` |
| TECHNICALLY_IMPLEMENTED | `supports_random_state() == False` (DBSCAN deterministic) | Implemented | `dbscan.py` → `DBSCANAdapter.supports_random_state` |
| TECHNICALLY_IMPLEMENTED | Hard cluster labels + dedicated noise label `-1` preserved verbatim | Implemented | `dbscan.py` → `DBSCANAdapter.fit` |
| TECHNICALLY_IMPLEMENTED | `noise_count`, `noise_ratio`, `core_sample_count`, `core_sample_ratio` recorded | Implemented | `dbscan.py` → `ClusterResult` + `ClusterResult.extra` |
| TECHNICALLY_IMPLEMENTED | `cluster_sizes` excluding noise | Implemented | `dbscan.py` |
| TECHNICALLY_IMPLEMENTED | 3-metric diagnostic runs (euclidean / manhattan / cosine) | Implemented | `reports/ml04/ml04_parameter_diagnostic.csv` |
| TECHNICALLY_IMPLEMENTED | Primary run với `eps=0.5, min_samples=5, metric='euclidean'` | Implemented | `experiment_log_ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg.json` |
| TECHNICALLY_IMPLEMENTED | Validation matrix theo FE-06 contract | Implemented | `tests/test_ml04_dbscan.py` (47 tests pass) |
| WORKING_ASSUMPTION | `eps = 0.5` | Working assumption | `configs/clustering.yaml` → `algorithms.dbscan.working_eps` |
| WORKING_ASSUMPTION | `min_samples = 5` | Working assumption | `configs/clustering.yaml` → `algorithms.dbscan.working_min_samples` |
| WORKING_ASSUMPTION | `metric = 'euclidean'` | Working assumption | `configs/clustering.yaml` → `algorithms.dbscan.working_metric` |
| WORKING_ASSUMPTION | `noise_label = -1` (sklearn convention) | Working assumption | `configs/clustering.yaml` → `algorithms.dbscan.noise_label` |
| PENDING_REVIEW | Methodology: chọn `working_eps=0.5` làm default cho ML-04 diagnostic | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: chọn `working_min_samples=5` làm default | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: chọn `working_metric='euclidean'` làm default | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: noise label `-1` được preserve verbatim (KHÔNG re-label noise như outlier) | MENTOR_REVIEW_PENDING | `dbscan.py` (xem Section 11) |
| OUT_OF_SCOPE | Compute evaluation metrics (silhouette KHÔNG applicable cho density-based clusters; DBI/CH applicable) | Explicit | EPIC-07/08 ownership |
| OUT_OF_SCOPE | Pick best eps / best min_samples / best metric | Explicit | EPIC-07 ownership |
| OUT_OF_SCOPE | Pick best algorithm | Explicit | EPIC-08 ownership |
| OUT_OF_SCOPE | Business interpretation của noise (e.g. outlier removal) | Explicit | AGENTS.md §2.9 + EPIC-09 ownership |
| OUT_OF_SCOPE | K-distance diagnostic plot | Explicit | EPIC-06 diagnostic viz optional (chưa tạo) |
| OUT_OF_SCOPE | Customer segment profiling / naming | Explicit | EPIC-09 ownership |
| OUT_OF_SCOPE | Mutate FE-06 output | Explicit | AGENTS.md §2.3 |

---

## 5. Implementation

### 5.1. Module / file chính

- Adapter: `src/customer_segmentation/clustering/dbscan.py` →
  `DBSCANAdapter`.
- Default constants: `DEFAULT_EPS`, `DEFAULT_MIN_SAMPLES`, `DEFAULT_METRIC`,
  `MIN_SAMPLES_MIN`, `EPS_MIN`, `SUPPORTED_METRICS`.
- Public re-export: `src/customer_segmentation/clustering/__init__.py`.
- Tests: `tests/test_ml04_dbscan.py` (47 tests).
- Script: `scripts/run_ml04_dbscan.py`.
- Reports: `reports/ml04/ml04_initial_diagnostic.md`,
  `reports/ml04/ml04_run_summary.json`,
  `reports/ml04/ml04_parameter_diagnostic.csv`.
- Artifacts: 4 files `cluster_labels_ML-04-DBSCAN-*.parquet` + 4 files
  `experiment_log_ML-04-DBSCAN-*.json`.

### 5.2. Class hierarchy

```
BaseClusterAlgorithm (ML-01)
    └── DBSCANAdapter (ML-04)
            ├── name = "dbscan"
            ├── version = "sklearn_<sklearn.__version__>" (= "sklearn_1.9.1")
            ├── family = AlgorithmFamily.DENSITY_BASED
            ├── __init__(eps, min_samples, metric)
            ├── fit(X) -> ClusterResult
            ├── get_params() -> dict
            ├── get_model() -> sklearn.cluster.DBSCAN | None
            └── supports_random_state() -> bool (returns False)
```

### 5.3. Pipeline

```
scripts/run_ml04_dbscan.py
  │
  ├── load configs/clustering.yaml (FrameworkConfig)
  ├── load data/processed/final_clustering_dataset.parquet (X)
  ├── load data/processed/customer_metadata.parquet (metadata)
  ├── compute SHA-256(input), SHA-256(metadata), SHA-256(config)
  │
  ├── for each (eps, min_samples, metric) variant:
  │     spec = ExperimentSpec(
  │         experiment_id = "ML-04-DBSCAN-{variant}-seedcfg",
  │         algorithm = "dbscan",
  │         hyperparameters = {"eps": e, "min_samples": ms, "metric": m},
  │     )
  │     runner = ExperimentRunner(cfg, spec, config_source, config_text)
  │     runner.run(X, metadata, input_sha256, ..., output_dir)
  │
  └── write ml04_parameter_diagnostic.csv, ml04_run_summary.json,
      ml04_initial_diagnostic.md
```

### 5.4. Configuration

| Config key | Value | Nguồn |
|------------|-------|--------|
| `clustering.algorithms.dbscan.enabled` | `true` | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.working_eps` | `0.5` | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.working_min_samples` | `5` | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.working_metric` | `"euclidean"` | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.noise_label` | `-1` | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.eps_range` | `"TODO"` (reserved cho EPIC-07) | `configs/clustering.yaml` |
| `clustering.algorithms.dbscan.min_samples_range` | `"TODO"` (reserved cho EPIC-07) | `configs/clustering.yaml` |

### 5.5. Input/output contract

**Input (`fit` parameter):** `X: numpy.ndarray` — shape `(4371, 14)`, dtype
`float64`, không chứa identifier.

**Output (`ClusterResult` fields):**

| Field | Value (ML-04 primary run) | Nguồn |
|-------|---------------------------|--------|
| `algorithm` | `"dbscan"` | `dbscan.py` |
| `algorithm_version` | `"sklearn_1.9.1"` | `dbscan.py` |
| `algorithm_family` | `"density_based"` | `dbscan.py` |
| `n_samples` | `4371` | `X.shape[0]` |
| `n_features` | `14` | `X.shape[1]` |
| `cluster_labels` | `np.ndarray`, shape `(4371,)`, dtype `int64`, values in `{-1, 0, 1, ..., 16}` | `model.fit_predict(X).astype(int64)` |
| `n_clusters` | `17` (= number of unique labels excluding `-1`) | `dbscan.py` |
| `soft_probabilities` | `None` | default |
| `soft_membership` | `None` | default |
| `noise_label` | `-1` | `dbscan.py` |
| `noise_count` | `3177` | `dbscan.py` |
| `noise_ratio` | `0.7268359643102265` | `dbscan.py` |
| `supports_random_state` | `False` | `DBSCANAdapter.supports_random_state()` |
| `random_seed_used` | `None` | runner không inject seed |
| `extra.eps` | `0.5` | `dbscan.py` |
| `extra.min_samples` | `5` | `dbscan.py` |
| `extra.metric` | `"euclidean"` | `dbscan.py` |
| `extra.n_clusters` | `17` | `dbscan.py` |
| `extra.noise_count` | `3177` | `dbscan.py` |
| `extra.noise_ratio` | `0.7268359643102265` | `dbscan.py` |
| `extra.has_noise` | `True` | `dbscan.py` |
| `extra.all_noise` | `False` | `dbscan.py` |
| `extra.has_single_cluster` | `False` | `dbscan.py` |
| `extra.core_sample_count` | `1037` | `dbscan.py` |
| `extra.core_sample_ratio` | `0.23724548158316175` | `dbscan.py` |
| `extra.cluster_sizes` | `{"0": 5, "1": 1042, "2": 7, ..., "16": 13}` | `dbscan.py` (excluding noise) |
| `extra.labels_value_counts` | `{"-1": 3177, "0": 5, "1": 1042, ...}` | `dbscan.py` (including noise) |
| `metrics.*` | tất cả `None` | EPIC-07/08 populate |

### 5.6. Validation (DBSCAN-specific)

Adapter validate input trong `fit`:

- `X` không None, là `np.ndarray`, `ndim == 2`.
- `n_features >= 1`.
- `n_samples >= 0` (DBSCAN cho phép n_samples = 0 hoặc 1; sklearn label mọi
  point là noise).

Adapter validate hyperparameter trong `__init__`:

- `eps > 0`.
- `min_samples >= MIN_SAMPLES_MIN (= 1)`.
- `metric` là string.

Metric final compatibility check delegate cho sklearn tại fit-time.

### 5.7. Artifacts (ML-04 actual)

4 cluster labels + 4 experiment log files (1 primary + 3 per-metric diagnostic):

| Artifact | Path | Schema |
|----------|------|--------|
| Primary cluster labels | `data/processed/clustering_experiments/cluster_labels_ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg.parquet` | `CustomerID` + `ClusterLabel` (int64, has `-1`) + `IsNoise` (bool) |
| Primary experiment log | `data/processed/clustering_experiments/experiment_log_ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg.json` | `ExperimentResult.to_dict()` |
| Diagnostic euclidean labels | `data/processed/clustering_experiments/cluster_labels_ML-04-DBSCAN-diag-eps0.5-ms5-euclidean-seedcfg.parquet` | same |
| Diagnostic manhattan labels | `data/processed/clustering_experiments/cluster_labels_ML-04-DBSCAN-diag-eps0.5-ms5-manhattan-seedcfg.parquet` | same |
| Diagnostic cosine labels | `data/processed/clustering_experiments/cluster_labels_ML-04-DBSCAN-diag-eps0.5-ms5-cosine-seedcfg.parquet` | same |
| Run summary | `reports/ml04/ml04_run_summary.json` | stage + experiments + diagnostics |
| Initial diagnostic | `reports/ml04/ml04_initial_diagnostic.md` | Vietnamese narrative |
| Parameter diagnostic | `reports/ml04/ml04_parameter_diagnostic.csv` | per-metric table |

### 5.8. JSON snippet (từ `experiment_log_ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg.json`)

```jsonc
{
  "experiment_id": "ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg",
  "status": "SUCCESS",
  "algorithm": "dbscan",
  "algorithm_version": "sklearn_1.9.1",
  "dataset_version": "FE06-v1.0",
  "dataset_sha256": "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c",
  "feature_count": 14, "n_samples": 4371,
  "hyperparameters": {"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
  "random_seed": 42, "random_seed_used": null,
  "n_clusters": 17,
  "cluster_labels_shape": [4371], "cluster_labels_dtype": "int64",
  "execution_time": 0.1328672239997104,
  "timestamp": "2026-09-21T04:54:10.639080+00:00",
  "cluster_result": {
    "algorithm": "dbscan", "algorithm_version": "sklearn_1.9.1", "algorithm_family": "density_based",
    "n_samples": 4371, "n_features": 14, "n_clusters": 17,
    "cluster_labels_shape": [4371], "cluster_labels_dtype": "int64",
    "cluster_labels_first_5": [-1, -1, -1, -1, -1],
    "noise_label": -1, "noise_count": 3177, "noise_ratio": 0.7268359643102265,
    "supports_random_state": false, "random_seed_used": null,
    "extra": {
      "eps": 0.5, "min_samples": 5, "metric": "euclidean",
      "n_clusters": 17, "noise_count": 3177, "noise_ratio": 0.7268359643102265,
      "has_noise": true, "all_noise": false, "has_single_cluster": false,
      "core_sample_count": 1037, "core_sample_ratio": 0.23724548158316175,
      "cluster_sizes": {"0": 5, "1": 1042, "2": 7, "3": 6, "4": 5, "5": 10,
                        "6": 37, "7": 5, "8": 13, "9": 19, "10": 6, "11": 6,
                        "12": 3, "13": 7, "14": 4, "15": 6, "16": 13},
      "labels_value_counts": {"-1": 3177, "0": 5, "1": 1042, ...}
    },
    "metrics": { /* all None */ }
  },
  "platform": {"python": "3.14.4", "system": "Linux", "release": "7.0.0-31-generic", "machine": "x86_64"},
  "library_versions": {"numpy": "2.3.5", "pandas": "3.0.6", "scipy": "1.18.1", "scikit-learn": "1.9.1", "pyarrow": "25.0.1"},
  "config_source": "yaml:/.../configs/clustering.yaml",
  "config_sha256": "352199f370a5520f9fea99e8f60d6f7f89d0c483c7a4d456226f6b58624e5271"
}
```

---

## 6. Experimental Design Boundary

| | EPIC-06 (ML-04 DBSCAN) | EPIC-07 | EPIC-08 | EPIC-09 |
|---|------------------------|---------|---------|---------|
| **Algorithm implementation** | ✅ DBSCANAdapter | — | — | — |
| **Configuration** | ✅ Working default (eps=0.5, min_samples=5, metric='euclidean') | Sweep matrix | — | — |
| **Single-fit experiment** | ✅ Initial diagnostic (1 algo × 1 (eps, min_samples, metric)) | Batch | — | — |
| **Sweep nhiều eps** | ❌ | ✅ (sẽ dùng `dbscan.eps_range`) | — | — |
| **Sweep nhiều min_samples** | ❌ | ✅ (sẽ dùng `dbscan.min_samples_range`) | — | — |
| **Sweep nhiều metric** | ❌ (chỉ 3 per-metric diagnostic, không phải sweep) | ✅ | — | — |
| **Sweep nhiều seed** | ❌ (deterministic) | N/A | — | — |
| **Compute internal metrics** | ❌ (silhouette KHÔNG applicable cho density-based clusters; DBI/CH applicable) | Partial (per fit) | ✅ Final | — |
| **Stability (ARI/AMI)** | ❌ (deterministic) | N/A | N/A (deterministic) | — |
| **Runtime comparison** | ❌ | Per-run time | ✅ Statistical summary | — |
| **Algorithm comparison** | ❌ | — | ✅ | — |
| **Diagnostic viz (k-distance plot)** | ⚠️ Optional per-task (chưa có trong EPIC-06) | — | — | — |
| **Research viz (silhouette, DBI, CH)** | ⚠️ DBI/CH applicable; silhouette KHÔNG applicable cho noise points | — | ✅ (DBI/CH only) | — |
| **Segment profile / naming** | ❌ | — | — | ✅ (noise segment riêng) |
| **Pick best algorithm / best (eps, min_samples)** | ❌ | — | ✅ (sau full eval) | — |
| **Customer profiling** | ❌ | — | — | ✅ |

---

## 7. Kết quả thực tế

ML-04 đã chạy 4 SUCCESS runs: 1 primary (`euclidean`) + 3 per-metric diagnostic
(`euclidean`, `manhattan`, `cosine`). Evidence:

### 7.1. Primary run

| Loại kết quả | Giá trị | Nguồn |
|--------------|---------|--------|
| Status | `SUCCESS` | `experiment_log_ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg.json` |
| Experiment ID | `ML-04-DBSCAN-eps0.5-ms5-euclidean-seedcfg` | `experiment_log_*.json` → `experiment_id` |
| Algorithm family | `density_based` | `cluster_result.algorithm_family` |
| n_clusters (excluding noise) | `17` | `experiment_log_*.json` → `n_clusters` |
| eps | `0.5` | `cluster_result.extra.eps` |
| min_samples | `5` | `cluster_result.extra.min_samples` |
| metric | `"euclidean"` | `cluster_result.extra.metric` |
| noise_count | `3177` | `cluster_result.noise_count` |
| noise_ratio | `0.7268359643102265` | `cluster_result.noise_ratio` |
| has_noise | `True` | `cluster_result.extra.has_noise` |
| all_noise | `False` | `cluster_result.extra.all_noise` |
| has_single_cluster | `False` | `cluster_result.extra.has_single_cluster` |
| core_sample_count | `1037` | `cluster_result.extra.core_sample_count` |
| core_sample_ratio | `0.23724548158316175` | `cluster_result.extra.core_sample_ratio` |
| cluster_sizes (excluding noise) | 17 clusters, sizes ranging 3–1042 | `cluster_result.extra.cluster_sizes` |
| labels_value_counts | `{"-1": 3177, "0": 5, "1": 1042, ..., "16": 13}` | `cluster_result.extra.labels_value_counts` |
| execution_time | `0.1328672239997104` (s) | `experiment_log_*.json` → `execution_time` |
| supports_random_state | `False` | `cluster_result.supports_random_state` |
| random_seed | `42` (requested, NOT consumed) | `experiment_log_*.json` → `random_seed` |
| random_seed_used | `None` | `cluster_result.random_seed_used` |
| config_sha256 | `352199f370a5520f9fea99e8f60d6f7f89d0c483c7a4d456226f6b58624e5271` | `experiment_log_*.json` |
| Library versions | numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`, scikit-learn `1.9.1`, pyarrow `25.0.1` | `experiment_log_*.json` |

### 7.2. Per-metric diagnostic runs

| Label | Metric | Status | n_clusters | noise_count | noise_ratio | core_sample_count | Execution time (s) |
|-------|--------|--------|-----------:|------------:|------------:|------------------:|-------------------:|
| diagnostic | euclidean | SUCCESS | 17 | 3177 | 0.7268 | 1037 | 0.1167 |
| diagnostic | manhattan | SUCCESS | 18 | 3914 | 0.8954 | 295 | 0.1046 |
| diagnostic | cosine | SUCCESS | 1 | 0 | 0.0000 | 4371 | 0.7124 |

Nguồn: `reports/ml04/ml04_parameter_diagnostic.csv`.

**Quan sát:** Cùng `eps=0.5`, `min_samples=5` nhưng các metric cho cluster
formation rất khác nhau:
- `euclidean` → 17 clusters, ~73% noise.
- `manhattan` → 18 clusters, ~90% noise.
- `cosine` → 1 cluster (no noise; mọi point là core với cosine metric + `eps=0.5`).

Đây là behavior đặc trưng của metric scaling trong DBSCAN; ML-04 KHÔNG dùng
observation này để kết luận "best metric" — đó là EPIC-07 scope.

### 7.3. Tests

| File | Số test | Trạng thái |
|------|---------|------------|
| `tests/test_ml04_dbscan.py` | 47 | **PASS** (verified trong session này) |

**Lưu ý về metric đánh giá:**

- ML-04 KHÔNG compute silhouette / DBI / CH / ARI / AMI.
- `MetricsResult` tất cả field = `None`.
- Per-metric diagnostics KHÔNG dùng để kết luận "best metric".
- Noise KHÔNG bị loại bỏ; đó là output chính thức của DBSCAN.

---

## 8. Công thức và ký hiệu

### 8.1. Ký hiệu DBSCAN

| Symbol | Ý nghĩa |
|--------|----------|
| `n` | Số customers (= `4371`) |
| `p` | Số features (= `14`) |
| `X ∈ ℝ^(n×p)` | Feature matrix |
| `x_i ∈ ℝ^p` | Vector feature của customer `i` |
| `eps` | Neighborhood radius (epsilon) |
| `min_samples` | Minimum points trong eps neighborhood (kể cả chính nó) |
| `d(x, y)` | Point-wise distance (định nghĩa bởi `metric`) |
| `N_eps(x)` | Epsilon-neighborhood của `x` |
| Core point | Point có `\|N_eps(x)\| >= min_samples` |
| Border point | Point không phải core nhưng nằm trong `N_eps` của core point |
| Noise point | Point không phải core, không phải border; label `-1` |

### 8.2. Epsilon-neighborhood

    N_eps(x) = {x_j | d(x, x_j) <= eps}

### 8.3. Core point criterion

    |N_eps(x)| >= min_samples

Trong sklearn convention: count includes `x` itself.

### 8.4. Density reachability

- Direct density-reachable: `p ∈ N_eps(q)` AND `q` là core point.
- Density-reachable: tồn tại chain of points nối `q` → `p` qua direct
  density-reachability.

### 8.5. Density connectivity

Hai points `p`, `q` density-connected nếu tồn tại `o` sao cho cả `p` và
`q` density-reachable từ `o`.

### 8.6. Objective

DBSCAN KHÔNG optimize một objective global. Behavior là deterministic
greedy: mỗi unlabeled point được gán core / border / noise; sau đó core
points và reachable neighbors được connect thành cluster; noise points giữ
label `-1`.

### 8.7. Thuật toán

1. **Initialize**: tất cả points unlabeled.
2. **Iterate**: for each unlabeled point `p`:
   a. Tìm `N_eps(p)`.
   b. Nếu `|N_eps(p)| < min_samples` → mark `p` as noise (có thể bị
      relabeled thành border ở step cuối).
   c. Else: tạo cluster mới; thêm `p` và tất cả density-reachable points
      vào cluster.
3. **Output**: cluster labels + noise label `-1` cho noise points.

Complexity: trung bình `O(n log n)` với spatial index; worst case `O(n²)`.

### 8.8. Tham khảo

Ester, M., Kriegel, H. P., Sander, J., & Xu, X. (1996). "A density-based
algorithm for discovering clusters in large spatial databases with noise".
Proceedings of the Second International Conference on Knowledge Discovery
and Data Mining (KDD-96).

---

## 9. Visualization boundary

### 9.1. EPIC-06 (ML-04 diagnostic — chưa có)

ML-04 chưa tạo diagnostic visualization nào trong EPIC-06. DBSCAN-specific
diagnostics (`noise_count`, `noise_ratio`, `core_sample_count`, `cluster_sizes`,
`labels_value_counts`) được captured trong `ClusterResult.extra` (JSON-friendly)
chứ KHÔNG phải visualization.

**K-distance plot chưa được tạo** trong EPIC-06. Đây là diagnostic viz
optional của EPIC-06 theo contract §3.4 + §9; ML-04 hiện tại KHÔNG thực hiện.

### 9.2. EPIC-06 (per-task diagnostic viz — optional, future)

| Task | Visualization (optional, future) | Loại | Status |
|------|----------------------------------|------|--------|
| ML-04 DBSCAN | k-distance plot để chọn `eps` | Diagnostic | **CHƯA ĐƯỢC TẠO** trong EPIC-06 |

### 9.3. EPIC-08 (research comparison)

EPIC-08 sở hữu (xem ML-01 Mentor document §9.3):

- DBI comparison, CH comparison (DBI/CH applicable cho DBSCAN sau khi exclude
  noise).
- Silhouette KHÔNG áp dụng cho density-based clusters có noise (AGENTS.md
  §3 Evaluation row).
- Algorithm comparison dashboard.

### 9.4. EPIC-09 (segment analysis)

EPIC-09 sở hữu (xem ML-01 Mentor document §9.4):

- Segment size (số customer / segment, có thể loại trừ noise hoặc gom vào
  "noise segment").
- RFM profile per segment.
- Feature distribution per segment.

### 9.5. Quy tắc tổng quát

- KHÔNG tạo visualization trong `reports/ml04/` ngoài JSON summary +
  Markdown narrative + CSV parameter diagnostic.
- KHÔNG re-label noise như outlier cần loại bỏ; đó là business interpretation,
  thuộc EPIC-09.
- KHÔNG gọi noise là "data quality issue"; đó là density-based output chính
  thức.

---

## 10. Verification

### 10.1. Tests

| Test category | File | Số test | Trạng thái |
|---------------|------|---------|------------|
| Unit tests cho DBSCANAdapter | `tests/test_ml04_dbscan.py` | 47 | **PASS** (verified trong session này) |

Test categories (từ test file):

- Adapter construction validation (`eps > 0`, `min_samples >= 1`, `metric`).
- `fit(X)` happy path — multiple metrics.
- `fit(X)` validation errors.
- `cluster_labels` shape, dtype, value range (bao gồm `-1`).
- Noise preserved verbatim (`noise_label == -1`, `noise_count`, `noise_ratio`).
- Core sample statistics (`core_sample_count`, `core_sample_ratio`).
- `cluster_sizes` excluding noise.
- Edge cases: `all_noise=True`, `has_single_cluster=True`.
- `supports_random_state() == False`.
- `get_params()` returns correct dict.
- `get_model()` returns fitted sklearn DBSCAN.
- Boundary discipline: no mutation, FE-06 input not mutated.

Verification command:

```bash
python3 -m pytest tests/test_ml04_dbscan.py -v
```

Verification result: **47 / 47 passed**.

### 10.2. Lint

```bash
ruff check src/customer_segmentation/clustering/
```

Result: **All checks passed!**

### 10.3. Format

```bash
black --check src/customer_segmentation/clustering/
```

Result: **15 files would be left unchanged**.

### 10.4. Reproducibility

- **Input SHA-256 unchanged**: FE-06 outputs không bị ML-04 mutate.
- **Config SHA-256 recorded**: `352199f370a5520f9fea99e8f60d6f7f89d0c483c7a4d456226f6b58624e5271`
  (primary run).
- **Library versions**: numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`,
  scikit-learn `1.9.1`, pyarrow `25.0.1`.
- **Determinism**: DBSCAN (n_clusters-free mode) là deterministic trong
  sklearn; không cần seed. Framework runner KHÔNG inject seed (đã advertise
  `supports_random_state() == False`).

### 10.5. Input integrity

Giống ML-02 / ML-03; `validate_clustering_matrix` và
`validate_customer_alignment` PASS.

### 10.6. Output integrity

- `cluster_labels` shape `(4371,)`, dtype `int64` ✅.
- `cluster_labels` values bao gồm `-1` (noise) và `[0, 16]` (cluster IDs)
  ✅.
- `IsNoise` column = `(ClusterLabel == -1)` ✅ (3177 True cho primary run).
- `cluster_result.noise_count == 3177` và
  `cluster_result.noise_ratio == 0.7268` ✅ (consistent với
  `labels_value_counts`).
- `extra.cluster_sizes` sum (excluding noise) = `n_samples - noise_count`
  = `4371 - 3177 = 1194` ✅.
- KHÔNG có `algorithm_output_*.parquet` (DBSCAN không có soft output).

### 10.7. Regression status

- Pre-existing tests còn pass: 47 / 47 ML-04 tests pass.
- Không có test nào bị skip không giải thích.
- Không có pre-existing failure chưa được giải thích.

---

## 11. Mentor Review

| ID | Nội dung cần review | Loại | Trạng thái |
|----|---------------------|------|------------|
| ML-04-MET-01 | Methodology: `working_eps=0.5` được chọn làm default cho ML-04 primary diagnostic | Methodology | PENDING_REVIEW |
| ML-04-MET-02 | Methodology: `working_min_samples=5` được chọn làm default | Methodology | PENDING_REVIEW |
| ML-04-MET-03 | Methodology: `working_metric='euclidean'` được chọn làm working default | Methodology | PENDING_REVIEW |
| ML-04-MET-04 | Methodology: noise label `-1` được preserve verbatim (KHÔNG re-label noise như outlier) | Methodology | PENDING_REVIEW |
| ML-04-MET-05 | Methodology: cho phép 3 per-metric diagnostic runs (euclidean / manhattan / cosine) trong EPIC-06 | Scope / Methodology | PENDING_REVIEW |
| ML-04-ENG-01 | Engineering: chỉ expose `eps`, `min_samples`, `metric` trong DBSCANAdapter — không expose thêm `algorithm`, `leaf_size`, `p`, `n_jobs` | Engineering / Scope | DOCUMENTED |
| ML-04-ENG-02 | Engineering: `n_clusters` không phải hyperparameter (DBSCAN discovers from data); adapter compute từ `np.unique(labels)` | Engineering | DOCUMENTED |
| ML-04-ENG-03 | Engineering: K-distance plot CHƯA ĐƯỢC TẠO trong EPIC-06 | Scope | DOCUMENTED (EPIC-06 diagnostic viz optional) |

**Ghi chú:**

- ML-04-MET-01, -02, -03, -04, -05 cần mentor review vì chúng ảnh hưởng đến
  cách initial diagnostic run được setup; EPIC-07 sweep sẽ reference các
  default này.
- ML-04-MET-04 đặc biệt quan trọng: **noise là output chính thức của DBSCAN**,
  KHÔNG phải "data quality issue cần fix". Mentor confirm giúp tránh hiểu
  lầm về scope.
- ML-04-ENG-01, -02, -03 là engineering / scope decisions; không ảnh hưởng
  experimental design.

---

## 12. Kết luận

### 12.1. Đã hoàn thành

ML-04 DBSCAN **TECHNICALLY_IMPLEMENTED** với evidence:

- **Code:** `src/customer_segmentation/clustering/dbscan.py`
  (`DBSCANAdapter` + default constants + sklearn wrapper).
- **Configuration:** `configs/clustering.yaml` →
  `clustering.algorithms.dbscan.*`.
- **Tests:** `tests/test_ml04_dbscan.py` — 47 / 47 tests passed.
- **Initial diagnostic runs đã chạy thành công:**
  - 1 primary run (`euclidean`, `eps=0.5`, `min_samples=5`): SUCCESS,
    n_clusters=17, noise_count=3177, noise_ratio=0.7268,
    core_sample_count=1037, execution_time=0.133s.
  - 3 per-metric diagnostic runs (`euclidean`, `manhattan`, `cosine`):
    tất cả SUCCESS với behavior rất khác nhau (xem
    `reports/ml04/ml04_parameter_diagnostic.csv`).
- **Artifacts:** 4 files `cluster_labels_ML-04-DBSCAN-*.parquet` + 4 files
  `experiment_log_ML-04-DBSCAN-*.json`.
- **Reports:**
  - `reports/ml04/ml04_run_summary.json`
  - `reports/ml04/ml04_initial_diagnostic.md`
  - `reports/ml04/ml04_parameter_diagnostic.csv`
- **Lint:** `ruff check` pass.
- **Format:** `black --check` pass.

### 12.2. Chưa hoàn thành

- **Evaluation metrics**: `MetricsResult` toàn field = `None`. EPIC-07/08
  sẽ compute (silhouette KHÔNG applicable; DBI/CH applicable sau khi
  exclude noise).
- **Sweep `(eps, min_samples, metric)`**: chỉ có 1 primary + 3 per-metric
  diagnostic; EPIC-07 sẽ sweep đầy đủ `dbscan.eps_range` và
  `dbscan.min_samples_range`.
- **K-distance diagnostic plot**: chưa được tạo trong EPIC-06; đó là
  diagnostic viz optional và có thể được tạo sau nếu cần.
- **Algorithm comparison**: EPIC-08.
- **Business interpretation của noise** (outlier removal, noise segment riêng):
  EPIC-09.
- **Segment profiling / naming**: EPIC-09.

### 12.3. Pending Mentor Review

| ID | Quyết định | Trạng thái |
|----|------------|------------|
| ML-04-MET-01 | `working_eps=0.5` cho ML-04 primary diagnostic | PENDING_REVIEW |
| ML-04-MET-02 | `working_min_samples=5` cho working default | PENDING_REVIEW |
| ML-04-MET-03 | `working_metric='euclidean'` cho working default | PENDING_REVIEW |
| ML-04-MET-04 | Noise label `-1` preserve verbatim | PENDING_REVIEW |
| ML-04-MET-05 | 3 per-metric diagnostic runs trong EPIC-06 | PENDING_REVIEW |

### 12.4. Chuyển tiếp sang task tiếp theo

**Output của ML-04 = input cho EPIC-07:**

- `cluster_labels_*.parquet` → EPIC-07 sẽ read cho mỗi `(eps, min_samples, metric)`.
- `experiment_log_*.json` → EPIC-07 sẽ populate `MetricsResult` (DBI/CH,
  silhouette bị skip cho density-based clusters có noise) per-fit.
- `cluster_result.extra.noise_count` / `noise_ratio` / `core_sample_count` →
  EPIC-07 sẽ collect cho mỗi (eps, min_samples, metric) để explore parameter
  space.
- `cluster_result.extra.cluster_sizes` → EPIC-09 sẽ dùng (sau khi exclude
  noise).

**Contract giữa ML-04 và consumer:**

| Field | Contract |
|-------|----------|
| `algorithm_family` | `"density_based"` |
| `cluster_labels` shape | `(4371,)` |
| `cluster_labels` dtype | `int64` |
| `cluster_labels` values | `[0, K-1] ∪ {-1}` (noise) |
| `IsNoise` column | `(ClusterLabel == -1)` |
| `noise_label` | `-1` |
| `noise_count`, `noise_ratio`, `core_sample_count`, `core_sample_ratio` | recorded in `ClusterResult` + `ClusterResult.extra` |
| `supports_random_state` | `False` (deterministic) |
| `soft_probabilities`, `soft_membership` | `None` (DBSCAN không có) |

**TUYỆT ĐỐI KHÔNG** trong Mentor document này: KHÔNG viết "best (eps,
min_samples)", KHÔNG gọi DBSCAN là "best algorithm", KHÔNG ranking với
algorithm khác, KHÔNG gọi noise là outlier cần loại bỏ. ML-04 là
implementation + initial diagnostics, KHÔNG là evaluation.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-04 implementation
(code, tests, config, primary + per-metric diagnostic runs, experiment log,
artifacts, parameter diagnostic CSV). Mọi con số trong tài liệu này đều
có provenance rõ ràng. Noise label `-1` là output chính thức của DBSCAN,
KHÔNG phải outlier cần xử lý — đó là EPIC-09 scope._