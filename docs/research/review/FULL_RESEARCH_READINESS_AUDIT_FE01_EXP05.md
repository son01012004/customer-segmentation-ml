# FULL RESEARCH-READINESS AUDIT — FE-01 → EXP-05

> **Audit được thực hiện trước khi chuyển sang EPIC-08.**
> Ngôn ngữ: tiếng Việt. Code/identifier/file name: tiếng Anh (theo convention hiện tại).
> Mục tiêu: đánh giá **readiness toàn diện** của repository, phân biệt rõ **engineering ready** vs **research methodology ready**.
> Tài liệu này KHÔNG tự quyết methodology; chỉ phân tích evidence và đề xuất.
> Không thay đổi AGENTS.md, FE-06 contract, hoặc các phase plan đã được approved.

**Audit date:** 2026-09-22
**Audit scope:** FE-01 → FE-06 → EPIC-06 / ML-01 → ML-06 → EXP-01 → EXP-05
**Auditor role:** AI Agent — read-only evidence verification + analysis

---

## 1. Executive Summary

Repository đang ở trạng thái **engineering-ready và research-evidence-ready** cho EPIC-08 implementation, với nhiều **methodology decisions** đang ở trạng thái `WORKING_ASSUMPTION` / `PENDING_REVIEW` / `DEFERRED` cần Mentor review trước khi kết luận nghiên cứu.

### 1.1. Trạng thái tổng thể (color-coded)

| Trục | Trạng thái | Ghi chú |
|---|---|---|
| **Engineering** | 🟢 **GREEN** | 1105/1105 tests PASS, ruff PASS, black PASS, SHAs verified, artifacts verified |
| **Reproducibility** | 🟢 **GREEN** | Tất cả 5 algorithms REPRODUCIBILITY_VERIFIED (Block R); inputs không bị mutate |
| **Data Lineage** | 🟢 **GREEN** | SHA chain verified end-to-end: raw → cleaned → aggregated → feature candidates → final matrix |
| **Feature Set** | 🟡 **YELLOW** | 6/14 features ở `ELIGIBLE_WORKING_ASSUMPTION`; 3 redundancy pairs detected (2 DUPLICATE_INFORMATION, 1 HIGH_CORRELATION) |
| **Clustering Implementation** | 🟡 **YELLOW** | 5 algorithms implemented (K-Medoids ở trạng thái placeholder) — discrepancy với AGENTS.md |
| **Metrics** | 🟢 **GREEN** | Silhouette / DBI / CH / WCSS chạy đúng, edge cases (ALL_NOISE, SINGLE_CLUSTER) handled, runtime tracking có sẵn |
| **EXP-01 → EXP-05** | 🟢 **GREEN** | 185/185 runs SUCCESS, tất cả 5 EXP có manifests + reports đầy đủ |
| **Cross-Experiment Consistency** | 🟢 **GREEN** | Inputs / SHA / configs / metrics consistent (EXP-04 dùng pre-transform input — by design, documented) |
| **RQ Coverage** | 🟡 **YELLOW** | RQ1 evidence OK, **RQ2 PARTIAL** (Family A DEFERRED — RFM-only chưa materialize), RQ3 evidence có nhưng EPIC-08 sẽ compute ARI/AMI |
| **Methodology Bias** | 🟡 **YELLOW** | Nhiều WORKING_ASSUMPTION; tuy nhiên KHÔNG có "best/winner/optimal" claim sai context |
| **Test Quality** | 🟢 **GREEN** | Tests kiểm tra behavior thật (determinism, SHA, alignment, redundancy, edge cases) |
| **Documentation** | 🟡 **YELLOW** | Methodology files (`docs/methodology/`) chỉ là TODO placeholders; K-Medoids discrepancy chưa được document rõ |

### 1.2. EPIC-08 Readiness Verdict

| Verdict | Status | Bằng chứng / Blockers |
|---|---|---|
| **ENGINEERING_READY** | 🟢 **YES** | All tests pass; artifacts exist; SHA chain verified; 1105 tests |
| **RESEARCH_EVIDENCE_READY** | 🟢 **YES** | 185 runs SUCCESS; labels artifact 327,825 rows; metrics values reproducible |
| **METHODOLOGY_READY** | 🟡 **PARTIAL** | Multiple `PENDING_REVIEW` + `WORKING_ASSUMPTION` decisions across experiments |
| **EPIC08_READY** | 🟡 **CONDITIONAL** | Can start implementation; but ~25+ methodology decisions need Mentor input for final claims |

**Audit Status:** 🟡 **YELLOW** — Engineering pipeline robust; cần Mentor review cho methodology decisions trước khi đưa ra research claims cuối cùng.

---

## 2. Scope

### 2.1. Trong phạm vi audit

```text
FE-01 (Data Audit)
  → FE-02 (Cleaning)
  → FE-03 (Outlier Analysis)
  → FE-04 (Customer Aggregation)
  → FE-05 (Feature Engineering: RFM + Extended)
  → FE-06 (Transformation + Scaling → Final Clustering Dataset)
  → EPIC-06 (ML-01 Framework → ML-02 → ML-03 → ML-04 → ML-05 → ML-06)
  → EXP-01 (Baseline)
  → EXP-02 (Cluster-count K sweep)
  → EXP-03 (Hyperparameter sensitivity)
  → EXP-04 (Preprocessing sensitivity)
  → EXP-05 (Reproducibility + Seed + Perturbation evidence)
  → EPIC-08 readiness
```

### 2.2. Ngoài phạm vi

- EPIC-09 / EPIC-10 / EPIC-11 / EPIC-12 / EPIC-13 (chỉ kiểm tra boundary nếu có overlap)
- Implementation mới (không tự thêm code; audit là read-only evidence verification)

---

## 3. Current Verified State

### 3.1. Tests / Lint / Format (verified at 2026-09-22)

| Item | Kết quả | Status |
|---|---|---|
| `pytest tests/` | **1105 / 1105 PASS** trong 109.03s | 🟢 |
| `pytest tests/test_exp0X_*.py` (5 files) | **208 / 208 PASS** | 🟢 |
| `ruff check .` | **All checks passed** | 🟢 |
| `black --check .` | **155 files unchanged** | 🟢 |

### 3.2. Input SHA chain verified

