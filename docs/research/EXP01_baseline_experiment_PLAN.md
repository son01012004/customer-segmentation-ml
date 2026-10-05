# PLAN — EXP-01 Baseline Experiment (Revision 1)

> **Mục đích:** Tài liệu này là **implementation PLAN** cho EXP-01, không phải
> Mentor document hoàn chỉnh.
>
> **Revision history:**
> - Revision 0: bản draft ban đầu.
> - Revision 1: sửa theo mentor review (xem §15 cho diff chi tiết).
>
> **TUYỆT ĐỐI KHÔNG** chạy code / tạo file / sửa file / commit / push / PR
> trong bước này.

---

## 1. Phạm vi EXP-01

### 1.1. Mục tiêu

Thiết lập và thực thi một **baseline experiment** thống nhất cho 5 thuật
toán EPIC-06 đã được TECHNICALLY_IMPLEMENTED:

- K-Means (ML-02)
- Hierarchical / Agglomerative (ML-03)
- DBSCAN (ML-04)
- Gaussian Mixture Model (ML-05)
- Fuzzy C-Means (ML-06)

Baseline cung cấp:

- **Mốc tham chiếu thống nhất** (single protocol) cho EPIC-07 sweep.
- **Bảo toàn evidence**: input SHA, config SHA, output SHA, hyperparameters,
  seed, library versions, evaluation metrics (giá trị + status), runtime statistics.
- **Hỗ trợ EPIC-07/EPIC-08** với unified metric schema.

### 1.2. Ranh giới EXP-01

| EXP-01 LÀM | EXP-01 KHÔNG LÀM |
|------------|-------------------|
| Chạy 5 algorithms trên cùng input | Chọn algorithm tốt nhất |
| Ghi nhận unified metrics (silhouette, DBI, CH, WCSS) với status rõ ràng | Ranking algorithm |
| Bảo toàn reproducibility metadata | Hyperparameter tuning |
| Đo runtime algorithm execution (không tính metric/report generation) | Sensitivity analysis |
| Tạo aggregate baseline report ghi nhận observed evidence | "Best" / "winner" / comparative conclusion |
| Tạo stability evidence (cluster labels per algorithm) cho EXP-05 | Stability analysis / ARI/AMI computation (EPIC-08 scope) |
| | Customer profiling / segment naming |

### 1.3. Tiêu chí "thành công" của EXP-01

EXP-01 TECHNICALLY_IMPLEMENTED khi:

1. **5 algorithms** đã chạy thành công qua unified baseline protocol.
2. **Unified metrics** (silhouette, DBI, CH, WCSS) đã được compute và ghi
   vào `MetricsResult` (hiện đang là placeholder) với status metadata.
3. **Runtime protocol** đã được thực thi: phân biệt algorithm execution
   runtime vs metric computation runtime vs artifact/report writing.
4. **Aggregate baseline report** đã được sinh ra.
5. **Tất cả tests** (unit + integration) pass.
6. **Lint + format** pass.
7. **KHÔNG có** "best algorithm" / "winner" claim trong code hoặc reports.

---

## 2. Hiện trạng EPIC-06 (gap analysis)

### 2.1. Những gì đã có thể tái sử dụng

| Component | Status | Tái sử dụng? |
|-----------|--------|--------------|
| `ExperimentRunner` (`runner.py`) | ✅ TECHNICALLY_IMPLEMENTED | **CÓ** — gọi trực tiếp, không sửa |
| `FrameworkConfig` + `load_framework_config` | ✅ | **CÓ** |
| 5 adapters (`kmeans`, `agglomerative`, `dbscan`, `gmm`, `fuzzy_cmeans`) | ✅ TECHNICALLY_IMPLEMENTED | **CÓ** — đăng ký sẵn |
| `ClusterResult` schema | ✅ | **CÓ** — không sửa |
| `ExperimentResult` schema | ✅ | **CÓ** — không sửa |
| `Artifact` writers | ✅ | **CÓ** — không sửa |
| `validate_clustering_matrix` + `validate_customer_alignment` | ✅ | **CÓ** |
| `config_sha256`, `dataset_sha256` provenance | ✅ | **CÓ** |
| `configs/clustering.yaml` working defaults | ✅ | **CÓ** — đọc, không sửa |
| `configs/experiment.yaml` evaluation block | ✅ (template) | **CÓ** — tham khảo |
| K-Means `extra.wcss` (= `inertia_`) | ✅ | **CÓ** — nguồn reference |
| GMM `extra.lower_bound`, `extra.aic`, `extra.bic` | ✅ | **CÓ** — diagnostic |
| FCM `extra.final_objective`, `extra.converged` | ✅ | **CÓ** — diagnostic |
| DBSCAN `extra.noise_count`, `extra.noise_ratio` | ✅ | **CÓ** — algorithm-specific |

### 2.2. Những gì CHƯA có — gap EXP-01

