# ML-01 — Clustering Experiment Framework: Lý thuyết và Implementation Notes

> **Tài liệu cho ML-01.**
> Phiên bản framework: `ML01-v1.0`.
> Trạng thái implementation: `TECHNICALLY_IMPLEMENTED` (chưa chạy bất kỳ clustering experiment nào).
> Ngôn ngữ tài liệu: tiếng Việt. Code / file name / config key: English theo convention hiện tại của repository.

Tài liệu này phân biệt rõ **phần đã được implement** (`TECHNICALLY_IMPLEMENTED`)
và **phần extension point** dành cho ML-02 → ML-06 và EPIC-07/08/09.
Không có chỗ nào trong tài liệu này mô tả extension point như thể nó đã chạy được.

---

## 1. Mục tiêu

ML-01 xây dựng một **framework thống nhất** để chạy nhiều thuật toán clustering trên
cùng một Final Clustering Dataset (do FE-06 sinh ra).

Framework phải:

- hỗ trợ hard clustering (K-Means, K-Medoids, Agglomerative),
- hỗ trợ density-based clustering (DBSCAN) bao gồm **noise label** `-1`,
- hỗ trợ model-based clustering (GMM) bao gồm **posterior probabilities**,
- hỗ trợ fuzzy clustering (Fuzzy C-Means) bao gồm **membership matrix**,
- **không** ép mọi thuật toán vào cùng một API nội bộ; mỗi adapter tự do expose
  output đặc thù qua cùng một schema thống nhất,
- **không** mutate Final Clustering Dataset (FE-06 là read-only),
- **không** chạy evaluation, ranking, hoặc chọn "best" algorithm.

Framework là nền tảng cho:

```
ML-01 Framework  (this document)
   ↓
ML-02 K-Means
ML-03 Hierarchical
ML-04 DBSCAN
ML-05 GMM
ML-06 Fuzzy C-Means
   ↓
EPIC-06 Diagnostic / algorithm-specific visualization
   ↓
EPIC-07 Controlled Experiments
   ↓
EPIC-08 Metrics + Research Comparison Visualization
   ↓
EPIC-09 Customer Segment Visualization
```

ML-01 deliverable là framework + test + documentation. Không deliverable là
kết quả clustering experiment thực tế.

---

## 2. Vai trò của ML-01 trong nghiên cứu

| Vai trò                     | Phạm vi ML-01                              |
|-----------------------------|--------------------------------------------|
| Cung cấp abstraction chung  | ✅ Đã implement (`BaseClusterAlgorithm`)    |
| Registry cho algorithm      | ✅ Đã implement (`AlgorithmRegistry`)      |
| Schema kết quả thống nhất   | ✅ Đã implement (`ClusterResult`, `ExperimentResult`) |
| Validation input            | ✅ Đã implement (`validate_clustering_matrix`, `validate_customer_alignment`) |
| Reproducibility metadata    | ✅ Đã implement (seed policy, config SHA, env snapshot) |
| Experiment logging          | ✅ Đã implement (`get_logger`, `write_experiment_log`) |
| Artifact management         | ✅ Đã implement (`write_cluster_labels`, `write_algorithm_output`) |
| Evaluation metrics          | ❌ **Chưa** implement — EPIC-07/08 sẽ làm |
| Algorithm benchmarking      | ❌ **Chưa** implement — ML-02 → ML-06 sẽ làm |
| Stability / runtime         | ❌ **Chưa** implement — EPIC-07/08 sẽ làm |
| Diagnostic visualization    | ❌ **Chưa** implement — EPIC-06 / ML-03 tự quyết |
| Research comparison viz    | ❌ **Chưa** implement — EPIC-08 sẽ làm   |
| Customer segment viz       | ❌ **Chưa** implement — EPIC-09 sẽ làm   |

---

## 3. Input từ FE-06

ML-01 consume **hai file** do FE-06 sinh ra, ở chế độ read-only:

| File                                          | Vai trò                             | Schema |
|-----------------------------------------------|-------------------------------------|--------|
| `data/processed/final_clustering_dataset.parquet` | Numeric feature matrix, 14 cột, không chứa CustomerID | `(4371, 14)` |
| `data/processed/customer_metadata.parquet`    | CustomerID tách riêng               | `(4371, 1)` với cột `CustomerID` |
| `data/processed/customer_candidates.parquet`   | KHÔNG dùng bởi ML-01                | —      |

- Dataset version mặc định: `FE06-v1.0` (đã ghi trong `configs/clustering.yaml`
  dưới `framework.input.dataset_version`).
