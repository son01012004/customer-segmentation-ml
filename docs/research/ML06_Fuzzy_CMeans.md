# ML-06 Mentor Document — Fuzzy C-Means (FCM)

> **Status: TECHNICALLY_IMPLEMENTED**
>
> Mentor document này tổng hợp evidence từ implementation, tests, và
> diagnostic runs. Nó ghi nhận các quyết định methodology/engineering
> cần mentor review, phân biệt rõ giữa `TECHNICALLY_IMPLEMENTED`
> và `RESEARCH_DECISION_APPROVED`.
>
> KHÔNG gọi FCM là "best algorithm", KHÔNG gọi `n_clusters=4` là
> "optimal", KHÔNG gọi `m=2.0` là "recommended". Đó là EPIC-07 scope.

---

## 1. Overview

| Field | Value |
|-------|-------|
| Task | ML-06 Fuzzy C-Means (FCM) |
| Algorithm family | `fuzzy` (fuzzy / soft clustering) |
| Implementation | Custom numpy-based Bezdek FCM core (`custom_v1`) |
| Adapter | `FuzzyCMeansAdapter` in `src/customer_segmentation/clustering/fuzzy_cmeans.py` |
| Primary experiment | `ML-06-FCM-c4-m2-err0.0001-mi300-seed42` |
| Primary status | **SUCCESS** |
| Framework | ML-01 `ExperimentRunner` |
| EPIC contract | EPIC-06 §3.6 |

**Mục tiêu ML-06:** Implement Fuzzy C-Means adapter cho ML-01 framework
và chạy initial diagnostic runs trên FE-06 dataset. KHÔNG evaluate,
KHÔNG so sánh, KHÔNG pick "best" configuration.

---

## 2. Algorithm summary

### 2.1 What FCM does

**Fuzzy C-Means** (Dunn 1973; Bezdek 1981) generalises K-Means bằng cách
thay binary "ownership" bằng *membership degree* `u_ik ∈ [0, 1]` thể
hiện mức độ observation `x_i` thuộc về cluster `k`.

**Constraints:**
```
u_ik ∈ [0, 1]    for all i, k
Σ_{k=1..c} u_ik = 1    for every observation i
```

Mỗi row của membership matrix `U = [u_ik]` là một probability simplex
vector.

**Objective function** mà FCM minimises:
```
J_m(U, V) = Σ_{i=1..n} Σ_{k=1..c} (u_ik)^m · ||x_i - v_k||²
```
- `V = {v_1, ..., v_c}` = fuzzy centroids.
- `m > 1` = **fuzziness parameter** kiểm soát partition mềm/cứng.
  - `m → 1` → hard partition (K-Means).
  - `m → ∞` → uniform membership (1/c cho mọi cluster).

**Fuzzy centroid:**
```
v_k = [Σ_i (u_ik)^m · x_i] / [Σ_i (u_ik)^m]
```
Đây KHÔNG phải arithmetic mean (K-Means centroid); weighting by
`(u_ik)^m` là điều làm centroid có fuzzy character.

**Membership update** (canonical Bezdek form, Euclidean distance):
```
u_ik = 1 / Σ_j (d_ik / d_ij)^(2/(m-1))
```
Exponent `p = 2/(m-1)` positive vì `m > 1`.

**Hard label:** `label_i = argmax_k u_ik` (lossy projection).

### 2.2 Algorithm family

FCM thuộc **fuzzy / soft clustering** family. So với GMM (model-based):
- FCM không assume Gaussian distribution.
- FCM membership = degree of belonging, không phải posterior probability.
- Cả hai đều cung cấp soft output.

### 2.3 Implementation note: Custom core

FCM implementation là **custom numpy-based** (không dùng `scikit-fuzzy`).
Rationale: AGENTS.md §5 cấm thêm dependency mới không qua ADR.
Custom implementation:
- Reproduces canonical Bezdek / Dunn FCM algorithm.
- Fully deterministic khi `random_state` fixed.
- Handles edge cases: empty cluster, zero-distance observations,
  numerical clipping, negative squared distance.

### 2.4 Random state

FCM **consumes** `random_state` cho membership-matrix Dirichlet
initialisation. → `supports_random_state() == True`. Framework runner
inject seed.

---

## 3. Adapter design decisions

### 3.1 Exposed hyperparameters

Adapter expose các hyperparameters sau:

