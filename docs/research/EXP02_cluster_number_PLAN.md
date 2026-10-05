# PLAN — EXP-02 Cluster Number Survey (Revision 0)

> **Mục đích:** Tài liệu này là **implementation PLAN** cho EXP-02, không phải
> Mentor document hoàn chỉnh.
>
> **TUYỆT ĐỐI KHÔNG** chạy code / tạo file / sửa file / commit / push / PR
> trong bước này (ngoài implementation phase đã được thực hiện).

---

## 1. Phạm vi EXP-02

### 1.1. Mục tiêu

Khảo sát ảnh hưởng của số lượng cluster / component (K) đối với 4 thuật
toán trong EPIC-06 có tham số K:

- K-Means (`n_clusters = K`)
- Agglomerative (`n_clusters = K`)
- Gaussian Mixture Model (`n_components = K`)
- Fuzzy C-Means (`n_clusters = K`)

DBSCAN **không** có K trực tiếp → chỉ được ghi nhận như một diagnostic
entry đơn lẻ (1 run duy nhất với baseline `eps=0.5, min_samples=5`).

EXP-02 cung cấp:

- **Metric curves** theo K cho mỗi (algorithm × K) combination:
  silhouette / Davies-Bouldin / Calinski-Harabasz / WCSS.
- **Evidence-based candidate cluster numbers** — tập K được flag bởi
  transparent, deterministic heuristic dựa trên metric evidence.
- **Bảo toàn provenance** cho mỗi (algorithm, K) combination:
  input SHA, config SHA, hyperparameters, seed, library versions,
  execution_time, metric status.
- **Tái sử dụng** EXP-01 metrics layer (silhouette, DBI, CH, WCSS) verbatim.

### 1.2. Ranh giới EXP-02

| EXP-02 LÀM | EXP-02 KHÔNG LÀM |
|------------|-------------------|
| K-sweep cho K-Means / Agglomerative / GMM / Fuzzy C-Means | Tạo RFM-only feature set (RQ2 dimension) |
| Reuse EXP-01 metrics layer | Rank algorithms |
| WCSS dùng arithmetic centroid từ hard labels | Chọn "best K" / "optimal K" / "final K" / "recommended K" |
| DBSCAN noise bị exclude khỏi metrics (mirror EXP-01) | Stability analysis (EXP-05 / EPIC-08 scope) |
| Diagnostic run cho DBSCAN | Sweep non-K hyperparameters |
| Tạo metric curves + candidates | Customer profiling (EPIC-09) |
| Đo runtime algorithm execution | Business interpretation |
| Tạo diagnostic plots (factual metric curves) | Comparative conclusion giữa algorithms |

### 1.3. Tiêu chí "thành công" của EXP-02

EXP-02 TECHNICALLY_IMPLEMENTED khi:

1. K-sweep chạy cho 4 algorithms × K=2..10 = 36 K-sweep runs.
2. DBSCAN diagnostic run chạy thành công (1 run).
3. Tất cả metrics có status `VALID_VALUE` (no `MISSING`).
4. Metric curves CSV (long format) được sinh ra.
5. Candidate cluster numbers CSV được sinh ra (evidence-based).
6. Bảo toàn FE-06 input SHA-256 (no mutation).
7. Tests pass (unit + integration).
8. Lint + format pass.
9. Không có "best K" / "winner" / "recommended" claim trong code/report.

---

## 2. Gap Analysis với EXP-01

### 2.1. Tái sử dụng từ EXP-01

| Component | Tái sử dụng? |
|-----------|--------------|
| `ExperimentRunner` | **CÓ** — gọi trực tiếp, không sửa |
| `FrameworkConfig` | **CÓ** — đọc `configs/clustering.yaml` |
| 5 algorithm adapters | **CÓ** — registry không sửa |
| `ClusterResult` / `ExperimentResult` schema | **CÓ** — không sửa |
| Artifact writers | **CÓ** — không sửa |
| `metrics.py` (silhouette, DBI, CH, WCSS) | **CÓ** — `attach_metrics_with_status` reused |
| `baseline.py` `BaselineRunner` (orchestrator pattern) | **CÓ** — pattern reused |
| Working defaults từ `configs/exp01_baseline.yaml` | **CÓ** — mirror trong `configs/exp02_cluster_number.yaml` |
| `baseline_seed=42`, `n_repeat=5` runtime protocol | **CÓ** — same convention |

