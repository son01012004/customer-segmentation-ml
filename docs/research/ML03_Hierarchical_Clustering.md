# ML-03 — Agglomerative (Hierarchical) Clustering

> **Mentor Document cho EPIC-06 / ML-03.**
> Adapter version: `sklearn_1.9.1` (ghi trong `AgglomerativeAdapter.version`).
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
| **Task ID** | `ML-03` |
| **Tên task** | Hierarchical (Agglomerative) Clustering |
| **Mục tiêu** | Triển khai Agglomerative clustering như một concrete `BaseClusterAlgorithm` adapter, plug vào ML-01 framework. Adapter là thin wrapper quanh `sklearn.cluster.AgglomerativeClustering`; nó chỉ expose các hyperparameter đã được quy ước trong ML-03 task contract (`n_clusters`, `linkage`, `metric`, `compute_distances`). KHÔNG compute evaluation metrics, KHÔNG so sánh algorithm, KHÔNG chọn best linkage / best K, KHÔNG mutate input. KHÔNG render dendrogram trong EPIC-06. |
| **Vị trí trong research pipeline** | ML-03 nằm sau ML-01 (framework) và sau FE-06 (dataset), song song với ML-02 (K-Means — cùng là hard clustering family). Output của ML-03 (`cluster_labels_*.parquet`, `experiment_log_*.json`) là input cho EPIC-07 (controlled sweep), EPIC-08 (evaluation), EPIC-09 (segment analysis). |
| **Input** | `data/processed/final_clustering_dataset.parquet` (FE-06 output; SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`); `data/processed/customer_metadata.parquet` (FE-06 output; SHA-256 `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`); `configs/clustering.yaml` (Agglomerative section: `clustering.algorithms.agglomerative.*`). |
| **Output** | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-*.parquet` (CustomerID + ClusterLabel + IsNoise); `data/processed/clustering_experiments/experiment_log_ML-03-Agglo-*.json` (full `ExperimentResult.to_dict()`); `reports/ml03/ml03_run_summary.json`; `reports/ml03/ml03_initial_diagnostic.md`; `reports/ml03/ml03_linkage_comparison.csv` (per-linkage diagnostics). |
| **Quan hệ với task trước/sau** | Trước: ML-01 framework cung cấp `BaseClusterAlgorithm`, `AlgorithmRegistry`, `ClusterResult`, `ExperimentResult`, `ExperimentRunner`. Sau: EPIC-07 sẽ sweep `(n_clusters, linkage, metric)`; EPIC-08 sẽ compute silhouette/DBI/CH trên `cluster_labels_*.parquet`; EPIC-09 sẽ phân tích segment dựa trên cluster labels. |
| **Algorithm family** | `hard` (mỗi customer thuộc đúng 1 cluster; không có soft probability, không có noise label, không có membership matrix). |

---

## 2. Mục tiêu nghiên cứu

ML-03 trả lời một phần câu hỏi nghiên cứu về **tính khả thi kỹ thuật** của
việc chạy Agglomerative clustering trên FE-06 dataset với framework thống nhất:

- "Có thể chạy Agglomerative clustering trên Final Clustering Dataset (4371
  customers, 14 features) với cùng schema output của ML-01 framework không?"
- "Các linkage criterion (`ward`, `complete`, `average`, `single`) có hội tụ
  đến cùng số cluster với cùng `n_clusters=4` không? Merge distance summary
  cho biết gì về hierarchical structure?"
- "Agglomerative clustering trong `n_clusters` mode có deterministic không?
  Reproducibility có được framework capture đúng không?"

**Phạm vi nghiên cứu:**

- ML-03 là technical implementation, KHÔNG phải evaluation.
- ML-03 KHÔNG sweep K; `working_n_clusters=4` là **WORKING_ASSUMPTION**.
- ML-03 KHÔNG chọn `best linkage`; `working_linkage='ward'` là working
  default; 4 per-linkage diagnostic runs (`ward`, `complete`, `average`,
  `single`) chỉ để verify adapter hỗ trợ đầy đủ và thu diagnostics.
- ML-03 KHÔNG render dendrogram trong EPIC-06; per-merge linkage distances
  được captured trong `ClusterResult.extra` (`max_merge_distance`,
  `min_merge_distance`, `median_merge_distance`, `merge_distances_summary`)
  nhưng KHÔNG phải dendrogram visualization.

**Mối liên hệ với đặc thù dữ liệu FE-06:**

- Agglomerative clustering dùng pairwise distance giữa các customer; FE-06
  đã scale features (RobustScaler trong C7) nên khoảng cách Euclidean giữa
  các customer là meaningful.
- `n_samples=4371` là đủ nhỏ để Agglomerative clustering chạy với O(n² log n)
  hoặc O(n³) trong thời gian hợp lý (~0.7s per fit tại runtime hiện tại).
- CustomerID alignment giống ML-02: CustomerID sống trong metadata, KHÔNG
  trong matrix.

**Mối liên hệ với EPIC-07/08/09:**

- EPIC-07 sẽ sweep `(n_clusters, linkage, metric)` và gọi
  `ExperimentRunner` với `algorithm="agglomerative"` cho mỗi fit.
- EPIC-08 sẽ compute silhouette / DBI / CH trên `cluster_labels_*.parquet`
  của ML-03; linkage diagnostic trong `cluster_result.extra` chỉ là
  algorithm-specific, KHÔNG thay thế EPIC-08 evaluation.
- EPIC-09 sẽ phân tích segment dựa trên `cluster_labels_*.parquet`.

---

## 3. Cơ sở lý thuyết

### 3.1. Hierarchical clustering

Hierarchical clustering xây cây phân cấp (dendrogram) của clusters. Có hai
hướng:

- **Agglomerative (bottom-up)**: bắt đầu mỗi observation là 1 singleton
  cluster; merge 2 cluster gần nhất ở mỗi bước cho đến khi còn 1 cluster.
- **Divisive (top-down)**: bắt đầu tất cả observation trong 1 cluster;
  split đệ quy.

ML-03 implement agglomerative / bottom-up direction (matching EPIC06 contract
§3.3).

