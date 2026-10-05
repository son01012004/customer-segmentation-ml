# ML-05 Mentor Document — Gaussian Mixture Model (GMM)

> **Status: TECHNICALLY_IMPLEMENTED**
>
> Mentor document này tổng hợp evidence từ implementation, tests, và
> diagnostic runs. Nó ghi nhận các quyết định methodology/engineering
> cần mentor review, phân biệt rõ giữa `TECHNICALLY_IMPLEMENTED`
> và `RESEARCH_DECISION_APPROVED`.
>
> KHÔNG gọi GMM là "best algorithm", KHÔNG gọi `n_components=4` là
> "optimal", KHÔNG gọi `covariance_type='full'` là "recommended". Đó
> là EPIC-07 scope.

---

## 1. Overview

| Field | Value |
|-------|-------|
| Task | ML-05 Gaussian Mixture Model (GMM) |
| Algorithm family | `model_based` (probabilistic / model-based clustering) |
| sklearn class | `sklearn.mixture.GaussianMixture` |
| Adapter | `GMMAdapter` in `src/customer_segmentation/clustering/gmm.py` |
| Primary experiment | `ML-05-GMM-k4-full-kmeans-seed42` |
| Primary status | **SUCCESS** |
| Framework | ML-01 `ExperimentRunner` |
| EPIC contract | EPIC-06 §3.5 |

**Mục tiêu ML-05:** Implement GMM adapter cho ML-01 framework và chạy
initial diagnostic runs trên FE-06 dataset. KHÔNG evaluate, KHÔNG so
sánh, KHÔNG pick "best" configuration.

---

## 2. Algorithm summary

### 2.1 What GMM does

**Gaussian Mixture Model** giả định dữ liệu được sinh ra từ tổng có
trọng số của K phân phối Gaussian đa biến:

```
p(x) = Σ_{k=1..K} π_k · N(x | μ_k, Σ_k)
```

- `K` = số components (`n_components`).
- `π_k >= 0`, `Σ_k π_k = 1` = mixture weights.
- `μ_k ∈ ℝ^p` = mean vector của component `k`.
- `Σ_k` = covariance matrix của component `k`.

**Hard cluster label** của observation `x_i`:

```
c_i = argmax_k P(z_i = k | x_i)
```

sklearn's `GaussianMixture.predict` trả về argmax này.

**Soft assignment** — posterior responsibility — của component `k`
cho observation `x_i`:

```
γ_ik = P(z_i = k | x_i)
     = [π_k · N(x_i | μ_k, Σ_k)] / [Σ_j π_j · N(x_i | μ_j, Σ_j)]
```

sklearn's `GaussianMixture.predict_proba` trả về responsibility
matrix shape `(n_samples, n_components)`. Mỗi row sum = 1.

### 2.2 Algorithm family

GMM thuộc **model-based / probabilistic** clustering family. So với
partitioning methods (K-Means) và hierarchical methods (Agglomerative),
GMM có:

- **Ưu điểm**: Cho soft assignment (posterior responsibilities), model
  có probabilistic interpretation, linh hoạt về covariance structure.
- **Nhược điểm**: EM có thể converge vào local maximum; sensitivity
  với initialization; label permutation property (component IDs có thể
  swap giữa các runs).

### 2.3 Random state

GMM **consumes** `random_state` cho EM initialization:
- `init_params="kmeans"`: K-Means seed cho initial means.
- `init_params="random"`: Dirichlet responsibilities + Gaussian samples.

→ `supports_random_state() == True`. Framework runner inject seed.

---

## 3. Adapter design decisions

### 3.1 Exposed hyperparameters

Adapter expose các hyperparameters sau (AGENTS.md §2, §3 scope control):