| Asset | SHA-256 (verified) | Match reported |
|---|---|---|
| `data/raw/primary/Online Retail.xlsx` | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` | ✅ |
| `data/raw/backup/online_retail_II.xlsx` | `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980` | ✅ |
| `data/processed/customer_candidates.parquet` | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` | ✅ |
| `data/processed/customer_metadata.parquet` | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | ✅ |
| `data/processed/final_clustering_dataset.parquet` | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | ✅ |
| `configs/clustering.yaml` | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` | ✅ |
| `configs/transformation.yaml` | `70ae113272918c81232521ff36760e0e4abbf02b0ec436ac0c1420823c506dd2` | ✅ |
| `configs/exp05_stability_reproducibility.yaml` | `3dec62060a5a6d1c09443debc51802f6f321e91f7dbbd792962e9b519afcda9e` | ✅ |

### 3.3. Artifact integrity verified (live)

| Artifact | Shape | Schema | NaN | Inf | Notes |
|---|---|---|---|---|---|
| `final_clustering_dataset.parquet` | (4371, 14) | 14 numeric | 0 per column | 0 per column | No constant features; all float64 |
| `customer_metadata.parquet` | (4371, 1) | CustomerID Int64 | 0 | 0 | 4371 unique CustomerIDs |
| `customer_candidates.parquet` | (4371, 15) | CustomerID + 14 features | 0/1312/2129 (PurchaseInterval*) | 0 | NaN chỉ ở PurchaseIntervalMean (1312) và PurchaseIntervalStd (2129) |
| `exp05_cluster_labels.parquet` | (327825, 9) | run_id, block, algorithm, seed, sigma, perturbation_seed, repeat_index, CustomerID, cluster_label | 0 | 0 | 75 unique run_ids; 4371 customers per run |

**Đã verify trực tiếp** bằng `pd.read_parquet()` không qua report.

---

## 4. AUDIT A — Data Lineage & Data Integrity

### A1. Dataset provenance

| Check | Status | Evidence |
|---|---|---|
| Primary dataset đúng UCI Online Retail | ✅ | `docs/decisions/0001-primary-dataset-uci-online-retail.md`; `docs/data_dictionary/dataset_provenance.md` |
| Backup dataset đúng UCI Online Retail II | ✅ | `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md` |
| Primary SHA khớp artifact | ✅ | `43465a06...` verified |
| Backup SHA khớp artifact | ✅ | `bcbe73b3...` verified |
| Filename mismatch có documented | ✅ | `dataset_provenance.md` "Notes" section documents `online_retail.xlsx` vs `Online Retail.xlsx` mismatch |
| Raw data không bị mutate | ✅ | Raw files SHA verified, không có script tự ý modify |

### A2. FE-01 → FE-02 → FE-03 → FE-04 → FE-05 → FE-06

| Check | Expected | Observed | Status |
|---|---|---|---|
| FE-01 raw row count | 541,909 | 541,909 | ✅ |
| FE-01 raw column count | 8 | 8 (InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country) | ✅ |
| FE-02 invalid_records drop | 135,120 removed | 135,120 removed | ✅ |
| FE-02 duplicates drop | 5,225 removed | 5,225 removed | ✅ |
| FE-02 cleaned row count | 401,564 | 401,564 | ✅ |
| FE-02 cancellation flagging | 9,288 flagged | 9,288 flagged (trước duplicates) | ✅ |
| FE-02 return flagging | 10,624 flagged | 10,624 flagged (trước duplicates) | ✅ |
| CustomerID handling (drop NaN) | enforced | enforced (CL-01) | ✅ |
| Quantity handling (drop 0) | enforced | enforced (CL-05) | ✅ |
| UnitPrice handling (drop ≤ 0) | enforced | enforced (CL-07) | ✅ |
| InvoiceDate handling (drop unparseable) | enforced | enforced (CL-04) | ✅ |
| Cancellations được flag đúng | Documented | "C" prefix → IsCancellation, Quantity<0 → IsReturn | ✅ |
| FE-04 customer count (4371) | expected 4371 | 4371 (verified) | ✅ |
| FE-06 final matrix shape | (4371, 14) | (4371, 14) | ✅ |

**Finding A-NEW-1:** Khi so sánh `cleaning_run.json` (FE-02 metadata) với `transactions_clean.parquet` thực tế:
- Pre-duplicate: IsCancellation=9288, IsReturn=10624 (different counts)
- Post-duplicate (trong file thực tế): CẢ HAI flags đều = 8872 (identical)
- Cross-tab verified: 100% identical rows (không có row nào IsCancellation=True mà IsReturn=False, hoặc ngược lại)
- **Net effect**: ở customer-invoice level, `CancellationInvoiceCount == ReturnInvoiceCount` cho tất cả 4371 customers
- Documentation ghi nhận đây là "data coincidence" (FE-06 §7.3.2) — đúng, nhưng nguồn gốc thực sự là cleaning pipeline (cancellations và returns drop đồng thời trong duplicate stage)
- **Severity:** INFO — đã được document, không phải bug, không ảnh hưởng nghiên cứu
- **Nguyên nhân:** Có 416 cancellation rows và 1752 return rows bị drop do exact-row duplicates (chính xác là các cặp duplicate đã được remove). Số liệu `10624 → 8872 = 1752` xác nhận điều này.
- **Impact:** CancellationRate = ReturnRate trên tất cả 4371 customers; redundancy pair được detect ở FE-06.

### A3. FE-02 → FE-03 → FE-04

| Check | Status | Evidence |
|---|---|---|
| Clean dataset là input đúng cho FE-04 | ✅ | `data/processed/customer_base.parquet` shape (4371, 11) verified |
| FE-03 outlier analysis KHÔNG xóa rows | ✅ | Chỉ diagnostic (FE-03 doc) |
| `TotalMonetary` (FE-04) signed baseline | ✅ | Trong `customer_base.parquet` |
| `PurchaseFrequency` (FE-04) FE-05 handles | ✅ | FE-05 review rename `PurchaseFrequency → Frequency`, document trong feature_dictionary.csv |
| FE-04 → FE-05 transition rõ ràng | ✅ | "PurchaseFrequency: KHÔNG phải RFM Frequency cuối cùng. FE-05 sẽ review" documented |

### A4. FE-04 → FE-05

| Feature | Status | Notes |
|---|---|---|
| 14 candidate features semantics đúng | ✅ | Tất cả 14 features có definition rõ trong FE-05 doc |
| AverageQuantity ≡ BasketSize (mathematical identity) | ✅ | `transaction_behavior.py:67, 89-90`: `BasketSize = alias for AverageQuantity` |
| CancellationRate ≡ ReturnRate (data coincidence) | ✅ | Verified: identical across all 4371 customers (Finding A-NEW-1) |
| Frequency ↔ ActiveDays correlation | ✅ | Pearson 0.9743 (pre-transform) verified in `redundancy_analysis.csv` |
| Denominator CancellationRate/ReturnRate nhất quán | ✅ | Cả hai dùng `DistinctInvoiceCount` (FE-05 final Frequency) |
| Structural NaN PurchaseIntervalMean/Std | ✅ | 1312 NaN Mean + 2129 NaN Std — match FE-06 doc; imputation median (41.0, 32.585...) documented |

### A5. FE-05 → FE-06

| Check | Status | Evidence |
|---|---|---|
| 14 features eligible | ✅ | `feature_eligibility.csv`: 14 ELIGIBLE / ELIGIBLE_WORKING_ASSUMPTION |
| CustomerID tách riêng | ✅ | `customer_metadata.parquet` chỉ có CustomerID |
| Median imputation | ✅ | 2 features (PurchaseIntervalMean, PurchaseIntervalStd) |
| Yeo-Johnson transformation | ✅ | Per-feature lambda saved (verified 14 lambdas in fe06_run.json) |
| RobustScaler | ✅ | Distribution post-scaling: median=0, IQR=1 |
| Transformation order | ✅ | eligibility → imputation → Yeo-Johnson → RobustScaler (documented in FE-06 §1.6) |
| No leakage | ✅ | 8/8 leakage checks PASS |
| No metadata | ✅ | Input integrity tests pass (input SHA unchanged) |
| Final matrix reproducible | ✅ | Deterministic pipeline (no random state used) |
| Final matrix SHA verified | ✅ | `ba54033e...` matches fe06_run.json |

**Finding A-OK-1:** FE-06 implement đúng như documentation mô tả. Không có gap giữa code và docs.

---

## 5. AUDIT B — Feature Semantics & Research Validity

### B1. 14 final features audit

| # | Feature | Definition | Source | Aggregation | Missing handling | Outlier handling | Duplicate? | Leakage? |
|---|---|---|---|---|---|---|---|---|
| 1 | `Recency` | `ReferenceDate − LastPurchaseDate` (days) | InvoiceDate | customer-level | 0% | None | No | No |
| 2 | `Frequency` | `nunique(InvoiceNo)` per customer | InvoiceNo | customer-level | 0% | None | No | No |
| 3 | `Monetary` | `sum(LineRevenue)` signed baseline | LineRevenue | customer-level | 0% | None | No | No |
| 4 | `TotalQuantity` | `sum(Quantity)` signed | Quantity | customer-level | 0% | None | No | No |
| 5 | `AverageQuantity` | `sum(Quantity)/nunique(InvoiceNo)` signed | Quantity, InvoiceNo | customer-level | 0% | None | **YES** (BasketSize) | No |
| 6 | `BasketSize` | alias for AverageQuantity (mathematical identity) | Quantity, InvoiceNo | customer-level | 0% | None | **YES** (AverageQuantity) | No |
| 7 | `TenureDays` | `ReferenceDate − FirstPurchaseDate` | InvoiceDate | customer-level | 0% | None | No | No |
| 8 | `PurchaseIntervalMean` | `diff(InvoiceDate).mean()` ≥2 invoices | InvoiceDate | customer-level | 30.0% (median) | None | No | No |
| 9 | `PurchaseIntervalStd` | `diff(InvoiceDate).std(ddof=1)` ≥3 invoices | InvoiceDate | customer-level | 48.7% (median) | None | No | No |
| 10 | `ActiveDays` | `nunique(date(InvoiceDate))` | InvoiceDate | customer-level | 0% | None | No | No |
| 11 | `AverageInvoiceValue` | `TotalMonetary / Frequency` | LineRevenue, InvoiceNo | customer-level | 0% | None | No | No |
| 12 | `ProductsPerInvoice` | `nunique(StockCode) / nunique(InvoiceNo)` | StockCode, InvoiceNo | customer-level | 0% | None | No | No |
| 13 | `CancellationRate` | `CancellationInvoiceCount / Frequency` | IsCancellation, InvoiceNo | customer-level | 0% | None | **YES** (ReturnRate) | No |
| 14 | `ReturnRate` | `ReturnInvoiceCount / Frequency` | IsReturn, InvoiceNo | customer-level | 0% | None | **YES** (CancellationRate) | No |

### B2. Findings on redundancy / correlation

#### Finding B-DUP-1: `AverageQuantity` ≡ `BasketSize`
- **Severity:** MEDIUM (data coincidence by construction)
- **Evidence:** Max abs diff = 0.000000 (verified live); `transaction_behavior.py` defines BasketSize = alias for AverageQuantity
- **Documented:** FE-06 §7.3.1 (mathematical identity by construction)
- **Recommendation:** KHÔNG auto-drop; MENTOR_REVIEW_REQUIRED cho promotion logic
- **No fix needed** — đây là working assumption, FE-06 đã ghi rõ

#### Finding B-DUP-2: `CancellationRate` ≡ `ReturnRate`
- **Severity:** MEDIUM (data coincidence, derived from cleaning)
- **Evidence:** Max abs diff = 0.000000 (verified live); cross-tab của IsCancellation vs IsReturn = 100% identical (8872 rows)
- **Documented:** FE-06 §7.3.2 (data coincidence)
- **Root cause:** Trong cleaning pipeline, duplicate stage drop cả cancellation và return rows cùng nhau → 416 cancellations + 1752 returns removed → cuối cùng CancellationInvoiceCount == ReturnInvoiceCount cho tất cả 4371 customers
- **Nguyên nhân gốc:** Cancellations và returns đều là negative-quantity transactions trong dataset này (theo FE-02 rules CL-06 cho returns và CL-08 cho cancellations); duplicate stage drop chúng đồng thời
- **Recommendation:** KHÔNG auto-drop; MENTOR_REVIEW_REQUIRED
- **Caveat for downstream:** Nếu data thay đổi, 2 rates có thể tách rời → feature selection logic phải robust

#### Finding B-CORR-1: `Frequency` ↔ `ActiveDays`
- **Severity:** LOW (related but distinct, NOT duplicate)
- **Pearson pre-transform:** 0.9743 (verified in `redundancy_analysis.csv`)
- **Pearson post-scaling:** 0.9838 (verified live; post-YeoJohnson+RobustScaler transformation slightly amplifies correlation)
- **EqualityRate:** 0.7735 (≠ 1.0 → KHÔNG duplicate)
- **Difference semantics:** Frequency = nunique(InvoiceNo) — invoice-level granularity; ActiveDays = nunique(date(InvoiceDate)) — calendar-day-level granularity
- **Documented:** FE-06 §7.3.3 (HIGH_CORRELATION, not duplicate)
- **Status:** OK — leave both, feature-level decision is mentor's

### B3. ELIGIBLE_WORKING_ASSUMPTION features

| Feature | FE-05 Decision | FE-06 Status | Risk |
|---|---|---|---|
| Frequency | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | If mentor changes definition, retraining required |
| AverageQuantity | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Definition variants existed (`reports/fe05/quantity_variants_comparison.csv`) |
| BasketSize | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Same as above |
| ActiveDays | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Frequency alternative |
| CancellationRate | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Pairs with ReturnRate |
| ReturnRate | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Pairs with CancellationRate |

**Note:** 6/14 features chưa được mentor approve. Nếu mentor chọn alternative definition, tất cả EXP-01 → EXP-05 phải rerun. Đây là **methodology risk** đã được document.

**Finding B-NEW-1:** Tất cả 6 features ở `ELIGIBLE_WORKING_ASSUMPTION` đều có comparison CSV (frequency_variants, monetary_definition, quantity_variants) chứng minh mentor có evidence để quyết định.

---

## 6. AUDIT C — Final Clustering Dataset Verification

### C1. Direct verification

| Check | Result | Verification method |
|---|---|---|
| Shape (4371, 14) | ✅ | `pd.read_parquet(...).shape` |
| No NaN | ✅ | `df.isna().sum().sum() = 0` |
| No Inf | ✅ | `(df == inf).sum().sum() = 0` |
| No constant features | ✅ | `df.nunique() > 1` cho 14 columns |
| All numeric (float64) | ✅ | `df.dtypes = [float64]*14` |
| 14 features đúng tên | ✅ | `[Recency, Frequency, Monetary, TotalQuantity, AverageQuantity, BasketSize, TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays, AverageInvoiceValue, ProductsPerInvoice, CancellationRate, ReturnRate]` |
| CustomerID absent | ✅ | Matrix không có CustomerID column |
| Metadata alignment | ✅ | `customer_metadata.parquet` 4371 unique CustomerIDs, aligned by position |
| SHA verified | ✅ | `ba54033e...` matches `fe06_run.json.output.final_clustering_dataset_sha256` |

### C2. Customer metadata verification

| Check | Result |
|---|---|
| Shape (4371, 1) | ✅ |
| CustomerID unique = 4371 | ✅ |
| CustomerID NaN = 0 | ✅ |
| CustomerID dtype Int64 | ✅ |
| SHA matches report | ✅ |

### C3. Conclusion

**Verdict:** Final clustering dataset đạt yêu cầu kỹ thuật. Mọi số liệu report đều reproducible từ artifact.

---

## 7. AUDIT D — Clustering Implementation (ML-01 → ML-06)

### D1. ML-01 — Clustering Experiment Framework

| Aspect | Status | Notes |
|---|---|---|
| `BaseClusterAlgorithm` interface | ✅ | `src/customer_segmentation/clustering/base.py` |
| `AlgorithmRegistry` registration | ✅ | Decorator-based registration, fail-fast on duplicate |
| `ClusterResult` / `MetricsResult` / `ExperimentResult` dataclasses | ✅ | `src/customer_segmentation/clustering/result.py` |
| `ExperimentRunner` lifecycle | ✅ | load → validate → fit → write |
| `Validation` rules | ✅ | `src/customer_segmentation/clustering/validation.py` |
| `Artifacts` writer | ✅ | `src/customer_segmentation/clustering/artifacts.py` |
| Config loader | ✅ | `src/customer_segmentation/clustering/config.py` |
| Logging utils | ✅ | `src/customer_segmentation/clustering/logging_utils.py` |
| 59 framework tests | ✅ | `tests/test_ml01_framework.py` — passes |

### D2. ML-02 — K-Means

| Aspect | Status | Notes |
|---|---|---|
| Input validation | ✅ | ndim check, NaN/Inf check, dtype check |
| `random_state` support | ✅ | Consumes seed |
| Parameter mapping (init, n_init, max_iter, tol) | ✅ | All configurable |
| Output labels | ✅ | int64 |
| Determinism with fixed seed | ✅ | Verified Block R |
| Runtime measurement | ✅ | time.perf_counter around adapter.fit() |
| Config SHA recorded | ✅ | In `experiment_log_*.json` |
| Library version | ✅ | sklearn 1.9.1 |
| Artifact written | ✅ | cluster_labels_EXP-01-kmeans_rep4.parquet + experiment_log |

### D3. ML-03 — Agglomerative

| Aspect | Status | Notes |
|---|---|---|
| Linkage variants (ward / complete / average / single) | ✅ | All 4 implemented |
| `compute_distances=True` | ✅ | For dendrogram diagnostic |
| Determinism | ✅ | No random axis |
| Runtime measurement | ✅ | Slowest algorithm (~0.5s mean) |
| EXP-03 Stage B linkage sweep | ✅ | All 4 linkages tested |
| EXP-03 Stage C linkage×K | ✅ | 3 interactions tested |

#### Finding D-AGG-1: Agglomerative Stage C linkage=average has CH=77.15 (vs alternatives 5029.13, 5081.40)
- **Severity:** MEDIUM (research decision pending)
- **Description:** Silhouette 0.8033 (highest in Stage C) but CH is 77× lower
- **Root cause:** Known **chaining artifact** của average-linkage ở small K=3
- **Documented:** EXP-03 review (`docs/research/review/EXP03_HYPERPARAMETER_REVIEW.md` §6)
- **Status:** `WORKING_SELECTED` per protocol silhouette-primary, NOT finalized
- **Recommendation:** EPIC-08 PHẢI do cross-metric evaluation và stability analysis trước khi bất kỳ conclusion nghiên cứu nào sử dụng configuration này
- **Mentor decision required:** Có nên accept WORKING_SELECTED theo protocol hay adjust protocol?

### D4. ML-04 — DBSCAN

| Aspect | Status | Notes |
|---|---|---|
| eps, min_samples, metric parameters | ✅ | All configurable |
| Noise handling (label -1) | ✅ | Correctly returned as noise_label=-1 |
| Determinism | ✅ | No random axis |
| EXP-03 Stage B sweep | ✅ | eps ∈ {0.3, 0.5, 0.7, 1.0}, min_samples ∈ {3, 5, 10, 15} |
| Working selection min_samples=10 | ✅ | Status `WORKING_SELECTED` (silhouette 0.1598) |

#### Finding D-DBSCAN-1: Baseline DBSCAN at eps=0.5, min_samples=5 has noise_ratio=0.7268
- **Severity:** MEDIUM (research decision pending)
- **Description:** 72.68% of 4371 customers labeled as noise at baseline
- **EXP-03 findings:** Sweep {0.3, 0.7, 1.0} × {3, 5, 10, 15} — none reduces noise dramatically:
  - eps=0.3: noise_ratio=0.8488 (worse)
  - eps=0.7: noise_ratio=0.6282 (better but still high)
  - eps=1.0: noise_ratio=0.4914 (lowest in sweep, but n_clusters=38)
  - min_samples=3: noise_ratio=0.6857
  - min_samples=10: noise_ratio=0.7687 (worse)
  - min_samples=15: noise_ratio=0.7991 (worse, n_clusters=2)
- **Documented:** EXP-01 review §A.8; config EXP-04 KEEP
- **Recommendation:** EPIC-08 needs consensus: keep or tune further? K-distance plot diagnostic only.
- **Mentor decision required:** Accept baseline vs. systematic eps/min_samples sweep?

### D5. ML-05 — GMM

| Aspect | Status | Notes |
|---|---|---|
| Covariance types (full, tied, diag, spherical) | ✅ | All 4 implemented |
| Soft probabilities output | ✅ | Stored in `algorithm_output_*` parquet |
| `random_state` support | ✅ | Consumes seed |
| Determinism | ✅ | With fixed seed |
| EXP-03 Stage B sweep | ✅ | covariance_type ∈ {tied, diag, spherical} + init_params=random |
| Working selection covariance_type=tied | ✅ | Silhouette 0.5702 (vs full=0.1843) |

**Note:** GMM full covariance type yields much lower silhouette (0.1843) than tied (0.5702); this is expected with high-dimensional skewness data — not a bug.

### D6. ML-06 — Fuzzy C-Means

| Aspect | Status | Notes |
|---|---|---|
| Custom NumPy implementation | ✅ | `src/customer_segmentation/clustering/fuzzy_cmeans.py` |
| Initialization (Dirichlet) | ✅ | Row-stochastic via `rng.dirichlet(alpha=ones(c))` |
| Membership normalization | ✅ | Per-row sum to 1 enforced |
| Update equations | ✅ | Canonical Bezdek update with exponent `2/(m-1)` |
| Stopping criterion | ✅ | max_iter AND/OR membership_change < error |
| Objective/convergence tracking | ✅ | `objective_history` recorded |
| Empty cluster behavior | ✅ | `denom_safe = where(denom > EPSILON, denom, EPSILON)` |
| Numerical stability | ✅ | Clip + epsilons + handle zero-distance cases |
| Random seed behavior | ✅ | `numpy.random.default_rng(random_state)` |
| Soft membership preservation | ✅ | `ClusterResult.soft_membership` field |

#### Finding D-FCM-1: m=1.5 is close to K-Means limit (m=1)
- **Severity:** MEDIUM (research decision pending)
- **Description:** Working selection for FCM is m=1.5 (Stage C K=3, silhouette=0.6296)
- **Implication:** m=1 reduces to K-Means; m=1.5 reduces fuzziness effect significantly
- **Documented:** `docs/research/review/EXP03_HYPERPARAMETER_REVIEW.md` §8
- **Status:** WORKING_SELECTED; bị flagged là cần mentor review
- **Mentor decision required:** Accept m=1.5 vs require m ≥ 2.0?

### D7. **CRITICAL Finding D-KMED-1: K-Medoids is a placeholder — discrepancy với AGENTS.md**

- **Severity:** 🔴 **HIGH (research methodology issue)**
- **Evidence:**
  - `AGENTS.md` §3 list 4 fixed benchmark algorithms: "K-Means, K-Medoids, Agglomerative Clustering, DBSCAN"
  - `README.md` §1 cũng mention "K-Means, K-Medoids, Agglomerative, DBSCAN"
  - `src/customer_segmentation/clustering/kmedoids.py`: contains only `NotImplementedError("fit_kmedoids is not implemented yet.")` plus `# TODO: implement K-Medoids benchmarking.`
  - `AlgorithmRegistry` does NOT register any K-Medoids adapter (grep verified)
  - `configs/clustering.yaml` có `kmedoids: enabled: true, metric: "TODO", init: "TODO"` (placeholder, không phải implement thật)
  - EXP-01 → EXP-05 chỉ chạy 5 algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means); K-Medoids KHÔNG xuất hiện
  - EPIC-06 Documentation Contract thực tế là về 6 algorithms (K-Means, Agglomerative, DBSCAN, GMM, FCM) — gọi ML-06 là "Algorithm Baseline"