- Final clustering matrix **không được chứa** `CustomerID` (`no_identifier_in_matrix`
  check; vi phạm → `IdentifierLeakageError`).
- ML-01 KHÔNG scale, KHÔNG transform, KHÔNG impute lại — đó là việc của FE-06.

---

## 4. Kiến trúc framework

```
src/customer_segmentation/clustering/
├── __init__.py            # Public API (re-exports)
├── base.py                # BaseClusterAlgorithm (abstract)
├── registry.py            # AlgorithmRegistry (in-process)
├── result.py              # ClusterResult, ExperimentResult, MetricsResult
├── validation.py          # validate_clustering_matrix, validate_customer_alignment
├── config.py              # FrameworkConfig loader (configs/clustering.yaml)
├── logging_utils.py       # get_logger, write_experiment_log
├── artifacts.py           # write_cluster_labels, write_algorithm_output
└── runner.py              # ExperimentRunner (end-to-end)
```

Cấu trúc này tuân theo convention FE-06 (`config.py` + `validation.py` +
`result.py` + `runner.py` + `report.py`); chỉ thay `report.py` bằng
`artifacts.py` để phản ánh rõ rằng ML-01 chỉ ghi artifact theo schema, chưa
sinh "report nghiên cứu".

Các module `kmeans.py`, `kmedoids.py`, `agglomerative.py`, `dbscan.py` hiện
đang là placeholder; ML-02 → ML-06 sẽ thay thân hàm bằng adapter thật đăng
ký vào `AlgorithmRegistry`.

### 4.1. Class diagram (rút gọn)

```
BaseClusterAlgorithm (abstract)
    │
    ├── name: str
    ├── version: str
    ├── family: AlgorithmFamily
    ├── fit(X: np.ndarray) -> ClusterResult     [abstract]
    ├── get_params() -> dict                    [default impl]
    ├── get_model() -> object | None            [default impl]
    └── supports_random_state() -> bool         [default True]


ClusterResult
    ├── algorithm, algorithm_version, algorithm_family
    ├── n_samples, n_features
    ├── cluster_labels: np.ndarray
    ├── n_clusters: int | None
    ├── soft_probabilities: np.ndarray | None      # GMM
    ├── soft_membership: np.ndarray | None        # Fuzzy C-Means
    ├── noise_label, noise_count, noise_ratio     # DBSCAN
    ├── supports_random_state, random_seed_used
    └── metrics: MetricsResult                    # placeholder

ExperimentResult
    ├── experiment_id, status (SUCCESS | FAILED)
    ├── algorithm, algorithm_version
    ├── dataset_version, dataset_sha256
    ├── feature_set, feature_count, n_samples
    ├── hyperparameters, random_seed, random_seed_used
    ├── cluster_result: ClusterResult | None
    ├── execution_time, timestamp
    ├── error: dict | None
    ├── platform, library_versions
    ├── scope_boundaries, pending_review_notes, assumptions
    └── artifact_paths: dict[str, str]


AlgorithmRegistry
    ├── register(name) -> decorator
    ├── get(name) -> class
    ├── list_registered() -> list[str]
    ├── is_registered(name) -> bool
    └── clear()                       # tests only


FrameworkConfig (frozen dataclasses)
    └── experiment / random_seed / input / validation / output / logging / metadata


ExperimentRunner
    └── run(matrix_df, metadata_df) -> ExperimentResult
```

---

## 5. Abstraction / interface

### 5.1. `BaseClusterAlgorithm`

Mọi concrete algorithm adapter phải subclass `BaseClusterAlgorithm` và định
nghĩa:

```python
class MyAlgorithm(BaseClusterAlgorithm):
    name = "my_algo"            # stable, lowercase
    version = "sklearn_1.x"     # implementation / library version
    family = AlgorithmFamily.HARD

    def __init__(self, k: int, seed: int | None = None):
        ...

    def fit(self, X: np.ndarray) -> ClusterResult:
        ...
        return ClusterResult(...)
```

Adapter **không** được:

- mutate `X` (framework truyền `X = matrix_df.to_numpy(dtype=np.float64, copy=False)`),
- tự ghi file (để runner xử lý),
- tự log framework-level message (chỉ log nội bộ nếu cần).

### 5.2. `AlgorithmRegistry`

```python
AlgorithmRegistry.register("my_algo")(MyAlgorithm)
cls = AlgorithmRegistry.get("my_algo")
AlgorithmRegistry.list_registered()  # → ["kmeans", "my_algo", ...]
```