### 3.2. Agglomerative process

Per iteration:

1. **Initialize**: mỗi observation là 1 cluster (`n` singleton clusters).
2. **Compute pairwise distances** giữa tất cả các observation (sklearn caches;
   cost depends on `metric`).
3. **Select**: pair of clusters với inter-cluster distance nhỏ nhất dưới
   linkage criterion đã chọn.
4. **Merge**: 2 clusters thành 1 cluster mới.
5. **Update**: distance matrix / heap.
6. **Repeat** steps 3–5 cho đến khi còn `n_clusters` clusters (mode
   `n_clusters` của ML-03).

Output cluster assignment ở `n_clusters` là `cluster_labels`. Merge tree
(`children_`) và optional per-merge distance (`distances_`) là
algorithm-specific diagnostics được ghi vào `ClusterResult.extra`.

### 3.3. Linkage criteria

Cho 2 clusters `A`, `B` và point-wise distance `d(x, y)`:

- **Single linkage** (nearest neighbour): `D(A, B) = min_{a∈A, b∈B} d(a, b)`.
  Tends to produce long, "chained" clusters; sensitive to noise.
- **Complete linkage** (farthest neighbour): `D(A, B) = max_{a∈A, b∈B} d(a, b)`.
  Avoids chaining; tends to produce compact, equal-diameter clusters;
  sensitive to outliers.
- **Average linkage** (UPGMA):
  `D(A, B) = (1 / (|A| · |B|)) Σ_{a∈A, b∈B} d(a, b)`.
  Compromise giữa single và complete.
- **Ward linkage**:
  `D(A, B) = Δ(ESS) = ESS(A ∪ B) - ESS(A) - ESS(B)`,
  với `ESS(C) = Σ_{x∈C} ‖x - μ_C‖²` và `μ_C` là centroid của `C`.
  Ward minimize tăng của total within-cluster variance tại mỗi merge.
  **Trong scikit-learn, Ward linkage chỉ tương thích với Euclidean metric**
  (hoặc L2-equivalent); adapter validate constraint này.

Không có linkage nào được claim "best"; việc chọn linkage thuộc EPIC-07.

### 3.4. Distance / metric

Adapter phân biệt hai khái niệm liên quan nhưng khác nhau:

- **Point-wise distance** `d(x, y)`: định nghĩa bởi `metric` parameter.
  Euclidean là default và là metric duy nhất tương thích với Ward linkage.
- **Inter-cluster distance** `D(A, B)`: derived từ `d(x, y)` bởi linkage
  criterion (xem §3.3).

### 3.5. Dendrogram concept

Dendrogram là canonical visualization của merge tree. Cutting dendrogram ở
một height → `K` clusters. ML-03 KHÔNG render dendrogram trong EPIC-06;
chỉ record numerical ingredients cho downstream dendrogram diagnostic:

- `linkage` (str), `metric` (str): what was used.
- `n_merges` (int): `n_samples - 1` (= `4370` cho FE-06).
- `n_leaves` (int): `n_samples` (= `4371`).
- `max_merge_distance` (float): largest linkage distance observed.
- `merge_distances_summary` (list of float): first/last 5 entries + "...".

### 3.6. Computational complexity

`O(n³)` hoặc `O(n² log n)` tùy implementation. Với `n=4371`, ML-03 runtime
~0.16s–0.77s per fit (linkage-dependent; single linkage nhanh nhất ~0.16s,
complete/average chậm hơn ~0.69s–0.77s). Không scale với dataset cực lớn
nhưng OK cho FE-06 scope.

### 3.7. Determinism

`sklearn.cluster.AgglomerativeClustering` trong `n_clusters` mode là
**deterministic** — không có internal RNG. ML-03 advertise
`supports_random_state() == False` và runner KHÔNG inject seed.

---

## 4. Phương pháp / Methodology

### 4.1. Dữ liệu sử dụng

| File | Vai trò | SHA-256 | Shape |
|------|---------|---------|-------|
| `data/processed/final_clustering_dataset.parquet` | Numeric feature matrix | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `(4371, 14)` |
| `data/processed/customer_metadata.parquet` | CustomerID mapping | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `(4371, 1)` |

Dataset version: `FE06-v1.0`.

**Feature set (14 features):** giống ML-02 (`Recency`, `Frequency`, `Monetary`,
`TotalQuantity`, `AverageQuantity`, `BasketSize`, `TenureDays`,
`PurchaseIntervalMean`, `PurchaseIntervalStd`, `ActiveDays`,
`AverageInvoiceValue`, `ProductsPerInvoice`, `CancellationRate`,
`ReturnRate`).

### 4.2. Preprocessing

ML-03 KHÔNG thực hiện preprocessing. Verify input đã qua FE-06 pipeline
(giong ML-02). FE-06 evidence: `reports/fe06/fe06_run.json` → `validations`
tất cả PASS.

### 4.3. Algorithm / configuration

| Hyperparameter | Working default | Nguồn |
|----------------|-----------------|--------|
| `n_clusters` | `4` | `configs/clustering.yaml` → `clustering.algorithms.agglomerative.working_n_clusters` |
| `linkage` | `"ward"` | `configs/clustering.yaml` → `clustering.algorithms.agglomerative.working_linkage` |
| `metric` | `"euclidean"` | `configs/clustering.yaml` → `clustering.algorithms.agglomerative.working_metric` |
| `compute_distances` | `True` | `configs/clustering.yaml` → `clustering.algorithms.agglomerative.compute_distances` |
| `random_state` | KHÔNG dùng (deterministic) | Agglomerative n_clusters mode không consume seed |

**Linkage options supported by adapter** (`SUPPORTED_LINKAGES`):
`ward`, `complete`, `average`, `single`.

**Metric options supported by adapter** (`SUPPORTED_METRICS`):
`euclidean`, `manhattan`, `cityblock`, `cosine`, `chebyshev`, `l1`, `l2`.

**Constraint:** Ward linkage chỉ tương thích với Euclidean metric (sklearn
hard constraint); adapter validate và raise `ClusterAlgorithmError` nếu
vi phạm.