### 2.2. Thành phần MỚI

| Path | Mô tả |
|------|-------|
| `configs/exp02_cluster_number.yaml` | EXP-02 config riêng (working K range, candidate heuristic) |
| `src/customer_segmentation/clustering/cluster_number.py` | `ClusterNumberRunner` orchestrator |
| `scripts/run_exp02_cluster_number.py` | CLI entry point |
| `tests/test_exp02_cluster_number.py` | Behavioral tests (44 tests) |
| `reports/exp02/` | Output reports & figures |

### 2.3. Feature set / RQ2

Repo hiện tại chỉ có FE-06 final clustering matrix = **Extended RFM**
(14 features: Recency, Frequency, Monetary, ... ReturnRate). Không có
RFM-only artifact riêng.

**PENDING_REVIEW (EXP02-FS-01):** Repo không expose RFM-only parquet;
EXP-02 chỉ chạy trên Extended RFM. RQ2 dimension (RFM-only vs
RFM-Extended comparison) yêu cầu FE-06 tạo thêm sub-artifact (cần ADR).
EXP-02 không có authority tự tạo feature set mới.

Khi/ Nếu FE-06 tạo RFM-only parquet → `configs/exp02_cluster_number.yaml`
phải add entry mới vào `feature_sets`, CLI phải chạy riêng cho feature
set mới.

### 2.4. Có sửa EPIC-06 framework không?

**KHÔNG.** EXP-02 chỉ:
- Đọc `FrameworkConfig` từ `configs/clustering.yaml`.
- Gọi `ExperimentRunner.run()` không qua modification.
- Reuse `metrics.attach_metrics_with_status` không qua modification.
- Reuse `AlgorithmRegistry` không qua modification.

Mọi EPIC-06 framework files (`runner.py`, `result.py`, `metrics.py`,
`baseline.py`, ...) không bị sửa.

---

## 3. K range selection

### 3.1. Quyết định K range = [2, 10], step=1

| Lý do | Giải thích |
|-------|-----------|
| Mirror framework default | `configs/clustering.yaml` đã có `k_range: [2, 10]` cho K-Means, Agglomerative, K-Medoids. Đây là **working assumption** đã có sẵn. |
| K=1 trivial | Với K=1, internal metrics (silhouette, DBI, CH) không được định nghĩa; không có elbow point để observe. |
| K=10 là upper bound | Đây là upper bound đã được khóa trong framework YAML; mentor/human researcher sẽ override nếu cần. |
| Step=1 fine-grained | Với budget chạy ~5 algo × 9 K × 5 repetitions ≈ 225 fits, runtime vẫn tractable với FE-06 dataset (n=4371). |

**Status:** `WORKING_ASSUMPTION` (PENDING_REVIEW `EXP02-KRNG-01`).

Mentor/human researcher có thể override trong `configs/exp02_cluster_number.yaml`
mà không cần sửa code.

### 3.2. KHÔNG sweep non-K hyperparameters

Mỗi (algorithm, K) combination giữ cố định:

| Algorithm | Fixed non-K hyperparameters |
|-----------|----------------------------|
| K-Means | `init='k-means++', n_init=10, max_iter=300, tol=1e-4` |
| Agglomerative | `linkage='ward', metric='euclidean', compute_distances=True` |
| GMM | `covariance_type='full', init_params='kmeans', tol=1e-3, reg_covar=1e-6, max_iter=100, n_init=1` |
| Fuzzy C-Means | `m=2.0, max_iter=300, error=1e-4` |

Đây là EXP-01 working defaults.

### 3.3. KHÔNG sweep DBSCAN

DBSCAN không có K parameter. Trong EXP-02:

- Chỉ chạy 1 diagnostic entry với `eps=0.5, min_samples=5`.
- Ghi nhận n_clusters phát hiện được, noise_count, noise_ratio.
- Tính metrics trên non-noise subset.
- KHÔNG tự sweep eps / min_samples trong EXP-02.

`PENDING_REVIEW (EXP02-DBSCAN-01)`: DBSCAN contribution to candidate set
là từ diagnostic entry này (1 sample point) — không phải K-sweep evidence.

---

## 4. Runtime Protocol (mirror EXP-01 §3)