- Đăng ký trùng tên → `AlgorithmRegistryError`.
- `AlgorithmRegistry.clear()` chỉ dành cho test.

### 5.3. `AlgorithmFamily`

```python
class AlgorithmFamily(StrEnum):
    HARD = "hard"                # K-Means, K-Medoids, Agglomerative
    DENSITY_BASED = "density_based"  # DBSCAN
    MODEL_BASED = "model_based"  # GMM
    FUZZY = "fuzzy"              # Fuzzy C-Means
    OTHER = "other"              # extension
```

---

## 6. Configuration

### 6.1. File cấu hình

ML-01 dùng `configs/clustering.yaml` làm **single source of truth**.
File này có hai phần:

1. **Phần cũ** (giữ nguyên) — `clustering.algorithms.*`, dành cho ML-02 → ML-06
   parse hyperparameter per algorithm.
2. **Phần mới** — `clustering.framework.*`, framework config mà ML-01 dùng.

### 6.2. Schema YAML của `framework`

```yaml
clustering:
  framework:
    enabled: true

    experiment:
      id: "ML-01-..."           # experiment_id
      description: "..."        # one-liner mô tả

    random_seed:
      default: 42
      per_algorithm_override: { gmm: 123, kmeans: 42 }

    input:
      final_clustering_dataset_path: "./data/processed/final_clustering_dataset.parquet"
      customer_metadata_path: "./data/processed/customer_metadata.parquet"
      dataset_version: "FE06-v1.0"
      customer_key: "CustomerID"

    validation:
      require_no_nan: true
      require_no_inf: true
      require_all_numeric: true
      min_samples: 2
      min_features: 1
      exclude_customer_id_from_features: true

    output:
      artifacts_dir: "./data/processed/clustering_experiments"
      report_dir: "./reports/ml01"
      save_labels: true
      save_metadata: false
      save_algorithm_specific: true
      cluster_labels_filename: "cluster_labels_{experiment_id}.parquet"
      experiment_log_filename: "experiment_log_{experiment_id}.json"
      algorithm_output_filename: "algorithm_output_{experiment_id}.parquet"

    logging:
      log_to_console: true
      log_to_file: true
      log_file_dir: "./reports/ml01"
      log_level: "INFO"

    metadata:
      stage: "ML-01"
      stage_version: "ML01-v1.0"
      stage_status: "TECHNICALLY_IMPLEMENTED"
      scope_boundaries: [ ... ]
      pending_review_notes: [ ... ]
      assumptions: [ ... ]
```

### 6.3. Loader

```python
from customer_segmentation.clustering import (
    load_framework_config,
    resolve_framework_config_path,
)

cfg = load_framework_config(resolve_framework_config_path())
```

Loader fail-fast với `FrameworkConfigError` nếu YAML thiếu key hoặc
`framework.enabled=false`. Không silent default.

---

## 7. Experiment lifecycle

```
caller code
   │
   ├── ExperimentSpec(experiment_id, algorithm, hyperparameters, seed_override)
   │
   ├── ExperimentRunner(cfg, spec, config_source, config_text)
   │
   └── runner.run(matrix_df, customer_metadata_df, output_dir)
            │
            ├── validate matrix → ValidationReport
            ├── validate customer alignment → ValidationReport
            ├── adapter = registry.get(spec.algorithm)(**spec.hyperparameters)
            ├── seed = resolve_random_seed(cfg, algorithm, spec.seed_override)
            ├── fit(X)
            │     ├── SUCCESS → ClusterResult
            │     └── EXCEPTION → FAILED with error dict
            ├── build ExperimentResult
            └── write artifacts (cluster_labels, experiment_log, algorithm_output)
```

### 7.1. Status semantics

| Status     | Khi nào                                                                              |
|------------|--------------------------------------------------------------------------------------|
| `SUCCESS`  | `adapter.fit()` trả về `ClusterResult` hợp lệ (shape đúng, không exception)        |
| `FAILED`   | Validation fail (NaN, Inf, non-numeric, constant features, ...) hoặc `fit()` raise  |

Algorithm exception **không** propagate lên caller. Runner bắt, log, và
trả `ExperimentResult(status=FAILED, error={type, message, traceback})`.

### 7.2. Identifier leakage

Identifier leakage (`CustomerID`, `InvoiceNo`, ...) trong matrix là **scope
violation**. Runner raise `IdentifierLeakageError` ngay khi phát hiện
(không nuốt vào FAILED). Lý do: leakage cho thấy caller đang feed sai
input — đó là bug, không phải data quality issue.