| Hyperparameter | Type | Default | Notes |
|---------------|------|---------|-------|
| `n_clusters` | int ≥ 1 | 4 | Số fuzzy clusters `c` |
| `m` | float > 1 | 2.0 | Fuzziness parameter |
| `max_iter` | int ≥ 1 | 300 | Maximum iterations |
| `error` | float > 0 | 1e-4 | Convergence threshold |
| `random_state` | int \| None | None | Seed for Dirichlet init |

**Working defaults** (`configs/clustering.yaml`):
- `n_clusters = 4` → WORKING_ASSUMPTION
- `m = 2.0` → WORKING_ASSUMPTION
- `max_iter = 300` → WORKING_ASSUMPTION
- `error = 1e-4` → WORKING_ASSUMPTION

### 3.2 What is NOT exposed

- Distance metric (fixed: Euclidean).
- Weighting exponent (`m-1` is implicit in Bezdek formula).
- Initialization strategy beyond random Dirichlet.
- Convergence criterion (fixed: max-norm change on U).

### 3.3 Soft clustering output

FCM là defining characteristic của **fuzzy clustering**:
- **Hard labels**: `argmax` over membership matrix.
- **Soft membership**: full fuzzy membership matrix
  `U` shape `(n_samples, n_clusters)`.

Adapter preserve **BOTH**:
1. `ClusterResult.cluster_labels` (hard labels).
2. `ClusterResult.soft_membership` (full membership matrix).

Artifact writer emit:
- `cluster_labels_*.parquet`: CustomerID + ClusterLabel + IsNoise + `Membership_k` columns.
- `algorithm_output_*.parquet`: CustomerID + `Membership_k` columns.

**Note:** GMM dùng `soft_probabilities`; FCM dùng `soft_membership`.
Đây là two distinct fields vì semantic khác nhau:
- GMM `soft_probabilities` = posterior Bayesian probabilities.
- FCM `soft_membership` = fuzzy degree of belonging.

### 3.4 Convergence diagnostics

Adapter records:
- `converged` (bool): max-norm change on U < `error`.
- `n_iter` (int): actual iterations used.
- `final_objective` (float): J_m value after convergence.
- `objective_history` (list): J_m at each iteration.

These are recorded in `ClusterResult.extra` as **diagnostic only**.
`final_objective` is NOT a clustering quality metric.

---

## 4. FCM-specific diagnostics

### 4.1 Membership integrity

| Diagnostic | Value |
|------------|-------|
| `membership_shape` | `[n_samples, n_clusters]` |
| `membership_min` | ≥ 0 (trong practice: 0.000467 cho primary run) |
| `membership_max` | ≤ 1 (trong practice: 0.995 cho primary run) |
| `membership_row_sum_min` | ≈ 1.0 (0.9999999999999997) |
| `membership_row_sum_max` | ≈ 1.0 (1.0000000000000002) |

### 4.2 Confidence summary

| Diagnostic | Description |
|------------|-------------|
| `membership_confidence_min` | Min of `max_k u_ik` across all observations |
| `membership_confidence_max` | Max of `max_k u_ik` (always 1 in theory, < 1 in practice) |
| `membership_confidence_mean` | Mean of `max_k u_ik` |

Higher mean → partition closer to hard (clear cluster boundaries).
Lower mean → partition closer to uniform 1/c (fuzzy boundary).

### 4.3 Objective behavior (diagnostic only)

`final_objective` decreases monotonically across iterations (EM-like).
m lớn hơn → objective nhỏ hơn (vì exponent `(u_ik)^m` giảm khi u_ik < 1).

**Observations từ diagnostic runs:**
- m=1.5: objective = 154974.8
- m=2.0: objective = 110009.7
- m=2.5: objective = 63855.8
- m=3.0: objective = 35051.8

**KHÔNG kết luận "best m" từ these numbers.** Đó là EPIC-07 scope.

---

## 5. Per-fuzziness diagnostic runs

### 5.1 Diagnostic results

| m | Status | converged | n_iter | final_objective | confidence_mean | Execution (s) |
|--:|--------|-----------|-------:|---------------:|---------------:|-------------:|
| 1.5 | SUCCESS | True | 41 | 154974.8005 | 0.9467 | 0.0551 |
| 2.0 | SUCCESS | True | 60 | 110009.6673 | 0.6152 | 0.0688 |
| 2.5 | SUCCESS | True | 100 | 63855.7596 | 0.4976 | 0.1327 |
| 3.0 | SUCCESS | True | 45 | 35051.7537 | 0.4587 | 0.0518 |

### 5.2 Observations (diagnostic only)