| Hyperparameter | Type | Default | Notes |
|---------------|------|---------|-------|
| `n_components` | int ≥ 1 | **REQUIRED** (no default) | Must be explicit from caller |
| `covariance_type` | str | `"full"` | full / tied / diag / spherical |
| `init_params` | str | `"kmeans"` | kmeans / random |
| `random_state` | int \| None | `None` | Consumed by sklearn EM init |
| `tol` | float > 0 | `1e-3` | sklearn default |
| `reg_covar` | float > 0 | `1e-6` | sklearn default |
| `max_iter` | int ≥ 1 | `100` | sklearn default |
| `n_init` | int ≥ 1 | `1` | sklearn default |

**Working defaults** (`configs/clustering.yaml`):
- `n_components = 4` → WORKING_ASSUMPTION
- `covariance_type = "full"` → WORKING_ASSUMPTION
- `init_params = "kmeans"` → WORKING_ASSUMPTION

### 3.2 What is NOT exposed

Theo AGENTS.md §3 (Clustering row) và ML-05 contract, adapter
**KHÔNG expose**:
- `weights_init` (initial mixture weights)
- `means_init` (initial means)
- `precisions_init` (initial precisions)
- `warm_start` (reuse previous fit)
- `copy_x` (input copy behavior)

Đây là engineering decision để giữ adapter surface small và stable.

### 3.3 Soft clustering output

GMM là defining characteristic của **model-based clustering**:
- **Hard labels**: `argmax` over responsibility matrix (sklearn `predict`).
- **Soft responsibilities**: full posterior probability matrix
  `P(z_i = k | x_i)` shape `(n_samples, n_components)`.

Adapter preserve **BOTH**:
1. `ClusterResult.cluster_labels` (hard labels).
2. `ClusterResult.soft_probabilities` (full responsibility matrix).

Artifact writer emit:
- `cluster_labels_*.parquet`: CustomerID + ClusterLabel + IsNoise + `Probability_k` columns.
- `algorithm_output_*.parquet`: CustomerID + `Probability_k` columns (responsibility matrix).

### 3.4 Convergence diagnostics

sklearn's `GaussianMixture` provides:
- `converged_` (bool): EM hit convergence criterion within `max_iter`.
- `n_iter_` (int): actual number of EM iterations.
- `lower_bound_` (float): negative variational lower bound (maximized by EM).

These are recorded in `ClusterResult.extra` as **diagnostic only**.
`lower_bound`, `AIC`, `BIC` are NOT clustering quality metrics.

---

## 4. GMM-specific diagnostics

### 4.1 Model-selection helpers (diagnostic only)

| Metric | Description | Scope |
|--------|-------------|-------|
| `lower_bound` | Negative variational lower bound (maximized by EM) | Diagnostic |
| `aic` | Akaike Information Criterion | Diagnostic only |
| `bic` | Bayesian Information Criterion | Diagnostic only |

**IMPORTANT:** AIC và BIC được ghi nhận trong `ClusterResult.extra` là
**diagnostics only**. Chúng KHÔNG được dùng để tuyên bố một
configuration là "best". Model-selection comparison thuộc EPIC-07.

sklearn convention: `lower_bound_` là **negative** variational lower
bound được maximize trong EM. Higher (less negative) = better fit
(với caveat về model complexity).

### 4.2 Mixture weights

- `model.weights_` array shape `(n_components,)`, sum = 1.
- Component sizes trong `extra.cluster_sizes` được derive từ **hard
  labels** (argmax), không phải từ mixture weights.

### 4.3 Responsibility integrity

Diagnostics recorded in `ClusterResult.extra`:
- `soft_probabilities_shape`: `[n_samples, n_components]`.
- `soft_probabilities_row_sum_min` / `_max`: row sums ∈ [1-K eps, 1+K eps].
- `responsibility_max_probability_min` / `_max` / `_mean`: confidence
  summary over max probability per row.

---

## 5. Per-covariance-type diagnostic runs

### 5.1 Diagnostic results