---

## 8. Result schema

### 8.1. `ClusterResult.to_dict()` (log-friendly)

```jsonc
{
  "algorithm": "kmeans",
  "algorithm_version": "sklearn_1.5",
  "algorithm_family": "hard",
  "n_samples": 4371,
  "n_features": 14,
  "n_clusters": 4,
  "cluster_labels_shape": [4371],
  "cluster_labels_dtype": "int64",
  "cluster_labels_first_5": [0, 2, 1, 3, 0],
  "soft_probabilities_shape": null,         // GMM: [4371, n_components]
  "soft_membership_shape": null,           // Fuzzy: [4371, c]
  "noise_label": -1,
  "noise_count": null,                     // DBSCAN: integer
  "noise_ratio": null,                     // DBSCAN: float
  "supports_random_state": true,
  "random_seed_used": 42,
  "model_artifact_path": null,
  "extra": {},
  "metrics": {                             // EPIC-07/08 populate
    "silhouette": null,
    "davies_bouldin": null,
    "calinski_harabasz": null,
    "wcss": null,
    "stability": null,
    "runtime": null,
    "extra": {}
  }
}
```

### 8.2. `ExperimentResult.to_dict()`

```jsonc
{
  "experiment_id": "ML-01-KMeans-k4-seed42",
  "status": "SUCCESS",                    // or "FAILED"
  "algorithm": "kmeans",
  "algorithm_version": "sklearn_1.5",
  "dataset_version": "FE06-v1.0",
  "dataset_sha256": "ba54033e...",
  "input_path": ".../final_clustering_dataset.parquet",
  "metadata_path": ".../customer_metadata.parquet",
  "feature_set": ["Recency", "Frequency", ...],
  "feature_count": 14,
  "n_samples": 4371,
  "hyperparameters": {"n_clusters": 4, "n_init": 10},
  "random_seed": 42,
  "random_seed_used": 42,
  "n_clusters": 4,
  "cluster_labels_shape": [4371],
  "cluster_labels_dtype": "int64",
  "execution_time": 0.42,
  "timestamp": "2026-09-21T10:09:00+07:00",
  "cluster_result": { ... },
  "metrics": { ... },
  "artifact_paths": {
    "cluster_labels": ".../cluster_labels_....parquet",
    "experiment_log": ".../experiment_log_....json",
    "algorithm_output": ".../algorithm_output_....parquet"
  },
  "error": null,                          // populated on FAILED
  "platform": { "python": "...", ... },
  "library_versions": { "numpy": "...", ... },
  "scope_boundaries": [ ... ],
  "pending_review_notes": [ ... ],
  "assumptions": [ ... ],
  "config_source": "yaml:/.../clustering.yaml",
  "config_sha256": "70ae1132..."
}
```

### 8.3. Schema hỗ trợ nhiều loại clustering

| Trường                       | Hard | DBSCAN | GMM | Fuzzy |
|------------------------------|:----:|:------:|:---:|:-----:|
| `cluster_labels`             |  ✅  |   ✅ (giữ `-1`)  | ✅  |  ✅ (argmax) |
| `n_clusters`                 |  ✅  |   ✅   | ✅  |  ✅   |
| `noise_label` / `noise_count`|  ⚪  |   ✅   | ⚪  |  ⚪   |
| `soft_probabilities`         |  ⚪  |   ⚪   | ✅  |  ⚪   |
| `soft_membership`            |  ⚪  |   ⚪   | ⚪  |  ✅   |
| `supports_random_state`      |  ✅  |   ✅ (DBSCAN: false) | ✅ | ✅  |

Schema KHÔNG ép một loại algorithm phải populate trường của loại khác.

---

## 9. Cluster label management

ML-01 cung cấp hai cơ chế:

### 9.1. Positional alignment (default)

Row `i` của cluster_labels ↔ row `i` của customer_metadata. Khi ghi
`cluster_labels.parquet`:

```python
df = pd.DataFrame({
    customer_key:  customer_metadata[customer_key],  # CustomerID
    "ClusterLabel": cluster_labels,                  # int64
    "IsNoise":      cluster_labels == noise_label,
    "Probability_0": soft_probabilities[:, 0],        # optional
    ...
})
```

Đây là contract: **cluster_labels row order = customer_metadata row order**.
ML-01 không reorder customer.

### 9.2. Validation

