# ML-01 — Clustering Experiment Framework

> **Mentor Document cho EPIC-06.**
> Framework version: `ML01-v1.0` (ghi trong `configs/clustering.yaml`
> dưới `framework.metadata.stage_version`).
> Trạng thái implementation: `TECHNICALLY_IMPLEMENTED`
> (chưa phải `RESEARCH_APPROVED_FINAL`).
> Ngôn ngữ tài liệu: tiếng Việt. Code / file name / config key / class
> name: English theo convention hiện tại của repository.

Tài liệu này phân biệt rõ giữa **đã implement** (`TECHNICALLY_IMPLEMENTED`),
**working assumption** (`WORKING_ASSUMPTION`), **pending mentor review**
(`PENDING_REVIEW`) và **out of scope** (`OUT_OF_SCOPE`).
Không có chỗ nào trong tài liệu này mô tả extension point như thể nó đã chạy
được ngoài EPIC-06.

---

## 1. Tên task và vai trò trong nghiên cứu

| Trường | Nội dung |
|--------|----------|
| **Task ID** | `ML-01` |
| **Tên task** | Clustering Experiment Framework |
| **Mục tiêu** | Xây dựng một framework thống nhất để chạy nhiều thuật toán clustering trên cùng Final Clustering Dataset (do FE-06 sinh ra), với cùng schema output, cùng reproducibility metadata, và cùng cơ chế validation. Framework KHÔNG tự chạy bất kỳ algorithm production nào; nó chỉ là nền tảng cho ML-02 → ML-06 và EPIC-07/08/09. |
| **Vị trí trong research pipeline** | ML-01 nằm ngay sau FE-06 (input) và trước ML-02 → ML-06 (algorithm adapters), EPIC-07 (controlled experiments), EPIC-08 (evaluation), EPIC-09 (segment analysis). |
| **Input** | `data/processed/final_clustering_dataset.parquet` (FE-06 output; SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`); `data/processed/customer_metadata.parquet` (FE-06 output; SHA-256 `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`); `configs/clustering.yaml` (framework configuration). |
| **Output** | Không sinh artifact clustering nào; ML-01 chỉ sinh code framework (`src/customer_segmentation/clustering/`), unit tests (`tests/test_ml01_framework.py`) và configuration contract. Các artifact clustering (`cluster_labels_*.parquet`, `experiment_log_*.json`, `algorithm_output_*.parquet`) chỉ được sinh khi ML-02 → ML-06 plug adapter và chạy qua `ExperimentRunner`. |
| **Quan hệ với task trước/sau** | Trước: FE-06 (`docs/research/FE06_Transformation_Final_Dataset.md`) sinh `final_clustering_dataset.parquet` (14 features, 4371 customers) và `customer_metadata.parquet` (CustomerID, 4371 rows). Sau: ML-02 → ML-06 plug concrete algorithm adapters (`KMeansAdapter`, `AgglomerativeAdapter`, `DBSCANAdapter`, `GMMAdapter`, `FuzzyCMeansAdapter`) vào `AlgorithmRegistry`; các task sau dùng `ExperimentRunner` + `ExperimentSpec` để chạy experiment và ghi artifact theo schema ML-01. |
| **Algorithm family** | Framework-only (KHÔNG thuộc hard / density_based / model_based / fuzzy). |

**Quan hệ với task khác trong EPIC-06:**

```
FE-06 Final Clustering Dataset
        ↓ (read-only)
ML-01 Framework  (this document)
        ↓ (registry + interface)
ML-02 K-Means ───┐
ML-03 Agglo   ───┤
ML-04 DBSCAN  ───┼── tất cả dùng ExperimentRunner → ExperimentResult
ML-05 GMM     ───┤
ML-06 FCM     ───┘
        ↓ (cluster_labels, soft output, experiment_log)
EPIC-07 Controlled Experiments
        ↓
EPIC-08 Metrics + Research Comparison Viz
        ↓
EPIC-09 Customer Segment Viz
```

ML-01 deliverable = framework code + framework tests + framework documentation.
ML-01 KHÔNG deliverable = bất kỳ clustering experiment run nào trên dataset thật.

---

## 2. Mục tiêu nghiên cứu

ML-01 trả lời một phần câu hỏi nghiên cứu về **tính khả thi kỹ thuật** của việc
chạy nhiều thuật toán clustering (K-Means, Agglomerative, DBSCAN, GMM, FCM)
trên cùng một customer-set (`FE-06`) với cùng một schema output, cùng một cơ chế
reproducibility và cùng một cơ chế validation:

- "Có thể chạy nhiều thuật toán clustering trên cùng Final Clustering Dataset
  mà vẫn giữ được CustomerID alignment, không mutate input, không leak identifier
  vào matrix, và không vi phạm FE-06 constraint về CustomerID không nằm trong
  feature matrix không?"
- "Có thể ghi log đầy đủ reproducibility metadata (input SHA, config SHA, seed,
  library versions) cho mỗi clustering run không?"
- "Có thể expose output đặc thù của từng algorithm family (soft probabilities
  cho GMM, soft membership cho FCM, noise label cho DBSCAN) qua cùng một
  schema JSON-friendly không?"

**Phạm vi nghiên cứu:** ML-01 là technical foundation, KHÔNG phải evaluation.
ML-01 không so sánh thuật toán, không chọn K tối ưu, không tính silhouette/DBI/CH
— đó là EPIC-07/08.

**Mối liên hệ với đặc thù dữ liệu FE-06:**

- FE-06 dataset có heavy-tail, mixed signs (sau Yeo-Johnson), sparse density
  (DBSCAN sẽ cho nhiều noise), và mixed feature types (numeric scale đã
  được đồng nhất bằng RobustScaler). Framework phải đủ linh hoạt để các
  adapter có thể phản ánh đúng bản chất của từng algorithm trên dữ liệu này.
- CustomerID alignment là hard constraint từ FE-06: CustomerID sống trong
  `customer_metadata.parquet`, KHÔNG trong `final_clustering_dataset.parquet`.
  Framework enforce điều này qua `validate_clustering_matrix` với check
  `no_identifier_in_matrix` raise `IdentifierLeakageError`.

**Quan hệ với FE-06 / EPIC-07/08/09:**

- FE-06 → ML-01: framework consume 2 file parquet của FE-06 ở READ-ONLY mode.
- ML-01 → EPIC-07: framework cung cấp schema `MetricsResult` (placeholders)
  và `ExperimentResult` để EPIC-07 chạy controlled sweep (algorithm × k × seed).
- ML-01 → EPIC-08: framework cung cấp artifact parquet + JSON log để EPIC-08
  compute silhouette/DBI/CH và stability metrics.
- ML-01 → EPIC-09: framework cung cấp `cluster_labels_*.parquet` và (nếu có)
  `algorithm_output_*.parquet` (soft probabilities cho GMM, membership matrix
  cho FCM) để EPIC-09 phân tích segment.

---

## 3. Cơ sở lý thuyết

ML-01 là framework — phần "lý thuyết" ở đây là các concept chung về cách
một clustering experiment framework nên được thiết kế để phục vụ nghiên cứu,
không phải lý thuyết của một thuật toán clustering cụ thể (xem ML-02 → ML-06
cho phần đó).

### 3.1. Clustering experiment framework

Một **clustering experiment framework** cung cấp abstraction chung cho phép
chạy nhiều thuật toán clustering khác nhau (hard / density-based / model-based
/ fuzzy) trên cùng một dataset, với cùng một schema output, cùng một cơ chế
reproducibility, cùng validation policy. Framework không tự chọn algorithm
"tốt nhất" và không compute evaluation metrics — nó chỉ đảm bảo tính nhất
quán giữa các lần chạy.

### 3.2. Experiment reproducibility (ML-01 sense)

ML-01 định nghĩa reproducibility theo nghĩa "cùng input + cùng config + cùng
seed + cùng library version → cùng output". ML-01 **KHÔNG đảm bảo** byte-level
reproducibility giữa các máy / library versions khác nhau; ML-01 chỉ capture
đủ metadata để một researcher khác có thể reproduce **trong cùng một môi
trường**.

Ba kênh reproducibility:

1. **Random seed policy**: `framework.random_seed.default` + per-algorithm
   override (`per_algorithm_override`) + per-experiment override
   (`ExperimentSpec.seed_override`). Adapter nào advertise
   `supports_random_state() == True` sẽ được runner inject seed.
2. **Config SHA-256**: text SHA-256 của YAML file được lưu trong
   `ExperimentResult.config_sha256`.
3. **Environment snapshot**: Python version, OS release, machine, library
   versions (numpy, pandas, scipy, scikit-learn, pyarrow).

### 3.3. Standardized pipeline

Quy trình thống nhất cho mọi clustering experiment trong EPIC-06:

```
Dataset → Validation → Algorithm → Configuration → Fit
       → Cluster Assignment → ClusterResult → Artifact
       → ExperimentResult → Experiment Log JSON
```

Mỗi bước đều có implementation trong framework:

| Bước | Module ML-01 |
|------|--------------|
| Dataset load (callers làm) | (ngoài framework) |
| Validation | `validation.py` → `validate_clustering_matrix`, `validate_customer_alignment` |
| Algorithm resolution | `registry.py` → `AlgorithmRegistry.get(name)` |
| Adapter construction | `runner.py` → `ExperimentRunner._build_adapter` |
| Seed resolution | `runner.py` → `resolve_random_seed` |
| Fit | adapter `.fit(X)` (mỗi ML-02 → ML-06 tự định nghĩa) |
| Result build | `result.py` → `ClusterResult`, `ExperimentResult` |
| Artifact write | `artifacts.py` → `write_cluster_labels`, `write_algorithm_output`, `write_experiment_artifacts` |
| Log write | `logging_utils.py` → `write_experiment_log` |

### 3.4. Algorithm abstraction

Mọi concrete algorithm adapter phải subclass `BaseClusterAlgorithm` và định
nghĩa:

```python
class MyAlgorithm(BaseClusterAlgorithm):
    name = "my_algo"            # stable, lowercase
    version = "sklearn_1.x"     # implementation / library version
    family = AlgorithmFamily.HARD  # hard / density_based / model_based / fuzzy

    def __init__(self, ...): ...
    def fit(self, X: np.ndarray) -> ClusterResult: ...
```

Adapter **không được**:

- mutate `X` (framework truyền `X = matrix_df.to_numpy(dtype=np.float64, copy=False)`);
- tự ghi file (để runner xử lý);
- tự log framework-level message (chỉ log nội bộ nếu cần).

### 3.5. Algorithm registry

In-process map `name → adapter class`, tránh duplicate registration.

```python
AlgorithmRegistry.register("my_algo")(MyAlgorithmAdapter)
cls = AlgorithmRegistry.get("my_algo")
```

Đăng ký trùng tên → `AlgorithmRegistryError`. `AlgorithmRegistry.clear()`
chỉ dành cho test.

### 3.6. Configuration

YAML schema, fail-fast loader (`FrameworkConfigError`), framework section
(`clustering.framework.*`) tách biệt với algorithm section
(`clustering.algorithms.*`). ML-01 chỉ parse `clustering.framework.*`; mỗi
algorithm adapter parse slice của mình.

### 3.7. Experiment result schema

- `ClusterResult` — output của một adapter.fit: cluster labels + soft output
  (nếu có) + extras + metrics placeholders.
- `MetricsResult` — schema cho silhouette / DBI / CH / WCSS / stability /
  runtime; ML-01 để tất cả field = `None` (EPIC-07/08 sẽ populate).
- `ExperimentResult` — wrapper end-to-end: experiment_id, status, dataset
  SHA, config SHA, seed, n_clusters, execution_time, cluster_result, metrics,
  artifact_paths, error (nếu FAILED), platform, library_versions, scope_boundaries,
  pending_review_notes, assumptions.

### 3.8. Validation policy

- Matrix checks (`validate_clustering_matrix`): dataset exists, required
  features, no identifier in matrix, all numeric, no NaN, no Inf, no constant
  features, min samples, min features.
- Customer alignment checks (`validate_customer_alignment`): metadata
  present, row alignment, customer_key present, customer_key unique, no NaN.

`IdentifierLeakageError` được raise ngay khi identifier leakage xảy ra
(không nuốt vào FAILED). Các validation fail khác được capture trong
`ValidationReport`; runner trả `ExperimentResult(status=FAILED, error=...)`.

### 3.9. Reproducibility metadata

Bắt buộc có trong `ExperimentResult`:

- `input_sha256` (SHA-256 của input parquet)
- `config_sha256` (SHA-256 của YAML config)
- `random_seed` (requested) + `random_seed_used` (consumed)
- `platform` (Python, OS, machine)
- `library_versions` (numpy, pandas, scipy, scikit-learn, pyarrow)
- `timestamp` (ISO-8601 UTC)

### 3.10. Logging & artifact management

- `[ML-01] <timestamp> [LEVEL] <message>` format (stderr handler + optional
  file handler).
- Artifact paths theo template `{experiment_id}` để nhiều experiment có thể
  cùng tồn tại trong một directory.
- Trên `status=FAILED`: chỉ ghi `experiment_log_*.json`; KHÔNG ghi
  `cluster_labels_*.parquet`.

---

## 4. Phương pháp / Methodology

### 4.1. Dữ liệu sử dụng

| File | Vai trò | SHA-256 (FE-06 evidence) | Shape |
|------|---------|--------------------------|-------|
| `data/processed/final_clustering_dataset.parquet` | Numeric feature matrix, 14 cột, KHÔNG chứa CustomerID | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `(4371, 14)` |
| `data/processed/customer_metadata.parquet` | CustomerID mapping | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `(4371, 1)` với cột `CustomerID` |

Dataset version mặc định: `FE06-v1.0` (ghi trong `configs/clustering.yaml`
dưới `framework.input.dataset_version`).

**Feature set (14 features):** `Recency`, `Frequency`, `Monetary`,
`TotalQuantity`, `AverageQuantity`, `BasketSize`, `TenureDays`,
`PurchaseIntervalMean`, `PurchaseIntervalStd`, `ActiveDays`,
`AverageInvoiceValue`, `ProductsPerInvoice`, `CancellationRate`,
`ReturnRate`. (FE-06 evidence: `reports/fe06/feature_eligibility.csv`.)

### 4.2. Preprocessing

ML-01 KHÔNG thực hiện preprocessing. Verify input đã qua FE-06 pipeline:

- `reports/fe06/fe06_run.json` → `validations`: tất cả PASS (`row_count`,
  `no_identifier_in_matrix`, `no_nan`, `no_inf`, `no_constant_feature`,
  `all_numeric`, `customer_metadata_alignment`).
- Matrix 4371 rows × 14 numeric columns, không chứa identifier, không NaN,
  không Inf, không constant feature.

### 4.3. Algorithm / configuration

ML-01 không tự định nghĩa algorithm hyperparameter. Configuration schema ở
`configs/clustering.yaml`:

```yaml
clustering:
  framework:
    enabled: true
    experiment:
      id: "ML-01-framework-template"
      description: "..."
    random_seed:
      default: 42
      per_algorithm_override: {}
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

Per-algorithm hyperparameters (`clustering.algorithms.*`) là slice của ML-02
→ ML-06 (xem các Mentor document tương ứng).

### 4.4. Cách chạy

ML-01 không có entry point standalone. Caller code (do ML-02 → ML-06 hoặc
EPIC-07 cung cấp) sẽ:

```python
from customer_segmentation.clustering import (
    ExperimentRunner, ExperimentSpec,
    load_framework_config, resolve_framework_config_path,
    compute_text_sha256,
)

cfg = load_framework_config(resolve_framework_config_path())
cfg_text = cfg_path.read_text(encoding="utf-8")

spec = ExperimentSpec(
    experiment_id="ML-XX-...",
    algorithm="kmeans",      # hoặc agglomerative / dbscan / gmm / fuzzy_cmeans
    hyperparameters={"n_clusters": 4},
    seed_override=None,
)

runner = ExperimentRunner(
    cfg, spec,
    config_source=f"yaml:{cfg_path}",
    config_text=cfg_text,
)
result = runner.run(
    matrix_df,
    customer_metadata_df,
    input_sha256="...",
    input_path="...",
    metadata_path="...",
    output_dir=artifacts_dir,
)
```

Workflow: load framework config → build ExperimentSpec → ExperimentRunner.run
→ write artifacts.

### 4.5. Cách lưu kết quả

Artifact paths theo `framework.output` config:

- `cluster_labels_{experiment_id}.parquet` — CustomerID + ClusterLabel +
  IsNoise (+ Probability_k columns cho soft clustering, Membership_k columns
  cho fuzzy clustering).
- `algorithm_output_{experiment_id}.parquet` — soft probability matrix /
  membership matrix (chỉ cho GMM / FCM; KHÔNG tạo cho hard / density-based).
- `experiment_log_{experiment_id}.json` — full `ExperimentResult.to_dict()`.

### 4.6. Cách đảm bảo reproducibility

- `experiment_log` ghi input SHA, output SHA (qua `artifact_paths`),
  config SHA, seed requested + seed used, library versions, platform info.
- Random seed policy: `framework.random_seed.default` + per-algorithm
  override (`per_algorithm_override`) + per-experiment override
  (`ExperimentSpec.seed_override`). Seed chỉ được pass xuống adapter nếu
  `adapter.supports_random_state()` trả về `True`.
- Determinism: nếu adapter advertise `supports_random_state=True` và caller
  cung cấp seed qua YAML hoặc `ExperimentSpec`, runner inject seed. Nếu
  adapter advertise `False` (Agglomerative n_clusters mode, DBSCAN), runner
  set `seed_to_pass = None` và log "Algorithm does not support random_state".

### 4.7. Bảng phân loại decision (BẮT BUỘC)

| Loại decision | Nội dung | Status | Bằng chứng / Nguồn |
|---------------|----------|--------|---------------------|
| TECHNICALLY_IMPLEMENTED | `BaseClusterAlgorithm` abstract class | Implemented | `src/customer_segmentation/clustering/base.py` |
| TECHNICALLY_IMPLEMENTED | `AlgorithmRegistry` in-process map | Implemented | `src/customer_segmentation/clustering/registry.py` |
| TECHNICALLY_IMPLEMENTED | `ClusterResult`, `MetricsResult`, `ExperimentResult` dataclasses | Implemented | `src/customer_segmentation/clustering/result.py` |
| TECHNICALLY_IMPLEMENTED | `validate_clustering_matrix`, `validate_customer_alignment` | Implemented | `src/customer_segmentation/clustering/validation.py` |
| TECHNICALLY_IMPLEMENTED | `FrameworkConfig` YAML loader | Implemented | `src/customer_segmentation/clustering/config.py` |
| TECHNICALLY_IMPLEMENTED | `ExperimentRunner` end-to-end orchestration | Implemented | `src/customer_segmentation/clustering/runner.py` |
| TECHNICALLY_IMPLEMENTED | `write_cluster_labels`, `write_algorithm_output`, `write_experiment_artifacts` | Implemented | `src/customer_segmentation/clustering/artifacts.py` |
| TECHNICALLY_IMPLEMENTED | `get_logger`, `setup_file_logging`, `write_experiment_log` | Implemented | `src/customer_segmentation/clustering/logging_utils.py` |
| TECHNICALLY_IMPLEMENTED | Framework tests (59 tests) | Implemented + passed | `tests/test_ml01_framework.py` |
| WORKING_ASSUMPTION | `framework.metadata.stage_status: TECHNICALLY_IMPLEMENTED` | Working assumption | `configs/clustering.yaml` |
| WORKING_ASSUMPTION | `framework.metadata.scope_boundaries` list | Working assumption | `configs/clustering.yaml` |
| WORKING_ASSUMPTION | `framework.metadata.pending_review_notes` list | Working assumption | `configs/clustering.yaml` |
| PENDING_REVIEW | Methodology: `MetricsResult` placeholder shape (silhouette / DBI / CH / WCSS / stability / runtime / extra) | MENTOR_REVIEW_PENDING | `src/customer_segmentation/clustering/result.py` (xem Section 11) |
| PENDING_REVIEW | Methodology: CustomerID positional alignment contract (vs key-based) | MENTOR_REVIEW_PENDING | `src/customer_segmentation/clustering/validation.py` (xem Section 11) |
| PENDING_REVIEW | Methodology: Visualization ownership split (EPIC-06 diagnostic / EPIC-08 research / EPIC-09 segment) | MENTOR_REVIEW_PENDING | EPIC06_DOCUMENTATION_CONTRACT §9 (xem Section 11) |
| PENDING_REVIEW | Methodology: Framework interfaces shape (`BaseClusterAlgorithm`, `AlgorithmRegistry`, `ClusterResult`, `ExperimentResult`) | MENTOR_REVIEW_PENDING | EPIC06_DOCUMENTATION_CONTRACT §1.2 (xem Section 11) |
| OUT_OF_SCOPE | Compute evaluation metrics (silhouette / DBI / CH / WCSS) | Explicit | EPIC-07/08 ownership |
| OUT_OF_SCOPE | Pick "best" algorithm or rank algorithms | Explicit | AGENTS.md §2.5 |
| OUT_OF_SCOPE | Run controlled sweep (algorithm × k × seed × config) | Explicit | EPIC-07 ownership |
| OUT_OF_SCOPE | Visualize research-grade plots (silhouette plot, comparison dashboard) | Explicit | EPIC-08 ownership |
| OUT_OF_SCOPE | Customer segment profiling / naming | Explicit | EPIC-09 ownership |
| OUT_OF_SCOPE | Mutate FE-06 outputs | Explicit | AGENTS.md §2.3 + framework contract |

---

## 5. Implementation

### 5.1. Module structure

```
src/customer_segmentation/clustering/
├── __init__.py            # Public API re-exports
├── base.py                # BaseClusterAlgorithm (abstract), ClusterAlgorithmError
├── registry.py            # AlgorithmRegistry (in-process)
├── result.py              # ClusterResult, MetricsResult, ExperimentResult
├── validation.py          # validate_clustering_matrix, validate_customer_alignment
├── config.py              # FrameworkConfig loader (configs/clustering.yaml)
├── logging_utils.py       # get_logger, write_experiment_log
├── artifacts.py           # write_cluster_labels, write_algorithm_output
└── runner.py              # ExperimentRunner (end-to-end)
```

`kmeans.py`, `agglomerative.py`, `dbscan.py`, `gmm.py`, `fuzzy_cmeans.py`,
`kmedoids.py` là adapter modules của ML-02 → ML-06 (xem các Mentor document
tương ứng); ML-01 chỉ reference chúng qua `__init__.py`.

### 5.2. Class hierarchy (rút gọn)

```
BaseClusterAlgorithm (abstract)
    │
    ├── name: str
    ├── version: str
    ├── family: str  (AlgorithmFamily)
    ├── fit(X) -> ClusterResult                       [abstract]
    ├── get_params() -> dict                          [default impl]
    ├── get_model() -> object | None                  [default impl]
    └── supports_random_state() -> bool               [default True]

ClusterResult
    ├── algorithm / algorithm_version / algorithm_family
    ├── n_samples / n_features
    ├── cluster_labels: np.ndarray
    ├── n_clusters: int | None
    ├── soft_probabilities: np.ndarray | None         # GMM
    ├── soft_membership: np.ndarray | None           # FCM
    ├── noise_label / noise_count / noise_ratio       # DBSCAN
    ├── supports_random_state / random_seed_used
    ├── extra: dict                                   # algorithm-specific
    └── metrics: MetricsResult                        # placeholder

ExperimentResult
    ├── experiment_id, status (SUCCESS | FAILED)
    ├── algorithm, algorithm_version
    ├── dataset_version, dataset_sha256
    ├── input_path, metadata_path
    ├── feature_set, feature_count, n_samples
    ├── hyperparameters, random_seed, random_seed_used
    ├── cluster_result: ClusterResult | None
    ├── execution_time, timestamp
    ├── metrics: MetricsResult
    ├── artifact_paths: dict
    ├── error: dict | None                           # populated on FAILED
    ├── platform: dict
    ├── library_versions: dict
    ├── scope_boundaries, pending_review_notes, assumptions
    └── config_source, config_sha256

AlgorithmRegistry
    ├── register(name) -> decorator
    ├── get(name) -> class
    ├── list_registered() -> list[str]
    ├── is_registered(name) -> bool
    └── clear()                                       # tests only

ExperimentRunner
    └── run(matrix_df, metadata_df, ...) -> ExperimentResult
```

### 5.3. Pipeline (end-to-end)

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
            │           (skip if adapter.supports_random_state() == False)
            ├── fit(X)  → ClusterResult (or FAILED)
            ├── build ExperimentResult
            ├── write artifacts (cluster_labels, experiment_log, algorithm_output)
            └── return ExperimentResult
```

### 5.4. Interface (`BaseClusterAlgorithm`)

```python
class BaseClusterAlgorithm(ABC):
    name: str = ""
    version: str = ""
    family: str = ""

    @abstractmethod
    def fit(self, X: np.ndarray) -> ClusterResult: ...

    def get_params(self) -> dict[str, Any]: ...        # default impl
    def get_model(self) -> Any: ...                    # default impl
    def supports_random_state(self) -> bool: ...       # default True
```

`name`, `version`, `family` là class-level attributes, set bởi registry khi
register hoặc bởi subclass.

### 5.5. Configuration

`configs/clustering.yaml` schema đã trình bày ở §4.3. Loader:

```python
from customer_segmentation.clustering import (
    load_framework_config,
    resolve_framework_config_path,
)

cfg = load_framework_config(resolve_framework_config_path())
```

Loader fail-fast với `FrameworkConfigError` nếu YAML thiếu key hoặc
`framework.enabled=false`.

### 5.6. Input/output contract

**Input:** `matrix_df` (pandas DataFrame, numeric, không chứa identifier, không
NaN/Inf, không constant feature) + `customer_metadata_df` (CustomerID, không
NaN, unique, len = len(matrix_df)).

**Output (`ClusterResult`):**
- `cluster_labels`: shape `(n_samples,)`, dtype `int64`.
- `n_clusters`: int hoặc None.
- `soft_probabilities` (GMM): shape `(n_samples, n_components)`, dtype `float64`.
- `soft_membership` (FCM): shape `(n_samples, c)`, dtype `float64`.
- `noise_label` / `noise_count` / `noise_ratio` (DBSCAN): noise label = `-1`.
- `metrics`: MetricsResult tất cả field = `None`.

**Output (`ExperimentResult`):** chứa `cluster_result` + experiment-level
metadata.

### 5.7. Validation

| Check name | Mô tả | Strict mode |
|------------|-------|-------------|
| `dataset_exists` | DataFrame không None, không empty | fail-fast |
| `required_features` | Mọi expected feature có trong DataFrame | fail-fast |
| `no_identifier_in_matrix` | Không có CustomerID / InvoiceNo / ... trong matrix | **raise `IdentifierLeakageError`** |
| `all_numeric` | Mọi cột là numeric | fail-fast |
| `no_nan` | Không có NaN | fail-fast |
| `no_inf` | Không có Inf | fail-fast |
| `no_constant_feature` | Variance > 0 | fail-fast |
| `min_samples` | n_samples >= threshold | fail-fast |
| `min_features` | n_features >= threshold | fail-fast |
| `metadata_present` | Metadata không None, không empty | fail-fast |
| `metadata_row_alignment` | len(metadata) == len(matrix) | fail-fast |
| `customer_key_present` | customer_key tồn tại trong metadata | fail-fast |
| `customer_key_unique` | customer_key unique 100% | fail-fast |
| `customer_key_no_nan` | customer_key không có NaN | fail-fast |

### 5.8. Artifacts (chỉ framework — KHÔNG có production artifact của ML-01)

ML-01 framework **không tự sinh** `cluster_labels_*.parquet` / `experiment_log_*.json`;
đây là output của ML-02 → ML-06 khi chạy qua `ExperimentRunner`. ML-01 chỉ
cung cấp schema + writer functions (`write_cluster_labels`,
`write_algorithm_output`, `write_experiment_artifacts`).

### 5.9. Pseudocode cho resolve_random_seed

```python
def resolve_random_seed(cfg, algorithm_name, override=None):
    if override is not None:
        return override, override
    algo_override = cfg.random_seed.per_algorithm_override.get(algorithm_name)
    if algo_override is not None:
        return algo_override, algo_override
    default = cfg.random_seed.default
    return default, default
```

Trong `ExperimentRunner.run`, sau khi resolve seed, nếu
`adapter.supports_random_state() == False`, runner set `seed_to_pass = None`
và log "Algorithm does not support random_state".

---

## 6. Experimental Design Boundary

| | EPIC-06 (ML-01 framework) | EPIC-07 | EPIC-08 | EPIC-09 |
|---|----------------------------|---------|---------|---------|
| **Algorithm implementation** | ✅ Framework interface + base class + registry | — | — | — |
| **Configuration** | ✅ Framework YAML schema + loader | Sweep matrix | — | — |
| **Single-fit experiment** | ✅ Adapter pattern cho từng fit | Batch | — | — |
| **Sweep nhiều k** | ❌ | ✅ | — | — |
| **Sweep nhiều seed** | ❌ | ✅ | — | — |
| **Sweep nhiều config** | ❌ | ✅ | — | — |
| **Compute internal metrics** | ❌ | Partial (per fit) | ✅ Final | — |
| **Stability (ARI/AMI)** | ❌ | Generate | ✅ Aggregate | — |
| **Runtime comparison** | ❌ | Per-run time | ✅ Statistical summary | — |
| **Algorithm comparison** | ❌ | — | ✅ | — |
| **Diagnostic viz (dendrogram, k-distance, BIC, membership hist)** | ⚠️ Optional per-task (ML-02 → ML-06) | — | — | — |
| **Research viz (silhouette, DBI, CH, elbow)** | ❌ | — | ✅ | — |
| **Segment profile / naming** | ❌ | — | — | ✅ |
| **Pick best algorithm** | ❌ | — | ✅ (sau full eval) | — |
| **Customer profiling** | ❌ | — | — | ✅ |

**Quy tắc rút ra:**

- ML-01 KHÔNG compute evaluation metrics, KHÔNG sweep, KHÔNG so sánh, KHÔNG
  visualize research-grade plots, KHÔNG profile customer.
- ML-01 chỉ cung cấp framework để EPIC-07/08/09 consume.
- ML-01 KHÔNG có diagnostic viz của riêng nó; diagnostic viz là của từng
  ML-02 → ML-06 (optional).

---

## 7. Kết quả thực tế

ML-01 framework **không tự chạy** clustering experiment; nó chỉ là code +
tests + documentation. Vì vậy ML-01 không có artifact clustering run nào.
Bảng dưới đây tổng hợp evidence thực tế của framework và dataset input mà
ML-01 consume từ FE-06:

| Loại kết quả | Giá trị / evidence | Nguồn |
|--------------|---------------------|--------|
| Số customers (n_samples) | 4371 | `data/processed/final_clustering_dataset.parquet` (FE-06 evidence: `reports/fe06/fe06_run.json`) |
| Số features (n_features) | 14 | `data/processed/final_clustering_dataset.parquet`; `reports/fe06/feature_eligibility.csv` |
| Feature names | `Recency`, `Frequency`, `Monetary`, `TotalQuantity`, `AverageQuantity`, `BasketSize`, `TenureDays`, `PurchaseIntervalMean`, `PurchaseIntervalStd`, `ActiveDays`, `AverageInvoiceValue`, `ProductsPerInvoice`, `CancellationRate`, `ReturnRate` | `reports/fe06/feature_eligibility.csv` |
| Final clustering matrix SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | `reports/fe06/fe06_run.json` → `output.final_clustering_dataset_sha256` |
| Customer metadata SHA-256 | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | `reports/fe06/fe06_run.json` → `output.customer_metadata_sha256` |
| Dataset version | `FE06-v1.0` | `reports/fe06/fe06_run.json`; `configs/clustering.yaml` |
| Framework stage version | `ML01-v1.0` | `configs/clustering.yaml` → `framework.metadata.stage_version` |
| Framework stage status | `TECHNICALLY_IMPLEMENTED` | `configs/clustering.yaml` → `framework.metadata.stage_status` |
| Số framework tests | 59 | `tests/test_ml01_framework.py` (collect count: 59) |
| Số framework tests pass | 59 / 59 | `pytest tests/test_ml01_framework.py -v` |
| Library versions (tại thời điểm FE-06 run) | numpy `2.3.5`, pandas `3.0.6`, scipy `1.18.1`, scikit-learn `1.9.1`, pyarrow `25.0.1` | `reports/fe06/fe06_run.json` → `library_versions` |

**Lưu ý về evidence định lượng:**

- ML-01 framework không sinh ra số liệu clustering (n_clusters, runtime, WCSS,
  silhouette, v.v.). Những con số đó thuộc về ML-02 → ML-06 (xem các
  Mentor document tương ứng).
- ML-01 chỉ record các con số "framework-level" (số modules, số tests, số
  validation checks). Những con số này truy được từ code và `pytest`
  output, không từ clustering run.

---

## 8. Công thức và ký hiệu

ML-01 là framework — nó không tự optimize một objective cụ thể. Phần
notation dưới đây cover các framework-level formulas / conventions. Per-task
formulas (K-Means, Agglomerative, DBSCAN, GMM, FCM) nằm ở ML-02 → ML-06.

### 8.1. Ký hiệu chung (áp dụng cho cả EPIC-06)

| Symbol | Ý nghĩa |
|--------|----------|
| `n` | Số customers (samples) |
| `p` | Số features |
| `X ∈ ℝ^(n×p)` | Feature matrix |
| `x_i ∈ ℝ^p` | Vector feature của customer `i` |
| `K`, `k`, `c` | Số cluster (tùy algorithm) |
| `μ_k ∈ ℝ^p` | Centroid của cluster `k` (K-Means, FCM) |
| `c_i ∈ {0, ..., K-1}` | Cluster label của point `i` (hard clustering) |
| `u_ik ∈ [0, 1]` | Membership degree của point `i` trong cluster `k` (FCM) |
| `Σ_k ∈ ℝ^(p×p)` | Covariance matrix của component `k` (GMM) |
| `π_k` | Mixing weight của component `k` (GMM) |
| `eps` | Epsilon neighborhood radius (DBSCAN) |
| `min_samples` | Minimum points in eps neighborhood (DBSCAN) |
| `seed` / `random_state` | Random seed |

### 8.2. Framework-level formulas

| Concept | Notation | Ý nghĩa |
|---------|----------|----------|
| Validation check name | `name: str` | Tên của validation check (`dataset_exists`, `no_nan`, ...) |
| Validation check status | `status: str ∈ {"PASS", "FAIL"}` | Trạng thái của check |
| Validation report aggregated | `all_passed = all(status == "PASS")` | Tổng hợp; False → runner trả FAILED |
| Identifier leakage detection | `_FORBIDDEN_IDENTIFIERS = {CustomerID, InvoiceNo, InvoiceDate, StockCode, Description, Country}` | Hard-coded FE-06 identifier set |
| CustomerID positional alignment | `len(metadata) == len(matrix)` AND `metadata[customer_key].is_unique` | Row `i` của cluster_labels ↔ row `i` của metadata |
| Random seed resolution | `seed_used = override if override else per_algo_override[algo] if exists else default` | Trả (requested, seed_used) |
| Config SHA-256 | `sha256(config_text.encode("utf-8"))` | Lưu trong `ExperimentResult.config_sha256` |
| Input SHA-256 | `sha256(file contents)` | Lưu trong `ExperimentResult.dataset_sha256` |
| Artifact filename template | `"{name}_{experiment_id}.{ext}"` | Nhiều experiment có thể cùng tồn tại |
| Cluster result → JSON-friendly | `cluster_result.to_dict()` (numpy arrays → shape / dtype / first_5 metadata) | Lưu trong experiment log JSON |
| Status semantics | `SUCCESS` ↔ `adapter.fit()` trả ClusterResult hợp lệ; `FAILED` ↔ exception hoặc validation fail | Algorithm exception KHÔNG propagate lên caller |

### 8.3. Per-task formulas (tham chiếu)

ML-01 không tự định nghĩa per-task objective. Công thức cho K-Means, Agglomerative,
DBSCAN, GMM, FCM xem ML-02 → ML-06:

- **ML-02 K-Means**: `J = Σ_i ‖x_i - μ_{c_i}‖²` (Lloyd's algorithm).
- **ML-03 Agglomerative**: `d(C₁, C₂)` per linkage.
- **ML-04 DBSCAN**: density-reachability, eps neighborhood, min_samples.
- **ML-05 GMM**: `log L(θ) = Σ_i log Σ_k π_k · N(x_i; μ_k, Σ_k)` (EM).
- **ML-06 FCM**: `J_m = Σ_i Σ_k (u_ik)^m · ‖x_i - v_k‖²` (membership + centroid update).

---

## 9. Visualization boundary

### 9.1. EPIC-06 (ML-01 framework — KHÔNG có viz)

ML-01 framework **KHÔNG tạo visualization** nào. Không có diagnostic viz nào
thuộc về framework.

### 9.2. EPIC-06 (per-task diagnostic viz — tùy ML-02 → ML-06)

| Task | Visualization (optional) | Loại | Status |
|------|--------------------------|------|--------|
| ML-02 K-Means | Elbow / WCSS diagnostic plot | Diagnostic | Optional |
| ML-03 Agglomerative | Dendrogram, linkage matrix visualization, distance heatmap | Diagnostic | Optional |
| ML-04 DBSCAN | k-distance plot để chọn eps | Diagnostic | Optional |
| ML-05 GMM | BIC / AIC curve theo số components | Diagnostic | Optional |
| ML-06 FCM | Membership distribution per cluster | Diagnostic | Optional |

**Hiện trạng evidence trong EPIC-06:**

- ML-02 K-Means: elbow / WCSS plot **CHƯA ĐƯỢC TẠO** trong EPIC-06
  (xem ML-02 Mentor document §9).
- ML-03 Agglomerative: dendrogram **CHƯA ĐƯỢC TẠO** trong EPIC-06; merge
  distance summary đã được capture trong `ClusterResult.extra`
  (`max_merge_distance`, `min_merge_distance`, `median_merge_distance`,
  `merge_distances_summary`) nhưng KHÔNG phải dendrogram visualization
  (xem ML-03 Mentor document §9).
- ML-04 DBSCAN: k-distance plot **CHƯA ĐƯỢC TẠO** trong EPIC-06 (xem ML-04
  Mentor document §9).
- ML-05 GMM: BIC / AIC curve **CHƯA ĐƯỢC TẠO** trong EPIC-06; AIC / BIC
  đã được record là diagnostics only trong `ClusterResult.extra` (xem ML-05
  Mentor document §9).
- ML-06 FCM: membership distribution per cluster **CHƯA ĐƯỢC TẠO** trong
  EPIC-06; `membership_confidence_min/max/mean` đã được record là
  diagnostics only trong `ClusterResult.extra` (xem ML-06 Mentor document §9).

### 9.3. EPIC-08 (research comparison)

EPIC-08 sở hữu:

- Silhouette plot / silhouette comparison across algorithms & k.
- Davies-Bouldin comparison.
- Calinski-Harabasz comparison.
- WCSS / Elbow plot (cho analysis, không phải diagnostic).
- Runtime comparison across algorithms.
- Stability (ARI / AMI) distribution plot.
- Parameter sensitivity heatmap.
- Algorithm comparison (multi-metric dashboard).

### 9.4. EPIC-09 (segment analysis)

EPIC-09 sở hữu:

- Segment size (số customer / segment).
- RFM profile (radar / heatmap) theo segment.
- Feature distribution theo segment.
- Boxplot (numeric features × segments).
- Segment characteristics table / chart.
- Customer profiles (per-segment summary).

### 9.5. Quy tắc tổng quát

- KHÔNG tạo visualization trong `reports/ml01/` (ML-01 không có viz).
- KHÔNG tự tạo hình trong Documentation Contract — chỉ list loại viz thực sự
  được tạo trong implementation.
- Mỗi visualization thực sự tạo phải có SHA-256 / file path / generation
  metadata.

---

## 10. Verification

### 10.1. Tests

| Test category | File | Số test | Trạng thái |
|---------------|------|---------|------------|
| Unit tests cho framework | `tests/test_ml01_framework.py` | 59 | **PASS** (verified bằng `pytest`) |
| Test class `TestBaseAlgorithm` | `tests/test_ml01_framework.py::TestBaseAlgorithm` | (subset) | PASS |
| Test class `TestRegistry` | `tests/test_ml01_framework.py::TestRegistry` | (subset) | PASS |
| Test class `TestValidation` | `tests/test_ml01_framework.py::TestValidation` | (subset) | PASS |
| Test class `TestCustomerAlignment` | `tests/test_ml01_framework.py::TestCustomerAlignment` | (subset) | PASS |
| Test class `TestResultSchema` | `tests/test_ml01_framework.py::TestResultSchema` | (subset) | PASS |
| Test class `TestReproducibility` | `tests/test_ml01_framework.py::TestReproducibility` | (subset) | PASS |
| Test class `TestRunner` | `tests/test_ml01_framework.py::TestRunner` | (subset) | PASS |
| Test class `TestArtifactWriting` | `tests/test_ml01_framework.py::TestArtifactWriting` | (subset) | PASS |
| Test class `TestConfig` | `tests/test_ml01_framework.py::TestConfig` | (subset) | PASS |
| Test class `TestSeedResolution` | `tests/test_ml01_framework.py::TestSeedResolution` | (subset) | PASS |
| Test class `TestEnvironmentSnapshots` | `tests/test_ml01_framework.py::TestEnvironmentSnapshots` | (subset) | PASS |
| Test class `TestLogger` | `tests/test_ml01_framework.py::TestLogger` | (subset) | PASS |
| Test class `TestIntegrationWithFE06` | `tests/test_ml01_framework.py::TestIntegrationWithFE06` | (subset) | PASS |

Verification command:

```bash
python3 -m pytest tests/test_ml01_framework.py -v
```

Verification result: **59 / 59 passed** (verified trong session này).

Adapter dùng trong framework tests là **toy algorithm**
(`ToyHardAlgorithm`, `ToyNoiseAlgorithm`, `ToySoftAlgorithm`,
`ToyFailingAlgorithm`, `ToyDeterministicAlgorithm`). ML-02 → ML-06 sẽ thay
bằng production adapter; ML-01 không test production adapter (đó là việc
của ML-02 → ML-06).

### 10.2. Lint

```bash
ruff check src/customer_segmentation/clustering/
```

Result: **All checks passed!** (verified trong session này với `ruff 0.16.8`).

### 10.3. Format

```bash
black --check src/customer_segmentation/clustering/
```

Result: **15 files would be left unchanged** (verified trong session này
với `black 26.5.1`).

### 10.4. Reproducibility

ML-01 framework không tự produce clustering output, nên không có
"output SHA-256" của ML-01. Reproducibility của ML-01 framework:

- **Input SHA-256 unchanged**: FE-06 outputs `final_clustering_dataset.parquet`
  và `customer_metadata.parquet` không bị ML-01 mutate (framework ở
  READ-ONLY mode).
- **Config SHA-256 recorded**: trong `ExperimentResult.config_sha256`.
- **Library versions recorded**: trong `ExperimentResult.library_versions`.

ML-01 chỉ capture metadata; reproducibility của clustering output thuộc về
ML-02 → ML-06.

### 10.5. Input integrity

ML-01 framework không trực tiếp load input; việc này do caller (ML-02 → ML-06
script) làm. Tuy nhiên framework cung cấp `validate_clustering_matrix` để
verify input đã qua FE-06 pipeline. Test class `TestValidation` cover:

- None dataset → FAIL.
- Empty dataset → FAIL.
- NaN in matrix → FAIL.
- Inf in matrix → FAIL.
- Non-numeric column → FAIL.
- Identifier leakage → raise `IdentifierLeakageError`.
- Constant feature → FAIL.
- min_samples / min_features threshold → FAIL.
- fail_fast mode toggle.

### 10.6. Output integrity

ML-01 framework không tự produce output; output integrity test thuộc về
ML-02 → ML-06. Tuy nhiên test class `TestArtifactWriting` cover:

- CustomerID alignment (positional) giữa matrix và cluster_labels parquet.
- DBSCAN noise label `-1` preserved verbatim.
- Soft output (GMM probability / FCM membership) parquet đúng schema.

### 10.7. Regression status

- Pre-existing tests còn pass: không có test nào bị skip không giải thích
  trong `tests/test_ml01_framework.py`.
- Không có pre-existing failure chưa được giải thích trong framework tests.

---

## 11. Mentor Review

Bảng tổng hợp các decision cần mentor review (methodology / engineering /
scope). Phân loại theo EPIC06_DOCUMENTATION_CONTRACT §11.

| ID | Nội dung cần review | Loại | Trạng thái |
|----|---------------------|------|------------|
| ML-01-MET-01 | Framework interfaces shape (`BaseClusterAlgorithm`, `AlgorithmRegistry`, `ClusterResult`, `ExperimentResult`) — schema này định nghĩa shape của mọi output clustering, kéo theo cách EPIC-07/08 consume | Methodology | PENDING_REVIEW |
| ML-01-MET-02 | CustomerID positional alignment contract (cluster_labels row `i` ↔ metadata row `i`) — hiện tại positional; key-based sẽ đổi semantics | Methodology | PENDING_REVIEW |
| ML-01-MET-03 | Metrics placeholder shape (`silhouette`, `davies_bouldin`, `calinski_harabasz`, `wcss`, `stability`, `runtime`, `extra`) — định nghĩa bộ metric nào sẽ tồn tại trong evaluation | Methodology | PENDING_REVIEW |
| ML-01-MET-04 | Visualization ownership split: EPIC-06 diagnostic / EPIC-08 research comparison / EPIC-09 segment analysis — đã ghi trong §9 nhưng cần mentor confirm trước khi các EPIC sau reference | Methodology / Scope | PENDING_REVIEW |
| ML-01-ENG-01 | Per-algorithm seed override trong YAML — chỉ là escape hatch cho per-experiment control | Engineering | DOCUMENTED (có thể promote final sau engineer review) |
| ML-01-ENG-02 | Artifact filename template (`{experiment_id}`) — chỉ là naming convention | Engineering | DOCUMENTED |
| ML-01-ENG-03 | Noise label mặc định `-1` (sklearn convention) — DBSCAN adapter enforce verbatim | Engineering | DOCUMENTED |

**Ghi chú về promotion:**

- ML-01-MET-01, -02, -03, -04 cần ADR + mentor review **trước khi** ML-02 → ML-06
  hoặc EPIC-07/08/09 reference framework interfaces để downstream changes.
- ML-01-ENG-01, -02, -03 có thể promote final cùng các EPIC sau khi reviewer
  xác nhận không có implicit methodology effect.
- Mọi thay đổi ở ML-01-MET-* phải qua pull request workflow theo
  `AGENTS.md` §4.

---

## 12. Kết luận

### 12.1. Đã hoàn thành

ML-01 framework **TECHNICALLY_IMPLEMENTED** với evidence:

- **Code:** `src/customer_segmentation/clustering/__init__.py`,
  `base.py`, `registry.py`, `result.py`, `validation.py`, `config.py`,
  `artifacts.py`, `logging_utils.py`, `runner.py`. File paths absolute
  trong repository: `src/customer_segmentation/clustering/`.
- **Configuration:** `configs/clustering.yaml` → `clustering.framework.*`
  section.
- **Tests:** `tests/test_ml01_framework.py` — 59 / 59 tests passed
  (verified trong session này).
- **Lint:** `ruff check` pass.
- **Format:** `black --check` pass (15 files unchanged).
- **Dataset input evidence:**
  - `final_clustering_dataset.parquet` SHA-256
    `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
    (FE-06 evidence: `reports/fe06/fe06_run.json`).
  - `customer_metadata.parquet` SHA-256
    `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`
    (FE-06 evidence: `reports/fe06/fe06_run.json`).
  - Dataset version `FE06-v1.0`, n_samples = 4371, n_features = 14,
    CustomerID sống trong `customer_metadata.parquet` chứ không trong matrix
    (FE-06 evidence: `reports/fe06/feature_eligibility.csv`,
    `reports/fe06/fe06_run.json`).

ML-01 chỉ là nền tảng; nó **không tự sinh ra clustering experiment run**
trên dataset thật. ML-01 commit thành công nghĩa là framework + tests +
lint + format đều pass, KHÔNG phải là "đã chạy clustering".

### 12.2. Chưa hoàn thành

- **Production algorithm adapter**: chỉ có toy adapter (`ToyHardAlgorithm`,
  v.v.) cho test. K-Means / K-Medoids / Agglomerative / DBSCAN / GMM / FCM
  production code sẽ do ML-02 → ML-06 deliver (xem ML-02 → ML-06 Mentor
  document).
- **Compute evaluation metrics**: `MetricsResult` toàn field = `None`.
  EPIC-07/08 sẽ compute.
- **Model persistence by default**: `model_artifact_path = None`. ML-02 → ML-06
  có thể set field này trong `ClusterResult.extra` nếu cần persist model.
- **Parallel runner**: chạy tuần tự. EPIC-07 sẽ quyết định parallel sweep.
- **Diagnostic visualization**: ML-01 không có diagnostic viz; per-task
  diagnostic viz là tùy chọn của ML-02 → ML-06.

### 12.3. Pending Mentor Review

Các decision cần mentor xác nhận — liệt kê theo Section 11:

| ID | Quyết định | Trạng thái |
|----|------------|------------|
| ML-01-MET-01 | Framework interfaces shape | PENDING_REVIEW |
| ML-01-MET-02 | CustomerID positional alignment contract | PENDING_REVIEW |
| ML-01-MET-03 | Metrics placeholder shape | PENDING_REVIEW |
| ML-01-MET-04 | Visualization ownership split | PENDING_REVIEW |

### 12.4. Chuyển tiếp sang task tiếp theo

**Output của ML-01 = input cho ML-02 → ML-06:**

- `BaseClusterAlgorithm` interface → mỗi ML-02 → ML-06 subclass và register
  adapter vào `AlgorithmRegistry`.
- `AlgorithmRegistry` → ML-02 → ML-06 dùng `AlgorithmRegistry.get("name")`
  để lookup adapter theo name.
- `ClusterResult`, `ExperimentResult` schema → ML-02 → ML-06 dùng schema
  này để build result và ghi experiment log JSON.
- `ExperimentRunner` → ML-02 → ML-06 dùng `ExperimentRunner(cfg, spec, ...)`
  để chạy experiment end-to-end (validate → fit → write artifacts).
- `validate_clustering_matrix`, `validate_customer_alignment` → ML-02 → ML-06
  runner gọi để verify input trước khi fit.
- `FrameworkConfig` → ML-02 → ML-06 load qua
  `load_framework_config(resolve_framework_config_path())`.

**Contract giữa ML-01 và consumer (downstream):**

| Field | Contract |
|-------|----------|
| `cluster_labels` shape | `(n_samples,)` |
| `cluster_labels` dtype | `int64` |
| `cluster_labels` value (hard) | `[0, K-1]` |
| `cluster_labels` value (DBSCAN) | `[0, K-1] ∪ {-1}` (noise) |
| `soft_probabilities` shape (GMM) | `(n_samples, n_components)` |
| `soft_membership` shape (FCM) | `(n_samples, c)` |
| `noise_label` | `-1` (sklearn convention) |
| `cluster_labels` row order | = `customer_metadata` row order (positional) |

**TUYỆT ĐỐI KHÔNG** trong Mentor document này: KHÔNG viết "best framework",
KHÔNG gọi framework là "final", KHÔNG ranking giữa các adapter
implementation. ML-01 là foundation, KHÔNG là evaluation.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-01 implementation
(code, tests, config) và FE-06 evidence (`reports/fe06/`). Mọi con số trong
tài liệu này đều có provenance rõ ràng. Không có số liệu bịa, không có
experiment bịa, không có best/optimal/recommended/winner claim._