**Library version:** `sklearn 1.9.1` (ghi trong
`cluster_result.algorithm_version`).

### 4.4. Cách chạy

Script entry point: `scripts/run_ml03_agglomerative.py`.

Lệnh này chạy:

1. **Primary run**: `n_clusters=4`, `linkage='ward'`, `metric='euclidean'`,
   `compute_distances=True`.
2. **4 per-linkage diagnostic runs**: cùng `n_clusters=4` nhưng thay `linkage`
   thành `ward`, `complete`, `average`, `single`. Đây KHÔNG phải controlled
   sweep — chỉ để verify adapter hỗ trợ đầy đủ và thu diagnostics.

Mỗi run ghi artifact riêng với `experiment_id` khác nhau (theo
`{linkage}` tag).

### 4.5. Cách lưu kết quả

Artifact paths theo `framework.output` config:

- `cluster_labels_ML-03-Agglo-{variant}-*.parquet` — CustomerID + ClusterLabel
  + IsNoise.
- `experiment_log_ML-03-Agglo-{variant}-*.json` — full `ExperimentResult.to_dict()`.
- KHÔNG có `algorithm_output_*.parquet` (Agglomerative không có soft
  probability / membership).

`{variant}` ∈ {`k4-ward-euclidean-cd1` (primary), `diag-k4-{ward,complete,average,single}-euclidean-cd1`}.

### 4.6. Cách đảm bảo reproducibility

- Agglomerative n_clusters mode là deterministic → không cần seed.
- Framework runner KHÔNG inject seed vì `adapter.supports_random_state()
  == False`. Experiment log ghi `random_seed = 42` (requested) nhưng
  `random_seed_used = None`.
- `experiment_log` ghi input SHA-256, config SHA-256, library versions.

### 4.7. Bảng phân loại decision (BẮT BUỘC)

| Loại decision | Nội dung | Status | Bằng chứng / Nguồn |
|---------------|----------|--------|---------------------|
| TECHNICALLY_IMPLEMENTED | `AgglomerativeAdapter` class | Implemented | `src/customer_segmentation/clustering/agglomerative.py` |
| TECHNICALLY_IMPLEMENTED | Adapter registered in `AlgorithmRegistry` as `"agglomerative"` | Implemented | `agglomerative.py` → `@AlgorithmRegistry.register("agglomerative")` |
| TECHNICALLY_IMPLEMENTED | `supports_random_state() == False` (Agglomerative n_clusters mode is deterministic) | Implemented | `agglomerative.py` → `AgglomerativeAdapter.supports_random_state` |
| TECHNICALLY_IMPLEMENTED | Hard cluster labels output, dtype `int64`, shape `(n_samples,)` | Implemented | `agglomerative.py` → `AgglomerativeAdapter.fit` |
| TECHNICALLY_IMPLEMENTED | Per-merge linkage distances captured in `ClusterResult.extra` (`max_merge_distance`, `min_merge_distance`, `median_merge_distance`, `merge_distances_summary`) | Implemented | `agglomerative.py` |
| TECHNICALLY_IMPLEMENTED | Ward + non-Euclidean constraint validation | Implemented | `agglomerative.py` → `__init__` validation |
| TECHNICALLY_IMPLEMENTED | 4-linkage diagnostic runs (ward / complete / average / single) | Implemented | `reports/ml03/ml03_linkage_comparison.csv`; `reports/ml03/ml03_initial_diagnostic.md` |
| TECHNICALLY_IMPLEMENTED | Primary run với `n_clusters=4, linkage='ward', metric='euclidean'` | Implemented | `experiment_log_ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg.json` |
| TECHNICALLY_IMPLEMENTED | Validation matrix theo FE-06 contract | Implemented | `tests/test_ml03_agglomerative.py` (59 tests pass) |
| WORKING_ASSUMPTION | `n_clusters = 4` | Working assumption | `configs/clustering.yaml` → `algorithms.agglomerative.working_n_clusters` |
| WORKING_ASSUMPTION | `linkage = 'ward'` | Working assumption | `configs/clustering.yaml` → `algorithms.agglomerative.working_linkage` |
| WORKING_ASSUMPTION | `metric = 'euclidean'` | Working assumption | `configs/clustering.yaml` → `algorithms.agglomerative.working_metric` |
| WORKING_ASSUMPTION | `compute_distances = True` | Working assumption | `configs/clustering.yaml` → `algorithms.agglomerative.compute_distances` |
| PENDING_REVIEW | Methodology: chọn `working_n_clusters=4` làm default cho ML-03 diagnostic | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: chọn `working_linkage='ward'` cho working default | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| PENDING_REVIEW | Methodology: chọn `working_metric='euclidean'` cho working default | MENTOR_REVIEW_PENDING | `configs/clustering.yaml` (xem Section 11) |
| OUT_OF_SCOPE | Compute evaluation metrics (silhouette, DBI, CH) | Explicit | EPIC-07/08 ownership |
| OUT_OF_SCOPE | Pick best K / best linkage / best metric | Explicit | EPIC-07 ownership |
| OUT_OF_SCOPE | Pick best algorithm | Explicit | EPIC-08 ownership |
| OUT_OF_SCOPE | Render dendrogram visualization | Explicit | EPIC-06 diagnostic viz optional (chưa tạo trong EPIC-06) |
| OUT_OF_SCOPE | Customer segment profiling / naming | Explicit | EPIC-09 ownership |
| OUT_OF_SCOPE | Mutate FE-06 output | Explicit | AGENTS.md §2.3 |

---

## 5. Implementation

### 5.1. Module / file chính

- Adapter: `src/customer_segmentation/clustering/agglomerative.py` →
  `AgglomerativeAdapter`.
- Default constants: `DEFAULT_LINKAGE`, `DEFAULT_METRIC`, `MIN_N_CLUSTERS`,
  `SUPPORTED_LINKAGES`, `SUPPORTED_METRICS`.