| Covariance | Status | converged | n_iter | lower_bound | AIC | BIC | Execution (s) |
|------------|--------|-----------|-------:|------------:|----:|----:|--------------:|
| `full` | SUCCESS | True | 19 | 12.2883 | -106475.65 | -103418.31 | 0.8795 |
| `tied` | SUCCESS | True | 5 | -0.9738 | 8835.95 | 9882.72 | 0.2635 |
| `diag` | SUCCESS | True | 18 | -9.7671 | 85608.65 | 86342.66 | 0.0615 |
| `spherical` | SUCCESS | True | 16 | -23.6452 | 206827.06 | 207229.17 | 0.0777 |

### 5.2 Covariance type semantics

- **`full`**: Mỗi component có covariance matrix riêng. Linh hoạt nhất,
  nhiều parameters nhất. Primary run sử dụng type này.
- **`tied`**: Tất cả components dùng chung một covariance matrix.
  Intermediate parameter count.
- **`diag`**: Mỗi component có diagonal covariance (không có correlation
  terms giữa features). Tương đương assumption features are independent
  within each component.
- **`spherical`**: Mỗi component có một variance scalar duy nhất.
  Fewest parameters.

**KHÔNG có covariance type nào được kết luận là "best" trong tài liệu này.**

### 5.3 Observations (diagnostic only)

- `full` đạt highest (least negative) `lower_bound` trên FE-06 data.
- `tied` hội tụ nhanh nhất (5 iterations).
- `diag` và `spherical` có lower bound thấp hơn (more constrained models).
- Execution time `full` > `tied` > `spherical` ≈ `diag` (reflects
  computational complexity của covariance estimation).

Đây là **diagnostic observations**, KHÔNG phải recommendations.
Controlled comparison thuộc EPIC-07.

---

## 6. Primary run summary

### 6.1 Configuration

| Parameter | Value | Status |
|-----------|-------|--------|
| `n_components` | 4 | WORKING_ASSUMPTION |
| `covariance_type` | `"full"` | WORKING_ASSUMPTION |
| `init_params` | `"kmeans"` | WORKING_ASSUMPTION |
| `random_state` | 42 | Framework seed |
| `tol` | `1e-3` | sklearn default |
| `reg_covar` | `1e-6` | sklearn default |
| `max_iter` | 100 | sklearn default |
| `n_init` | 1 | sklearn default |

### 6.2 Results

| Metric | Value |
|--------|-------|
| Status | SUCCESS |
| n_clusters | 4 |
| n_samples | 4371 |
| n_features | 14 |
| `converged` | True |
| `n_iter` | 19 |
| `lower_bound` | 12.2883 |
| AIC | -106475.65 (diagnostic only) |
| BIC | -103418.31 (diagnostic only) |
| Execution time | 0.6564 s |

### 6.3 Mixture weights and cluster sizes

| Component | Mixture weight (π_k) | Hard label size |
|-----------|---------------------:|----------------:|
| 0 | 0.2184 | 952 |
| 1 | 0.4730 | 2068 |
| 2 | 0.0595 | 255 |
| 3 | 0.2490 | 1096 |

**Note:** Mixture weights và hard label sizes KHÔNG equal vì hard label
là argmax của responsibility matrix, không phải argmax của mixture
weights.

### 6.4 Responsibility confidence

| Metric | Value |
|--------|-------|
| `max_probability_min` | 0.5005 |
| `max_probability_max` | 1.0000 |
| `max_probability_mean` | 0.9891 |

Mean max probability ≈ 0.989 → observations are assigned with high
confidence to their respective components. Min max probability ≈ 0.50
→ some observations lie near component boundaries.

---

## 7. Reproducibility

### 7.1 GMM reproducibility contract

GMM **consumes** `random_state` for EM initialization. Same input +
same configuration + same library version → same:
- Responsibilities
- Mixture weights
- Lower bound
- AIC / BIC
- Converged flag + n_iter

### 7.2 Label permutation caveat