- m gần 1 → partition cứng hơn → confidence_mean cao hơn (~0.95).
- m lớn → partition mềm hơn → confidence_mean thấp hơn (~0.46).
- m=2.5 đạt max_iter (100) → có thể chưa fully converge với `error=1e-4`.
- m=3.0 đạt 45 iterations → nhanh hơn m=2.0 (vì smoother objective landscape).

**KHÔNG có m nào được kết luận là "best" trong tài liệu này.**

---

## 6. Primary run summary

### 6.1 Configuration

| Parameter | Value | Status |
|-----------|-------|--------|
| `n_clusters` | 4 | WORKING_ASSUMPTION |
| `m` (fuzziness) | 2.0 | WORKING_ASSUMPTION |
| `max_iter` | 300 | WORKING_ASSUMPTION |
| `error` | 1e-4 | WORKING_ASSUMPTION |
| `random_state` | 42 | Framework seed |

### 6.2 Results

| Metric | Value |
|--------|-------|
| Status | SUCCESS |
| n_clusters | 4 |
| n_samples | 4371 |
| n_features | 14 |
| `converged` | True |
| `n_iter` | 60 |
| `final_objective` J_m | 110009.6673 |
| Execution time | 0.0652 s |

### 6.3 Membership statistics

| Metric | Value |
|--------|-------|
| `membership_min` | 0.000467 |
| `membership_max` | 0.995239 |
| `membership_row_sum_min` | 0.9999999999999997 |
| `membership_row_sum_max` | 1.0000000000000002 |
| `confidence_min` | 0.262439 |
| `confidence_max` | 0.995239 |
| `confidence_mean` | 0.615160 |

### 6.4 Cluster sizes from hard label

| Cluster | Size |
|---------|-----:|
| 0 | 1337 |
| 1 | 529 |
| 2 | 1928 |
| 3 | 577 |

---

## 7. Reproducibility

### 7.1 FCM reproducibility contract

FCM **consumes** `random_state` for Dirichlet membership initialization.
Same input + same configuration + same library version → same:
- Membership matrix
- Centroids
- Final objective
- Converged flag + n_iter

### 7.2 Label permutation caveat

FCM có known **label permutation property**: cluster IDs có thể swap
giữa các runs (ngay cả với cùng seed, khi FCM partition khác nhau
ở local minimum khác nhau). Therefore:
- **KHÔNG** dùng raw label equality làm reproducibility check.
- Dùng permutation-invariant quantities: membership matrix, centroids,
  final objective, n_iter.

---

## 8. Verification

### 8.1 Tests

| Test category | File | Số test | Trạng thái |
|--------------|------|---------|------------|
| Interface + registration | `test_ml06_fuzzy.py` | 11 | **PASS** |
| Parameter validation | `test_ml06_fuzzy.py` | 7 | **PASS** |
| Input validation | `test_ml06_fuzzy.py` | 6 | **PASS** |
| Membership integrity | `test_ml06_fuzzy.py` | 6 | **PASS** |
| Objective convergence | `test_ml06_fuzzy.py` | 4 | **PASS** |
| Reproducibility | `test_ml06_fuzzy.py` | 4 | **PASS** |
| Fuzziness behavior | `test_ml06_fuzzy.py` | 2 | **PASS** |
| Output schema | `test_ml06_fuzzy.py` | 7 | **PASS** |
| Integration with ExperimentRunner | `test_ml06_fuzzy.py` | 9 | **PASS** |
| **TOTAL** | | **56** | **PASS (56/56)** |

### 8.2 Lint

```bash
ruff check src/customer_segmentation/clustering/fuzzy_cmeans.py tests/test_ml06_fuzzy.py scripts/run_ml06_fuzzy_cmeans.py
```

Result: **All checks passed!**

### 8.3 Format

```bash
black --check src/customer_segmentation/clustering/fuzzy_cmeans.py tests/test_ml06_fuzzy.py scripts/run_ml06_fuzzy_cmeans.py
```

Result: **3 files would be left unchanged.**

### 8.4 Input integrity

- FE-06 outputs không bị ML-06 mutate.
- `validate_clustering_matrix` và `validate_customer_alignment` PASS.
- Input SHA-256: `ba54033e45525bf5...`
- Config SHA-256: `d5172c4640d7bc2c...`

### 8.5 Output integrity

- `cluster_labels` shape `(4371,)`, dtype `int64` ✅.
- `cluster_labels` values in `[0, 3]` (4 clusters) ✅.
- `soft_membership` shape `(4371, 4)` ✅.
- `soft_membership` row sums ∈ [0.9999999999999997, 1.0000000000000002] ✅.
- `converged == True`, `n_iter == 60` ✅.
- `noise_count == 0` (FCM không có noise concept) ✅.
- Artifacts: `cluster_labels_*.parquet` + `experiment_log_*.json` +
  `algorithm_output_*.parquet` ✅.