- Public re-export: `src/customer_segmentation/clustering/__init__.py`.
- Tests: `tests/test_ml03_agglomerative.py` (59 tests).
- Script: `scripts/run_ml03_agglomerative.py`.
- Reports: `reports/ml03/ml03_initial_diagnostic.md`,
  `reports/ml03/ml03_run_summary.json`,
  `reports/ml03/ml03_linkage_comparison.csv`.
- Artifacts: 5 files `cluster_labels_ML-03-Agglo-*.parquet` + 5 files
  `experiment_log_ML-03-Agglo-*.json`.

### 5.2. Class hierarchy

```
BaseClusterAlgorithm (ML-01)
    └── AgglomerativeAdapter (ML-03)
            ├── name = "agglomerative"
            ├── version = "sklearn_<sklearn.__version__>" (= "sklearn_1.9.1")
            ├── family = AlgorithmFamily.HARD
            ├── __init__(n_clusters, *, linkage, metric, compute_distances)
            ├── fit(X) -> ClusterResult
            ├── get_params() -> dict
            ├── get_model() -> sklearn.cluster.AgglomerativeClustering | None
            └── supports_random_state() -> bool (returns False)
```

### 5.3. Pipeline

```
scripts/run_ml03_agglomerative.py
  │
  ├── load configs/clustering.yaml (FrameworkConfig)
  ├── load data/processed/final_clustering_dataset.parquet (X)
  ├── load data/processed/customer_metadata.parquet (metadata)
  ├── compute SHA-256(input), SHA-256(metadata), SHA-256(config)
  │
  ├── for each (n_clusters, linkage, metric) variant:
  │     spec = ExperimentSpec(
  │         experiment_id = "ML-03-Agglo-{variant}-seedcfg",
  │         algorithm = "agglomerative",
  │         hyperparameters = {"n_clusters": K, "linkage": L, "metric": M,
  │                             "compute_distances": True},
  │     )
  │     runner = ExperimentRunner(cfg, spec, config_source, config_text)
  │     runner.run(X, metadata, input_sha256, ..., output_dir)
  │
  └── write ml03_linkage_comparison.csv, ml03_run_summary.json,
      ml03_initial_diagnostic.md
```

### 5.4. Configuration

| Config key | Value | Nguồn |
|------------|-------|--------|
| `clustering.algorithms.agglomerative.enabled` | `true` | `configs/clustering.yaml` |
| `clustering.algorithms.agglomerative.k_range` | `[2, 10]` | `configs/clustering.yaml` |
| `clustering.algorithms.agglomerative.working_n_clusters` | `4` | `configs/clustering.yaml` |
| `clustering.algorithms.agglomerative.working_linkage` | `"ward"` | `configs/clustering.yaml` |
| `clustering.algorithms.agglomerative.working_metric` | `"euclidean"` | `configs/clustering.yaml` |
| `clustering.algorithms.agglomerative.compute_distances` | `true` | `configs/clustering.yaml` |

### 5.5. Input/output contract

**Input (`fit` parameter):** `X: numpy.ndarray` — shape `(4371, 14)`, dtype
`float64`, không chứa identifier.

**Output (`ClusterResult` fields):**

| Field | Value (ML-03 primary run) | Nguồn |
|-------|---------------------------|--------|
| `algorithm` | `"agglomerative"` | `agglomerative.py` |
| `algorithm_version` | `"sklearn_1.9.1"` | `agglomerative.py` |
| `algorithm_family` | `"hard"` | `agglomerative.py` |
| `n_samples` | `4371` | `X.shape[0]` |
| `n_features` | `14` | `X.shape[1]` |
| `cluster_labels` | `np.ndarray`, shape `(4371,)`, dtype `int64` | `model.fit_predict(X).astype(int64)` |
| `n_clusters` | `4` | `labels.max() + 1` |
| `soft_probabilities` | `None` | default |
| `soft_membership` | `None` | default |
| `noise_label` | `-1` | default; Agglomerative n_clusters mode không dùng |
| `noise_count` | `0` | hardcoded |
| `noise_ratio` | `0.0` | hardcoded |
| `supports_random_state` | `False` | `AgglomerativeAdapter.supports_random_state()` |
| `random_seed_used` | `None` | runner không inject seed |
| `extra.linkage` | `"ward"` | `agglomerative.py` |
| `extra.metric` | `"euclidean"` | `agglomerative.py` |
| `extra.compute_distances_used` | `True` | `agglomerative.py` |
| `extra.n_leaves` | `4371` | `model.n_leaves_` |
| `extra.n_merges` | `4370` | `n_samples - 1` |
| `extra.max_merge_distance` | `805.9027713163268` | từ `model.distances_` |
| `extra.min_merge_distance` | `0.0057495411035834105` | từ `model.distances_` |
| `extra.median_merge_distance` | `1.1520568931489268` | từ `model.distances_` |
| `extra.merge_distances_summary` | `[0.0057, 0.0095, 0.0418, 0.0424, 0.0460, "...", 217.52, 241.18, 308.95, 656.98, 805.90]` | first/last 5 merge distances |
| `extra.cluster_sizes` | `{"0": 511, "1": 155, "2": 3040, "3": 665}` | `agglomerative.py` |
| `metrics.*` | tất cả `None` | EPIC-07/08 populate |

### 5.6. Validation (Agglomerative-specific)

Adapter validate input trong `fit`:

- `X` không None, là `np.ndarray`, `ndim == 2`.
- `n_samples >= 2`.
- `n_clusters < n_samples`.
- `n_features >= 1`.

Adapter validate hyperparameter trong `__init__`:

- `n_clusters >= MIN_N_CLUSTERS (= 2)`.
- `linkage ∈ {ward, complete, average, single}`.
- `metric ∈ {euclidean, manhattan, cityblock, cosine, chebyshev, l1, l2}`.
- **Ward + non-Euclidean**: reject up-front (sklearn hard constraint).
- `compute_distances` is bool.

Nếu validate fail → raise `ClusterAlgorithmError`.

### 5.7. Artifacts (ML-03 actual)

5 cluster labels + 5 experiment log files (1 primary + 4 per-linkage diagnostic):