- `len(cluster_labels) == len(customer_metadata)` (positional).
- `customer_metadata[customer_key]` unique và không NaN.
- Nếu metadata = `None`: chỉ ghi `RowIndex` + `ClusterLabel` (caller chịu
  trách nhiệm re-attach CustomerID bên ngoài).

---

## 10. Reproducibility

ML-01 hỗ trợ reproducibility qua ba kênh:

1. **`random_seed`** — config YAML + `ExperimentSpec.seed_override` +
   `per_algorithm_override`. Seed chỉ được pass xuống adapter nếu
   `adapter.supports_random_state()` trả về `True`.
2. **`config_sha256`** — text SHA-256 của YAML, lưu trong
   `ExperimentResult.config_sha256`.
3. **`environment snapshot`** — Python version, OS, library versions
   (numpy, pandas, scipy, scikit-learn, pyarrow).

ML-01 **không đảm bảo** byte-level reproducibility giữa các máy / library
versions (giống FE-06). ML-01 chỉ capture đủ metadata để một researcher khác
có thể reproduce **trong cùng một môi trường**.

---

## 11. Logging & artifact management

### 11.1. Logging

- `[ML-01] <timestamp> [LEVEL] <message>` format.
- `log_to_console`: stderr handler (default).
- `log_to_file`: file handler tại `log_file_dir/ml01.log`.
- Cả hai đều bật/tắt được từ YAML.

### 11.2. Artifacts

| Artifact              | Path template                                          | Nội dung |
|-----------------------|--------------------------------------------------------|----------|
| Cluster labels        | `cluster_labels_{experiment_id}.parquet`               | CustomerID + ClusterLabel + IsNoise (+ probability columns nếu soft) |
| Algorithm output      | `algorithm_output_{experiment_id}.parquet`             | Soft probability matrix / membership matrix (nếu có) |
| Experiment log JSON   | `experiment_log_{experiment_id}.json`                  | Full `ExperimentResult.to_dict()` |

`save_labels`, `save_metadata`, `save_algorithm_specific` đều bật/tắt
qua YAML. Trên status `FAILED`, runner chỉ ghi experiment log (không
ghi cluster labels).

---

## 12. Validation (input)

### 12.1. Matrix validation checks

| Check name              | Mô tả                                                                | Strict mode |
|-------------------------|----------------------------------------------------------------------|-------------|
| `dataset_exists`        | DataFrame không None, không empty                                     | fail-fast   |
| `required_features`     | Mọi expected feature có trong DataFrame                              | fail-fast   |
| `no_identifier_in_matrix` | Không có `CustomerID` / `InvoiceNo` / ... trong matrix              | **raise `IdentifierLeakageError`** |
| `all_numeric`           | Mọi cột là numeric                                                   | fail-fast   |
| `no_nan`                | Không có NaN                                                          | fail-fast   |
| `no_inf`                | Không có Inf                                                          | fail-fast   |
| `no_constant_feature`   | Variance > 0                                                          | fail-fast   |
| `min_samples`           | n_samples >= threshold                                               | fail-fast   |
| `min_features`          | n_features >= threshold                                              | fail-fast   |

### 12.2. Customer alignment checks

| Check name              | Mô tả                                                                |
|-------------------------|----------------------------------------------------------------------|
| `metadata_present`      | Metadata không None, không empty                                      |
| `metadata_row_alignment`| `len(metadata) == len(matrix)`                                       |
| `customer_key_present`  | Cột customer_key tồn tại trong metadata                               |
| `customer_key_unique`   | `customer_key` unique 100%                                            |
| `customer_key_no_nan`   | `customer_key` không có NaN                                           |

### 12.3. Fail-fast vs FAILED status

- **Identifier leakage** → raise `IdentifierLeakageError` (scope violation).
- **Other validation failures** → `ExperimentResult(status=FAILED,
  error={type: ClusteringInputError, message, validation_report})`.

Cả hai đường đều dẫn đến `experiment_log.json` được ghi (để debug).

---

## 13. Boundary với EPIC-07/08

ML-01 **chỉ** chuẩn bị schema cho metrics; EPIC-07/08 sẽ compute.

Trong `ClusterResult.metrics`:

```python
@dataclass
class MetricsResult:
    silhouette: float | None = None         # sklearn convention [-1, 1]
    davies_bouldin: float | None = None
    calinski_harabasz: float | None = None
    wcss: float | None = None              # K-Means inertia_
    stability: dict | None = None          # EPIC-08: ARI/AMI distribution
    runtime: dict | None = None            # EPIC-08: mean/std/min/max
    extra: dict = field(default_factory=dict)
```