---

## 9. Decision status

### 9.1 Engineering / Scope decisions (DOCUMENTED)

| ID | Decision | Status |
|----|----------|--------|
| ML-06-ENG-01 | Custom numpy-based Bezdek FCM core (không dùng `scikit-fuzzy` để tránh expanding dependency surface) | DOCUMENTED |
| ML-06-ENG-02 | Adapter expose `(n_clusters, m, max_iter, error, random_state)` — không expose distance metric, weighting exponent, initialization strategy | DOCUMENTED |
| ML-06-ENG-03 | Soft membership preserved via `ClusterResult.soft_membership` + `algorithm_output_*.parquet` + `Membership_k` columns in `cluster_labels_*.parquet` | DOCUMENTED |
| ML-06-ENG-04 | `soft_probabilities = None`, `soft_membership` set (FCM ≠ GMM: membership is degree of belonging, not posterior probability) | DOCUMENTED |
| ML-06-ENG-05 | `n_clusters` computed from `n_clusters` parameter (not from `np.unique(labels)`) | DOCUMENTED |
| ML-06-ENG-06 | `noise_count == 0`, `noise_label == -1` (FCM không có noise concept) | DOCUMENTED |

### 9.2 Methodology decisions (PENDING_REVIEW)

| ID | Decision | Status |
|----|----------|--------|
| ML-06-MET-01 | `working_n_clusters=4` cho ML-06 primary diagnostic | PENDING_REVIEW |
| ML-06-MET-02 | `working_m=2.0` (fuzziness) cho working default | PENDING_REVIEW |
| ML-06-MET-03 | `working_max_iter=300`, `working_error=1e-4` cho convergence | PENDING_REVIEW |
| ML-06-MET-04 | `final_objective`, `n_iter`, `converged`, confidence summary ghi nhận là diagnostics only, KHÔNG dùng để tuyên bố "best" configuration | PENDING_REVIEW |
| ML-06-MET-05 | 4 per-fuzziness diagnostic runs (m=1.5, 2.0, 2.5, 3.0) trong EPIC-06 | PENDING_REVIEW |

---

## 10. Contract with downstream EPICs

### 10.1 Output schema

| Field | Type | Value |
|-------|------|-------|
| `algorithm_family` | str | `"fuzzy"` |
| `cluster_labels` | np.ndarray shape `(4371,)` dtype `int64` | `[0, K-1]` |
| `soft_membership` | np.ndarray shape `(4371, n_clusters)` dtype `float64` | Full membership matrix |
| `soft_probabilities` | None | FCM dùng `soft_membership` |
| `n_clusters` | int | `n_clusters` parameter |
| `noise_count` | int | `0` |
| `noise_ratio` | float | `0.0` |
| `supports_random_state` | bool | `True` |

### 10.2 Extra diagnostics for EPIC-07

| Key | Description | Consumer |
|-----|-------------|----------|
| `n_clusters` | Number of fuzzy clusters | EPIC-07 sweep |
| `fuzziness` | Fuzziness parameter `m` | EPIC-07 sweep |
| `max_iter`, `error` | Convergence parameters | EPIC-07 diagnostics |
| `converged` | Convergence flag | EPIC-07 diagnostics |
| `n_iter` | Iterations used | EPIC-07 diagnostics |
| `final_objective` | J_m value (diagnostic only) | EPIC-07 diagnostics |
| `objective_history` | J_m per iteration | EPIC-09 profiling |
| `membership_shape` | Membership matrix shape | Verification |
| `membership_confidence_*` | Confidence summary | EPIC-09 analysis |
| `cluster_sizes` | Hard label sizes | EPIC-09 profiling |

### 10.3 Soft clustering consumers

- **EPIC-07**: Consume membership matrix cho model comparison.
- **EPIC-08**: Algorithm comparison dashboard.
- **EPIC-09**: Segment analysis với confidence-based interpretation.

---

## 11. What ML-06 does NOT do

| Scope | Reason |
|-------|--------|
| Evaluation metrics (silhouette, DBI, CH) | EPIC-07/08 scope |
| Algorithm comparison (FCM vs others) | EPIC-08 scope |
| Sweep `(n_clusters, m, max_iter, error)` | EPIC-07 scope |
| Model selection via objective / confidence | EPIC-07 scope (diagnostics only) |
| Segment profiling / naming | EPIC-09 scope |
| Visualization | EPIC-08/09 scope |
| Claim "best n_clusters" / "best m" / "best algorithm" | AGENTS.md §2.5 |