| Artifact | Path | Schema |
|----------|------|--------|
| Primary cluster labels | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg.parquet` | `CustomerID` + `ClusterLabel` + `IsNoise` |
| Primary experiment log | `data/processed/clustering_experiments/experiment_log_ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg.json` | `ExperimentResult.to_dict()` |
| Diagnostic ward labels | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-diag-k4-ward-euclidean-cd1-seedcfg.parquet` | same |
| Diagnostic complete labels | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-diag-k4-complete-euclidean-cd1-seedcfg.parquet` | same |
| Diagnostic average labels | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-diag-k4-average-euclidean-cd1-seedcfg.parquet` | same |
| Diagnostic single labels | `data/processed/clustering_experiments/cluster_labels_ML-03-Agglo-diag-k4-single-euclidean-cd1-seedcfg.parquet` | same |
| Run summary | `reports/ml03/ml03_run_summary.json` | stage + experiments + diagnostics |
| Initial diagnostic | `reports/ml03/ml03_initial_diagnostic.md` | Vietnamese narrative |
| Linkage comparison | `reports/ml03/ml03_linkage_comparison.csv` | per-linkage table |

### 5.8. JSON snippet (từ `experiment_log_ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg.json`)

```jsonc
{
  "experiment_id": "ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg",
  "status": "SUCCESS",
  "algorithm": "agglomerative",
  "algorithm_version": "sklearn_1.9.1",
  "dataset_version": "FE06-v1.0",
  "dataset_sha256": "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c",
  "feature_count": 14, "n_samples": 4371,
  "hyperparameters": {"n_clusters": 4, "linkage": "ward", "metric": "euclidean", "compute_distances": true},
  "random_seed": 42, "random_seed_used": null,
  "n_clusters": 4,
  "cluster_labels_shape": [4371], "cluster_labels_dtype": "int64",
  "execution_time": 0.6809902200002398,
  "timestamp": "2026-09-21T04:30:26.184553+00:00",
  "cluster_result": {
    "algorithm": "agglomerative", "algorithm_version": "sklearn_1.9.1", "algorithm_family": "hard",
    "n_samples": 4371, "n_features": 14, "n_clusters": 4,
    "cluster_labels_shape": [4371], "cluster_labels_dtype": "int64",
    "cluster_labels_first_5": [1, 1, 1, 1, 1],
    "noise_label": -1, "noise_count": 0, "noise_ratio": 0.0,
    "supports_random_state": false, "random_seed_used": null,
    "extra": {
      "linkage": "ward", "metric": "euclidean", "compute_distances_used": true,
      "n_leaves": 4371, "n_merges": 4370,
      "max_merge_distance": 805.9027713163268,
      "min_merge_distance": 0.0057495411035834105,
      "median_merge_distance": 1.1520568931489268,
      "merge_distances_summary": [
        0.0057, 0.0095, 0.0418, 0.0424, 0.0460,
        "...", 217.52, 241.18, 308.95, 656.98, 805.90
      ],
      "cluster_sizes": {"0": 511, "1": 155, "2": 3040, "3": 665}
    },
    "metrics": { /* all None */ }
  },
  "platform": {"python": "3.14.4", "system": "Linux", "release": "7.0.0-31-generic", "machine": "x86_64"},
  "library_versions": {"numpy": "2.3.5", "pandas": "3.0.6", "scipy": "1.18.1", "scikit-learn": "1.9.1", "pyarrow": "25.0.1"},
  "config_source": "yaml:/.../configs/clustering.yaml",
  "config_sha256": "7acbcddce99cac817324f6832dbc9d9d514a25cf9ed8c2134b594c73a0078660"
}
```

---

## 6. Experimental Design Boundary

| | EPIC-06 (ML-03 Agglomerative) | EPIC-07 | EPIC-08 | EPIC-09 |
|---|------------------------------|---------|---------|---------|
| **Algorithm implementation** | ✅ AgglomerativeAdapter | — | — | — |
| **Configuration** | ✅ Working default (n_clusters=4, linkage='ward', metric='euclidean') | Sweep matrix | — | — |
| **Single-fit experiment** | ✅ Initial diagnostic (1 algo × 1 K × 1 linkage × 1 metric) | Batch | — | — |
| **Sweep nhiều K** | ❌ | ✅ (sẽ dùng `agglomerative.k_range = [2, 10]`) | — | — |
| **Sweep nhiều linkage** | ❌ (chỉ 4 per-linkage diagnostic, không phải sweep) | ✅ | — | — |
| **Sweep nhiều metric** | ❌ | ✅ | — | — |
| **Sweep nhiều seed** | ❌ (deterministic) | N/A (deterministic) | — | — |
| **Compute internal metrics** | ❌ | Partial (per fit) | ✅ Final | — |
| **Stability (ARI/AMI)** | ❌ (deterministic) | N/A | N/A (deterministic) | — |
| **Runtime comparison** | ❌ | Per-run time | ✅ Statistical summary | — |
| **Algorithm comparison** | ❌ | — | ✅ | — |
| **Diagnostic viz (dendrogram, distance heatmap)** | ⚠️ Optional per-task (chưa có trong EPIC-06) | — | — | — |
| **Research viz (silhouette, DBI, CH)** | ❌ | — | ✅ | — |
| **Segment profile / naming** | ❌ | — | — | ✅ |
| **Pick best algorithm / best K / best linkage** | ❌ | — | ✅ (sau full eval) | — |
| **Customer profiling** | ❌ | — | — | ✅ |

---

## 7. Kết quả thực tế

ML-03 đã chạy 5 SUCCESS runs: 1 primary (`ward`) + 4 per-linkage diagnostic
(`ward`, `complete`, `average`, `single`). Evidence:

### 7.1. Primary run