| Component thiếu | Mô tả | Action |
|----------------|-------|--------|
| **Evaluation/metrics module** | Không có code compute `silhouette`, `davies_bouldin`, `calinski_harabasz`. | **CẦN TẠO** `metrics.py` |
| **WCSS universal** | K-Means có `inertia_` nhưng Agglomerative, GMM, FCM không có sẵn. | **CẦN COMPUTE** trong metrics layer |
| **DBSCAN noise handling policy** | Phải định nghĩa rõ noise exclusion cho metrics. | **CẦN ĐỊNH NGHĨA** trong metrics layer |
| **Metric applicability status** | Không có convention cho "metric not applicable". | **CẦN ĐỊNH NGHĨA** status schema |
| **Runtime protocol** | Không phân biệt algorithm execution vs metric computation vs artifact writing. | **CẦN ĐỊNH NGHĨA** trong baseline orchestrator |
| **Baseline orchestrator** | Chưa có module orchestrate 5 algorithms × runtime repetition. | **CẦN TẠO** `baseline.py` + `run_exp01_baseline.py` |
| **Aggregate baseline report** | Chưa có format/schema cho cross-algorithm manifest. | **CẦN TẠO** `reports/exp01/` |
| **Tests cho metrics + baseline** | Chưa có test cho metrics computation và orchestrator. | **CẦN TẠO** `test_metrics.py`, `test_exp01_baseline.py` |

### 2.3. Đánh giá metrics thống nhất

> **Câu hỏi:** "Metrics thống nhất trong EXP-01 có thể thực hiện ngay với code hiện tại hay cần bổ sung evaluation layer/protocol trước?"

**Trả lời:** **CẦN BỔ SUNG evaluation layer trước.** Hiện tại:

- `MetricsResult.silhouette`, `davies_bouldin`, `calinski_harabasz`, `wcss`,
  `stability`, `runtime` đều = `None`.
- Không có module nào thực sự compute các metric này.
- K-Means `extra.wcss` chỉ là inertia, không phải universal WCSS.

---

## 3. Runtime Protocol

### 3.1. Ba loại runtime — phân biệt bắt buộc

| Loại | Định nghĩa | Được ghi vào baseline runtime? |
|------|-------------|--------------------------------|
| **Algorithm execution runtime** | `time.perf_counter()` bao quanh `adapter.fit(X)` duy nhất | **CÓ** — đây mới là metric đo algorithm thuần túy |
| **Metric computation runtime** | Thời gian compute silhouette / DBI / CH / WCSS sau fit | **GHI RIÊNG** trong `metrics.extra.computation_time_seconds` |
| **Artifact/report writing runtime** | Thời gian serialize parquet, JSON, CSV | **KHÔNG** — không ghi vào runtime |

### 3.2. Lý do phân biệt

Mục tiêu của EXP-01 là đo **execution time của algorithm**, không phải
thời gian tổng cộng bao gồm I/O. Nếu cộng metric computation và artifact
writing vào runtime, runtime không còn so sánh được giữa algorithms vì:

- Silhouette/DBI/CH có O(n²) complexity trên mỗi run.
- Artifact writing tỉ lệ với số soft outputs (GMM/FCM có n×K matrix lớn).
- Report generation không liên quan đến algorithm performance.

### 3.3. Runtime repetition

Mỗi (algorithm, k, seed) chạy `n_repeat` lần để:

1. Đo algorithm execution time với statistics (mean / std / min / max).
2. Verify reproducibility: cùng seed → cùng labels (trong tolerance).

**Lưu ý quan trọng:** Repetition này **KHÔNG phải stability analysis**.
Stability analysis yêu cầu đánh giá ARI/AMI qua nhiều seeds khác nhau để
xác định algorithm consistency. EXP-01 repetition chỉ đo runtime variance và
verify determinism. Stability evidence (cluster labels từ nhiều seeds) được
tạo bởi **EXP-05**; stability analysis/comparison thuộc **EPIC-08**.

| Context | Phân biệt |
|---------|-----------|
| EXP-01 repetition | Runtime measurement / reproducibility verification. **NOT** stability. |
| EXP-05 (trong EPIC-07) | Generate stability evidence (cluster labels across multiple seeds). **NOT** analysis. |
| EPIC-08 | Analyze and interpret stability (ARI/AMI across seeds). |

### 3.4. Runtime structure trong MetricsResult

```python
# metrics.runtime = {
#     "algorithm_execution": {
#         "n_repeat": 5,
#         "mean_seconds": 0.234,
#         "std_seconds": 0.012,
#         "min_seconds": 0.221,
#         "max_seconds": 0.256,
#         "raw_seconds": [0.231, 0.224, 0.256, 0.221, 0.238],
#     },
#     "metric_computation": {
#         "silhouette_seconds": 0.089,
#         "davies_bouldin_seconds": 0.045,
#         "calinski_harabasz_seconds": 0.012,
#         "wcss_seconds": 0.003,
#     },
#     "note": "Artifact/report writing time excluded.",
# }
```

---

## 4. Metrics Policy cho EXP-01

### 4.1. Metric applicability — status schema

**Nguyên tắc:** Không dùng `0` để đại diện cho metric không applicable.
Mỗi metric có:

- `value`: số thực hoặc `None` nếu không compute.
- `status`: một trong 4 giá trị dưới.
- `reason`: chuỗi mô tả ngắn gọn (khi status ≠ `VALID_VALUE`).

| Status | Ý nghĩa | Value |
|--------|---------|-------|
| `VALID_VALUE` | Metric được compute thành công. | Số thực |
| `NOT_APPLICABLE` | Metric không áp dụng cho configuration hiện tại (ví dụ: silhouette khi chỉ có 1 cluster). | `None` |
| `COMPUTATION_ERROR` | sklearn raise exception khi compute (ví dụ: all-noise DBSCAN với silhouette). | `None` |
| `MISSING` | Metric chưa được compute (placeholder ban đầu). | `None` |