- **Root cause:** AGENTS.md đã OUTDATED so với EPIC-06 actual scope. EPIC-06 mở rộng scope ngầm (thêm GMM, FCM; K-Medoids trở thành placeholder).
- **Impact:** Documentation claim "4 fixed algorithms" không match implementation. Phải:
  - Option A: Implement K-Medoids và add vào EXP-01-05 (cần dep `scikit-learn-extra`, ADR, +38 runs)
  - Option B: Update AGENTS.md / README.md / FE-06 doc / FE-04 doc / FE-05 doc / ML-01 docs để reflect 5-algorithm scope (hiện tại: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means)
- **Status:** KHÔNG TỰ SỬA — methodology decision
- **MENTOR_REVIEW_REQUIRED**

### D8. Other framework-level findings

#### Finding D-NEW-1: Test count (`pytest tests/test_ml01_framework.py`)
- **Severity:** INFO
- **Description:** REPO nói "59 tests" trong EPIC06 contract §8.3; actual count not verified but pytest passes
- **Recommendation:** Verify exact count of test functions in `test_ml01_framework.py`

#### Finding D-NEW-2: Algorithms registered in `AlgorithmRegistry`
- **Severity:** INFO
- **Verified:** K-means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means = 5 registered
- **NOT registered:** K-Medoids (placeholder only)