| Loại kết quả | Giá trị | Nguồn |
|--------------|---------|--------|
| Status | `SUCCESS` | `experiment_log_ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg.json` |
| Experiment ID | `ML-03-Agglo-k4-ward-euclidean-cd1-seedcfg` | `experiment_log_*.json` → `experiment_id` |
| Algorithm family | `hard` | `cluster_result.algorithm_family` |
| n_clusters | `4` | `experiment_log_*.json` → `n_clusters` |
| Linkage | `ward` | `experiment_log_*.json` → `cluster_result.extra.linkage` |
| Metric | `euclidean` | `experiment_log_*.json` → `cluster_result.extra.metric` |
| n_merges | `4370` | `cluster_result.extra.n_merges` |
| n_leaves | `4371` | `cluster_result.extra.n_leaves` |
| max_merge_distance | `805.9027713163268` | `cluster_result.extra.max_merge_distance` |
| min_merge_distance | `0.0057495411035834105` | `cluster_result.extra.min_merge_distance` |
| median_merge_distance | `1.1520568931489268` | `cluster_result.extra.median_merge_distance` |
| cluster_sizes | `{0: 511, 1: 155, 2: 3040, 3: 665}` | `cluster_result.extra.cluster_sizes` |
| execution_time | `0.6809902200002398` (s) | `experiment_log_*.json` → `execution_time` |
| supports_random_state | `False` | `cluster_result.supports_random_state` |
| random_seed | `42` (requested, NOT consumed) | `experiment_log_*.json` → `random_seed` |
| random_seed_used | `None` | `cluster_result.random_seed_used` |
| config_sha256 | `7acbcddce99cac817324f6832dbc9d9d514a25cf9ed8c2134b594c73a0078660` | `experiment_log_*.json` |
| Library versions | numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`, scikit-learn `1.9.1`, pyarrow `25.0.1` | `experiment_log_*.json` |

### 7.2. Per-linkage diagnostic runs

| Linkage | Status | n_clusters | max_merge_distance | Execution time (s) | Cluster sizes |
|---------|--------|-----------:|-------------------:|-------------------:|---------------|
| `ward` | SUCCESS | 4 | 805.9028 | 0.6924 | `0:511; 1:155; 2:3040; 3:665` |
| `complete` | SUCCESS | 4 | 167.9850 | 0.6922 | `0:3894; 1:463; 2:13; 3:1` |
| `average` | SUCCESS | 4 | 88.2105 | 0.7702 | `0:4365; 1:1; 2:4; 3:1` |
| `single` | SUCCESS | 4 | 59.5179 | 0.1565 | `0:4367; 1:2; 2:1; 3:1` |

Nguồn: `reports/ml03/ml03_linkage_comparison.csv`.

**Quan sát:** Cùng `n_clusters=4` nhưng các linkage cho cluster_sizes rất
khác nhau; ward produce một large cluster (3040 customers), average/single
produce near-degenerate (gần như one big cluster với một vài singletons).
Đây là behavior đặc trưng của mỗi linkage; ML-03 KHÔNG dùng observation
này để kết luận "best linkage" — đó là EPIC-07 scope.

### 7.3. Tests

| File | Số test | Trạng thái |
|------|---------|------------|
| `tests/test_ml03_agglomerative.py` | 59 | **PASS** (verified trong session này) |

**Lưu ý về metric đánh giá:**

- ML-03 KHÔNG compute silhouette / DBI / CH / ARI / AMI.
- `MetricsResult` tất cả field = `None`.
- Per-linkage diagnostics KHÔNG dùng để kết luận "best linkage".
- Dendrogram visualization CHƯA ĐƯỢC TẠO trong EPIC-06 (xem Section 9).

---

## 8. Công thức và ký hiệu

### 8.1. Ký hiệu Agglomerative

| Symbol | Ý nghĩa |
|--------|----------|
| `n` | Số customers (= `4371`) |
| `p` | Số features (= `14`) |
| `X ∈ ℝ^(n×p)` | Feature matrix |
| `x_i ∈ ℝ^p` | Vector feature của customer `i` |
| `K` | Số cluster (= `4` working default) |
| `c_i ∈ {0, ..., K-1}` | Cluster label của customer `i` (sau khi cắt merge tree) |
| `A, B` | Cluster intermediate (singleton hoặc merged) |
| `D(A, B)` | Inter-cluster distance |
| `d(x, y)` | Point-wise distance (định nghĩa bởi `metric`) |
| `μ_C` | Centroid của cluster `C` (cho Ward linkage) |
| `ESS(C) = Σ_{x∈C} ‖x - μ_C‖²` | Error sum of squares của cluster `C` |

### 8.2. Linkage formulas

**Single linkage** (nearest neighbour):

    D_single(A, B) = min_{a ∈ A, b ∈ B} d(a, b)

**Complete linkage** (farthest neighbour):

    D_complete(A, B) = max_{a ∈ A, b ∈ B} d(a, b)

**Average linkage** (UPGMA):

    D_average(A, B) = (1 / (|A| · |B|)) · Σ_{a ∈ A, b ∈ B} d(a, b)

**Ward linkage**:

    D_ward(A, B) = ESS(A ∪ B) - ESS(A) - ESS(B)
                  = Σ_{x ∈ A ∪ B} ‖x - μ_{A∪B}‖² - Σ_{x ∈ A} ‖x - μ_A‖² - Σ_{x ∈ B} ‖x - μ_B‖²

### 8.3. Point-wise distance

Sklearn metric `euclidean`:

    d(x, y) = ‖x - y‖_2 = sqrt(Σ_d (x_d - y_d)²)

Trong ML-03, Ward linkage chỉ tương thích với metric L2-equivalent (i.e.
`euclidean`).

### 8.4. Objective

Agglomerative clustering KHÔNG optimize một objective global như K-Means.
Mỗi linkage criterion định nghĩa cách merge; merge process là deterministic
greedy.

Ward linkage có một objective gián tiếp: tại mỗi step, merge 2 cluster làm
tăng total WCSS ít nhất. Đây là một heuristic cho "compact, similar-volume"
clusters.

### 8.5. Thuật toán

Bottom-up agglomerative:

1. Initialize: `n` singleton clusters (mỗi `x_i` là 1 cluster).
2. Compute pairwise distance matrix / heap.
3. While số cluster > `n_clusters`:
   a. Find pair (A, B) minimize `D(A, B)` theo linkage.
   b. Merge A và B thành cluster mới.
   c. Update distance matrix / heap.
4. Output: cluster labels (argmax of membership matrix sau cut).

Complexity: `O(n³)` naive, `O(n² log n)` với heap-based implementation.

### 8.6. Công thức merge distance (Ward)

Per-merge distance được ghi vào `model.distances_` (sklearn). Với Ward:

    merge_distance_k = sqrt(Δ_ESS_k) = sqrt(ESS(A_k ∪ B_k) - ESS(A_k) - ESS(B_k))

(vì Ward sử dụng ESS increase như objective; sklearn trả sqrt.)

Với single / complete / average: `merge_distance_k` = trực tiếp linkage
distance tại step k.

---

## 9. Visualization boundary

### 9.1. EPIC-06 (ML-03 diagnostic — chưa có)

ML-03 chưa tạo diagnostic visualization nào trong EPIC-06. Per-merge linkage
distances được captured trong `ClusterResult.extra` dưới dạng numerical
data (`max_merge_distance`, `min_merge_distance`, `median_merge_distance`,
`merge_distances_summary`), KHÔNG phải dendrogram visualization.

**Dendrogram chưa được tạo** trong EPIC-06. Đây là diagnostic visualization
optional của EPIC-06 theo contract §3.3 + §9; ML-03 hiện tại KHÔNG thực
hiện.

### 9.2. EPIC-06 (per-task diagnostic viz — optional, future)

| Task | Visualization (optional, future) | Loại | Status |
|------|----------------------------------|------|--------|
| ML-03 Agglomerative | Dendrogram, linkage matrix visualization, distance heatmap | Diagnostic | **CHƯA ĐƯỢC TẠO** trong EPIC-06 |

### 9.3. EPIC-08 (research comparison)

EPIC-08 sở hữu (xem ML-01 Mentor document §9.3): silhouette plot, DBI
comparison, CH comparison, etc. KHÔNG bao gồm dendrogram (đó là diagnostic
viz của EPIC-06).

### 9.4. EPIC-09 (segment analysis)

EPIC-09 sở hữu (xem ML-01 Mentor document §9.4): segment size, RFM profile
per segment, etc.

### 9.5. Quy tắc tổng quát

- KHÔNG tạo visualization trong `reports/ml03/` ngoài JSON summary +
  Markdown narrative + CSV linkage comparison table.
- KHÔNG render dendrogram trong EPIC-06; đó là diagnostic viz optional và
  có thể được tạo sau nếu cần.
- KHÔNG gọi cluster_sizes per-linkage là "evidence for best linkage"; đó
  là sweep result, không phải evaluation.

---

## 10. Verification

### 10.1. Tests

| Test category | File | Số test | Trạng thái |
|---------------|------|---------|------------|
| Unit tests cho AgglomerativeAdapter | `tests/test_ml03_agglomerative.py` | 59 | **PASS** (verified trong session này) |

Test categories (từ test file):

- Adapter construction validation (`n_clusters`, `linkage`, `metric`,
  `compute_distances`).
- Ward + non-Euclidean rejected up-front.
- `fit(X)` happy path — 4 linkages (ward, complete, average, single).
- `fit(X)` validation errors.
- `cluster_labels` shape, dtype, value range.
- `cluster_result.extra` keys (`linkage`, `metric`, `compute_distances_used`,
  `n_leaves`, `n_merges`, `max_merge_distance`, `min_merge_distance`,
  `median_merge_distance`, `merge_distances_summary`, `cluster_sizes`).
- `supports_random_state() == False`.
- `get_params()` returns correct dict.
- `get_model()` returns fitted sklearn AgglomerativeClustering.
- Boundary discipline: no mutation, FE-06 input not mutated.

Verification command:

```bash
python3 -m pytest tests/test_ml03_agglomerative.py -v
```

Verification result: **59 / 59 passed**.

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

- **Input SHA-256 unchanged**: FE-06 outputs không bị ML-03 mutate.
- **Config SHA-256 recorded**: `7acbcddce99cac817324f6832dbc9d9d514a25cf9ed8c2134b594c73a0078660`
  (primary run).
- **Library versions**: numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`,
  scikit-learn `1.9.1`, pyarrow `25.0.1`.