### 4.1. Ba loại runtime — phân biệt bắt buộc

| Loại | EXP-02 ghi vào? |
|------|----------------|
| **Algorithm execution runtime** | **CÓ** — `result.runtime_stats.mean/std/min/max/raw_seconds` |
| **Metric computation runtime** | **GHI RIÊNG** trong `metrics.runtime["metric_computation"]` |
| **Artifact/report writing runtime** | **KHÔNG** — ngoài runtime stats |

### 4.2. Repetition protocol

- `n_repeat = 5` cho mỗi (algorithm, K).
- `seed = 42` cho mọi repetitions.
- Đây là **runtime measurement**, KHÔNG phải stability analysis.
- Stability analysis (ARI/AMI across seeds) thuộc EXP-05 / EPIC-08.

### 4.3. WCSS policy

- WCSS dùng **arithmetic centroid từ hard labels** (mirror EXP-01).
- GMM: hard labels = `argmax(posterior probabilities)`.
- FCM: hard labels = `argmax(membership matrix)`.
- DBSCAN: noise excluded trước khi tính WCSS.

---

## 5. Candidate Cluster Number Heuristic

### 5.1. Transparent, deterministic

`generate_candidate_clusters(curves, top_n, elbow_drop, min_agreement)`:

Per algorithm:
1. **silhouette_top_n**: top-N K có silhouette cao nhất.
2. **davies_bouldin_low_n**: bottom-N K có DBI thấp nhất (DBI convention: thấp hơn = clusters compact hơn).
3. **calinski_harabasz_top_n**: top-N K có CH cao nhất.
4. **wcss_elbow_drop**: K mà WCSS(K+1)/WCSS(K) drop ≥ `elbow_drop_ratio_threshold`.

Một K được flag bởi ≥ `min_agreement_count` indicators → candidate.

### 5.2. Working defaults (WORKING_ASSUMPTION)

| Constant | Default | Status |
|----------|---------|--------|
| `top_n_per_indicator` | 3 | `WORKING_ASSUMPTION` |
| `elbow_drop_ratio_threshold` | 0.2 | `WORKING_ASSUMPTION` |
| `min_agreement_count` | 2 | `WORKING_ASSUMPTION` |

Mentor/human researcher có thể override trong `configs/exp02_cluster_number.yaml`.

### 5.3. Candidate ≠ Final

Candidate là tập K **worth inspecting**, KHÔNG phải:
- "best K" / "optimal K" / "final K" / "recommended K"
- comparative conclusion
- final model selection

Final selection thuộc về EPIC-08 và mentor/human researcher.

### 5.4. Disagreement giữa indicators

Khi các indicators flag K khác nhau (e.g., silhouette chọn K=2, CH chọn
K=5) → KHÔNG tự resolve bằng cách chọn 1 metric. Mỗi indicator evidence
được ghi nhận trong `evidence_indicators` field.

---

## 6. Implementation Overview

### 6.1. Architecture

```
scripts/run_exp02_cluster_number.py
        │
        v
ClusterNumberRunner (cluster_number.py)
        │
        ├── run_sweep()
        │       ├── For each (algorithm in CANONICAL_ORDER) × (K in k_range):
        │       │     ├── build ClusterNumberSpec
        │       │     ├── _run_single()
        │       │     │     ├── ExperimentRunner.run() × n_repeat
        │       │     │     │     ├── fit() ← algorithm execution time
        │       │     │     │     └── (output_dir=None for non-final reps)
        │       │     │     └── attach_metrics_with_status() ← metric computation time
        │       │     └── collect ClusterNumberResult
        │       ├── For each diagnostic algorithm (e.g. dbscan):
        │       │     └── _run_diagnostic()
        │       │
        │       ├── generate_metric_curves()
        │       └── generate_candidate_clusters()
        │
        └── write_reports()
                ├── reports/exp02/exp02_manifest.json
                ├── reports/exp02/exp02_run_summary.json
                ├── reports/exp02/exp02_cluster_number_summary.csv
                ├── reports/exp02/exp02_metric_curves.csv
                ├── reports/exp02/exp02_candidate_cluster_numbers.csv
                ├── reports/exp02/exp02_cluster_number_analysis.md
                └── reports/exp02/figures/exp02_<algo>_<metric>_vs_k.png
```

### 6.2. Reuse vs New