**Implementation:** Lưu status/reason trong `MetricsResult.extra`:

```python
# metrics.silhouette = 0.612
# metrics.extra["silhouette_status"] = "VALID_VALUE"
# metrics.extra["silhouette_reason"] = None

# metrics.silhouette = None
# metrics.extra["silhouette_status"] = "NOT_APPLICABLE"
# metrics.extra["silhouette_reason"] = "ALL_NOISE"
```

**Edge cases và status:**

| Edge case | Internal metric status | Reason |
|-----------|----------------------|--------|
| All points are noise (DBSCAN) | `NOT_APPLICABLE` | `ALL_NOISE` |
| Only 1 cluster (single-cluster edge) | `NOT_APPLICABLE` | `SINGLE_CLUSTER` |
| Fewer than 2 clusters | `NOT_APPLICABLE` | `INSUFFICIENT_CLUSTERS` |
| sklearn raises (unexpected) | `COMPUTATION_ERROR` | Exception message |
| Valid computation | `VALID_VALUE` | `None` |

### 4.2. WCSS — chuẩn hóa công thức

**Định nghĩa:**

```
WCSS = Σ_{i=1..n} || x_i - μ_{c_i} ||²
```

Trong đó:
- `x_i` là feature vector của customer `i`.
- `c_i` là hard cluster label của customer `i`.
- `μ_c` là **arithmetic centroid** của cluster `c`:
  ```
  μ_c = (1 / |C_c|) * Σ_{i∈C_c} x_i
  ```
  `C_c = {i | c_i = c}` là tập samples thuộc hard cluster `c`.

**Nguyên tắc quan trọng:**

- WCSS **luôn dựa trên hard cluster assignment** (`argmax` cho GMM/FCM),
  không dựa trên GMM Gaussian mean hay FCM fuzzy centroid.
- **Cách tính với GMM:**
  1. Lấy hard labels: `labels = argmax(soft_probabilities, axis=1)`.
  2. Tính arithmetic centroid từ `X` theo hard labels.
  3. Tính `Σ_i ||x_i - μ_{c_i}||²`.
- **Cách tính với FCM:**
  1. Lấy hard labels: `labels = argmax(soft_membership, axis=1)`.
  2. Tính arithmetic centroid từ `X` theo hard labels.
  3. Tính `Σ_i ||x_i - μ_{c_i}||²`.
- **Không gọi** GMM `means_` hay FCM `centroids_` là WCSS centroid.
  Chúng là algorithm-specific parameters, không phải arithmetic centroid.

### 4.3. DBSCAN — noise handling chính thức

**Quy ước bắt buộc:**

| Quy ước | Chi tiết |
|---------|----------|
| Noise label | `-1` (sklearn convention, đã được DBSCANAdapter enforce) |
| Internal metrics (silhouette / DBI / CH) | **Exclude noise** — compute trên non-noise subset |
| WCSS | **Exclude noise** — compute trên non-noise subset |
| Noise không phải cluster | KHÔNG gán label `-1` vào cluster centroid computation |
| All-noise case | Internal metrics → `NOT_APPLICABLE`, `ALL_NOISE` |
| Noise count được ghi | `ClusterResult.extra.noise_count`, `noise_ratio` |

**Implementation:**

```python
def _mask_non_noise(labels, noise_label=-1):
    return labels != noise_label

# Silhouette / DBI / CH
mask = _mask_non_noise(labels, noise_label=-1)
X_valid = X[mask]
labels_valid = labels[mask]
# sklearn silhouette_score(X_valid, labels_valid)
```

### 4.4. Tổng hợp metrics policy

| Metric | Áp dụng cho | DBSCAN / edge case policy | Ghi vào |
|--------|-------------|--------------------------|---------|
| **silhouette** | K-Means, Agglomerative, GMM, FCM, DBSCAN | Exclude noise; `NOT_APPLICABLE` nếu all-noise / single-cluster | `metrics.silhouette` + `extra.silhouette_status` |
| **davies_bouldin** | K-Means, Agglomerative, GMM, FCM, DBSCAN | Exclude noise; `NOT_APPLICABLE` nếu all-noise / single-cluster | `metrics.davies_bouldin` + `extra` |
| **calinski_harabasz** | K-Means, Agglomerative, GMM, FCM, DBSCAN | Exclude noise; `NOT_APPLICABLE` nếu all-noise / single-cluster | `metrics.calinski_harabasz` + `extra` |
| **wcss** | Tất cả 5 algorithms | Exclude noise; `NOT_APPLICABLE` nếu all-noise | `metrics.wcss` + `extra.wcss_status` |
| **runtime** | Tất cả 5 algorithms | Algorithm execution time (không gồm metric computation / I/O) | `metrics.runtime` (dict với n_repeat stats) |

---

## 5. Config Architecture Analysis

### 5.1. Hiện trạng

| Config file | Vai trò | Có gì liên quan? |
|-------------|---------|------------------|
| `configs/experiment.yaml` | Generic experiment config; drives `run_pipeline.py` và experiment logs | Có `evaluation:` block (internal_metrics, stability, runtime). **Lưu ý:** `stability.enabled: true` là generic placeholder, chưa reflect EPIC-07/08 boundary chính xác. |
| `configs/clustering.yaml` | ML-01 framework config; drives `ExperimentRunner` | Có `framework:` block + `algorithms:` block với working defaults. KHÔNG chứa evaluation config. |