- **Determinism**: Agglomerative n_clusters mode là deterministic; không
  cần seed. Framework runner KHÔNG inject seed (đã advertise
  `supports_random_state() == False`).

### 10.5. Input integrity

Giống ML-02; `validate_clustering_matrix` và `validate_customer_alignment`
PASS.

### 10.6. Output integrity

- `cluster_labels` shape `(4371,)`, dtype `int64` ✅.
- `cluster_labels` values trong `{0, 1, 2, 3}` cho primary run ✅.
- `IsNoise` column always `False` (Agglomerative n_clusters mode không có
  noise) ✅.
- `extra.n_merges` = `n_samples - 1` (= 4370) ✅.
- `extra.n_leaves` = `n_samples` (= 4371) ✅.
- `extra.merge_distances_summary` đúng schema (first 5 + "..." + last 5) ✅.
- `extra.cluster_sizes` sum = `n_samples` ✅.
- KHÔNG có `algorithm_output_*.parquet` (Agglomerative không có soft output).

### 10.7. Regression status

- Pre-existing tests còn pass: 59 / 59 ML-03 tests pass.
- Không có test nào bị skip không giải thích.
- Không có pre-existing failure chưa được giải thích.

---

## 11. Mentor Review

| ID | Nội dung cần review | Loại | Trạng thái |
|----|---------------------|------|------------|
| ML-03-MET-01 | Methodology: `working_n_clusters=4` được chọn làm default cho ML-03 primary diagnostic | Methodology | PENDING_REVIEW |
| ML-03-MET-02 | Methodology: `working_linkage='ward'` được chọn làm working default | Methodology | PENDING_REVIEW |
| ML-03-MET-03 | Methodology: `working_metric='euclidean'` được chọn làm working default | Methodology | PENDING_REVIEW |
| ML-03-MET-04 | Methodology: cho phép 4 per-linkage diagnostic runs (ward / complete / average / single) trong EPIC-06 | Scope / Methodology | PENDING_REVIEW |
| ML-03-MET-05 | Methodology: capture per-merge linkage distance summary (`merge_distances_summary`) trong `cluster_result.extra` cho downstream dendrogram diagnostic | Engineering | DOCUMENTED (algorithm-specific diagnostic) |
| ML-03-ENG-01 | Engineering: chỉ expose `n_clusters`, `linkage`, `metric`, `compute_distances` trong AgglomerativeAdapter — không expose thêm `connectivity`, `memory`, `compute_full_tree`, `distance_threshold` | Engineering / Scope | DOCUMENTED |
| ML-03-ENG-02 | Engineering: Ward + non-Euclidean rejected up-front với `ClusterAlgorithmError` thay vì để sklearn raise | Engineering | DOCUMENTED |
| ML-03-ENG-03 | Engineering: dendrogram visualization CHƯA ĐƯỢC TẠO trong EPIC-06 | Scope | DOCUMENTED (EPIC-06 diagnostic viz optional) |