---

## 12. Completion summary

### 12.1 Files created / modified

| File | Type | Description |
|------|------|-------------|
| `src/customer_segmentation/clustering/fuzzy_cmeans.py` | Implementation | `FuzzyCMeansAdapter` class + Bezdek FCM core |
| `tests/test_ml06_fuzzy.py` | Tests | 56 tests covering all aspects |
| `scripts/run_ml06_fuzzy_cmeans.py` | Orchestrator | Diagnostic runs + report generation |
| `reports/ml06/ml06_run_summary.json` | Report | Machine-readable summary |
| `reports/ml06/ml06_initial_diagnostic.md` | Report | Vietnamese narrative |
| `reports/ml06/ml06_fuzziness_diagnostic.csv` | Report | Per-fuzziness diagnostic table |
| `reports/ml06/ml06_baseline_matrix.csv` | Report | Algorithm comparison baseline |
| `data/processed/clustering_experiments/cluster_labels_ML-06-FCM-*.parquet` | Artifact | Labels + Membership_k columns |
| `data/processed/clustering_experiments/algorithm_output_ML-06-FCM-*.parquet` | Artifact | Full membership matrix |
| `data/processed/clustering_experiments/experiment_log_ML-06-FCM-*.json` | Artifact | Full experiment metadata |

### 12.2 Implementation summary

ML-06 Fuzzy C-Means **TECHNICALLY_IMPLEMENTED** với:
- **Adapter**: `FuzzyCMeansAdapter` wraps custom numpy-based Bezdek FCM core.
- **Soft clustering**: Full fuzzy membership matrix preserved in
  `ClusterResult.soft_membership` + artifacts.
- **Convergence diagnostics**: `converged`, `n_iter`, `final_objective`,
  `objective_history`, confidence summary recorded in `extra`.
- **Reproducibility**: `supports_random_state() == True`; framework
  injects seed; permutation-invariant checks in tests.
- **Per-fuzziness diagnostics**: 4 runs (m=1.5, 2.0, 2.5, 3.0) verified.

### 12.3 Tests: 56 / 56 PASS

### 12.4 Lint: PASS

### 12.5 Format: PASS

### 12.6 Input / Output SHA

| Item | SHA-256 |
|------|---------|
| Input dataset | `ba54033e45525bf5...` |
| Customer metadata | `c2a42b3c8b035dcf...` |
| Config | `d5172c4640d7bc2c...` |

### 12.7 Assumptions

1. `n_clusters=4` là WORKING_ASSUMPTION (EPIC-07 sẽ sweep).
2. `m=2.0` (fuzziness) là WORKING_ASSUMPTION (EPIC-07 sẽ sweep).
3. `max_iter=300`, `error=1e-4` là WORKING_ASSUMPTION.
4. `final_objective`, `n_iter`, confidence summary là diagnostics only,
   không dùng cho model selection trong ML-06.
5. Custom FCM core deterministic dưới fixed `random_state`.

### 12.8 Pending Review

| ID | Decision | Status |
|----|----------|--------|
| ML-06-MET-01 | `working_n_clusters=4` | PENDING_REVIEW |
| ML-06-MET-02 | `working_m=2.0` | PENDING_REVIEW |
| ML-06-MET-03 | `working_max_iter=300`, `working_error=1e-4` | PENDING_REVIEW |
| ML-06-MET-04 | Objective / confidence diagnostics only | PENDING_REVIEW |
| ML-06-MET-05 | Per-fuzziness diagnostic runs | PENDING_REVIEW |

### 12.9 Remaining issues

- **Evaluation metrics**: `MetricsResult` toàn field = `None`. EPIC-07/08
  sẽ compute.
- **Sweep `(n_clusters, m)`**: Chỉ có 1 primary + 4 per-fuzziness
  diagnostic; EPIC-07 sẽ sweep đầy đủ.
- **Algorithm comparison**: EPIC-08.
- **Segment profiling / naming**: EPIC-09.

---

_Báo cáo này được tổng hợp từ evidence thực tế của ML-06 implementation
(code, tests, config, primary + per-fuzziness diagnostic runs, experiment
log, artifacts, parameter diagnostic CSV). Mọi con số đều có provenance
rõ ràng. Soft clustering output (membership matrix) là primary
characteristic của FCM, được bảo toàn cho downstream consumers
(EPIC-07/08/09)._