| Component | Source | Modified? |
|-----------|--------|-----------|
| `ExperimentRunner.run()` | EXP-01 / EPIC-06 | NO |
| `ExperimentSpec` | EXP-01 / EPIC-06 | NO |
| `attach_metrics_with_status()` | EXP-01 metrics.py | NO |
| `compute_runtime_stats()` | EXP-01 metrics.py | NO |
| `ClusterResult` | EXP-01 / EPIC-06 | NO |
| `ExperimentResult` | EXP-01 / EPIC-06 | NO |
| `ClusterNumberSpec` / `ClusterNumberResult` / `ClusterNumberRunner` | NEW | YES |
| `generate_metric_curves()` / `generate_candidate_clusters()` | NEW | YES |
| `run_exp02_cluster_number.py` | NEW | YES |
| `configs/exp02_cluster_number.yaml` | NEW | YES |

---

## 7. File Plan

### 7.1. MỚI

| Path | Lines (approx) | Mô tả |
|------|----------------|-------|
| `configs/exp02_cluster_number.yaml` | ~270 | EXP-02 config |
| `src/customer_segmentation/clustering/cluster_number.py` | ~880 | EXP-02 orchestrator |
| `scripts/run_exp02_cluster_number.py` | ~822 | CLI runner |
| `tests/test_exp02_cluster_number.py` | ~692 | Behavioral tests |

### 7.2. KHÔNG sửa

- `src/customer_segmentation/clustering/runner.py`
- `src/customer_segmentation/clustering/result.py`
- `src/customer_segmentation/clustering/metrics.py`
- `src/customer_segmentation/clustering/baseline.py`
- `src/customer_segmentation/clustering/{kmeans,agglomerative,dbscan,gmm,fuzzy_cmeans}.py`
- `configs/clustering.yaml`
- `configs/experiment.yaml`
- `configs/exp01_baseline.yaml`

### 7.3. Output (under `reports/exp02/`)

| File | Format | Mô tả |
|------|--------|-------|
| `exp02_manifest.json` | JSON | Full manifest: all results + candidates + provenance |
| `exp02_run_summary.json` | JSON | Machine-readable summary |
| `exp02_cluster_number_summary.csv` | CSV (long) | Flat per-(algorithm, K) summary |
| `exp02_metric_curves.csv` | CSV (long) | Metric curves |
| `exp02_candidate_cluster_numbers.csv` | CSV | Candidates with evidence |
| `exp02_cluster_number_analysis.md` | Markdown | Vietnamese narrative report |
| `figures/exp02_<algo>_<metric>_vs_k.png` | PNG | 16 diagnostic plots (4 algos × 4 metrics) |

---

## 8. Tests

44 behavioral tests trong `tests/test_exp02_cluster_number.py`:

| Category | Tests |
|----------|-------|
| K range & combinations | 4 |
| Runner initialization | 2 |
| Single (algorithm, K) run | 5 |
| Diagnostic run | 2 |
| Full sweep | 6 |
| Output schema | 2 |
| Metrics reuse | 4 |
| Metric curves | 4 |
| Candidate evidence | 4 |
| Provenance | 3 |
| No input mutation | 1 |
| Config loading | 3 |
| Working defaults | 3 |
| Canonical ordering | 1 |

Coverage bao gồm:
- K passed đúng vào `n_clusters` (KMeans, Agglomerative, FCM) và `n_components` (GMM).
- DBSCAN không bị đưa vào K-sweep.
- Metrics reuse EXP-01 (no MISSING after success).
- Input SHA preserved.
- CustomerID alignment preserved.
- Canonical ordering preserved.
- Candidate evidence flags K correctly.
- No duplicate experiment IDs.
- No input mutation.

---

## 9. Assumptions