**Ghi chú:**

- ML-03-MET-01, -02, -03, -04 cần mentor review vì chúng ảnh hưởng đến cách
  initial diagnostic run được setup; EPIC-07 sweep sẽ reference các
  default này.
- ML-03-MET-05, -ENG-01, -02, -03 là engineering / scope decisions; không
  ảnh hưởng experimental design.

---

## 12. Kết luận

### 12.1. Đã hoàn thành

ML-03 Agglomerative **TECHNICALLY_IMPLEMENTED** với evidence:

- **Code:** `src/customer_segmentation/clustering/agglomerative.py`
  (`AgglomerativeAdapter` + default constants + sklearn wrapper + validation
  cho ward + non-Euclidean).
- **Configuration:** `configs/clustering.yaml` → `clustering.algorithms.agglomerative.*`.
- **Tests:** `tests/test_ml03_agglomerative.py` — 59 / 59 tests passed.
- **Initial diagnostic runs đã chạy thành công:**
  - 1 primary run (`ward`, `n_clusters=4`): SUCCESS, n_clusters=4,
    n_merges=4370, n_leaves=4371, max_merge_distance=805.9028,
    execution_time=0.681s.
  - 4 per-linkage diagnostic runs (`ward`, `complete`, `average`, `single`):
    tất cả SUCCESS với n_clusters=4 (xem `reports/ml03/ml03_linkage_comparison.csv`).
- **Artifacts:** 5 files `cluster_labels_ML-03-Agglo-*.parquet` + 5 files
  `experiment_log_ML-03-Agglo-*.json`.
- **Reports:**
  - `reports/ml03/ml03_run_summary.json`
  - `reports/ml03/ml03_initial_diagnostic.md`
  - `reports/ml03/ml03_linkage_comparison.csv`
- **Lint:** `ruff check` pass.
- **Format:** `black --check` pass.

### 12.2. Chưa hoàn thành

- **Evaluation metrics** (silhouette / DBI / CH): `MetricsResult` toàn
  field = `None`. EPIC-07/08 sẽ compute.
- **Sweep nhiều K / linkage / metric**: chỉ có 1 primary + 4 per-linkage
  diagnostic; EPIC-07 sẽ sweep đầy đủ.
- **Dendrogram visualization**: chưa được tạo trong EPIC-06; đó là
  diagnostic viz optional và có thể được tạo sau nếu cần.
- **Algorithm comparison**: EPIC-08.
- **Segment profiling / naming**: EPIC-09.
- **Soft probability / membership output**: Agglomerative không có; đó là
  đặc trưng của GMM (ML-05) và FCM (ML-06).

### 12.3. Pending Mentor Review

| ID | Quyết định | Trạng thái |
|----|------------|------------|
| ML-03-MET-01 | `working_n_clusters=4` cho ML-03 primary diagnostic | PENDING_REVIEW |
| ML-03-MET-02 | `working_linkage='ward'` cho working default | PENDING_REVIEW |
| ML-03-MET-03 | `working_metric='euclidean'` cho working default | PENDING_REVIEW |
| ML-03-MET-04 | 4 per-linkage diagnostic runs trong EPIC-06 | PENDING_REVIEW |

### 12.4. Chuyển tiếp sang task tiếp theo

**Output của ML-03 = input cho EPIC-07:**

- `cluster_labels_*.parquet` → EPIC-07 sẽ read cho mỗi (K, linkage, metric).
- `experiment_log_*.json` → EPIC-07 sẽ populate `MetricsResult` (silhouette,
  DBI, CH) per-fit.
- `cluster_result.extra.merge_distances_summary` → EPIC-07 có thể dùng cho
  elbow / dendrogram-cut heuristic per (K, linkage).
- `cluster_result.extra.cluster_sizes` → EPIC-07 sẽ thu thập per
  (K, linkage, metric) cho stability analysis.

**Contract giữa ML-03 và consumer:**

| Field | Contract |
|-------|----------|
| `algorithm_family` | `"hard"` |
| `cluster_labels` shape | `(4371,)` |
| `cluster_labels` dtype | `int64` |
| `cluster_labels` values | `[0, K-1]` |
| `IsNoise` column | always `False` (Agglomerative không có noise) |
| `supports_random_state` | `False` (deterministic) |
| `extra.linkage` / `extra.metric` | giá trị string |
| `extra.n_merges` | `n_samples - 1` |
| `extra.merge_distances_summary` | first 5 + `...` + last 5 floats |

**TUYỆT ĐỐI KHÔNG** trong Mentor document này: KHÔNG viết "best linkage",
KHÔNG gọi Agglomerative là "best algorithm", KHÔNG ranking với algorithm
khác. ML-03 là implementation + initial diagnostics, KHÔNG là evaluation.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-03 implementation
(code, tests, config, primary + per-linkage diagnostic runs, experiment log,
artifacts, linkage comparison CSV). Mọi con số trong tài liệu này đều có
provenance rõ ràng. Per-linkage diagnostics KHÔNG dùng để kết luận
"best linkage" — đó là EPIC-07 scope._