### 5.2. Phân tích

**`configs/experiment.yaml`** hiện tại:
- Dùng cho generic experiment pipeline (`run_pipeline.py`).
- Có `evaluation:` block nhưng chưa reflect chính xác EXP-01 needs.
- Có `stability.enabled: true` — không chính xác vì stability analysis
  thuộc EPIC-08, EXP-01 không compute stability.
- Đang có `TODO_experiment_name` — không phù hợp cho production baseline.

**`configs/clustering.yaml`**:
- Dùng cho ML-01 framework.
- KHÔNG nên sửa vì chứa EPIC-06 working defaults đã set.
- Không chứa evaluation config.

### 5.3. Đề xuất: tạo `configs/exp01_baseline.yaml`

**Rationale:**

1. **Sạch hơn**: EXP-01 baseline có config riêng, không làm bẩn
   `experiment.yaml` (còn dùng cho pipeline generic) hay
   `clustering.yaml` (ML-01 framework).
2. **Không conflict**: Tránh override `TODO_experiment_name` hoặc
   `stability.enabled` trong file dùng chung.
3. **Traceable**: EXP-01 run ghi `config_sha256` của riêng file.
4. **Loại bỏ**: Không cần sửa `experiment.yaml` (tránh side-effect).

**Đề xuất cấu trúc `configs/exp01_baseline.yaml`:**

```yaml
# EXP-01 Baseline Configuration
# Single source of truth for the EXP-01 baseline experiment.

exp01:
  name: "EXP-01 Baseline"
  description: >
    Unified baseline experiment for 5 clustering algorithms.
    Serves as the reference point for EPIC-07 sweep and EPIC-08 comparison.

  # Which algorithms to run in the baseline
  algorithms:
    - kmeans
    - agglomerative
    - dbscan
    - gmm
    - fuzzy_cmeans

  # Evaluation configuration
  evaluation:
    internal_metrics:
      - silhouette
      - davies_bouldin
      - calinski_harabasz
      - wcss
    # Stability evidence generation: EXP-05 generates cluster labels
    # across seeds; EPIC-08 analyzes stability with ARI/AMI.
    # EXP-01 does NOT compute ARI/AMI.
    stability:
      enabled: false   # EXP-01 scope: record cluster labels; not compute ARI/AMI
    # Runtime measurement
    runtime:
      repeat: 5        # PENDING_REVIEW: n_repeat

  # Noise handling policy (DBSCAN)
  dbscan:
    exclude_noise_from_metrics: true   # EXP01-MET-01: PENDING_REVIEW
    noise_label: -1                  # sklearn convention (locked)

  # WCSS convention
  wcss:
    exclude_noise: true              # EXP01-MET-02: PENDING_REVIEW
    # WCSS always uses arithmetic centroid from hard labels
    centroid_method: "arithmetic_hard_labels"

  # Metric applicability
  metric_applicability:
    # How to handle NOT_APPLICABLE cases
    silhouette:
      on_single_cluster: "NOT_APPLICABLE"   # status = NOT_APPLICABLE, reason = SINGLE_CLUSTER
      on_all_noise: "NOT_APPLICABLE"         # status = NOT_APPLICABLE, reason = ALL_NOISE
```

**Kết luận §5:** Khuyến nghị tạo `configs/exp01_baseline.yaml` riêng.
**PENDING_REVIEW (EXP01-ENG-01):** Mentor confirm architecture này.

### 5.4. File config KHÔNG sửa

| File | Lý do |
|------|-------|
| `configs/experiment.yaml` | Dùng chung cho pipeline generic; không sửa để tránh side-effect. |
| `configs/clustering.yaml` | Chứa EPIC-06 working defaults; KHÔNG sửa theo EXP-01 §5. |

---

## 6. Implementation strategy

### 6.1. Tổng quan kiến trúc EXP-01

```
scripts/run_exp01_baseline.py
        │
        v
BaselineRunner (baseline.py)
        │
        ├── ExperimentRunner.run() [× n_repeat]
        │       ├── fit() ← algorithm execution time
        │       └── (skip artifact writing for non-final runs)
        │
        ├── compute_metrics() [metrics.py]
        │       ├── silhouette / DBI / CH ← metric computation time
        │       ├── wcss (arithmetic centroid, hard labels)
        │       └── attach status metadata
        │
        └── write_baseline_aggregates()
                ├── reports/exp01/exp01_baseline_manifest.json
                ├── reports/exp01/exp01_baseline_summary.csv
                └── reports/exp01/exp01_initial_baseline.md
```

### 6.2. Nguyên tắc thiết kế

1. **Tận dụng tối đa EPIC-06**: KHÔNG sửa `runner.py`, `result.py`,
   adapters, validation.
2. **Metrics layer value-neutral**: Compute silhouette/DBI/CH/WCSS bằng
   sklearn nhưng KHÔNG dùng để chọn algorithm.
3. **Runtime phân biệt rõ**: Algorithm execution time ghi riêng; metric
   computation time ghi riêng; artifact writing KHÔNG ghi.