GMM có known **label permutation property**: component IDs có thể swap
giữa các runs ngay cả với cùng seed (khi EM converge vào different local
maxima). Therefore:
- **KHÔNG** dùng raw label equality làm reproducibility check.
- Dùng permutation-invariant quantities: responsibilities, mixture weights,
  lower bound, AIC, BIC, centroids sau khi sort.

ML-05 tests verify permutation-invariant reproducibility:
- `test_same_seed_same_responsibilities`: responsibilities exact match.
- `test_permutation_invariant_centroids`: centroids match after sort.

### 7.3 Library versions

| Library | Version |
|---------|---------|
| numpy | 2.3.5 |
| pandas | 3.0.6 |
| scipy | 1.18.1 |
| scikit-learn | 1.9.1 |
| pyarrow | 25.0.1 |

---

## 8. Verification

### 8.1 Tests

| Test category | File | Số test | Trạng thái |
|--------------|------|---------|------------|
| Interface + registration | `test_ml05_gmm.py` | 14 | **PASS** |
| Parameter validation | `test_ml05_gmm.py` | 11 | **PASS** |
| Input validation | `test_ml05_gmm.py` | 5 | **PASS** |
| Covariance types | `test_ml05_gmm.py` | 5 | **PASS** |
| Output schema | `test_ml05_gmm.py` | 8 | **PASS** |
| Responsibility / soft clustering | `test_ml05_gmm.py` | 6 | **PASS** |
| Reproducibility | `test_ml05_gmm.py` | 4 | **PASS** |
| Integration with ExperimentRunner | `test_ml05_gmm.py` | 13 | **PASS** |
| **TOTAL** | | **66** | **PASS (66/66)** |

### 8.2 Lint

```bash
ruff check src/customer_segmentation/clustering/gmm.py tests/test_ml05_gmm.py scripts/run_ml05_gmm.py
```

Result: **All checks passed!**

### 8.3 Format

```bash
black --check src/customer_segmentation/clustering/gmm.py tests/test_ml05_gmm.py scripts/run_ml05_gmm.py
```

Result: **3 files would be left unchanged.**

### 8.4 Input integrity

- FE-06 outputs không bị ML-05 mutate.
- `validate_clustering_matrix` và `validate_customer_alignment` PASS.
- Input SHA-256: `ba54033e45525bf5...`
- Config SHA-256: `d5172c4640d7bc2c...`

### 8.5 Output integrity

- `cluster_labels` shape `(4371,)`, dtype `int64` ✅.
- `cluster_labels` values in `[0, 3]` (4 components) ✅.
- `soft_probabilities` shape `(4371, 4)` ✅.
- `soft_probabilities` row sums ∈ [0.9999999999999982, 1.0000000000000018] ✅.
- `converged == True`, `n_iter == 19` ✅.
- `noise_count == 0` (GMM không có noise concept) ✅.
- Artifacts: `cluster_labels_*.parquet` + `experiment_log_*.json` +
  `algorithm_output_*.parquet` ✅.

---

## 9. Decision status

### 9.1 Engineering / Scope decisions (DOCUMENTED)

| ID | Decision | Status |
|----|----------|--------|
| ML-05-ENG-01 | Adapter expose `(n_components, covariance_type, init_params, random_state, tol, reg_covar, max_iter, n_init)` — không expose `weights_init`, `means_init`, `precisions_init`, `warm_start`, `copy_x` | DOCUMENTED |
| ML-05-ENG-02 | Soft clustering output preserved via `ClusterResult.soft_probabilities` + `algorithm_output_*.parquet` + `Probability_k` columns in `cluster_labels_*.parquet` | DOCUMENTED |
| ML-05-ENG-03 | `n_clusters` computed from `n_components` (not from `np.unique(labels)`) | DOCUMENTED |
| ML-05-ENG-04 | `noise_count == 0`, `noise_label == -1` (GMM không có noise concept) | DOCUMENTED |