---

## 8. AUDIT E — Metric Implementation

### E1. Direct implementation audit (`metrics.py`)

| Metric | Implementation | Status |
|---|---|---|
| Silhouette | `sklearn.metrics.silhouette_score(X_subset, labels_subset)` | ✅ |
| Davies-Bouldin | `sklearn.metrics.davies_bouldin_score(X_subset, labels_subset)` | ✅ |
| Calinski-Harabasz | `sklearn.metrics.calinski_harabasz_score(X_subset, labels_subset)` | ✅ |
| WCSS | Manual: arithmetic centroid per cluster, sum of squared distances | ✅ (per EXP-01 plan §4.2) |

### E2. Status handling

| Status | Reason | Behavior |
|---|---|---|
| `VALID_VALUE` | Metric computed successfully | value populated |
| `NOT_APPLICABLE` | `ALL_NOISE` (n_clusters=0 after noise exclusion) | value=None |
| `NOT_APPLICABLE` | `SINGLE_CLUSTER` (n_unique < 2) | value=None |
| `COMPUTATION_ERROR` | sklearn raises | value=None, reason=exception type+message |
| `MISSING` | placeholder | (should not remain in successful run) |

### E3. Noise handling

| Decision | Implementation | Status |
|---|---|---|
| DBSCAN noise (-1) excluded from silhouette/DBI/CH/WCSS | `mask = labels != -1` | ✅ |
| Other algorithms (no actual noise points) | masked array = full | ✅ |
| `noise_count` field in `ClusterResult` | populated for DBSCAN; 0 for others | ✅ |

### E4. Runtime tracking

| Aspect | Status |
|---|---|
| `algorithm_execution` time | ✅ (separate from metric computation) |
| `metric_computation` time | ✅ (separate) |
| Artifact/report writing time | ✅ EXCLUDED (per EXP-01 plan §3.1) |

### E5. Findings on metrics

#### Finding E-NEW-1: WCSS convention — arithmetic centroid from hard labels
- **Severity:** MEDIUM (research decision pending, requires mentor)
- **Description:** WCSS for GMM/FCM uses `argmax` hard labels, then arithmetic centroid — NOT GMM's Gaussian means / FCM's fuzzy centroids
- **Documented:** EXP-01 plan §4.2; PENDING_REVIEW
- **Rationale:** Consistent cross-algorithm comparison
- **Trade-off:** Mathematical purity vs comparability
- **Status:** PENDING_REVIEW EXP01-MET-02
- **Recommendation:** Accept current convention; alternative would risk inconsistency

#### Finding E-NEW-2: WCSS không comparable across scenarios với khác scale
- **Severity:** INFO (documented, no fix needed)
- **Description:** EXP-04 C0 (no transform, no scale) silhouette=0.9465, WCSS=53 billion. EXP-04 C7 (FE-06 working) silhouette=0.5681, WCSS=179K. Different scales — không so sánh được directly.
- **Documented:** EXP-04 review §5

#### Finding E-NEW-3: Cross-algorithm metric comparison có thể gây hiểu nhầm
- **Severity:** MEDIUM (research decision pending)
- **Description:** Algorithms có số cluster khác nhau (K-Means=4, Agglo=4, DBSCAN=17, GMM=4, FCM=4). Một số metric normalize bằng số cluster.
- **Recommendation:** EPIC-08 cần explicit caveat khi compare cross-algorithm
- **Current handling:** DBSCAN noise excluded; metrics computed on remaining points only
- **Status:** Document trong metrics.py docstring

---

## 9. AUDIT F — EXP-01

| Aspect | Status | Evidence |
|---|---|---|
| Baseline configuration | ✅ | 5 algorithms × EXP-01 working defaults |
| K values | ✅ | K=4 for k-means/agglom/gmm/fcm; n/a for dbscan |
| Seed | ✅ | 42 |
| n_repeat=5 | ✅ | EXP-01 plan §3.3 |
| Runtime protocol | ✅ | Algorithm execution only (excludes metric + writing) |
| Metric protocol | ✅ | 4 metrics per run, status enum |
| DBSCAN noise | ✅ | 17 clusters, noise_ratio=0.7268 |
| Artifact | ✅ | 5 cluster_labels_*.parquet + 5 experiment_log_*.json + 2 algorithm_output_*.parquet |
| Report | ✅ | exp01_initial_baseline.md + summary csv + manifest |
| Reproducibility | ✅ | 5 algorithms blocked_R verified |

### Findings

- **Finding F-NEW-1:** All 5 algorithms SUCCESS; metrics reproducible from artifacts.
- **Finding F-NEW-2:** No "best algorithm" claim in reports (per AGENTS.md §2.5).
- **Finding F-NEW-3:** EXP-01 does NOT include stability analysis (per plan §3.3); EXP-05 owns that.

**Verdict:** TECHNICALLY_IMPLEMENTED_AND_VERIFIED.

---

## 10. AUDIT G — EXP-02

| Aspect | Status | Evidence |
|---|---|---|
| K range | ✅ | [2, 10], step=1 (WORKING_ASSUMPTION EXP02-KRNG-01) |
| Algorithms sweep | ✅ | 4 K-bearing + 1 DBSCAN diagnostic |
| DBSCAN không trong K-sweep | ✅ | Correctly handled |
| Candidate logic | ✅ | 13 candidates via heuristic (top_n=3, drop_ratio=0.2, min_agreement=2) |
| Silhouette / DBI / CH / WCSS | ✅ | Per (algorithm, K) |
| Không promote "best K" | ✅ | No "best/optimal/final/recommended" claim |
| `min_agreement=2` heuristic | ✅ | WORKING_ASSUMPTION |
| Candidates reproducible | ✅ | Same input → same candidates |

### Findings

#### Finding G-NEW-1: EXP-02 trả lời cluster-count sensitivity question, KHÔNG tạo "best K"
- **Severity:** INFO
- **Description:** 13 candidates flagged; NO `best K` / `final K` declared
- **Status:** TECHNICALLY_IMPLEMENTED, methodology choice (how to use candidates in EPIC-08) is PENDING_REVIEW

#### Finding G-NEW-2: Disagreement giữa indicators được ghi evidence, không tự resolve
- **Severity:** INFO
- **Verified:** Different indicators flag different K → candidates flagged by ≥2 indicators
- **Status:** OK — proper handling

**Verdict:** TECHNICALLY_IMPLEMENTED, methodology conclusions pending.

---

## 11. AUDIT H — EXP-03

### H1. Stage A — baseline per algorithm

| Aspect | Status |
|---|---|
| 1 run per algorithm (5 runs total) | ✅ |
| Reuses EXP-01 working defaults | ✅ |

### H2. Stage B — Single-parameter sensitivity

| Algorithm | Parameters swept | N_runs |
|---|---|---|
| K-Means | init, n_init, max_iter | 6 |
| Agglomerative | linkage | 3 |
| DBSCAN | eps, min_samples | 6 |
| GMM | covariance_type, init_params | 4 |
| FCM | m, max_iter | 5 |

Total Stage B: 24 runs

### H3. Stage C — Selected interactions

| Algorithm | Interactions | N_runs |
|---|---|---|
| K-Means K=3 × n_init | 3 |
| Agglomerative K=3 × linkage | 3 |
| FCM K=3 × m | 3 |
| DBSCAN | (none — no K) |

Total Stage C: 9 runs

**Total EXP-03:** 5 (Stage A) + 24 (Stage B) + 9 (Stage C) = 38 runs ✅

### H4. Selection per algorithm

| Algorithm | Status | Configuration | Notes |
|---|---|---|---|
| K-Means | `TIED_WORKING_SELECTED` | Stage C K=3 n_init=1 | Genuine 3-way tie (K-Means deterministic) |
| Agglomerative | `WORKING_SELECTED` | Stage C K=3 linkage=average | CH=77.15 vs alternatives 5029/5081 — chaining artifact |
| DBSCAN | `WORKING_SELECTED` | Stage B min_samples=10 | Silhouette 0.1598 |
| GMM | `WORKING_SELECTED` | Stage B covariance_type=tied | Silhouette 0.5702 |
| FCM | `WORKING_SELECTED` | Stage C K=3 m=1.5 | Silhouette 0.6296; m=1.5 close to K-Means limit |

### Findings

#### Finding H-KM-1: K-Means Stage C 3-way tie
- **Severity:** INFO (expected behavior)
- **Description:** n_init ∈ {1, 10, 20} → identical metrics (K-Means deterministic với fixed seed)
- **Resolution:** Status `TIED_WORKING_SELECTED` documented; deferred to EPIC-08 if needed
- **Status:** TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING

#### Finding H-AGG-1: Agglomerative disagreement (covered above D-AGG-1)
- See D-AGG-1.

#### Finding H-GMM-1: GMM full covariance produces much lower silhouette (0.1843) than tied (0.5702)
- **Severity:** INFO (expected)
- **Description:** High-dimensional skewness in the data
- **Documented:** EXP-01 review §A.8

#### Finding H-FCM-1: FCM m=1.5 close to K-Means (covered above D-FCM-1)
- See D-FCM-1.

#### Finding H-NEW-1: Stage C is "small curated subset"
- **Severity:** INFO
- **Description:** Only 3 interactions per algorithm × 3 algorithms (K-Means, Agglo, FCM); not full grid
- **Documented:** EXP03-INT-01; can be expanded if needed

**Verdict:** TECHNICALLY_IMPLEMENTED, multiple methodology decisions pending.

---

## 12. AUDIT I — EXP-04

### I1. Family A (DEFERRED)

- **Status:** DEFERRED — RFM-only artifact does not exist
- **Impact:** RQ2 PARTIAL
- **Owner:** FE-06 (cần ADR materialize RFM-only)
- **Severity:** 🔴 HIGH (RQ2 incomplete)

### I2. Family B (Preprocessing Sensitivity) — EXECUTED

| Aspect | Status | Notes |
|---|---|---|
| K-Means only | ✅ | CONTROLLED_REFERENCE_ALGORITHM |
| K=4 | ✅ | CONTROLLED_REFERENCE_K |
| Median imputation | ✅ | CONTROLLED_REFERENCE_IMPUTATION (FE-06 C7 fitted values) |
| Seed=42 | ✅ | CONTROLLED_VARIABLE |
| n_repeat=5 | ✅ | Determinism verification |
| Pre-transform input | ✅ | `customer_candidates.parquet` (by design) |
| 6 scenarios | ✅ | C0, C1, C2, C3, C6, C7 |
| labels_hash determinism | ✅ | 30/30 SUCCESS, 6/6 deterministic |
| C7 mirrors EXP-01 K-Means baseline | ✅ | silhouette=0.5681, DBI=0.6128, CH=4819.08 — identical |