4. **WCSS universal**: Arithmetic centroid từ hard labels.
5. **DBSCAN noise exclusion**: Không xem noise là cluster.
6. **Metric status rõ ràng**: `VALID_VALUE` / `NOT_APPLICABLE` /
   `COMPUTATION_ERROR` / `MISSING`.
7. **KHÔNG ghi nhận stability** (ARI/AMI) trong EXP-01.

---

## 7. File sẽ tạo / sửa

### 7.1. File MỚI

| Path | Type | Mô tả |
|------|------|-------|
| `src/customer_segmentation/clustering/metrics.py` | Module | Evaluation layer: `compute_internal_metrics()`, `compute_wcss()`, `compute_runtime_stats()`, `attach_metrics_with_status()` |
| `src/customer_segmentation/clustering/baseline.py` | Module | `BaselineRunner` class |
| `scripts/run_exp01_baseline.py` | Script | CLI orchestrator |
| `configs/exp01_baseline.yaml` | Config | EXP-01 baseline configuration |
| `tests/test_metrics.py` | Tests | Unit tests cho metrics layer (≥15 tests) |
| `tests/test_exp01_baseline.py` | Tests | Integration tests cho BaselineRunner (≥10 tests) |
| `reports/exp01/` | Directory | Baseline reports |

### 7.2. File SỬA

| Path | Loại sửa | Lý do |
|------|----------|-------|
| `src/customer_segmentation/clustering/__init__.py` | Thêm export | Chỉ sửa nếu repo convention yêu cầu export metrics/baseline. Nếu convention hiện tại KHÔNG yêu cầu re-export từ `__init__.py`, thì KHÔNG sửa. **PENDING_REVIEW (EXP01-ENG-02).** |
| `configs/experiment.yaml` | **KHÔNG SỬA** | Không sửa vì dùng chung cho pipeline generic. |
| `configs/clustering.yaml` | **KHÔNG SỬA** | Không sửa theo EXP-01 §5. |

### 7.3. File KHÔNG động đến

Tất cả EPIC-06 code và docs (runner, result, validation, artifacts,
logging, config, adapters, test files ML-01→ML-06, Mentor docs ML-01→ML-06).

---

## 8. Chi tiết từng file

### 8.1. `src/customer_segmentation/clustering/metrics.py` (MỚI)

**Mục đích:** Evaluation layer duy nhất cho EXP-01. KHÔNG chọn best.

**Constants cho metric status:**

```python
METRIC_VALID = "VALID_VALUE"
METRIC_NOT_APPLICABLE = "NOT_APPLICABLE"
METRIC_COMPUTATION_ERROR = "COMPUTATION_ERROR"
METRIC_MISSING = "MISSING"

REASON_ALL_NOISE = "ALL_NOISE"
REASON_SINGLE_CLUSTER = "SINGLE_CLUSTER"
REASON_INSUFFICIENT_CLUSTERS = "INSUFFICIENT_CLUSTERS"
```

**Public API:**

```python
def compute_internal_metrics(
    X: np.ndarray,
    labels: np.ndarray,
    *,
    noise_label: int = -1,
    exclude_noise: bool = True,
) -> tuple[
    dict[str, float | None],      # values
    dict[str, str],               # status per metric
    dict[str, str],               # reason per metric (None if VALID)
    float,                        # computation_time_seconds
]:
    """Compute silhouette, DBI, CH với noise handling + status.

    Returns (values, status, reason, computation_time).
    Silhouette trả về None nếu:
    - exclude_noise=True và tất cả points là noise → NOT_APPLICABLE / ALL_NOISE
    - Chỉ có 1 cluster → NOT_APPLICABLE / SINGLE_CLUSTER
    - sklearn raises → COMPUTATION_ERROR / exception_message
    """

def compute_wcss(
    X: np.ndarray,
    labels: np.ndarray,
    *,
    noise_label: int = -1,
    exclude_noise: bool = True,
) -> tuple[float | None, str, str | None]:
    """WCSS = Σ_i ||x_i - μ_{c_i}||², dùng arithmetic centroid theo hard labels.

    Returns (wcss_value, status, reason).
    """

def compute_runtime_stats(
    callable_: Callable[[], Any],
    n_repeat: int,
) -> dict:
    """Repetition-based runtime stats. Trả về dict với mean/std/min/max/raw."""

def attach_metrics_with_status(
    cluster_result: ClusterResult,
    X: np.ndarray,
    *,
    exclude_noise: bool = True,
    noise_label: int = -1,
    metric_computation_time: float = 0.0,
    runtime_stats: dict | None = None,
) -> ClusterResult:
    """Populate cluster_result.metrics với values + status + reasons.
    Ghi computation time vào metrics.extra.
    Ghi runtime stats vào metrics.runtime.
    """
```

**Implementation notes:**

- Dùng `sklearn.metrics.silhouette_score`, `davies_bouldin_score`,
  `calinski_harabasz_score`.
- WCSS: `for k in unique_non_noise_labels: centroid = X[labels==k].mean(axis=0)`.
- DBSCAN noise: mask `labels != noise_label` trước khi gọi sklearn.
- Metric computation time: `time.perf_counter()` trước và sau sklearn calls.
- KHÔNG thêm dependency mới.

### 8.2. `src/customer_segmentation/clustering/baseline.py` (MỚI)

**Mục đích:** Orchestrate baseline experiment cho 5 algorithms.