Tất cả field = `None` khi ML-01 trả về. EPIC-07/08 sẽ:

1. Đọc `experiment_log_{id}.json` để lấy `cluster_labels` (qua parquet)
   và `cluster_result.extra`.
2. Compute metrics và **ghi đè vào cùng file** hoặc file mới trong
   `reports/epic07/` (theo convention EPIC-07).

ML-01 KHÔNG tính silhouette, KHÔNG so sánh algorithm, KHÔNG chọn best.

---

## 14. Visualization boundary

ML-01 KHÔNG tạo visualization nghiên cứu chính. Phân chia theo từng EPIC
sở hữu:

### EPIC-06 (diagnostic / algorithm-specific visualization)

EPIC-06 sở hữu các visualization **diagnostic / algorithm-specific**
phục vụ hiểu thuật toán, không phải nghiên cứu đánh giá. Ví dụ:

- **ML-03 Hierarchical**: dendrogram (linkage tree), distance matrix heatmap.
- **ML-04 DBSCAN**: k-distance plot để chọn `eps`.
- **ML-05 GMM**: BIC / AIC curve theo số components.
- **Toy diagnostic**: elbow plot cho K-Means / K-Medoids.

ML-01 KHÔNG yêu cầu EPIC-06 visualize. EPIC-06 / ML-03 tự quyết định
có cần diagnostic plot hay không, và phải đánh dấu rõ `diagnostic`.

### EPIC-08 (research visualization phục vụ đánh giá / so sánh clustering)

EPIC-08 sở hữu các visualization nghiên cứu phục vụ so sánh và đánh giá
clustering:

- Silhouette plot / silhouette comparison across algorithms & k.
- Davies-Bouldin comparison.
- Calinski-Harabasz comparison.
- WCSS / Elbow plot.
- Runtime comparison across algorithms.
- Stability (ARI / AMI) distribution plot.
- Parameter sensitivity heatmap.
- Algorithm comparison (multi-metric dashboard).

ML-01 KHÔNG tạo các plot này. `MetricsResult` của ML-01 chỉ là **schema
placeholder**; EPIC-08 sẽ compute và visualize.

### EPIC-09 (visualization phục vụ phân tích Customer Segments)

EPIC-09 sở hữu các visualization phục vụ phân tích customer segments:

- Segment size (số customer / segment).
- RFM profile (radar / heatmap) theo segment.
- Feature distribution theo segment.
- Boxplot (numeric features × segments).
- Segment characteristics table / chart.
- Customer profiles (per-segment summary).

ML-01 KHÔNG tạo các plot này; ML-01 chỉ cung cấp cluster_labels + soft
probabilities / membership (nếu có) để EPIC-09 dùng.

### Quy tắc chung

- ML-01 KHÔNG tạo bất kỳ visualization nào cho `reports/ml01/`.
- Nếu một diagnostic plot nào được tạo trong quá trình dev (ví dụ elbow
  plot trong notebook), nó phải được đánh dấu `diagnostic` rõ ràng và
  không nằm trong `reports/ml01/`.
- Phân chia visualization ownership giữa EPIC-06 (diagnostic),
  EPIC-08 (research comparison), và EPIC-09 (segment analysis) là một
  **methodology decision** cần mentor review + ADR trước khi promote
  final.

---

## 15. Testing

`tests/test_ml01_framework.py` (59 tests) cover:

| Test class                     | Coverage                                              |
|--------------------------------|-------------------------------------------------------|
| `TestBaseAlgorithm`            | Abstract contract, `get_params`, `supports_random_state` |
| `TestRegistry`                 | Register / get / list / duplicate / non-subclass      |
| `TestValidation`               | None / empty / NaN / Inf / non-numeric / leakage / constant / fail_fast |
| `TestCustomerAlignment`        | Row count / uniqueness / NaN / missing key            |
| `TestResultSchema`             | Required fields, JSON serialisation, soft round-trip, noise preservation, FAILED status |
| `TestReproducibility`          | Same seed → same labels, deterministic alg không consume seed |
| `TestRunner`                   | Happy path, algorithm exception, validation fail, unknown algo, config SHA |
| `TestArtifactWriting`          | CustomerID alignment, DBSCAN noise preserved, soft output parquet |
| `TestConfig`                   | YAML load, dict round-trip, missing section, disabled framework, canonical YAML |
| `TestSeedResolution`           | Override, default, per-algorithm override             |
| `TestEnvironmentSnapshots`     | Platform info, library versions                       |
| `TestLogger`                   | Logger smoke test                                     |
| `TestIntegrationWithFE06`      | Real FE-06 dataset end-to-end (skipped nếu data absent), identifier leakage |