### 9.2 Methodology decisions (PENDING_REVIEW)

| ID | Decision | Status |
|----|----------|--------|
| ML-05-MET-01 | `working_n_components=4` cho ML-05 primary diagnostic | PENDING_REVIEW |
| ML-05-MET-02 | `working_covariance_type='full'` cho working default | PENDING_REVIEW |
| ML-05-MET-03 | `working_init_params='kmeans'` cho EM initialization | PENDING_REVIEW |
| ML-05-MET-04 | AIC / BIC / `lower_bound` ghi nhận trong `extra` là diagnostics only, KHÔNG dùng để tuyên bố "best" configuration | PENDING_REVIEW |
| ML-05-MET-05 | Label permutation caveat: raw label equality KHÔNG phải reproducibility check; dùng responsibilities, mixture weights, lower_bound | PENDING_REVIEW |
| ML-05-MET-06 | 4 per-covariance-type diagnostic runs (full / tied / diag / spherical) trong EPIC-06 | PENDING_REVIEW |

---

## 10. Contract with downstream EPICs

### 10.1 Output schema

| Field | Type | Value |
|-------|------|-------|
| `algorithm_family` | str | `"model_based"` |
| `cluster_labels` | np.ndarray shape `(4371,)` dtype `int64` | `[0, K-1]` |
| `soft_probabilities` | np.ndarray shape `(4371, n_components)` dtype `float64` | Full responsibility matrix |
| `n_clusters` | int | `n_components` |
| `noise_count` | int | `0` |
| `noise_ratio` | float | `0.0` |
| `supports_random_state` | bool | `True` |
| `soft_membership` | None | GMM dùng `soft_probabilities` |

### 10.2 Extra diagnostics for EPIC-07

| Key | Description | Consumer |
|-----|-------------|----------|
| `n_components` | Number of Gaussian components | EPIC-07 sweep |
| `covariance_type` | Shape of covariance matrices | EPIC-07 sweep |
| `init_params` | EM initialization strategy | EPIC-07 sweep |
| `converged` | EM convergence flag | EPIC-07 diagnostics |
| `n_iter` | Number of EM iterations | EPIC-07 diagnostics |
| `lower_bound` | Variational lower bound | EPIC-07 (diagnostic only) |
| `aic`, `bic` | Model-selection helpers | EPIC-07 (diagnostic only) |
| `mixture_weights` | Component weights | EPIC-09 profiling |
| `cluster_sizes` | Hard label sizes | EPIC-09 profiling |
| `soft_probabilities_shape` | Responsibility matrix shape | Verification |
| `responsibility_max_probability_*` | Confidence summary | EPIC-09 analysis |

### 10.3 Soft clustering consumers

- **EPIC-07**: Consume responsibility matrix cho model comparison.
- **EPIC-08**: Algorithm comparison dashboard.
- **EPIC-09**: Segment analysis và confidence-based interpretation.

---

## 11. What ML-05 does NOT do

| Scope | Reason |
|-------|--------|
| Evaluation metrics (silhouette, DBI, CH) | EPIC-07/08 scope |
| Algorithm comparison (GMM vs others) | EPIC-08 scope |
| Sweep `(n_components, covariance_type, init_params)` | EPIC-07 scope |
| Model selection via AIC / BIC | EPIC-07 scope (diagnostics only) |
| Segment profiling / naming | EPIC-09 scope |
| Visualization (cluster plots, BIC curves) | EPIC-08/09 scope |
| Claim "best n_components" / "best covariance_type" / "best algorithm" | AGENTS.md §2.5 |

---

## 12. Completion summary

### 12.1 Files created / modified