```python
@dataclass
class BaselineSpec:
    experiment_id: str
    algorithm: str
    hyperparameters: dict[str, Any]
    seed: int | None

@dataclass
class BaselineResult:
    experiment_id: str
    algorithm: str
    algorithm_version: str
    hyperparameters: dict[str, Any]
    cluster_result: ClusterResult          # from final repetition
    runtime_stats: dict                   # from n_repeat repetitions
    input_sha256: str
    config_sha256: str
    library_versions: dict[str, str]

class BaselineRunner:
    def run(
        self,
        spec: BaselineSpec,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame,
        n_repeat: int,
        exclude_noise: bool,
        output_dir: Path | None,
    ) -> BaselineResult:
        # 1. Repetition loop (n_repeat times):
        #    - fit() with timer (algorithm execution only)
        #    - discard cluster_result except last repetition
        #    - collect raw runtime seconds
        # 2. Final repetition: attach_metrics_with_status()
        # 3. Return BaselineResult
```

**Lưu ý:** `ExperimentRunner.run()` được gọi cho mỗi repetition. Để
tránh artifact writing nhiều lần, dùng `output_dir=None` cho các
lần repetition trước; chỉ lần cuối có `output_dir=actual`.

### 8.3. `scripts/run_exp01_baseline.py` (MỚI)

**Workflow:**

1. Load `configs/exp01_baseline.yaml` + `configs/clustering.yaml` (cho
   framework defaults).
2. Load FE-06 input + customer metadata. Compute input SHA.
3. For each of 5 algorithms:
   - Build `BaselineSpec` với working defaults từ `clustering.yaml`.
   - Call `BaselineRunner.run()`.
   - Collect `BaselineResult`.
4. Write:
   - `reports/exp01/exp01_baseline_manifest.json`
   - `reports/exp01/exp01_baseline_summary.csv`
   - `reports/exp01/exp01_initial_baseline.md`
   - `reports/exp01/exp01_run_summary.json`

### 8.4. `configs/exp01_baseline.yaml` (MỚI)

Cấu trúc đã mô tả ở §5.3.

### 8.5. `tests/test_metrics.py` (MỚI)

| Category | Tests |
|----------|-------|
| Silhouette correctness | Well-separated → gần 1, uniform → gần 0. |
| DBI correctness | Well-separated → thấp, overlap → cao. |
| CH correctness | Well-separated → cao. |
| WCSS correctness | Reproduce K-Means `inertia_` trong tolerance 1e-6. |
| WCSS với GMM | Hard label centroid → WCSS. |
| WCSS với FCM | Hard label centroid → WCSS. |
| Noise exclusion (DBSCAN) | Silhouette trên non-noise subset. |
| All-noise edge case | Status = NOT_APPLICABLE, reason = ALL_NOISE. |
| Single-cluster edge case | Status = NOT_APPLICABLE, reason = SINGLE_CLUSTER. |
| Runtime repetition | Stats đúng mean/std/min/max. |
| Metric computation time recorded | > 0 và < total wall time. |
| Status schema integrity | VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR. |
| **Tổng** | **≥15 tests** |

### 8.6. `tests/test_exp01_baseline.py` (MỚI)

| Category | Tests |
|----------|-------|
| 5 algorithms đều SUCCESS | 5 tests riêng. |
| Output schema đúng | `BaselineResult` đầy đủ field. |
| Runtime stats structure | Có mean/std/min/max/raw. |
| Metrics populated với status | Silhouette/DBI/CH/WCSS ≠ MISSING. |
| DBSCAN noise: metrics status | NOT_APPLICABLE hoặc VALID_VALUE. |
| DBSCAN DBSCAN: noise_count > 0 | Ghi nhận đúng. |
| Manifest structure | `exp01_baseline_manifest.json` có 5 entries. |
| No input mutation | Input SHA không đổi. |
| Same seed → same labels | Reproducibility. |
| **Tổng** | **≥10 tests** |

### 8.7. `reports/exp01/` (MỚI)

| File | Mô tả |
|------|-------|
| `exp01_baseline_manifest.json` | Full manifest: 5 algorithms × all fields (values + status + reasons + runtime stats) |
| `exp01_baseline_summary.csv` | Flat CSV: 5 rows × (algorithm, n_clusters, silhouette, silhouette_status, DBI, DBI_status, CH, CH_status, WCSS, WCSS_status, runtime_mean, runtime_std, ...) |
| `exp01_initial_baseline.md` | Vietnamese narrative: mục tiêu, methodology, results table, boundary, decisions |
| `exp01_run_summary.json` | Machine-readable summary |

---

## 9. Assumptions

1. **5 working defaults** từ EPIC-06 được dùng **nguyên si** trong baseline.
   Đây là `WORKING_ASSUMPTION`, chưa phải final research decision.

| Algorithm | Working default |
|-----------|----------------|
| K-Means | `n_clusters=4`, `init='k-means++'`, `n_init=10`, `max_iter=300`, `tol=1e-4` |
| Agglomerative | `n_clusters=4`, `linkage='ward'`, `metric='euclidean'`, `compute_distances=True` |
| DBSCAN | `eps=0.5`, `min_samples=5`, `metric='euclidean'`, `noise_label=-1` |
| GMM | `n_components=4`, `covariance_type='full'`, `init_params='kmeans'` |
| Fuzzy C-Means | `n_clusters=4`, `m=2.0`, `max_iter=300`, `error=1e-4` |