Các adapter dùng trong test là **toy algorithm** (`ToyHardAlgorithm`,
`ToyNoiseAlgorithm`, `ToySoftAlgorithm`, `ToyFailingAlgorithm`,
`ToyDeterministicAlgorithm`). ML-02 → ML-06 sẽ thay bằng adapter production.

---

## 16. Limitations (ML-01)

1. **Không có production algorithm**: chỉ có toy adapter cho test.
   K-Means / DBSCAN / GMM / Fuzzy C-Means production code sẽ do
   ML-02 → ML-06 deliver.
2. **Không compute metrics**: `MetricsResult` toàn field `None`.
   EPIC-07/08 sẽ compute.
3. **Không có model persistence by default**: `model_artifact_path` = `None`.
   Nếu ML-02 → ML-06 muốn persist model, họ set field này trong
   `ClusterResult.extra` hoặc wrap trong adapter.
4. **Không parallel runner**: chạy tuần tự. EPIC-07 sẽ quyết định
   có cần parallel sweep hay không.
5. **In-process registry**: không persist giữa các process. ML-02 → ML-06
   phải `AlgorithmRegistry.register(...)` trong `__init__.py` của họ.
6. **No streaming**: matrix phải fit trong memory. Final clustering dataset
   4371×14 ≈ 0.5 MB, không phải vấn đề trong ML-01 scope.

---

## 17. Chuẩn bị cho ML-02 → ML-06

ML-02 (K-Means) implement pattern:

```python
# src/customer_segmentation/clustering/kmeans.py
from customer_segmentation.clustering.base import BaseClusterAlgorithm
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import ClusterResult, AlgorithmFamily

@AlgorithmRegistry.register("kmeans")
class KMeansAdapter(BaseClusterAlgorithm):
    version = "sklearn_1.x"
    family = AlgorithmFamily.HARD

    def __init__(self, n_clusters: int = 4, n_init: int = 10, seed: int | None = None):
        self.n_clusters = n_clusters
        self.n_init = n_init
        self.seed = seed
        # ... build sklearn KMeans

    def fit(self, X):
        # ... fit + return ClusterResult
```

Tương tự cho ML-03 → ML-06. ML-02 → ML-06 ownership:

- Tự register adapter vào `AlgorithmRegistry`.
- KHÔNG sửa framework code trừ khi cần mở rộng schema.
- KHÔNG compute metrics — để EPIC-07/08.
- Mỗi adapter PHẢI override `supports_random_state()` đúng sự thật.

---

## 18. Trạng thái implementation

| Item                                     | Status                  |
|------------------------------------------|-------------------------|
| BaseClusterAlgorithm                     | ✅ TECHNICALLY_IMPLEMENTED |
| AlgorithmRegistry                        | ✅ TECHNICALLY_IMPLEMENTED |
| ClusterResult + MetricsResult            | ✅ TECHNICALLY_IMPLEMENTED |
| ExperimentResult                         | ✅ TECHNICALLY_IMPLEMENTED |
| validate_clustering_matrix               | ✅ TECHNICALLY_IMPLEMENTED |
| validate_customer_alignment              | ✅ TECHNICALLY_IMPLEMENTED |
| FrameworkConfig + YAML loader            | ✅ TECHNICALLY_IMPLEMENTED |
| get_logger / write_experiment_log         | ✅ TECHNICALLY_IMPLEMENTED |
| write_cluster_labels                     | ✅ TECHNICALLY_IMPLEMENTED |
| write_algorithm_output                   | ✅ TECHNICALLY_IMPLEMENTED |
| ExperimentRunner                         | ✅ TECHNICALLY_IMPLEMENTED |
| ML-02 K-Means adapter                    | ❌ PENDING               |
| ML-03 Hierarchical adapter               | ❌ PENDING               |
| ML-04 DBSCAN adapter                     | ❌ PENDING               |
| ML-05 GMM adapter                        | ❌ PENDING               |
| ML-06 Fuzzy C-Means adapter              | ❌ PENDING               |
| EPIC-06 Diagnostic / algorithm-specific visualization | ❌ PENDING       |
| EPIC-07 Controlled experiments           | ❌ PENDING               |
| EPIC-08 Metrics + research comparison    | ❌ PENDING               |
| EPIC-09 Customer segment visualization   | ❌ PENDING               |