1. **FE-06 final clustering matrix** (Extended RFM, 14 features, SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`) là input duy nhất của EXP-02.

2. **CustomerID** nằm trong metadata (4371 rows), không nằm trong matrix.

3. **RFM-only feature set** không có sẵn (PENDING_REVIEW `EXP02-FS-01`). EXP-02 không tự tạo.

4. **EXP-01 working defaults** mirror từ `configs/exp01_baseline.yaml` được chấp nhận làm WORKING_ASSUMPTION.

5. **K range [2, 10]** mirror framework default là WORKING_ASSUMPTION (`PENDING_REVIEW`).

6. **Candidate heuristic constants** (`top_n=3, elbow_drop=0.2, min_agreement=2`) là WORKING_ASSUMPTION.

7. **DBSCAN diagnostic** dùng `eps=0.5, min_samples=5` (EXP-01 working default).

8. **Metrics implementation** mirror EXP-01 verbatim; KHÔNG tạo metric mới.

9. **DBSCAN noise handling** mirror EXP-01 (exclude noise khỏi metrics & WCSS).

10. **Random seed** = 42, same across all (algorithm, K) repetitions.

11. **`n_repeat` = 5** mirror EXP-01.

---

## 10. PENDING_REVIEW decisions

| ID | Decision | Status |
|----|----------|--------|
| EXP02-KRNG-01 | K range = [2, 10], step=1 | `WORKING_ASSUMPTION` |
| EXP02-FS-01 | RFM-only feature set NOT present; EXP-02 runs on RFM Extended only | `PENDING_REVIEW` (FE-06 ADR needed for RFM-only parquet) |
| EXP02-CDHC-01 | Candidate heuristic: top_n=3, drop_ratio=0.2, min_agreement=2 | `WORKING_ASSUMPTION` |
| EXP02-DBSCAN-01 | DBSCAN contributes only via diagnostic entry (no K-sweep) | `WORKING_ASSUMPTION` |
| EXP02-METRIC-01 | Metric status semantics mirror EXP-01 (no new metric) | `TECHNICALLY_IMPLEMENTED` |
| EXP02-REPRO-01 | Same seed across (algorithm, K) repetitions; this is NOT stability analysis | `TECHNICALLY_IMPLEMENTED` |

---

## 11. Những gì KHÔNG nằm trong scope EXP-02

| Nội dung | Lý do | Thuộc EPIC |
|----------|-------|-----------|
| Tạo RFM-only feature set | EXP-02 không có authority tạo feature set mới | FE-06 (cần ADR) |
| Sweep non-K hyperparameters (linkage, covariance_type, m, eps, ...) | Chỉ K là biến khảo sát | EPIC-07 (sweep) / EPIC-08 |
| Stability analysis (ARI/AMI across seeds) | EXP-02 chỉ reproducibility check; not stability | EXP-05 (evidence) + EPIC-08 (analysis) |
| Algorithm comparison / ranking | Ranking = EPIC-08 | EPIC-08 |
| "Best K" / "optimal K" / "final K" selection | AGENTS.md §2.5 cấm | EPIC-08 |
| Customer profiling / segment naming | Customer profiling = EPIC-09 | EPIC-09 |
| Hyperparameter tuning beyond K | Out of scope | EPIC-07 |

---

## 12. Workflow thực thi (đã hoàn thành)

```
Step 1: Tạo configs/exp02_cluster_number.yaml ✅
Step 2: Tạo src/customer_segmentation/clustering/cluster_number.py ✅
Step 3: Tạo scripts/run_exp02_cluster_number.py ✅
Step 4: Tạo tests/test_exp02_cluster_number.py ✅
Step 5: pytest test_exp02_cluster_number.py pass ✅ (44/44)
Step 6: pytest full pass ✅ (963/963)
Step 7: ruff check pass ✅
Step 8: black --check pass ✅
Step 9: Smoke run → verify reports ✅
```

---

## 13. Final Verification

EXP-02 has been verified:

- **37 runs total** (4 K-bearing algorithms × 9 K values + 1 DBSCAN diagnostic)
- **37/37 SUCCESS** (all metrics VALID_VALUE, no MISSING)
- **Input SHA-256**: `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` (FE-06, preserved)
- **Customer count**: 4,371 (matrix and metadata aligned)
- **Config SHA-256**: `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79`
- **13 candidates surfaced** with transparent evidence indicators
- **16 diagnostic plots** generated (4 algos × 4 metrics)
- **No mutation** of FE-06 final clustering dataset
- **No "best/winner/optimal/recommended"** language in code or reports
- **Canonical ordering** preserved (kmeans → agglomerative → dbscan → gmm → fuzzy_cmeans)
- **No modifications** to EPIC-06 framework files

Final status: `TECHNICALLY_IMPLEMENTED_AND_VERIFIED`.

---

*Plan Revision 0. Implementation completed Sep 21, 2026.*
