# ML-02 — K-Means Clustering

> **Mentor Document cho EPIC-06 / ML-02.**
> Adapter version: `sklearn_1.9.1` (ghi trong `KMeansAdapter.version`).
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
| **Task ID** | `ML-02` |
| **Tên task** | K-Means Clustering |
| **Mục tiêu** | Triển khai K-Means như một concrete `BaseClusterAlgorithm` adapter, plug vào ML-01 framework. Adapter là thin wrapper quanh `sklearn.cluster.KMeans`; nó chỉ expose các hyperparameter đã được quy ước trong ML-02 task contract (`n_clusters`, `init`, `n_init`, `max_iter`, `random_state`, `tol`), truyền chúng qua sklearn, ghi lại diagnostics (`wcss`, `n_iter`, `cluster_sizes`) vào `ClusterResult.extra`. KHÔNG compute evaluation metrics, KHÔNG so sánh algorithm, KHÔNG chọn best K, KHÔNG mutate input. |
| **Vị trí trong research pipeline** | ML-02 nằm sau ML-01 (framework) và sau FE-06 (dataset). ML-02 là adapter đầu tiên trong EPIC-06 (sau K-Means là K-Medoids placeholder → Agglomerative → DBSCAN → GMM → FCM). Output của ML-02 (`cluster_labels_*.parquet`, `experiment_log_*.json`) là input cho EPIC-07 (controlled sweep), EPIC-08 (evaluation), EPIC-09 (segment analysis). |
| **Input** | `data/processed/final_clustering_dataset.parquet` (FE-06 output; SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`); `data/processed/customer_metadata.parquet` (FE-06 output; SHA-256 `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`); `configs/clustering.yaml` (K-Means section: `clustering.algorithms.kmeans.*`). |
| **Output** | `data/processed/clustering_experiments/cluster_labels_{experiment_id}.parquet` (CustomerID + ClusterLabel + IsNoise); `data/processed/clustering_experiments/experiment_log_{experiment_id}.json` (full `ExperimentResult.to_dict()`); `reports/ml02/ml02_run_summary.json` (Machine-readable summary); `reports/ml02/ml02_initial_diagnostic.md` (Vietnamese narrative report). |
| **Quan hệ với task trước/sau** | Trước: ML-01 framework cung cấp `BaseClusterAlgorithm`, `AlgorithmRegistry`, `ClusterResult`, `ExperimentResult`, `ExperimentRunner`. Sau: EPIC-07 sẽ sweep `(n_clusters, init, n_init, max_iter, random_state)`; EPIC-08 sẽ compute silhouette/DBI/CH trên `cluster_labels_*.parquet`; EPIC-09 sẽ phân tích segment dựa trên cluster labels. |
| **Algorithm family** | `hard` (mỗi customer thuộc đúng 1 cluster; không có soft probability, không có noise label, không có membership matrix). |

---

## 2. Mục tiêu nghiên cứu

ML-02 trả lời một phần câu hỏi nghiên cứu về **tính khả thi kỹ thuật** của
việc chạy K-Means trên FE-06 dataset với framework thống nhất:

- "Có thể chạy K-Means trên Final Clustering Dataset (4371 customers, 14
  features) với cùng schema output của ML-01 framework không?"
- "K-Means có hội tụ trên FE-06 dataset trong working configuration không?
  WCSS / `n_iter` / `converged` flag cho biết gì?"
- "Có thể reproduce K-Means run với cùng input + config + seed + library
  version không? `random_state` policy của K-Means có được framework enforce
  đúng không?"

**Phạm vi nghiên cứu:**

- ML-02 là technical implementation, KHÔNG phải evaluation.
- ML-02 KHÔNG sweep K; `working_n_clusters=4` là **WORKING_ASSUMPTION**,
  không phải final methodology.
- ML-02 KHÔNG chọn `best init` hay `best n_init`; `init='k-means++'` và
  `n_init=10` là working defaults từ `configs/clustering.yaml`.

**Mối liên hệ với đặc thù dữ liệu FE-06:**

- FE-06 dataset là Yeo-Johnson + RobustScaler (xem
  `reports/fe06/comparison_matrix.csv` → C7). K-Means dùng khoảng cách
  Euclidean, nên scaling là bắt buộc để feature có variance lớn không
  dominate; FE-06 đã mitigate điều này bằng RobustScaler.
- CustomerID alignment: CustomerID sống trong `customer_metadata.parquet`;
  feature matrix 14 cột KHÔNG chứa CustomerID. K-Means adapter enforce
  positional alignment (row `i` của `cluster_labels` ↔ row `i` của
  `customer_metadata`).

**Mối liên hệ với EPIC-07/08/09:**

- EPIC-07 sẽ sweep `(n_clusters, init, n_init, max_iter, random_state)` và
  gọi `ExperimentRunner` với `algorithm="kmeans"` cho mỗi fit.
- EPIC-08 sẽ compute silhouette / DBI / CH trên `cluster_labels_*.parquet`
  của ML-02; WCSS hiện có trong `cluster_result.extra` chỉ là diagnostic,
  KHÔNG thay thế EPIC-08 evaluation.
- EPIC-09 sẽ phân tích segment dựa trên `cluster_labels_*.parquet`; KHÔNG
  có segment profiling trong ML-02.

---

## 3. Cơ sở lý thuyết

### 3.1. K-Means algorithm

K-Means (Lloyd's algorithm) là hard clustering dựa trên centroid: mỗi
observation được assign về centroid gần nhất (theo Euclidean distance), và
centroid được update là trung bình cộng của các observation trong cluster.
Hai bước này lặp cho đến khi centroid không đổi hoặc đạt `max_iter`.

### 3.2. Centroid

Centroid của cluster `k` là trung bình cộng của tất cả các observation
hiện đang thuộc cluster `k`:

    μ_k = (1 / |C_k|) · Σ_{x_i ∈ C_k} x_i

### 3.3. Distance metric

K-Means mặc định dùng **Euclidean distance**:

    d(x_i, μ_k) = ||x_i - μ_k||_2 = sqrt(Σ_d (x_i,d - μ_k,d)^2)

`metric="euclidean"` là working default trong ML-02; K-Means sklearn không
expose metric khác qua interface của ML-02.

### 3.4. Assignment step

Mỗi observation được assign về cluster có centroid gần nhất:

    c_i = argmin_k ||x_i - μ_k||_2

### 3.5. Centroid update step

Sau assignment, mỗi centroid được update là trung bình của observation hiện
đang thuộc cluster:

    μ_k = (1 / |C_k|) · Σ_{x_i ∈ C_k} x_i

### 3.6. Objective function (WCSS / Inertia)

Objective mà K-Means minimize là **within-cluster sum of squares** (WCSS),
còn gọi là **inertia**:

    J = Σ_i ||x_i - μ_{c_i}||^2 = Σ_k Σ_{x_i ∈ C_k} ||x_i - μ_k||^2

Hai bước assignment và update làm `J` giảm (hoặc giữ nguyên) qua mỗi
iteration; K-Means converge đến local minimum.

### 3.7. Initialization

- `init="k-means++"` (default trong sklearn từ 1.1): seed initial centroids
  bằng distance-proportional probability scheme, tránh poor local minima
  của pure random initialization.
- `init="random"`: pure random initialization.
- ML-02 working default là `"k-means++"` (`configs/clustering.yaml`
  → `algorithms.kmeans.init`).

### 3.8. Convergence

Dừng khi:
1. Centroid không đổi qua một iteration.
2. `max_iter` đạt.
3. Relative tolerance `tol` đạt (`||U_new - U_old|| < tol` trong sklearn).

### 3.9. Role of K (n_clusters)

Số cluster `K` phải được chọn trước. EPIC-07 sẽ sweep `k_range` đã ghi
trong `configs/clustering.yaml` → `algorithms.kmeans.k_range = [2, 10]`.

### 3.10. n_init

Số random restart. sklearn chạy algorithm `n_init` lần với các seed khác
nhau và trả về run có inertia thấp nhất. ML-02 working default: `n_init=10`
(`configs/clustering.yaml` → `algorithms.kmeans.n_init`).

### 3.11. Random initialization

K-Means có thể cho kết quả khác nhau giữa các lần chạy nếu không fix
`random_state`. Đây là lý do ML-02 advertise `supports_random_state() == True`
và framework runner inject seed.

### 3.12. Hard clustering

Mỗi observation thuộc đúng 1 cluster. ML-02 KHÔNG có soft probability, KHÔNG
có noise label (K-Means luôn assign mỗi observation về 1 cluster).

### 3.13. Sensitivity to scaling

K-Means dùng khoảng cách → bị dominated bởi feature có variance lớn. FE-06 đã
mitigate điều này bằng Yeo-Johnson + RobustScaler (C7 working config);
ML-02 không re-scale.

---

## 4. Phương pháp / Methodology

### 4.1. Dữ liệu sử dụng

| File | Vai trò | SHA-256 | Shape |
|------|---------|---------|-------|
| `data/processed/final_clustering_dataset.parquet` | Numeric feature matrix | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `(4371, 14)` |
| `data/processed/customer_metadata.parquet` | CustomerID mapping | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `(4371, 1)` |

Dataset version: `FE06-v1.0`.

**Feature set (14 features):** `Recency`, `Frequency`, `Monetary`,
`TotalQuantity`, `AverageQuantity`, `BasketSize`, `TenureDays`,
`PurchaseIntervalMean`, `PurchaseIntervalStd`, `ActiveDays`,
`AverageInvoiceValue`, `ProductsPerInvoice`, `CancellationRate`,
`ReturnRate`. (FE-06 evidence: `reports/fe06/feature_eligibility.csv`.)

### 4.2. Preprocessing

ML-02 KHÔNG thực hiện preprocessing. Verify input đã qua FE-06 pipeline:

- `reports/fe06/fe06_run.json` → `validations`: tất cả PASS (`row_count`,
  `no_identifier_in_matrix`, `no_nan`, `no_inf`, `no_constant_feature`,
  `all_numeric`, `customer_metadata_alignment`).
- Matrix 4371 rows × 14 numeric columns, không chứa identifier, không NaN,
  không Inf, không constant feature.

### 4.3. Algorithm / configuration

| Hyperparameter | Working default | Nguồn |
|----------------|-----------------|--------|
| `n_clusters` | `4` | `configs/clustering.yaml` → `clustering.algorithms.kmeans.working_n_clusters` |
| `init` | `"k-means++"` | `configs/clustering.yaml` → `clustering.algorithms.kmeans.init` |
| `n_init` | `10` | `configs/clustering.yaml` → `clustering.algorithms.kmeans.n_init` |
| `max_iter` | `300` | `configs/clustering.yaml` → `clustering.algorithms.kmeans.max_iter` |
| `tol` | `1e-4` (sklearn default) | `kmeans.py` → `KMeansAdapter(tol=...)` |
| `random_state` | `42` (từ framework) | `configs/clustering.yaml` → `clustering.random_seed: 42` |

`k_range = [2, 10]` đã được ghi trong YAML nhưng EPIC-07 mới thực sự sweep.

**Library version:** `sklearn 1.9.1` (ghi trong `cluster_result.algorithm_version`
và `cluster_result.extra`). ML-02 không pin sklearn version; phiên bản cụ thể
phụ thuộc vào môi trường runtime.

**Per-algorithm random-seed policy:**

- `framework.random_seed.default = 42` → K-Means adapter nhận
  `random_state=42` qua `ExperimentRunner.run()` → `KMeans(random_state=42)`.
- K-Means advertise `supports_random_state() == True` → runner inject seed.

### 4.4. Cách chạy

Script entry point: `scripts/run_ml02_kmeans.py`.

```bash
python -m scripts.run_ml02_kmeans
python -m scripts.run_ml02_kmeans --n-clusters 5 --seed 7
```

Lệnh này:

1. Load `configs/clustering.yaml` qua `load_framework_config()`.
2. Load `data/processed/final_clustering_dataset.parquet` và
   `data/processed/customer_metadata.parquet`.
3. Compute SHA-256 của input, metadata, config.
4. Build `ExperimentSpec(experiment_id, algorithm="kmeans",
   hyperparameters={n_clusters, init, n_init, max_iter}, seed_override=None)`.
5. Run `ExperimentRunner.run(matrix_df, metadata_df, input_sha256, ..., output_dir)`.
6. Ghi `cluster_labels_*.parquet`, `experiment_log_*.json` trong
   `data/processed/clustering_experiments/`.
7. Ghi `reports/ml02/ml02_run_summary.json` và `reports/ml02/ml02_initial_diagnostic.md`.

Workflow: load framework config → load FE-06 inputs → build ExperimentSpec →
ExperimentRunner.run → write artifacts → write summary + diagnostic report.

### 4.5. Cách lưu kết quả

Artifact paths theo `framework.output` config:

- `cluster_labels_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.parquet` —
  schema: `CustomerID` (int64/string) + `ClusterLabel` (int64) + `IsNoise`
  (bool, always False cho K-Means vì không có noise).
- `experiment_log_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.json` —
  full `ExperimentResult.to_dict()` (cluster_result, hyperparameters, seed,
  execution_time, library_versions, scope_boundaries, ...).
- KHÔNG có `algorithm_output_*.parquet` cho K-Means (không có soft
  probability / membership).

### 4.6. Cách đảm bảo reproducibility

- `experiment_log` ghi input SHA-256, config SHA-256, seed requested +
  seed used, library versions.
- Random seed policy: framework default `42` được inject vào `KMeans(random_state=42)`.
- Determinism: cùng input + config + random_state + library version → cùng
  cluster labels + cùng inertia + cùng n_iter.

### 4.7. Bảng phân loại decision (BẮT BUỘC)

| Loại decision | Nội dung | Status | Bằng chứng / Nguồn |
|---------------|----------|--------|---------------------|
| TECHNICALLY_IMPLEMENTED | `KMeansAdapter` class | Implemented | `src/customer_segmentation/clustering/kmeans.py` |
| TECHNICALLY_IMPLEMENTED | Adapter registered in `AlgorithmRegistry` as `"kmeans"` | Implemented | `kmeans.py` → `@AlgorithmRegistry.register("kmeans")` |
| TECHNICALLY_IMPLEMENTED | `supports_random_state() == True` (K-Means consumes random_state) | Implemented | `kmeans.py` → `KMeansAdapter.supports_random_state` |
| TECHNICALLY_IMPLEMENTED | Hard cluster labels output, dtype `int64`, shape `(n_samples,)` | Implemented | `kmeans.py` → `KMeansAdapter.fit` |
| TECHNICALLY_IMPLEMENTED | K-Means diagnostic WCSS / n_iter / cluster_sizes / converged | Implemented | `kmeans.py` → `ClusterResult.extra` |
| TECHNICALLY_IMPLEMENTED | Validation matrix theo FE-06 contract | Implemented | `tests/test_ml02_kmeans.py` (40 tests pass) |
| TECHNICALLY_IMPLEMENTED | Initial diagnostic run trên FE-06 dataset | Implemented | `reports/ml02/ml02_initial_diagnostic.md`; `experiment_log_ML-02-KMeans-...json` |
| WORKING_ASSUMPTION | `n_clusters = 4` | Working assumption | `configs/clustering.yaml` → `algorithms.kmeans.working_n_clusters` |
| WORKING_ASSUMPTION | `init = 'k-means++'` | Working assumption | `configs/clustering.yaml` → `algorithms.kmeans.init` |
| WORKING_ASSUMPTION | `n_init = 10` | Working assumption | `configs/clustering.yaml` → `algorithms.kmeans.n_init` |
| WORKING_ASSUMPTION | `max_iter = 300` | Working assumption | `configs/clustering.yaml` → `algorithms.kmeans.max_iter` |
| WORKING_ASSUMPTION | `tol = 1e-4` (sklearn default) | Working assumption | `kmeans.py` → `KMeansAdapter(tol=...)` |
| WORKING_ASSUMPTION | `random_state = 42` (framework default) | Working assumption | `configs/clustering.yaml` → `clustering.random_seed` |
| PENDING_REVIEW | Methodology: chọn working `n_clusters=4` làm default cho ML-02 diagnostic | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: chọn `init='k-means++'` cho working default | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| OUT_OF_SCOPE | Compute evaluation metrics (silhouette, DBI, CH) | Explicit | EPIC-07/08 ownership |
| OUT_OF_SCOPE | Pick best K hoặc best init | Explicit | EPIC-07 ownership |
| OUT_OF_SCOPE | Pick best algorithm | Explicit | EPIC-08 ownership |
| OUT_OF_SCOPE | Customer segment profiling / naming | Explicit | EPIC-09 ownership |
| OUT_OF_SCOPE | Mutate FE-06 output | Explicit | AGENTS.md §2.3 |

---

## 5. Implementation

### 5.1. Module / file chính

- Adapter: `src/customer_segmentation/clustering/kmeans.py` → `KMeansAdapter`.
- Default constants: `DEFAULT_INIT`, `DEFAULT_N_INIT`, `DEFAULT_MAX_ITER`,
  `MIN_N_CLUSTERS` (ghi trong `kmeans.py`).
- Public re-export: `src/customer_segmentation/clustering/__init__.py` →
  `from customer_segmentation.clustering.kmeans import KMeansAdapter`.
- Tests: `tests/test_ml02_kmeans.py` (40 tests).
- Script: `scripts/run_ml02_kmeans.py`.
- Reports: `reports/ml02/ml02_initial_diagnostic.md`,
  `reports/ml02/ml02_run_summary.json`.
- Artifacts: `data/processed/clustering_experiments/cluster_labels_ML-02-KMeans-*.parquet`,
  `data/processed/clustering_experiments/experiment_log_ML-02-KMeans-*.json`.

### 5.2. Class hierarchy

```
BaseClusterAlgorithm (ML-01)
    └── KMeansAdapter (ML-02)
            ├── name = "kmeans"
            ├── version = "sklearn_<sklearn.__version__>" (= "sklearn_1.9.1" tại thời điểm run)
            ├── family = AlgorithmFamily.HARD
            ├── __init__(n_clusters, *, init, n_init, max_iter, random_state, tol)
            ├── fit(X) -> ClusterResult
            ├── get_params() -> dict
            ├── get_model() -> sklearn.cluster.KMeans | None
            └── supports_random_state() -> bool (returns True)
```

### 5.3. Pipeline

```
scripts/run_ml02_kmeans.py
  │
  ├── load configs/clustering.yaml (FrameworkConfig)
  ├── load data/processed/final_clustering_dataset.parquet (X)
  ├── load data/processed/customer_metadata.parquet (metadata)
  ├── compute SHA-256(input), SHA-256(metadata), SHA-256(config)
  │
  ├── spec = ExperimentSpec(
  │       experiment_id = "ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg",
  │       algorithm = "kmeans",
  │       hyperparameters = {
  │           "n_clusters": 4,
  │           "init": "k-means++",
  │           "n_init": 10,
  │           "max_iter": 300,
  │       },
  │       seed_override = None,
  │   )
  │
  ├── runner = ExperimentRunner(cfg, spec, config_source, config_text)
  │
  └── runner.run(X, metadata, input_sha256, input_path, metadata_path,
                  output_dir="data/processed/clustering_experiments/")
         │
         ├── validate_clustering_matrix(X)  → ValidationReport (PASS)
         ├── validate_customer_alignment(metadata, X)  → ValidationReport (PASS)
         ├── adapter = AlgorithmRegistry.get("kmeans")(**spec.hyperparameters)
         ├── seed = resolve_random_seed(cfg, "kmeans", None) → (42, 42)
         │       (KMeansAdapter.supports_random_state() == True → seed injected)
         ├── KMeans(n_clusters=4, init="k-means++", n_init=10, max_iter=300,
         │           random_state=42, tol=1e-4).fit_predict(X)
         │   → cluster_labels (np.ndarray, shape (4371,), dtype int64)
         │
         └── ClusterResult(
                algorithm="kmeans",
                algorithm_version="sklearn_1.9.1",
                algorithm_family="hard",
                n_samples=4371,
                n_features=14,
                cluster_labels=labels,            # int64
                n_clusters=4,
                soft_probabilities=None,           # K-Means không có
                soft_membership=None,             # K-Means không có
                noise_label=-1,                   # default; K-Means không dùng
                noise_count=0,
                noise_ratio=0.0,
                supports_random_state=True,
                random_seed_used=42,
                extra={
                    "init_strategy": "k-means++",
                    "effective_n_init": 10,
                    "n_iter": 11,
                    "converged": True,
                    "wcss": 179859.0233766095,
                    "cluster_sizes": {"0": 3021, "1": 555, "2": 571, "3": 224},
                },
                metrics=MetricsResult(... all None ...),
            )
```

### 5.4. Configuration

| Config key | Value | Nguồn |
|------------|-------|--------|
| `clustering.framework.input.final_clustering_dataset_path` | `./data/processed/final_clustering_dataset.parquet` | `configs/clustering.yaml` |
| `clustering.framework.input.customer_metadata_path` | `./data/processed/customer_metadata.parquet` | `configs/clustering.yaml` |
| `clustering.framework.input.dataset_version` | `FE06-v1.0` | `configs/clustering.yaml` |
| `clustering.framework.random_seed.default` | `42` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.enabled` | `true` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.k_range` | `[2, 10]` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.working_n_clusters` | `4` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.init` | `"k-means++"` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.n_init` | `10` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.max_iter` | `300` | `configs/clustering.yaml` |
| `clustering.algorithms.kmeans.tol` | `1.0e-4` | `configs/clustering.yaml` |

### 5.5. Input/output contract

**Input (`fit` parameter):**

- `X: numpy.ndarray` — shape `(n_samples, n_features) = (4371, 14)`, dtype
  `float64`, không chứa identifier.

**Output (`ClusterResult` fields):**

| Field | Value (ML-02 actual) | Nguồn |
|-------|----------------------|--------|
| `algorithm` | `"kmeans"` | `kmeans.py` → `KMeansAdapter.name` |
| `algorithm_version` | `"sklearn_1.9.1"` | `kmeans.py` → `KMeansAdapter.version` |
| `algorithm_family` | `"hard"` | `kmeans.py` → `KMeansAdapter.family` |
| `n_samples` | `4371` | `X.shape[0]` |
| `n_features` | `14` | `X.shape[1]` |
| `cluster_labels` | `np.ndarray`, shape `(4371,)`, dtype `int64`, values in `{0, 1, 2, 3}` | `model.fit_predict(X).astype(int64)` |
| `n_clusters` | `4` (= `labels.max() + 1`) | `kmeans.py` → `n_clusters_found` |
| `soft_probabilities` | `None` (K-Means không có) | default |
| `soft_membership` | `None` (K-Means không có) | default |
| `noise_label` | `-1` (default; K-Means không dùng) | default |
| `noise_count` | `0` (K-Means không có noise) | hardcoded |
| `noise_ratio` | `0.0` (K-Means không có noise) | hardcoded |
| `supports_random_state` | `True` | `KMeansAdapter.supports_random_state()` |
| `random_seed_used` | `42` (= `self.random_state`) | `kmeans.py` |
| `extra.init_strategy` | `"k-means++"` | `kmeans.py` |
| `extra.effective_n_init` | `10` (= `model.n_init_used`) | `kmeans.py` |
| `extra.n_iter` | `11` (= `model.n_iter_`) | `kmeans.py` |
| `extra.converged` | `True` (= `model.n_iter_ < max_iter`) | `kmeans.py` |
| `extra.wcss` | `179859.0233766095` (= `model.inertia_`) | `kmeans.py` |
| `extra.cluster_sizes` | `{"0": 3021, "1": 555, "2": 571, "3": 224}` | `kmeans.py` |
| `metrics.*` | tất cả `None` (EPIC-07/08 populate) | `cluster_result.metrics` |

### 5.6. Validation (K-Means-specific)

Adapter validate input trong `fit`:

- `X` không None.
- `X` là `np.ndarray`.
- `X.ndim == 2`.
- `n_samples >= 2`.
- `n_clusters < n_samples`.
- `n_features >= 1`.

Nếu validate fail → raise `ClusterAlgorithmError`, runner catch và trả
`ExperimentResult(status=FAILED)`.

### 5.7. Artifacts (ML-02 actual)

| Artifact | Path | Schema |
|----------|------|--------|
| Cluster labels | `data/processed/clustering_experiments/cluster_labels_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.parquet` | `CustomerID` (int64) + `ClusterLabel` (int64) + `IsNoise` (bool, always False cho K-Means) |
| Experiment log | `data/processed/clustering_experiments/experiment_log_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.json` | `ExperimentResult.to_dict()` |
| Run summary | `reports/ml02/ml02_run_summary.json` | Stage + input + metadata + config + experiment + result + artifacts |
| Initial diagnostic | `reports/ml02/ml02_initial_diagnostic.md` | Vietnamese narrative report (diagnostic only) |
| Algorithm output | KHÔNG có | K-Means không có soft probability |

### 5.8. JSON snippet (từ `experiment_log_ML-02-...json`)

```jsonc
{
  "experiment_id": "ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg",
  "status": "SUCCESS",
  "algorithm": "kmeans",
  "algorithm_version": "sklearn_1.9.1",
  "dataset_version": "FE06-v1.0",
  "dataset_sha256": "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c",
  "feature_set": [
    "Recency", "Frequency", "Monetary", "TotalQuantity", "AverageQuantity",
    "BasketSize", "TenureDays", "PurchaseIntervalMean", "PurchaseIntervalStd",
    "ActiveDays", "AverageInvoiceValue", "ProductsPerInvoice",
    "CancellationRate", "ReturnRate"
  ],
  "feature_count": 14,
  "n_samples": 4371,
  "hyperparameters": {
    "n_clusters": 4, "init": "k-means++", "n_init": 10,
    "max_iter": 300, "random_state": null, "tol": 0.0001
  },
  "random_seed": 42, "random_seed_used": 42,
  "n_clusters": 4,
  "cluster_labels_shape": [4371],
  "cluster_labels_dtype": "int64",
  "execution_time": 0.05543958299949736,
  "timestamp": "2026-09-21T04:12:25.334102+00:00",
  "cluster_result": {
    "algorithm": "kmeans",
    "algorithm_version": "sklearn_1.9.1",
    "algorithm_family": "hard",
    "n_samples": 4371, "n_features": 14, "n_clusters": 4,
    "cluster_labels_shape": [4371], "cluster_labels_dtype": "int64",
    "cluster_labels_first_5": [2, 2, 2, 2, 2],
    "soft_probabilities_shape": null,
    "soft_membership_shape": null,
    "noise_label": -1, "noise_count": 0, "noise_ratio": 0.0,
    "supports_random_state": true, "random_seed_used": null,
    "extra": {
      "init_strategy": "k-means++", "effective_n_init": 10,
      "n_iter": 11, "converged": true,
      "wcss": 179859.0233766095,
      "cluster_sizes": {"0": 3021, "1": 555, "2": 571, "3": 224}
    },
    "metrics": { /* all None */ }
  },
  "metrics": { /* all None */ },
  "platform": {"python": "3.14.4", "system": "Linux", "release": "7.0.0-31-generic", "machine": "x86_64"},
  "library_versions": {"numpy": "2.3.5", "pandas": "3.0.6", "scipy": "1.18.1", "scikit-learn": "1.9.1", "pyarrow": "25.0.1"},
  "config_source": "yaml:/.../configs/clustering.yaml",
  "config_sha256": "9b5f3d55ae24cc4e359b337cd57f48d362f38f0831b0e94b810ff2a38741f941"
}
```

---

## 6. Experimental Design Boundary

| | EPIC-06 (ML-02 K-Means) | EPIC-07 | EPIC-08 | EPIC-09 |
|---|--------------------------|---------|---------|---------|
| **Algorithm implementation** | ✅ KMeansAdapter | — | — | — |
| **Configuration** | ✅ Working default (n_clusters=4, init='k-means++', ...) | Sweep matrix | — | — |
| **Single-fit experiment** | ✅ Initial diagnostic (1 algo × 1 K × 1 seed) | Batch | — | — |
| **Sweep nhiều K** | ❌ | ✅ (sẽ dùng `kmeans.k_range = [2, 10]`) | — | — |
| **Sweep nhiều seed** | ❌ | ✅ | — | — |
| **Sweep nhiều config** | ❌ | ✅ (init, n_init, max_iter, ...) | — | — |
| **Compute internal metrics** | ❌ (chỉ record diagnostic WCSS / n_iter / cluster_sizes trong `extra`) | Partial (per fit) | ✅ Final | — |
| **Stability (ARI/AMI)** | ❌ | Generate | ✅ Aggregate | — |
| **Runtime comparison** | ❌ | Per-run time | ✅ Statistical summary | — |
| **Algorithm comparison** | ❌ | — | ✅ | — |
| **Diagnostic viz (elbow, WCSS curve)** | ⚠️ Optional (chưa có trong EPIC-06) | — | — | — |
| **Research viz (silhouette, DBI, CH)** | ❌ | — | ✅ | — |
| **Segment profile / naming** | ❌ | — | — | ✅ |
| **Pick best algorithm / best K** | ❌ | — | ✅ (sau full eval) | — |
| **Customer profiling** | ❌ | — | — | ✅ |

---

## 7. Kết quả thực tế

ML-02 initial diagnostic run đã chạy thành công với evidence:

| Loại kết quả | Giá trị | Nguồn |
|--------------|---------|--------|
| Status | `SUCCESS` | `data/processed/clustering_experiments/experiment_log_ML-02-KMeans-...json` → `status` |
| Experiment ID | `ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg` | `experiment_log_*.json` → `experiment_id` |
| Algorithm version | `sklearn_1.9.1` | `experiment_log_*.json` → `algorithm_version` |
| Algorithm family | `hard` | `experiment_log_*.json` → `cluster_result.algorithm_family` |
| Dataset version | `FE06-v1.0` | `experiment_log_*.json` → `dataset_version` |
| Input SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `experiment_log_*.json` → `dataset_sha256` |
| Metadata SHA-256 | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `experiment_log_*.json` → `metadata_path` (verify qua FE-06) |
| Config SHA-256 (lần run này) | `9b5f3d55ae24cc4e359b337cd57f48d362f38f0831b0e94b810ff2a38741f941` | `experiment_log_*.json` → `config_sha256` |
| n_samples | `4371` | `experiment_log_*.json` → `n_samples` |
| n_features | `14` | `experiment_log_*.json` → `feature_count` |
| n_clusters | `4` | `experiment_log_*.json` → `n_clusters` |
| Hyperparameters | `{n_clusters: 4, init: "k-means++", n_init: 10, max_iter: 300, random_state: null, tol: 0.0001}` | `experiment_log_*.json` → `hyperparameters` |
| random_seed (requested) | `42` | `experiment_log_*.json` → `random_seed` |
| random_seed_used | `42` | `experiment_log_*.json` → `random_seed_used` |
| init_strategy | `"k-means++"` | `experiment_log_*.json` → `cluster_result.extra.init_strategy` |
| effective_n_init | `10` | `cluster_result.extra.effective_n_init` |
| n_iter | `11` | `cluster_result.extra.n_iter` |
| converged | `True` | `cluster_result.extra.converged` |
| WCSS (inertia) | `179859.0233766095` | `cluster_result.extra.wcss` (**diagnostic only**, KHÔNG phải evaluation metric) |
| Cluster sizes | `{"0": 3021, "1": 555, "2": 571, "3": 224}` | `cluster_result.extra.cluster_sizes` |
| Execution time | `0.05543958299949736` (s) | `experiment_log_*.json` → `execution_time` |
| Timestamp | `2026-09-21T04:12:25.334102+00:00` | `experiment_log_*.json` → `timestamp` |
| Platform | python `3.14.4`, system `Linux`, release `7.0.0-31-generic`, machine `x86_64` | `experiment_log_*.json` → `platform` |
| Library versions | numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`, scikit-learn `1.9.1`, pyarrow `25.0.1` | `experiment_log_*.json` → `library_versions` |
| Số tests | `40` | `tests/test_ml02_kmeans.py` (collect count: 40) |
| Số tests pass | `40 / 40` | `pytest tests/test_ml02_kmeans.py` (verified trong session này) |

**Provenance template (theo EPIC06_DOCUMENTATION_CONTRACT §5):**

- `n_clusters = 4` -- nguồn --> `experiment_log_ML-02-KMeans-...json` -- field --> `n_clusters`
- `execution_time = 0.0554 s` -- nguồn --> `experiment_log_ML-02-KMeans-...json` -- field --> `execution_time`
- `cluster_sizes` -- nguồn --> `experiment_log_ML-02-KMeans-...json` -- field --> `cluster_result.extra.cluster_sizes`
- `WCSS = 179859.0234` -- nguồn --> `experiment_log_ML-02-KMeans-...json` -- field --> `cluster_result.extra.wcss`
- `n_iter = 11` -- nguồn --> `experiment_log_ML-02-KMeans-...json` -- field --> `cluster_result.extra.n_iter`

**Lưu ý về metric đánh giá:**

- ML-02 KHÔNG compute silhouette / DBI / CH / ARI / AMI. Đây là scope của
  EPIC-07/08. WCSS được ghi trong `cluster_result.extra` là **diagnostic
  only** (ghi nhận inertia của K-Means sau fit), KHÔNG dùng để kết luận.
- `MetricsResult` tất cả field = `None` trong ML-02 (`silhouette`,
  `davies_bouldin`, `calinski_harabasz`, `wcss`, `stability`, `runtime`,
  `extra`).
- KHÔNG có "best K" / "best init" / "best algorithm" claim trong tài liệu
  này.

---

## 8. Công thức và ký hiệu

### 8.1. Ký hiệu K-Means

| Symbol | Ý nghĩa |
|--------|----------|
| `n` | Số customers (= `4371`) |
| `p` | Số features (= `14`) |
| `X ∈ ℝ^(n×p)` | Feature matrix |
| `x_i ∈ ℝ^p` | Vector feature của customer `i` |
| `K` | Số cluster (= `4` working default) |
| `μ_k ∈ ℝ^p` | Centroid của cluster `k` |
| `c_i ∈ {0, ..., K-1}` | Cluster label của customer `i` |
| `C_k = {i : c_i = k}` | Tập các customer thuộc cluster `k` |
| `\|C_k\|` | Số customer trong cluster `k` |

### 8.2. Objective function (K-Means)

K-Means minimize within-cluster sum of squares (WCSS), còn gọi là inertia:

    J = Σ_i ‖x_i - μ_{c_i}‖²  =  Σ_{k=1..K} Σ_{x_i ∈ C_k} ‖x_i - μ_k‖²

Trong đó `‖·‖` là Euclidean distance:

    ‖x_i - μ_k‖² = Σ_{d=1..p} (x_i,d - μ_k,d)²

WCSS là không tăng qua mỗi iteration (assignment + update); K-Means converge
đến local minimum.

### 8.3. Centroid update

    μ_k = (1 / |C_k|) · Σ_{x_i ∈ C_k} x_i

### 8.4. Assignment step

    c_i = argmin_{k ∈ {1, ..., K}} ‖x_i - μ_k‖

### 8.5. Thuật toán tối ưu

K-Means dùng **Lloyd's algorithm**:

1. **Initialize** — chọn `K` centroids khởi đầu (k-means++ hoặc random).
2. **Assignment** — mỗi observation được assign về centroid gần nhất.
3. **Update** — recompute centroid là mean của observation hiện tại trong
   cluster.
4. **Repeat** 2–3 cho đến khi centroid không đổi hoặc `max_iter` đạt.

### 8.6. Initialization (k-means++)

Default sklearn từ 1.1: `init="k-means++"`. Seed initial centroids bằng
distance-proportional probability scheme:

1. Chọn centroid đầu tiên ngẫu nhiên.
2. Với mỗi observation `x_i`, tính `D(x_i)` = khoảng cách Euclidean bình
   phương đến centroid gần nhất đã chọn.
3. Chọn centroid tiếp theo với xác suất tỉ lệ thuận với `D(x_i)`.
4. Repeat cho đến khi có `K` centroids.

k-means++ có theoretical guarantee: expected inertia của k-means++ initialization
≤ `8 (ln K + 2)` lần optimal inertia (Arthur & Vassilvitskii, 2007).

### 8.7. Convergence criterion

Sklearn dùng relative tolerance trên inertia (default `tol=1e-4`):

    |J_new - J_old| / |J_old| < tol

Hoặc dừng khi `max_iter` đạt. ML-02 giữ default sklearn.

### 8.8. Tham khảo formal

- Lloyd, S. P. (1982). "Least squares quantization in PCM". IEEE Transactions
  on Information Theory.
- MacQueen, J. (1967). "Some methods for classification and analysis of
  multivariate observations". Proceedings of the Fifth Berkeley Symposium.
- Arthur, D., & Vassilvitskii, S. (2007). "k-means++: The advantages of
  careful seeding". Proceedings of the Eighteenth Annual ACM-SIAM Symposium
  on Discrete Algorithms.

---

## 9. Visualization boundary

### 9.1. EPIC-06 (ML-02 diagnostic — chưa có)

ML-02 chưa tạo diagnostic visualization nào trong EPIC-06. WCSS, n_iter,
converged flag, cluster_sizes đều được ghi trong `cluster_result.extra`
(JSON-friendly) chứ KHÔNG phải visualization.

Elbow / WCSS plot chưa được tạo trong EPIC-06; EPIC-06 cho phép ML-02 có
diagnostic viz (optional) nhưng chưa thực hiện.

### 9.2. EPIC-06 (per-task diagnostic viz — optional, future)

| Task | Visualization (optional, future) | Loại | Status |
|------|----------------------------------|------|--------|
| ML-02 K-Means | Elbow / WCSS diagnostic plot | Diagnostic | **CHƯA ĐƯỢC TẠO** trong EPIC-06 |

### 9.3. EPIC-08 (research comparison)

EPIC-08 sở hữu (xem ML-01 Mentor document §9.3):

- WCSS / Elbow plot (cho analysis, không phải diagnostic).
- Silhouette plot / comparison.
- Davies-Bouldin comparison.
- Calinski-Harabasz comparison.
- Algorithm comparison dashboard.

### 9.4. EPIC-09 (segment analysis)

EPIC-09 sở hữu (xem ML-01 Mentor document §9.4):

- Segment size (số customer / segment).
- RFM profile (radar / heatmap) theo segment.
- Feature distribution theo segment.

### 9.5. Quy tắc tổng quát

- KHÔNG tạo visualization trong `reports/ml02/` ngoài JSON summary +
  Markdown narrative. Narrative chỉ mô tả diagnostics (WCSS, n_iter, ...),
  KHÔNG tạo plot.
- KHÔNG gọi WCSS là "evaluation metric". WCSS chỉ là diagnostic.

---

## 10. Verification

### 10.1. Tests

| Test category | File | Số test | Trạng thái |
|---------------|------|---------|------------|
| Unit tests cho KMeansAdapter | `tests/test_ml02_kmeans.py` | 40 | **PASS** (verified trong session này) |

Test categories (từ test file):

- Adapter construction validation (`n_clusters` type/range, `init` choice,
  `n_init` positive, `max_iter` positive, `random_state` type).
- `fit(X)` happy path — K-Means convergence.
- `fit(X)` validation errors — ndim, n_samples, n_features, n_clusters >= n_samples.
- `cluster_labels` shape, dtype, value range.
- `cluster_result.extra` keys (`init_strategy`, `effective_n_init`, `n_iter`,
  `converged`, `wcss`, `cluster_sizes`).
- `supports_random_state() == True`.
- `get_params()` returns correct dict.
- `get_model()` returns fitted sklearn KMeans.
- Boundary discipline: no mutation of input matrix, FE-06 input not mutated.
- Adapter registered in `AlgorithmRegistry` as `"kmeans"`.

Verification command:

```bash
python3 -m pytest tests/test_ml02_kmeans.py -v
```

Verification result: **40 / 40 passed**.

### 10.2. Lint

```bash
ruff check src/customer_segmentation/clustering/
```

Result: **All checks passed!** (verified trong session này).

### 10.3. Format

```bash
black --check src/customer_segmentation/clustering/
```

Result: **15 files would be left unchanged**.

### 10.4. Reproducibility

- **Input SHA-256 unchanged**: FE-06 outputs không bị ML-02 mutate. Input
  SHA `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`.
- **Config SHA-256 recorded**: `9b5f3d55ae24cc4e359b337cd57f48d362f38f0831b0e94b810ff2a38741f941`
  (cho lần run diagnostic).
- **Output SHA-256**: cluster_labels + experiment_log SHA sẽ được EPIC-07
  compute và record trong `experiment_log.json` ở `artifact_paths`.
- **Library versions**: numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`,
  scikit-learn `1.9.1`, pyarrow `25.0.1` (ghi trong `experiment_log`).
- **Random seed behavior**: `random_state=42` → K-Means reproducible với
  cùng input + config + library version.

### 10.5. Input integrity

`validate_clustering_matrix` kiểm tra:

- Dataset exists, không None.
- Required features có (None trong YAML, nên check bị skip).
- No identifier in matrix → PASS (CustomerID sống trong metadata).
- All numeric → PASS.
- No NaN → PASS.
- No Inf → PASS.
- No constant feature → PASS.
- min_samples (= 2) → PASS (4371 >= 2).
- min_features (= 1) → PASS (14 >= 1).

`validate_customer_alignment` kiểm tra:

- metadata_present → PASS.
- metadata_row_alignment → PASS (4371 == 4371).
- customer_key_present → PASS (`CustomerID` column có).
- customer_key_unique → PASS (4371 unique).
- customer_key_no_nan → PASS.

### 10.6. Output integrity

- `cluster_labels` shape `(4371,)`, dtype `int64` ✅.
- `cluster_labels` values trong `{0, 1, 2, 3}` ✅.
- `IsNoise` column = `(ClusterLabel == -1)`, always `False` cho K-Means ✅.
- `extra.wcss` là `float`, không NaN ✅.
- `extra.n_iter` là `int`, ≥ 0 ✅.
- `extra.cluster_sizes` là `dict[str, int]`, sum = `n_samples` ✅.
- KHÔNG có `algorithm_output_*.parquet` (K-Means không có soft output).

### 10.7. Regression status

- Pre-existing tests còn pass: 40 / 40 ML-02 tests pass.
- Không có test nào bị skip không giải thích.
- Không có pre-existing failure chưa được giải thích.

---

## 11. Mentor Review

| ID | Nội dung cần review | Loại | Trạng thái |
|----|---------------------|------|------------|
| ML-02-MET-01 | Methodology: `working_n_clusters=4` được chọn làm default cho ML-02 initial diagnostic | Methodology | PENDING_REVIEW |
| ML-02-MET-02 | Methodology: `init='k-means++'` được chọn làm working default | Methodology | PENDING_REVIEW |
| ML-02-MET-03 | Methodology: `n_init=10` (theo sklearn recommendation) được chọn làm working default | Methodology | PENDING_REVIEW |
| ML-02-MET-04 | Methodology: `tol=1e-4` (sklearn default) được chấp nhận làm working default | Engineering | DOCUMENTED (sklearn default; không có methodology effect) |
| ML-02-MET-05 | Methodology: `random_state=42` (framework default) được dùng cho working default | Methodology | PENDING_REVIEW |
| ML-02-ENG-01 | Engineering: chỉ expose `n_clusters`, `init`, `n_init`, `max_iter`, `random_state`, `tol` trong KMeansAdapter — không expose thêm `algorithm`, `precompute_distances`, `copy_x`, v.v. | Engineering / Scope | DOCUMENTED (deliberately narrow per EPIC-07 ownership) |
| ML-02-ENG-02 | Engineering: WCSS / n_iter / cluster_sizes được ghi trong `cluster_result.extra` (diagnostic) chứ không ghi vào `MetricsResult.wcss` | Engineering | DOCUMENTED |
| ML-02-ENG-03 | Engineering: `k_range = [2, 10]` ghi trong YAML là informational; EPIC-07 sẽ sweep | Engineering / Scope | DOCUMENTED |

**Ghi chú:**

- ML-02-MET-01, -02, -03, -05 cần mentor review vì chúng ảnh hưởng đến cách
  initial diagnostic run được setup; EPIC-07 sweep sẽ reference các
  default này.
- ML-02-MET-04, -ENG-01, -02, -03 là engineering decisions; không ảnh hưởng
  experimental design và có thể promote final cùng EPIC sau.

---

## 12. Kết luận

### 12.1. Đã hoàn thành

ML-02 K-Means **TECHNICALLY_IMPLEMENTED** với evidence:

- **Code:** `src/customer_segmentation/clustering/kmeans.py`
  (`KMeansAdapter` + default constants + sklearn wrapper).
- **Configuration:** `configs/clustering.yaml` → `clustering.algorithms.kmeans.*`
  (working defaults).
- **Tests:** `tests/test_ml02_kmeans.py` — 40 / 40 tests passed.
- **Initial diagnostic run đã chạy thành công** trên FE-06 dataset:
  - Status: `SUCCESS`.
  - n_clusters: `4`.
  - WCSS (diagnostic): `179859.0233766095`.
  - n_iter: `11`.
  - converged: `True`.
  - cluster_sizes: `{0: 3021, 1: 555, 2: 571, 3: 224}`.
  - execution_time: `0.0554 s`.
- **Artifacts:**
  - `cluster_labels_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.parquet`
  - `experiment_log_ML-02-KMeans-k4-k_meansplusplus-ninit10-maxiter300-seedcfg.json`
- **Reports:**
  - `reports/ml02/ml02_run_summary.json`
  - `reports/ml02/ml02_initial_diagnostic.md`
- **Lint:** `ruff check` pass.
- **Format:** `black --check` pass.

### 12.2. Chưa hoàn thành

- **Evaluation metrics** (silhouette / DBI / CH): `MetricsResult` toàn
  field = `None`. EPIC-07/08 sẽ compute.
- **Sweep nhiều K**: chỉ có 1 initial diagnostic run với `n_clusters=4`;
  EPIC-07 sẽ sweep `k_range = [2, 10]`.
- **Sweep nhiều init / n_init / max_iter**: EPIC-07 sẽ sweep.
- **Stability analysis (ARI / AMI across seeds)**: EPIC-07 sẽ generate,
  EPIC-08 sẽ aggregate.
- **Elbow / WCSS diagnostic viz**: chưa được tạo; EPIC-06 diagnostic viz
  là optional và có thể được tạo sau nếu cần.
- **Algorithm comparison**: EPIC-08.
- **Segment profiling / naming**: EPIC-09.
- **Soft probability output**: K-Means không có; đây là đặc trưng của GMM
  (xem ML-05) và FCM (xem ML-06).

### 12.3. Pending Mentor Review

| ID | Quyết định | Trạng thái |
|----|------------|------------|
| ML-02-MET-01 | `working_n_clusters=4` cho ML-02 diagnostic | PENDING_REVIEW |
| ML-02-MET-02 | `init='k-means++'` cho working default | PENDING_REVIEW |
| ML-02-MET-03 | `n_init=10` cho working default | PENDING_REVIEW |
| ML-02-MET-05 | `random_state=42` (framework default) | PENDING_REVIEW |

### 12.4. Chuyển tiếp sang task tiếp theo

**Output của ML-02 = input cho EPIC-07:**

- `cluster_labels_*.parquet` → EPIC-07 sẽ read cho mỗi K value trong
  `k_range` sweep.
- `experiment_log_*.json` → EPIC-07 sẽ ghi đè vào `MetricsResult` các
  internal metrics (silhouette, DBI, CH) per-fit.
- `cluster_result.extra.wcss` → EPIC-07 có thể dùng cho elbow diagnostic.
- `cluster_result.extra.n_iter` / `cluster_result.extra.converged` → EPIC-07
  có thể dùng để check K-Means convergence per K.

**Contract giữa ML-02 và consumer:**

| Field | Contract |
|-------|----------|
| `algorithm_family` | `"hard"` |
| `cluster_labels` shape | `(4371,)` |
| `cluster_labels` dtype | `int64` |
| `cluster_labels` values | `[0, K-1]` |
| `IsNoise` column | always `False` (K-Means không có noise) |
| `supports_random_state` | `True` |
| `soft_probabilities` | `None` (K-Means không có) |
| `soft_membership` | `None` (K-Means không có) |

**TUYỆT ĐỐI KHÔNG** trong Mentor document này: KHÔNG viết "best K-Means",
KHÔNG gọi K-Means là "best algorithm", KHÔNG ranking với algorithm khác.
ML-02 là implementation + initial diagnostic, KHÔNG là evaluation.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-02 implementation
(code, tests, config, initial diagnostic run, experiment log, artifacts).
Mọi con số trong tài liệu này đều có provenance rõ ràng. WCSS được ghi
trong `cluster_result.extra` là **diagnostic only** — KHÔNG dùng để kết luận
"best K"._