---

## 19. Assumptions

1. **Single global random_seed policy**: per-experiment override +
   per-algorithm override cùng tồn tại.
2. **Algorithms advertise random_state support** qua
   `BaseClusterAlgorithm.supports_random_state()`. ML-01 không tự
   detect.
3. **CustomerID sống trong metadata, KHÔNG trong matrix**. Đây là hard
   constraint từ FE-06, được enforce bởi `IdentifierLeakageError`.
4. **Noise label mặc định `-1`** (sklearn convention). DBSCAN adapter
   KHÔNG được đổi sang giá trị khác trừ khi có ADR.
5. **Cluster labels row order = metadata row order**. Adapter không
   được reorder customer; nếu algorithm internally reorder (ví dụ
   agglomerative cắt cây), caller vẫn đọc label tại row `i` ban đầu.

---

## 20. PENDING_REVIEW decisions

Các quyết định dưới đây cần mentor review trước khi promote final.
Phân loại theo AGENTS.md §2.10:

- **Methodology / research decision** — ảnh hưởng đến research
  methodology, cần mentor review + ADR.
- **Engineering / implementation decision** — chỉ liên quan đến cách
  implement, không ảnh hưởng experimental design, có thể promote
  final sau khi được reviewer xác nhận không có implicit methodology
  effect.

### 20.1. Methodology / research decisions (cần ADR)

1. **Framework interfaces** — schema `ClusterResult` / `ExperimentResult`
   định nghĩa "shape" của mọi output clustering, kéo theo cách EPIC-07/08
   consume. Nếu schema đổi, downstream evaluation thay đổi. Đây là
   methodology decision.
2. **CustomerID alignment contract** (positional vs key-based) — cách
   CustomerID được map về cluster labels. Positional alignment (hiện tại)
   ngầm giả định matrix row order = metadata row order; key-based sẽ
   thay đổi semantics. Đây là methodology decision vì nó ảnh hưởng cách
   researcher đối chiếu cluster với customer-level analysis.
3. **Metrics placeholder shape** (`silhouette`, `davies_bouldin`,
   `calinski_harabasz`, `wcss`, `stability`, `runtime`, `extra`) —
   định nghĩa bộ metric nào sẽ tồn tại trong evaluation. Đây là
   methodology decision (evaluation metric là một phần của methodology).
4. **Visualization ownership** — phân chia EPIC-06 (diagnostic),
   EPIC-08 (research comparison), EPIC-09 (segment analysis) đã được
   ghi rõ trong §14, nhưng cần mentor confirm trước khi các EPIC sau
   reference ownership này.

### 20.2. Engineering / implementation decisions (không ảnh hưởng experimental design)

5. **Per-algorithm seed override** trong YAML — chỉ là cách caller
   override seed cho một algorithm cụ thể khi cần debug. Không thay
   đổi random seed policy mặc định; chỉ là một escape hatch cho
   per-experiment control. Engineering decision.
6. **Artifact filename template** (`{experiment_id}`) — chỉ là naming
   convention để phân biệt nhiều experiment trong cùng directory.
   Không ảnh hưởng semantics của artifact. Engineering decision.
7. **Noise label mặc định `-1`** — sklearn convention, đã document
   trong `BaseClusterAlgorithm` docstring. Engineering decision.

### 20.3. Action

- Các điểm 1–4 (§20.1) cần ADR + mentor review **trước khi** ML-02 → ML-06
  hoặc EPIC-07/08 reference.
- Các điểm 5–7 (§20.2) có thể được engineer review sau; promote final
  cùng nhau với các EPIC sau.
- Mọi thay đổi ở §20.1 phải qua pull request workflow theo AGENTS.md §4.

---

## 21. Out of scope (cố ý chưa làm)

- Chạy bất kỳ clustering experiment nào trên dataset thật.
- Chọn algorithm "tốt nhất" hoặc ranking.
- Hyperparameter tuning / grid search.
- Internal evaluation metrics (silhouette, DBI, CH, ...).
- Stability analysis (ARI / AMI bootstrap).
- Runtime benchmarking.
- Customer profiling / segment naming.
- Diagnostic visualization (EPIC-06).
- Research comparison visualization (EPIC-08).
- Customer segment visualization (EPIC-09).
- Thay đổi FE-06 output.
- Thay đổi FE-05 output.
- Commit / push / PR (theo AGENTS.md §2.11).