### Findings

#### Finding I-1: K-Means only is CONTROLLED_REFERENCE_ALGORITHM
- **Severity:** MEDIUM
- **Description:** EXP-04 only tests K-Means for preprocessing sensitivity; not Agglomerative/GMM/FCM
- **Documented:** EXP04-ALG-01 PENDING_REVIEW
- **Impact:** RQ2 PARTIAL; can't assess how preprocessing affects other algorithms
- **Recommendation:** Consider expanding to other algorithms (or document as limitation)
- **MENTOR_REVIEW_REQUIRED**

#### Finding I-2: C0 (no transform, no scale) has silhouette 0.9465
- **Severity:** INFO
- **Description:** Very high silhouette but raw scale; Euclidean distance dominated by high-variance features
- **Documented:** EXP04-S01 in `exp04_preprocessing_sensitivity.csv`
- **Status:** Acknowledged as artifact

#### Finding I-3: log1p NOT included
- **Severity:** LOW
- **Description:** log1p excluded because 6/14 features have negative values
- **Documented:** EXP04-TR-01 PENDING_REVIEW
- **Status:** OK — by design

**Verdict:** TECHNICALLY_IMPLEMENTED, RQ2 PARTIAL due to Family A deferral.

---

## 13. AUDIT J — EXP-05

### J1. Block R (Reproducibility) — 25 runs

| Algorithm | n_repeat | Successful | labels_hash_unique | Decision |
|---|---|---|---|---|
| kmeans | 5 | 5 | 1 | REPRODUCIBILITY_VERIFIED |
| agglomerative | 5 | 5 | 1 | REPRODUCIBILITY_VERIFIED |
| dbscan | 5 | 5 | 1 | REPRODUCIBILITY_VERIFIED |
| gmm | 5 | 5 | 1 | REPRODUCIBILITY_VERIFIED |
| fuzzy_cmeans | 5 | 5 | 1 | REPRODUCIBILITY_VERIFIED |

### J2. Block S (Seed sensitivity) — 15 runs

| Algorithm | n_seeds | labels_hash_unique | Decision |
|---|---|---|---|
| kmeans | 5 | 5 | STABILITY_EVIDENCE_GENERATED |
| gmm | 5 | 5 | STABILITY_EVIDENCE_GENERATED |
| fuzzy_cmeans | 5 | 5 | STABILITY_EVIDENCE_GENERATED |

(Excludes Agglomerative, DBSCAN — deterministic)

### J3. Block N (Feature perturbation) — 35 runs

| Algorithm | sigma=0 | sigma=0.01 | sigma=0.05 | sigma_zero_match |
|---|---|---|---|---|
| kmeans | sigma=0 match | 3 unique labels_hash | 3 unique labels_hash | ✅ |
| agglomerative | sigma=0 match | 3 unique labels_hash | 3 unique labels_hash | ✅ |
| dbscan | sigma=0 match | n_clusters_unique=3 | n_clusters_unique=2 | ✅ |
| gmm | sigma=0 match | 3 unique labels_hash | 3 unique labels_hash | ✅ |
| fuzzy_cmeans | sigma=0 match | 3 unique labels_hash | 3 unique labels_hash | ✅ |

### Findings

#### Finding J-1: EXP-05 chỉ chạy trên EXP-01 working defaults, KHÔNG trên EXP-03 working selections
- **Severity:** MEDIUM
- **Description:** Stability not tested for EXP-03 per-algorithm optimal configurations
- **Documented:** EXP-05 review §15.2 (PENDING_REVIEW)
- **MENTOR_REVIEW_REQUIRED:** Rerun EXP-05 với EXP-03 selections?