| File | Type | Description |
|------|------|-------------|
| `src/customer_segmentation/clustering/gmm.py` | Implementation | `GMMAdapter` class |
| `tests/test_ml05_gmm.py` | Tests | 66 tests covering all aspects |
| `scripts/run_ml05_gmm.py` | Orchestrator | Diagnostic runs + report generation |
| `reports/ml05/ml05_run_summary.json` | Report | Machine-readable summary |
| `reports/ml05/ml05_initial_diagnostic.md` | Report | Vietnamese narrative |
| `reports/ml05/ml05_covariance_type_diagnostic.csv` | Report | Per-covariance diagnostic table |
| `data/processed/clustering_experiments/cluster_labels_ML-05-GMM-*.parquet` | Artifact | Labels + Probability_k columns |
| `data/processed/clustering_experiments/algorithm_output_ML-05-GMM-*.parquet` | Artifact | Full responsibility matrix |
| `data/processed/clustering_experiments/experiment_log_ML-05-GMM-*.json` | Artifact | Full experiment metadata |

### 12.2 Implementation summary

ML-05 GMM **TECHNICALLY_IMPLEMENTED** với:
- **Adapter**: `GMMAdapter` wraps `sklearn.mixture.GaussianMixture`.
- **Soft clustering**: Full posterior responsibility matrix preserved
  in `ClusterResult.soft_probabilities` + artifacts.
- **Convergence diagnostics**: `converged`, `n_iter`, `lower_bound`,
  `AIC`, `BIC` recorded in `extra`.
- **Reproducibility**: `supports_random_state() == True`; framework
  injects seed; permutation-invariant checks in tests.
- **Covariance types**: All four (`full`, `tied`, `diag`, `spherical`)
  verified via tests + diagnostic runs.

### 12.3 Tests: 66 / 66 PASS

### 12.4 Lint: PASS

### 12.5 Format: PASS

### 12.6 Input / Output SHA

| Item | SHA-256 |
|------|---------|
| Input dataset | `ba54033e45525bf5...` |
| Customer metadata | `c2a42b3c8b035dcf...` |
| Config | `d5172c4640d7bc2c...` |

### 12.7 Assumptions

1. `n_components=4` là WORKING_ASSUMPTION (EPIC-07 sẽ sweep).
2. `covariance_type='full'` là WORKING_ASSUMPTION (EPIC-07 sẽ sweep).
3. `init_params='kmeans'` là WORKING_ASSUMPTION (EPIC-07 sẽ sweep).
4. `lower_bound`, `AIC`, `BIC` là diagnostics only, không dùng cho
   model selection trong ML-05.
5. Label permutation là known GMM property; reproducibility check
   dùng responsibilities, không dùng raw labels.

### 12.8 Pending Review

| ID | Decision | Status |
|----|----------|--------|
| ML-05-MET-01 | `working_n_components=4` | PENDING_REVIEW |
| ML-05-MET-02 | `working_covariance_type='full'` | PENDING_REVIEW |
| ML-05-MET-03 | `working_init_params='kmeans'` | PENDING_REVIEW |
| ML-05-MET-04 | AIC/BIC/lower_bound diagnostics only | PENDING_REVIEW |
| ML-05-MET-05 | Label permutation reproducibility caveat | PENDING_REVIEW |
| ML-05-MET-06 | Per-covariance-type diagnostic runs | PENDING_REVIEW |

### 12.9 Remaining issues

- **Evaluation metrics**: `MetricsResult` toàn field = `None`. EPIC-07/08
  sẽ compute.
- **Sweep `(n_components, covariance_type, init_params)`**: Chỉ có 1
  primary + 4 per-covariance diagnostic; EPIC-07 sẽ sweep đầy đủ.
- **Algorithm comparison**: EPIC-08.
- **Segment profiling / naming**: EPIC-09.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-05 implementation
(code, tests, config, primary + per-covariance diagnostic runs,
experiment log, artifacts, parameter diagnostic CSV). Mọi con số đều có
provenance rõ ràng. Soft clustering output (responsibility matrix) là
primary characteristic của GMM, được bảo toàn cho downstream consumers
(EPIC-07/08/09)._