2. **DBSCAN KHÔNG bị ép về cùng n_clusters**: DBSCAN sử dụng
   `eps=0.5, min_samples=5`, kết quả cluster count = whatever DBSCAN
   discovers.

3. **Random seed**: `framework.random_seed.default = 42`. K-Means,
   Agglomerative, DBSCAN: deterministic; GMM, FCM: consume seed.

4. **Dataset unchanged**: FE-06 input SHA giữ nguyên. KHÔNG mutate.

5. **Metrics library**: dùng `sklearn.metrics` đã có. KHÔNG thêm
   dependency mới.

6. **WCSS universal**: arithmetic centroid theo hard labels. Không dùng
   GMM Gaussian mean hay FCM fuzzy centroid.

7. **Noise không là cluster**: noise label `-1` bị exclude khỏi internal
   metrics và WCSS.

---

## 10. PENDING_REVIEW decisions

| ID | Decision | Status | Cần mentor |
|----|----------|--------|-----------|
| EXP01-MET-01 | Noise exclusion policy: exclude noise khỏi silhouette/DBI/CH/WCSS | PENDING_REVIEW | Có |
| EXP01-MET-02 | WCSS convention: exclude noise khỏi WCSS | PENDING_REVIEW | Có |
| EXP01-MET-03 | `n_repeat=5` cho runtime measurement | PENDING_REVIEW | Có |
| EXP01-MET-04 | Metric applicability status schema (VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING + reason) | PENDING_REVIEW | Có |
| EXP01-MET-05 | All-noise DBSCAN: silhouette → NOT_APPLICABLE, WCSS → NOT_APPLICABLE | PENDING_REVIEW | Có |
| EXP01-MET-06 | Single-cluster edge case: silhouette → NOT_APPLICABLE | PENDING_REVIEW | Có |
| EXP01-ENG-01 | Tạo `configs/exp01_baseline.yaml` riêng (thay vì sửa experiment.yaml / clustering.yaml) | PENDING_REVIEW | Có |
| EXP01-ENG-02 | Có cần export metrics/baseline trong `clustering/__init__.py` không? (chỉ sửa nếu repo convention yêu cầu) | PENDING_REVIEW | Có |

---

## 11. Những gì KHÔNG nằm trong scope EXP-01

| Nội dung | Lý do | Thuộc EPIC |
|----------|-------|-----------|
| Sweep n_clusters / n_components / m / eps | EXP-01 chỉ chạy 1 working default per algo | EPIC-07 |
| Sweep linkage / covariance_type / init_params | EXP-01 chỉ chạy 1 working default per algo | EPIC-07 |
| Sweep multiple seeds | EXP-01 chỉ chạy 1 seed per algo (42) | EPIC-07 |
| **Stability analysis (ARI / AMI)** | EXP-01 chỉ tạo stability **evidence** (cluster labels per algorithm). EXP-05 generate evidence across multiple seeds. EPIC-08 analyze/comparison stability. | **EXP-05** (evidence) + **EPIC-08** (analysis) |
| Algorithm comparison / ranking | Algorithm comparison = EPIC-08 | EPIC-08 |
| "Best algorithm" / "winner" claim | AGENTS.md §2.5 cấm | — |
| Hyperparameter tuning | Hyperparameter optimization = EXP-02 → EXP-05 / EPIC-07 | EPIC-07 |
| Sensitivity analysis | Sensitivity = EPIC-07 | EPIC-07 |
| Feature/preprocessing comparison | Feature = FE-* | FE-* |
| Customer profiling | Customer profiling = EPIC-09 | EPIC-09 |
| Research-grade visualization | Visualization = EPIC-08 / EPIC-09 | EPIC-08/09 |

---

## 12. Baseline Report chỉ ghi nhận observed evidence

Baseline report (`exp01_initial_baseline.md`, `exp01_baseline_summary.csv`)
**chỉ ghi nhận** observed numbers từ 5 algorithms. KHÔNG bao gồm:

- Ranking / ordering nào giữa algorithms.
- Từ "best", "better", "winner", "recommended".
- Comparative conclusion giữa algorithms.
- Interpretation của metric values (ví dụ: "silhouette=0.7 là tốt").
- Recommendation nào.

Report structure:
- Mục tiêu (đọc lại EXP-01 goal).
- Methodology (working defaults, metrics policy, runtime protocol).
- Observed results table (algorithm × metric × value × status × reason).
- PENDING_REVIEW decisions.
- Scope boundaries (bảng LÀM / KHÔNG LÀM).
- KHÔNG có comparative analysis section.

---

## 13. Workflow thực thi (sau khi plan approved)

```
Step 1: Tạo metrics.py + tests/test_metrics.py
   └─→ pytest test_metrics.py pass

Step 2: Tạo baseline.py + tests/test_exp01_baseline.py
   └─→ pytest test_exp01_baseline.py pass

Step 3: Tạo configs/exp01_baseline.yaml
   └─→ Verify YAML load OK

Step 4: Tạo scripts/run_exp01_baseline.py
   └─→ Smoke test (output_dir=None) — verify không crash

Step 5: Chạy baseline đầy đủ → sinh reports
   └─→ Verify reports tồn tại, schema đúng, SHA recorded

Step 6: Final verification
   └─→ pytest (all tests)
   └─→ ruff check
   └─→ black --check

Step 7: (Sau EXP-01 verified) Viết docs/research/EXP01_baseline_experiment.md
```