#### Finding J-2: Agglomerative + DBSCAN không trong Block S
- **Severity:** LOW
- **Description:** These algorithms are deterministic; included only in Block R
- **Documented:** EXP05-BLK-02 PENDING_REVIEW
- **Alternative:** Add with random_state override (most K-Means have this; both algos use sklearn which doesn't consume random_state for these methods)
- **MENTOR_REVIEW_REQUIRED:** Expand scope?

#### Finding J-3: Sigma grid [0, 0.01, 0.05] not yet justified
- **Severity:** LOW
- **Documented:** EXP05-BLK-03 PENDING_REVIEW
- **Status:** WORKING_ASSUMPTION

#### Finding J-4: DBSCAN n_clusters varies with perturbation (3 unique at sigma=0.01, 2 unique at sigma=0.05)
- **Severity:** INFO
- **Description:** Expected behavior of density-based clustering
- **Status:** Documented correctly

#### Finding J-5: Perturbation is in-memory, not persisted
- **Severity:** INFO
- **Verified:** Constraint in `EXP05_constraints`; input FE-06 SHA unchanged pre/post

#### Finding J-6: Labels artifact schema correctly verified
- **Severity:** NONE
- **Verified:** 327,825 rows × 9 columns; 75 unique run_ids; 4371 CustomerIDs per run

**Verdict:** TECHNICALLY_IMPLEMENTED (raw evidence only); stability/robustness analysis thuộc EPIC-08.

---

## 14. AUDIT K — Cross-Experiment Consistency Matrix

| Dimension | EXP-01 | EXP-02 | EXP-03 | EXP-04 | EXP-05 |
|---|---|---|---|---|---|
| Dataset | final_clustering (FE-06) | final_clustering (FE-06) | final_clustering (FE-06) | customer_candidates (FE-05, pre-transform) | final_clustering (FE-06) |
| Feature set | RFM Extended (14) | RFM Extended (14) | RFM Extended (14) | RFM Extended (14) | RFM Extended (14) |
| Preprocessing | Applied (FE-06 C7) | Applied (FE-06 C7) | Applied (FE-06 C7) | Controlled per-scenario (C0/C1/C2/C3/C6/C7) | Applied (FE-06 C7) |
| Scaling | Applied (RobustScaler) | Applied (RobustScaler) | Applied (RobustScaler) | Per scenario | Applied (RobustScaler) |
| K | 4 fixed | sweep 2..10 | EXP-02 candidates | 4 fixed | EXP-01 working defaults (mostly K=4) |
| Seed | 42 | 42 | 42 | 42 | Block R: 42; Block S: [42, 7, 123, 2024, 1729]; Block N: [42, 43, 44] |
| n_repeat | 5 | 5 | 1 per (algo, params) | 5 | Block R: 5; Block S: 1; Block N: 1 |
| Algorithm config | EXP-01 working | EXP-01 working | EXP-03 Stage A→C | K-Means only | EXP-01 working |
| Metrics | silhouette/DBI/CH/WCSS | silhouette/DBI/CH/WCSS | silhouette/DBI/CH/WCSS | silhouette/DBI/CH/WCSS | None (evidence only) |
| Runtime | mean/std/min/max | mean/std/min/max | mean/std/min/max | mean/std/min/max | Recorded |
| Stability | Block R verified | (n/a) | (n/a) | labels_hash deterministic | Block R reproducible |

### Cross-experiment discrepancies found

#### Finding K-1: EXP-04 input ≠ EXP-01/02/03/05 input
- **By design:** EXP-04 dùng `customer_candidates.parquet` (FE-05 pre-transform) để control preprocessing scenarios
- **Documented:** Yes (`docs/research/review/EXP04_PREPROCESSING_FEATURE_REVIEW.md` §3.4)
- **Status:** Intentional, properly documented
- **Severity:** NONE (consistent with documentation)

#### Finding K-2: EXP-04 family A vs other experiments
- **Status:** Family A (RFM-only) DEFERRED — only Family B (preprocessing sensitivity) executed
- **Impact:** EXP-04 không fully comparable với các EXP khác về feature set coverage
- **Severity:** MEDIUM (research methodology decision pending)

#### Finding K-3: K-Means n_init tie cross-experiment
- **Description:** K-Means với fixed seed → identical labels across n_init values → identical metrics
- **Verified:** EXP-03 Stage B + Stage C K-Means runs identical metrics

#### Finding K-4: No cross-experiment metric drift
- **Verified:** Same algorithm + same config → same metric (within library version)
- **Status:** OK

#### Finding K-5: Shadow claim — "WORKING_SELECTED" vs "FINAL"
- **Verified:** All reviews use `WORKING_SELECTED` / `TIED_WORKING_SELECTED` / `CANDIDATE` / `PENDING_REVIEW`
- **No `final` / `best` / `optimal` / `winner` claims** anywhere in EXP artifacts

---

## 15. AUDIT L — Research Question Coverage

### L1. Inferred RQ1 — Compare clustering algorithms under controlled conditions

| Evidence | Status |
|---|---|
| All 5 algorithms implemented | ✅ (excluding K-Medoids placeholder) |
| Same FE-06 dataset | ✅ |
| Same scaling (RobustScaler) | ✅ |
| Same K=4 baseline | ✅ (DBSCAN at eps=0.5) |
| Same metrics | ✅ (silhouette, DBI, CH, WCSS) |
| Quality metrics | ✅ EXP-01 to 04 |
| Runtime | ✅ EXP-01 to 05 |
| Stability evidence | ⚠️ EXP-05 Block R/S/N raw evidence; EPIC-08 computes ARI/AMI |
| Interpretation boundary | ✅ KHÔNG có best algorithm claim |

**Verdict:** RQ1 evidence YELLOW — quality + runtime covered; stability needs EPIC-08 analysis.

### L2. Inferred RQ2 — RFM vs RFM Extended

| Evidence | Status |
|---|---|
| RFM-only artifact materialized | ❌ NO |
| EXP-02 runs on RFM Extended only | ✅ (by default; RFM-only would require artifact) |
| EXP-03 runs on RFM Extended only | ✅ |
| EXP-04 Family A (RFM-only comparison) | ❌ DEFERRED |
| EXP-05 runs on RFM Extended only | ✅ |

**Verdict:** RQ2 PARTIAL — RFM-only comparison cannot be evaluated.

### L3. Inferred RQ3 — Segment characteristics/business interpretation

| Evidence | Status |
|---|---|
| Internal metrics computed | ✅ |
| RFM profile per segment | ❌ EPIC-09 owns |
| Business validation | ❌ Out of scope EXP-01-05 |

**Verdict:** RQ3 thuộc EPIC-09 (segment analysis) và EPIC-10 (visualization). EXP-01-05 không answer RQ3.

### Finding L-RQ-1: Methodology files trong `docs/methodology/` chỉ TODO placeholders
- **Severity:** 🔴 HIGH (research methodology issue)
- **Description:** `docs/methodology/README.md` documents research questions as TODO placeholders
- **Impact:** RQ1/RQ2/RQ3 mappings ở review overview là INFERRED, không phải từ approved methodology docs
- **MENTOR_REVIEW_REQUIRED:** Approve RQ definitions chính thức trước khi claim methodology coverage

---

## 16. AUDIT M — Research Bias / Methodology Risks

### M1. Post-hoc selection

| Risk | Evidence | Severity |
|---|---|---|
| Configuration chosen sau khi nhìn kết quả rồi mới gọi "working reference" | No — all reviews explicitly note `WORKING_SELECTED` is not final; `TIED_WORKING_SELECTED` không ép chọn; protocol silhouette-primary→DBI→CH stated up-front | NONE |

### M2. Metric cherry-picking

| Risk | Evidence | Severity |
|---|---|---|
| Metric ưu tiên chỉ vì cho kết quả thuận lợi | No — 4 metrics (silhouette/DBI/CH/WCSS) used consistently; WCSS/runtime diagnostic only; protocol documented | NONE |

### M3. Cross-experiment leakage

| Risk | Evidence | Severity |
|---|---|---|
| Experiment dùng kết quả của experiment sau để định nghĩa experiment trước | EXP-03 K reused from EXP-02 — DOCUMENTED as CONTROLLED_REUSE_OF_EXP02_EVIDENCE. This is OK because EXP-02 ran BEFORE EXP-03. | NONE |

### M4. Circularity

| Risk | Evidence | Severity |
|---|---|---|
| EXP-03 chọn K → EXP-04/05 reuse K → EPIC-08 justify K | EXP-04 uses K=4 (independent baseline). EXP-05 uses EXP-01 working defaults (independent of EXP-03 selections). EPIC-08 not yet implemented. | LOW (need to monitor when EPIC-08 starts) |

### M5. Unsupported claims

- **Verified:** No "best/optimal/winner/superior/final/recommended" claims trong artifacts
- **Status:** OK

### M6. Other bias risks

#### Finding M-NEW-1: EXP-05 chỉ trên EXP-01 working defaults
- **Severity:** LOW (documented; running on EXP-03 selections would give different picture)
- **MENTOR_REVIEW_REQUIRED**

#### Finding M-NEW-2: Stability analysis chưa compute ARI/AMI
- **Severity:** MEDIUM (EPIC-08 ownership)
- **Current:** Block R/S/N generate raw evidence; ARI/AMI/Hungarian/thuộc EPIC-08

---

## 17. AUDIT N — Test Quality

### N1. Test count and coverage

| Category | Test files | Pass rate |
|---|---|---|
| Total pytest tests | 48 files | **1105/1105 PASS** (109s) |
| EXP-specific tests | 5 files | 208/208 PASS |
| Framework tests | `test_ml01_framework.py` | (subset of 1105) |
| Input integrity | `test_input_integrity.py` | ✅ |
| Determinism | `test_determinism.py` | ✅ |
| FE-06 pipeline | `test_pipeline_fe06.py` | 22 tests |
| Test data quality (QA) | `test_features.py`, `test_rfm.py` | ✅ |

### N2. Test depth (heuristic)

| Aspect | Status |
|---|---|
| Tests for behavior (not just mock) | ✅ |
| Tests for boundary conditions | ✅ |
| Tests for determinism | ✅ (`test_determinism.py`) |
| Tests for SHA integrity | ✅ (`test_input_integrity.py`) |
| Tests for redundancy (AverageQuantity=BasketSize) | ✅ (`test_pipeline_fe06.py::test_averagequantity_basketsize_equal`) |
| Tests for cancellation=return equality | ✅ (`test_pipeline_fe06.py::test_cancellationrate_returnrate_equal`) |
| Tests for stability/perturbation | ✅ (`test_exp05_stability.py`) |
| Tests for cross-run consistency | ✅ (determinism tests) |
| Tests for edge cases (ALL_NOISE, SINGLE_CLUSTER) | ✅ (metric tests) |
| Tests for FCM convergence | ✅ (`test_ml06_fuzzy.py`) |
| Tests for algorithm registration | ✅ (`test_ml01_framework.py`) |

**Verdict:** Tests are deep enough; not just smoke tests.

### N3. Lint / Format

- **ruff:** PASS (0 errors)
- **black:** PASS (155 files unchanged)
- **Pre-existing fix:** `tests/test_fe04_pipeline.py` đã được sửa `# noqa: E402` (documented in review)

---

## 18. AUDIT O — Reproducibility from Clean State

### O1. Smoke reproducibility test

| Component | Test | Status |
|---|---|---|
| Input SHA unchanged across experiments | Verified (per-experiment manifest) | ✅ |
| Config SHA recorded | Verified (`fe06_run.json`, `exp0X_manifest.json`) | ✅ |
| Library versions recorded | ✅ (numpy 2.3.5, pandas 3.0.6, sklearn 1.9.1, scipy 1.18.1, pyarrow 25.0.1) |
| Python version recorded | ✅ (3.14.4) |
| Platform recorded | ✅ (Linux 7.0.0-31-generic, x86_64) |
| Random seed protocol | ✅ (documented per-exp) |
| Output SHA recorded | ✅ (per `experiment_log_*.json`) |

### O2. Determinism verification

- **Block R:** 5/5 algorithms REPRODUCIBILITY_VERIFIED
- **EXP-04:** 6/6 scenarios deterministic
- **EXP-03:** Cross-config values where expected (e.g., K-Means n_init sweep gives identical labels)

### O3. Manual smoke test result

Verified:
- `final_clustering_dataset.parquet` loads correctly with 4371 rows × 14 columns
- 14 feature names match the documented list
- No NaN, no Inf, no constants
- `customer_metadata.parquet` aligns positionally
- `exp05_cluster_labels.parquet` has correct schema (9 cols, 75 unique run_ids)

**Verdict:** Reproducibility is solid. A reviewer can rerun from documented commands and reproduce evidence.

---

## 19. Issues Table (full)

| ID | Severity | Category | Location | Observed | Expected | Root cause | Impact | Action | Auto-fix? | Mentor? |
|---|---|---|---|---|---|---|---|---|---|---|
| **D-KMED-1** | 🔴 HIGH | Methodology | AGENTS.md §3 / README.md §1 / src/clustering/kmedoids.py | AGENTS.md claims "4 fixed algorithms: K-Means, K-Medoids, Agglomerative, DBSCAN" but K-Medoids is `NotImplementedError` placeholder; EXP-01-05 runs 5 algorithms (added GMM, FCM) | Documentation matches implementation scope | EPIC-06 expanded to 5 algorithms implicitly; docs not updated | Documentation và code don't match; future reviewer confusion | Either implement K-Medoids + rerun, OR update docs to reflect 5-algorithm scope | No | YES |
| **L-RQ-1** | 🔴 HIGH | Methodology | docs/methodology/README.md | RQ files are TODO placeholders | Research questions should be approved before EXP-01 | Methodology files not yet written | RQ1/RQ2/RQ3 are INFERRED from pending_review notes, not officially approved | Write official methodology docs (RQs, unit of analysis, benchmarking protocol) + ADR | No | YES |
| **EXP04-FS-01** | 🔴 HIGH | Methodology | reports/exp04/exp04_pending_review.json | RFM-only artifact doesn't exist → Family A DEFERRED → RQ2 PARTIAL | RQ2 should be evaluable | FE-06 hasn't materialized RFM-only artifact | RQ2 PARTIAL — can't claim RFM vs RFM Extended comparison | Materialize RFM-only via FE-06 ADR + EXP-04 Family A run | No | YES |
| **D-AGG-1** / H-AGG-1 | 🟡 MEDIUM | Methodology | exp03 review + working selection | Agglomerative Stage C K=3 linkage=average: silhouette=0.8033 (highest) but CH=77.15 vs alternatives 5029/5081 (~60× lower) | Either accept or adjust protocol | Known chaining artifact of average-linkage at small K | EXP03-SEL-02 TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING | EPIC-08 must do cross-metric + stability analysis before any claim; maybe adjust protocol | No | YES |
| **D-DBSCAN-1** | 🟡 MEDIUM | Methodology | exp01 working default + exp03 review | DBSCAN baseline at eps=0.5, min_samples=5: 17 clusters + 72.68% noise ratio | High noise ratio is unusual baseline | Default eps/min_samples chưa được tune cho working dataset | EXP-04-DBSCAN-01 PENDING_REVIEW | Either accept or systematic eps/min_samples sweep | No | YES |
| **D-FCM-1** / H-FCM-1 | 🟡 MEDIUM | Methodology | exp03 working selection | FCM m=1.5 selected per protocol; m=1.5 close to K-Means limit (m=1) | FCM should be meaningfully fuzzy | Selection protocol chose m=1.5 because silhouette cao nhất | EXP03 review §8 — flag là cần mentor | Either accept m=1.5 or require m ≥ 2.0 | No | YES |
| **B-DUP-1 / B-DUP-2** | 🟡 MEDIUM | Methodology | final matrix + redundancy_analysis.csv | AverageQuantity ≡ BasketSize; CancellationRate ≡ ReturnRate | Choose which feature(s) to use | Mathematical identity + data coincidence | Working matrix has 2 redundant pairs | No auto-drop (per FE-06 doc); mentor decision needed | No | YES |
| **B-NEW-1** | 🟡 MEDIUM | Methodology | customer_candidates.parquet | 6/14 features are `ELIGIBLE_WORKING_ASSUMPTION` | Features should be approved for clustering | FE-05 PENDING_REVIEW propagated to FE-06 | If mentor changes, all EXP-01-05 rerun | Mentor reviews feature definitions | No | YES |
| **I-1** | 🟡 MEDIUM | Methodology | exp04 review | EXP-04 only tests K-Means for preprocessing sensitivity | Should test multiple algorithms for generalizable conclusion | Algorithm scope = WORKING_ASSUMPTION | RQ2 PARTIAL broader sense | Either expand or document as limitation | No | YES |
| **E-NEW-1** | 🟡 MEDIUM | Methodology | metrics.py + EXP-01 plan | WCSS uses arithmetic centroid from hard labels (after argmax for GMM/FCM) | Cross-algorithm consistency | Methodological choice | EXP01-MET-02 PENDING_REVIEW | Accept current convention | No | YES |
| **J-1** | 🟡 MEDIUM | Methodology | exp05 review | EXP-05 only uses EXP-01 working defaults, not EXP-03 selections | Stability for optimal configurations | Scope = WORKING_ASSUMPTION | EP-IC-08 stability might miss optimal config evidence | Rerun EXP-05 with EXP-03 selections if needed | No | YES |
| **J-2** | 🟢 LOW | Methodology | exp05 review | Agglomerative + DBSCAN not in Block S | Test all algorithms for seed sensitivity | Assumed deterministic | EXP05-BLK-02 PENDING_REVIEW | Either expand or keep current | No | YES |
| **J-3** | 🟢 LOW | Methodology | exp05 review | Sigma grid [0, 0.01, 0.05] not yet justified | Justified sigma grid | WORKING_ASSUMPTION | EXP05-BLK-03 PENDING_REVIEW | Either expand (e.g., [0.1, 0.2]) or keep current | No | YES |
| **M-NEW-2** | 🟡 MEDIUM | Methodology | exp05 review | Stability/robustness analysis (ARI/AMI) chưa compute | Compute stability metrics for EPIC-08 | EPIC-08 ownership | ARI/AMI/Hungarian missing until EPIC-08 | EPIC-08 implementation | No | YES |
| **A-NEW-1** | 🟢 INFO | Data lineage | transactions_clean.parquet vs cleaning_run.json | Cancellation flag vs Return flag trở thành identical ở post-duplicate stage (100%) | OK | Cleaning pipeline drops both flags in duplicate stage | Documented in FE-06 §7.3.2 | OK - already documented | N/A | N/A |
| **H-KM-1** | 🟢 INFO | Expected behavior | exp03 results | K-Means n_init tie (deterministic) | Expected | Fixed seed → identical labels | Documented | OK | N/A | N/A |
| **D-NEW-1 / D-NEW-2** | 🟢 INFO | Documentation | tests/, registry.py | Counts và registered names | Documentation accuracy | Counts may be slightly stale | Review integrity | Verify counts in review | N/A | N/A |
| **I-3** | 🟢 LOW | Methodology | exp04 review | log1p NOT included in scenario matrix | log1p alternative | 6 features have negative values | EXP04-TR-01 PENDING_REVIEW | Either add log1p-compatible subset or document | No | YES |
| **E-NEW-2** | 🟢 INFO | Methodology | exp04 results | WCSS không comparable across scenarios với khác scale | WCSS comparison | Different feature scales per scenario | Documented | OK | N/A | N/A |
| **E-NEW-3** | 🟡 MEDIUM | Methodology | metrics.py | Cross-algorithm metric comparison có thể gây hiểu nhầm khi số cluster khác nhau | Explicit caveat | DBSCAN=17, others=4 | Document in EPIC-08 | Add caveat in EPIC-08 viz | No | YES |
| **K-4** | 🟢 INFO | Cross-experiment | All | Same algorithm + same config = same metric | Expected | Deterministic pipeline | OK | N/A | N/A | N/A |
| **G-NEW-2** | 🟢 INFO | Methodology | exp02 review | Disagreement giữa indicators không tự resolve | OK | Documented | OK | N/A | N/A | N/A |

---

## 20. Fixes Performed (engineering/documentation only)

Audit này **không tự sửa** methodology decisions. Tất cả methodology issues được liệt kê ở trên cần Mentor review.

Tuy nhiên, một số engineering/documentation gaps đã được verify (không modify):

1. **Verified SHAs** — không modify files nhưng xác nhận mọi SHA trong report khớp với artifact thực tế
2. **Verified tests** — pytest/ruff/black pass locally
3. **Verified artifacts** — direct `pd.read_parquet()` xác nhận shape, schema, NaN=0, Inf=0
4. **Verified redundancy claims** — AverageQuantity=BasketSize confirmed via direct diff
5. **Verified K-Means tie** — Stage C runs produce identical metrics (deterministic)
6. **Verified FCM convergence** — `n_iter`, `converged`, `final_objective` populated correctly

### No automated engineering fix was applied

The audit did not:
- Modify any code (per AGENTS.md §2.11 — no commit)
- Modify any config
- Modify any documentation
- Modify any report
- Modify any test

**Reason:** All fixes that involve research methodology require Mentor decision. Engineering-only fixes (typos, broken paths, wrong SHA) were not found in this audit.

---

## 21. Remaining Mentor Decisions (consolidated)

From all experiments + framework, the consolidated Mentor decision items are:

### Dataset / Feature

| ID | Decision | Status |
|---|---|---|
| FE-06-DATASET-01 | FE-06 working version = FE06-v1.0 (C7) | WORKING_ASSUMPTION |
| FE-06-DATASET-02 | Promote `FE06-v1.0` thành `RESEARCH_APPROVED_FINAL`? | PENDING |
| EXP04-FS-01 / EXP04-FS-02 / EXP04-FS-03 | Materialize RFM-only artifact? | PENDING |
| EXP04-IMP-01 | Median imputation with FE-06 fitted values | PENDING |
| EXP04-TR-01 | log1p NOT included | PENDING |
| FE05-FEATURES-01..06 (Frequency, Monetary, Quantity, Variance variants) | Promote final 14 features | TECHNICALLY_IMPLEMENTED, awaiting promotion |

### Methodology / Algorithm

| ID | Decision | Status |
|---|---|---|
| EXP03-SEL-01 | Selection protocol: silhouette (primary) → DBI → CH | WORKING_ASSUMPTION |
| EXP03-SEL-02 | Agglomerative Stage C K=3 linkage=average | TECHNICALLY_IMPLEMENTED_WITH_PENDING |
| EXP03-KM-01 | K-Means Stage C 3-way tie | TECHNICALLY_IMPLEMENTED_WITH_PENDING |
| EXP03-KM-01 (FCM) | FCM m=1.5 close to K-Means limit | PENDING |
| D-DBSCAN-1 / EXP04-DBSCAN-01 | DBSCAN baseline noise_ratio 0.7268 | PENDING |
| EXP04-ALG-01 | K-Means only for preprocessing | PENDING |
| EXP04-K-01 | K=4 CONTROLLED_REFERENCE_K | PENDING |
| EXP04-CONCL-01 | Decision taxonomy (CANDIDATE/TIED/PENDING/DEFERRED) | PENDING |
| E-NEW-1 / EXP01-MET-02 | WCSS convention (arithmetic centroid) | PENDING |
| EXP01-MET-01 / -03 / -04 / -05 / -06 | Noise exclusion, n_repeat=5, metric status schema | PENDING |

### EXP-05 / Stability

| ID | Decision | Status |
|---|---|---|
| EXP05-BLK-01 / -02 / -03 | Block R/S/N scope | WORKING_ASSUMPTION |
| EXP05-SEED-01 | Seeds [42, 7, 123, 2024, 1729] | WORKING_ASSUMPTION |
| EXP05-PERT-01 / -02 | Gaussian perturbation, sigma=0 sanity | WORKING_ASSUMPTION |
| EXP05-DEC-01 | Decision status taxonomy | WORKING_ASSUMPTION |
| EXP05-EPIC-08 | EPIC-08 owns ARI/AMI/Hungarian | TECHNICALLY_IMPLEMENTED |

### EPIC-08 Cross-cutting

| ID | Decision | Status |
|---|---|---|
| EPIC08-PLAN-01 | EPIC-08 plan dựa trên EXP-05 labels artifact? | PENDING |
| EPIC08-CROSS-ALG-01 | EPIC-08 allowed cross-algorithm ranking? | PENDING |
| EPIC08-WORKING-01 | EXP-01 defaults vs EXP-03 selections? | PENDING |
| EPIC08-INPUT-01 | FE-06 vs FE-05 input? | PENDING |
| EPIC08-VIZ-01 | Visualization scope | PENDING |
| EPIC08-FAMILY-A-01 | Block on EXP-04 Family A? | PENDING |
| EPIC08-PROFILE-01 | Overlap with EPIC-09? | PENDING |
| EPIC08-METRIC-01 | Add ARI/AMI? | PENDING |
| EPIC08-STAB-01..03 | Stability methodology | PENDING |
| EPIC08-RUNTIME-01 | Runtime comparison methodology | PENDING |
| EPIC08-BIZ-01 | Business validation | PENDING |
| EPIC08-CLAIM-01 | "Most stable algorithm" claim allowed? | PENDING |

### New Methodology Decisions (raised by this audit)

| ID | Decision | Severity | Source |
|---|---|---|---|
| **D-KMED-1** | K-Medoids implementation vs documentation update | 🔴 HIGH | AGENTS.md §3 / README.md §1 |
| **L-RQ-1** | Write official methodology docs (RQs, unit of analysis, benchmarking protocol) | 🔴 HIGH | docs/methodology/README.md |
| **E-NEW-3** | Cross-algorithm caveat for metrics when n_clusters differs | 🟡 MEDIUM | EPIC-08 vẽ comparison plots |

---

## 22. EPIC-08 Readiness Assessment

### 22.1. Layer-by-layer assessment

#### Engineering layer (IMPLEMENTATION-READY)
- ✅ Framework code (ML-01) solid: 59 tests pass
- ✅ 5 algorithm adapters implemented and tested (K-Means, Agglomerative, DBSCAN, GMM, FCM)
- ✅ Metric layer handles edge cases
- ✅ Artifact writing pipeline reproducible
- ✅ Input integrity tests pass
- ✅ 1105/1105 tests pass locally
- ✅ Lint / format clean

#### Research Evidence layer (EVIDENCE-READY)
- ✅ 185 successful runs (5 EXP × ~37 avg)
- ✅ Input SHA unchanged across all runs
- ✅ Config SHA recorded
- ✅ Library versions recorded
- ✅ exp05_cluster_labels.parquet: 327,825 rows × 9 cols, 75 unique run_ids
- ✅ Reproducibility verified for all 5 algorithms (Block R)
- ✅ Seed sensitivity evidence (Block S)
- ✅ Perturbation evidence (Block N)
- ✅ Baseline + K-sweep + hyperparameter + preprocessing + reproducibility

#### Methodology layer (PARTIAL)
- ✅ No `best/optimal/winner/final/recommended` claims inappropriate
- ✅ WORKING_ASSUMPTION / PENDING_REVIEW / DEFERRED explicitly tracked
- ⚠️ Multiple decisions pending Mentor review (see §21)
- ⚠️ RQ2 PARTIAL (Family A DEFERRED)
- ⚠️ Methodology files in `docs/methodology/` are TODO
- ⚠️ K-Medoids placeholder vs documentation claim (4 fixed algorithms)

#### EPIC-08 layer (CONDITIONAL)
- CAN start implementation: framework + evidence sufficient
- CANNOT finalize research claims: ~30+ methodology decisions pending

### 22.2. Phased EPIC-08 implementation suggestion

Phase A — Independent of methodology decisions (can start NOW):

| Task | Status | Why can start |
|---|---|---|
| ARI/AMI/Hungarian matching computation | ⚠️ EPIC-08 | Independent of pending decisions |
| Statistical tests (paired t-test, Wilcoxon) | ⚠️ EPIC-08 | Same |
| Confidence interval computation | ⚠️ EPIC-08 | Same |
| Runtime statistical comparison | ⚠️ EPIC-08 | Same |
| Cluster-size consistency analysis | ⚠️ EPIC-08 (already partially in EXP-05) | Same |
| Diagnostic viz (silhouette plot, comparison dashboard) | ⚠️ EPIC-08 | Same |

Phase B — Requires methodology decisions (must wait):

| Task | Blocking decision |
|---|---|
| Cross-algorithm ranking | EXP03-SEL-01, EXP03-SEL-02 |
| Working algorithm config for stability analysis | EXP03-KM-01, EXP03-SEL-02 (3-way tie, Agglomerative disagreement) |
| RFM Extended vs RFM-only comparison in EPIC-08 | EXP04-FS-01 (Family A not executed) |
| "Most stable algorithm" claim | EPIC08-CLAIM-01 + AGENTS.md §2.5 restriction |
| Segment profile / business validation | EPIC-09 |

### 22.3. Final verdict

| Layer | Verdict |
|---|---|
| **ENGINEERING_READY** | 🟢 **YES** — All tests pass, artifacts present, SHA chain verified |
| **RESEARCH_EVIDENCE_READY** | 🟢 **YES** — 185 runs successful, evidence reproducible, metrics valid |
| **METHODOLOGY_READY** | 🟡 **PARTIAL** — Multiple PENDING_REVIEW / WORKING_ASSUMPTION decisions |
| **EPIC08_READY** | 🟡 **CONDITIONAL** — Can start Phase A (metric/stability computation) but not Phase B (algorithm ranking) |

---

## 23. Recommended Next Steps

### 23.1. Immediate (no decision needed)

1. ✅ **Review this audit report** for accuracy
2. ✅ **Verify SHA values** match documented values (already done in this audit)
3. ✅ **Review existing review documents** (`docs/research/review/EXP01_EXP05_REVIEW_OVERVIEW.md`, etc.)

### 23.2. Mentor decision needed (BEFORE Phase B of EPIC-08)

1. 🔴 **K-Medoids methodology decision** (D-KMED-1):
   - Option A: Implement K-Medoids + add to EXP-01-05 (~38+ extra runs)
   - Option B: Update AGENTS.md / README.md / FE-06 doc / FE-04 doc / FE-05 doc / ML-01 docs to reflect 5-algorithm scope (no K-Medoids)
2. 🔴 **RQ1/RQ2/RQ3 official write-up** (L-RQ-1):
   - Write RQ definitions in `docs/methodology/TODO_research_questions.md` (rename / replace)
   - Write unit of analysis doc
   - Write benchmarking protocol doc
   - Get mentor approval + ADR
3. 🔴 **RFM-only artifact decision** (EXP04-FS-01):
   - Materialize RFM-only artifact via FE-06 ADR → run EXP-04 Family A → complete RQ2
   - OR document RQ2 as inherently not evaluable in current scope

### 23.3. Required for Phase A of EPIC-08 (less blocking)

1. 🟡 Confirm ARI/AMI computation method
2. 🟡 Confirm statistical test choice (parametric vs non-parametric)
3. 🟡 Confirm confidence interval method (bootstrap vs percentile)
4. 🟡 Confirm runtime comparison protocol
5. 🟡 Confirm cross-block cluster-size analysis (Block S vs Block N)

### 23.4. Required for Phase B of EPIC-08 (more blocking)

1. 🟡 Resolve Agglomerative disagreement (silhouette vs CH)
2. 🟡 Resolve K-Means tie (tiebreaker decision)
3. 🟡 Resolve DBSCAN baseline (accept 72.68% noise or tune)
4. 🟡 Resolve FCM m=1.5 (accept or require m ≥ 2.0)
5. 🟡 Decide whether to rerun EXP-05 with EXP-03 selections
6. 🟡 Decide whether to claim "most stable algorithm"
7. 🟡 Decide whether to materialize RFM-only
8. 🟡 Decide whether to expand EXP-04 to multiple algorithms

---

## 24. Color-coded Audit Summary

| Trục | Color | Why |
|---|---|---|
| Engineering | 🟢 GREEN | All tests pass, all SHAs verified, lint/format clean |
| Data Lineage | 🟢 GREEN | End-to-end SHA chain verified |
| Reproducibility | 🟢 GREEN | Block R verified all 5 algorithms |
| Feature Semantics | 🟡 YELLOW | 6/14 features pending; 3 redundancy pairs documented |
| Clustering Implementation | 🟡 YELLOW | K-Medoids placeholder vs docs claim |
| Metrics | 🟢 GREEN | Implementation correct, edge cases handled |
| EXP-01 to EXP-05 | 🟢 GREEN | 185 runs SUCCESS, all artifacts present |
| Cross-Experiment | 🟢 GREEN | EXP-04 input difference is by design |
| RQ Coverage | 🟡 YELLOW | RQ2 PARTIAL; RQ1/RQ3 partially covered |
| Methodology Bias | 🟡 YELLOW | Many WORKING_ASSUMPTION but no misuse |
| Test Quality | 🟢 GREEN | Deep tests, not just smoke |
| Documentation | 🟡 YELLOW | Methodology files TODO; review docs comprehensive |
| **Overall** | **🟡 YELLOW** | Engineering + Evidence solid; Methodology partial |

---

## 25. Conclusions

### 25.1. What repository IS ready for

- ✅ Engineering implementation of EPIC-08 (compute ARI/AMI, statistical tests, CI, runtime analysis)
- ✅ Reproducibility analysis on existing evidence
- ✅ Diagnostic visualization plots for EPIC-08 (silhouette plots, comparison dashboards)
- ✅ Using evidence for cross-algorithm discussion in report-writing
- ✅ Audit / verification work (the current document)

### 25.2. What repository is NOT ready for (without Mentor review)

- ❌ Final claim về "best algorithm" / "winning algorithm" / "most stable algorithm"
- ❌ RQ2 (RFM vs RFM Extended) — RFM-only artifact chưa materialize
- ❌ Final claim về working K, working hyperparameter, working preprocessing (đang WORKING_ASSUMPTION)
- ❌ Segment profile / business interpretation (EPIC-09 scope)

### 25.3. Status

**🟡 YELLOW — Pipeline ổn nhưng methodology chưa final.**

Specifically:
- Repository đã vượt qua engineering bar với evidence đầy đủ để compute ARI/AMI etc.
- Methodology vẫn còn hàng chục quyết định ở trạng thái PENDING_REVIEW / WORKING_ASSUMPTION cần mentor
- 2 high-severity methodology issues raised by this audit: K-Medoids discrepancy + missing official RQ definitions
- EPIC-08 Phase A (independent computation) có thể bắt đầu; Phase B (cross-algorithm ranking/claims) phải chờ mentor input

---

## 26. Provenance

Tất cả số liệu và phát hiện trong audit này được verify trực tiếp từ:

### 26.1. Code & tests
- `src/customer_segmentation/clustering/*.py` — clustering adapters
- `src/customer_segmentation/transformation/*.py` — FE-06 pipeline
- `tests/*.py` — 1105 tests

### 26.2. Reports
- `reports/fe01/*.csv|md|json` — FE-01 data audit
- `reports/fe02/*.csv|md|json` — FE-02 cleaning
- `reports/fe03/*.csv|md|json` — FE-03 outlier analysis
- `reports/fe04/*.csv|md|json` — FE-04 aggregation
- `reports/fe05/*.csv|md|json` — FE-05 feature engineering
- `reports/fe06/*.csv|md|json` — FE-06 transformation + final dataset
- `reports/exp01/*.csv|md|json` — EXP-01 baseline
- `reports/exp02/*.csv|md|json` — EXP-02 K-sweep
- `reports/exp03/*.csv|md|json` — EXP-03 hyperparameter
- `reports/exp04/*.csv|md|json` — EXP-04 preprocessing
- `reports/exp05/*.csv|md|json|parquet` — EXP-05 reproducibility

### 26.3. Documentation
- `AGENTS.md` — agent rules
- `README.md` — project README
- `docs/data_dictionary/*` — schema, provenance
- `docs/decisions/0001-*, 0002-*` — dataset ADRs
- `docs/research/*.md` — phase plans
- `docs/research/review/*` — existing reviews

### 26.4. Verification commands

```bash
# Tests / lint / format
pytest tests/ -q                                    # 1105/1105 PASS
ruff check .                                        # All checks passed
black --check .                                     # 155 files unchanged

# SHA verification
sha256sum data/processed/final_clustering_dataset.parquet
sha256sum data/processed/customer_metadata.parquet
sha256sum data/processed/customer_candidates.parquet
sha256sum data/raw/primary/'Online Retail.xlsx'
sha256sum data/raw/backup/online_retail_II.xlsx
sha256sum configs/clustering.yaml
sha256sum configs/transformation.yaml
sha256sum configs/exp05_stability_reproducibility.yaml

# Live artifact verification
python3 -c "
import pandas as pd
df = pd.read_parquet('data/processed/final_clustering_dataset.parquet')
assert df.shape == (4371, 14)
assert df.isna().sum().sum() == 0
md = pd.read_parquet('data/processed/customer_metadata.parquet')
assert len(md) == 4371
assert md['CustomerID'].nunique() == 4371
exp05 = pd.read_parquet('reports/exp05/exp05_cluster_labels.parquet')
assert exp05.shape == (327825, 9)
assert exp05['run_id'].nunique() == 75
print('All checks PASS')
"
```

---

**AUDIT COMPLETED.**

**Audit Status:** 🟡 **YELLOW**

**Audit Date:** 2026-09-22

**Auditor:** AI Agent (read-only evidence verification)

**No commit / no push / no PR performed** (per AGENTS.md §2.11 and audit protocol).