Dependencies: Step 2 → Step 1; Step 4 → Step 1 + 2 + 3; Step 5 → Step 4; Step 7 → Step 6.

---

## 14. Đề xuất cấu trúc Mentor Document (sau này)

File: `docs/research/EXP01_baseline_experiment.md`

12 sections theo EPIC-06 Documentation Contract §2:

| § | Nội dung |
|---|----------|
| 1 | Task ID, mục tiêu, input/output, research pipeline position |
| 2 | Mục tiêu nghiên cứu: unified baseline làm mốc cho EPIC-07/08 |
| 3 | Cơ sở lý thuyết: metrics definitions, WCSS formula, noise handling |
| 4 | Methodology: working defaults, runtime protocol, metrics applicability status |
| 5 | Implementation: metrics.py, baseline.py, run_exp01_baseline.py |
| 6 | Experimental Design Boundary (LÀM / KHÔNG LÀM table) |
| 7 | Observed results (5 algorithms × metrics × values × status × reason) |
| 8 | Formulas (silhouette, DBI, CH, WCSS) |
| 9 | Visualization boundary |
| 10 | Verification (tests, lint, format, input integrity, output integrity) |
| 11 | Mentor Review (PENDING_REVIEW list) |
| 12 | Kết luận (TECHNICALLY_IMPLEMENTED, OUT_OF_SCOPE explicit) |

---

## 15. Danh sách thay đổi so với PLAN Revision 0

| # | Review point | Thay đổi |
|---|-------------|-----------|
| 1 | Runtime protocol | Thêm §3 mới: phân biệt 3 loại runtime. Chỉ algorithm execution time được ghi vào baseline runtime. Metric computation time ghi riêng trong `metrics.extra`. Artifact writing không ghi. |
| 2 | Runtime repetition vs Stability | §1.2: thêm row "Tạo stability evidence (cluster labels) cho EXP-05". §11: sửa table — stability thuộc **EXP-05** (evidence) + **EPIC-08** (analysis), không phải EPIC-08 đơn thuần. §12: thêm note "KHÔNG có stability analysis". §3.3: thêm bảng phân biệt rõ. |
| 3 | WCSS | §4.2: định nghĩa WCSS chuẩn hóa dùng arithmetic centroid theo hard labels. GMM/FCM: dùng hard labels (argmax), không dùng GMM Gaussian mean hay FCM fuzzy centroid. Thêm test "WCSS với GMM" và "WCSS với FCM". |
| 4 | DBSCAN | §4.3: quy ước noise handling chính thức. Noise không là cluster. All-noise → NOT_APPLICABLE. WCSS exclude noise. |
| 5 | Metric applicability | §4.1: thêm status schema 4 giá trị (VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING) + reason field. Không dùng `0` cho not applicable. Implementation trong `metrics.py`. §8.1: update API. |
| 6 | EXP-07 vs EPIC-08 boundary | §11: sửa table — stability evidence thuộc EXP-05, stability analysis thuộc EPIC-08. §3.3: bổ sung context. |
| 7 | Config architecture | Thêm §5 mới: phân tích chi tiết `experiment.yaml` và `clustering.yaml`. Khuyến nghị tạo `configs/exp01_baseline.yaml` riêng. Xóa plan sửa `experiment.yaml`. |
| 8 | `__init__.py` | §7.2: sửa thành "chỉ sửa nếu repo convention yêu cầu". Không bắt buộc. |
| 9 | Baseline report | §12: thêm constraints cho baseline report — chỉ ghi nhận observed evidence, không comparative conclusion, không ranking, không "best/winner/recommended". |
| 10 | Working defaults | §9: thêm note "WORKING_ASSUMPTION, chưa phải final research decision". |

---

## 16. Tổng kết

| Câu hỏi | Trả lời |
|---------|---------|
| Có thể chạy baseline với code hiện tại? | **KHÔNG** — cần bổ sung `metrics.py`. |
| Metrics nào cần implement? | silhouette, DBI, CH, WCSS + runtime stats. KHÔNG stability (EXP-05/EPIC-08). |
| DBSCAN xử lý noise thế nào? | Exclude noise khỏi internal metrics + WCSS. Status = NOT_APPLICABLE nếu all-noise. |
| WCSS tính thế nào với GMM/FCM? | Hard labels (argmax) → arithmetic centroid → WCSS. Không dùng GMM Gaussian mean hay FCM fuzzy centroid. |
| Runtime đo thế nào? | Algorithm execution time (n_repeat × mean/std/min/max). Metric computation time ghi riêng. Artifact writing không ghi. |
| Repetition có phải stability analysis? | **KHÔNG.** Repetition = runtime measurement + reproducibility verification. Stability evidence = EXP-05. Stability analysis = EPIC-08. |
| Metric not applicable dùng gì? | `None` + status = `NOT_APPLICABLE` + reason field. Không dùng `0`. |
| Config architecture? | Khuyến nghị tạo `configs/exp01_baseline.yaml` riêng. **PENDING_REVIEW.** |
| Có commit/push/PR? | **KHÔNG** — AGENTS.md §2.11. |
| Mentor document khi nào? | Sau khi EXP-01 verified (Step 7 của §13). |

---

*Plan này là Revision 1. TUYỆT ĐỐI KHÔNG thực hiện code ở bước này.*
