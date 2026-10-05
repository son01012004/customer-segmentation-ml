# Research Questions

> **Status:** METHODOLOGY_LOCKED (per ADR-0004)
> **Date:** 2026-09-22
> **Source:** ADR-0004 — `docs/decisions/0004-research-questions.md`

This document records the three official Research Questions for the customer segmentation project. Each RQ is defined with its population, dataset, scope, evidence base, and interpretation boundary.

---

## RQ1 — Algorithm Comparison Under Controlled Conditions

> **Question:** How do different clustering algorithms perform on customer-level behavioral feature spaces derived from retail transactional data, under controlled experimental conditions?

### Population and Unit of Analysis

- **Unit**: Customer (one row per customer, identified by `CustomerID`)
- **Observation count**: 4,371 customers
- **Feature space**: R¹⁴ (14 features per customer)

### Dataset

- **File**: `data/processed/final_clustering_dataset.parquet`
- **SHA-256**: `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
- **Version**: FE06-v1.0
- **Source**: UCI Online Retail (primary dataset, per ADR-0001)
- **Preprocessing**: FE-06 C7 (median imputation + Yeo-Johnson transformation + RobustScaler). Status: `WORKING_ASSUMPTION`.

### Feature Representation

RFM Extended — 14 features:

| # | Feature | FE-06 Status | Notes |
|---|---|---|---|
| 1 | Recency | ELIGIBLE | Days from last purchase to ReferenceDate |
| 2 | Frequency | ELIGIBLE_WORKING_ASSUMPTION | nunique(InvoiceNo) |
| 3 | Monetary | ELIGIBLE | Sum of signed LineRevenue |
| 4 | TotalQuantity | ELIGIBLE | Sum of signed Quantity |
| 5 | AverageQuantity | ELIGIBLE_WORKING_ASSUMPTION | TotalQuantity / Frequency |
| 6 | BasketSize | ELIGIBLE_WORKING_ASSUMPTION | Alias for AverageQuantity |
| 7 | TenureDays | ELIGIBLE | Days from first to last purchase |
| 8 | PurchaseIntervalMean | ELIGIBLE | Mean inter-invoice days (NaN if <2 invoices) |
| 9 | PurchaseIntervalStd | ELIGIBLE | Std of inter-invoice days (NaN if <3 invoices) |
| 10 | ActiveDays | ELIGIBLE_WORKING_ASSUMPTION | nunique(calendar days) |
| 11 | AverageInvoiceValue | ELIGIBLE | Monetary / Frequency |
| 12 | ProductsPerInvoice | ELIGIBLE | DistinctProducts / DistinctInvoiceCount |
| 13 | CancellationRate | ELIGIBLE_WORKING_ASSUMPTION | CancellationInvoiceCount / Frequency |
| 14 | ReturnRate | ELIGIBLE_WORKING_ASSUMPTION | ReturnInvoiceCount / Frequency |

Six features are in `ELIGIBLE_WORKING_ASSUMPTION` status. See FE-06 documentation §13 for pending review items.

### Algorithm Scope

Five algorithms (per ADR-0003):

1. **K-Means** (`kmeans`) — sklearn implementation
2. **Agglomerative Clustering** (`agglomerative`) — sklearn with Ward linkage
3. **DBSCAN** (`dbscan`) — sklearn, density-based
4. **Gaussian Mixture Model** (`gmm`) — sklearn, probabilistic
5. **Fuzzy C-Means** (`fuzzy_cmeans`) — custom NumPy implementation

K-Medoids is **OUT OF SCOPE** (per ADR-0003).

### K Treatment

- EXP-02 swept K ∈ [2, 10] step=1, identified 13 candidates via deterministic heuristic.
- EXP-03 used K=3 as a controlled interaction point (from EXP-02 candidates).
- K is treated per-experiment. No "best K" or "optimal K" claim is made.
- Per-algorithm K candidates are reported as evidence.

### Hyperparameter Treatment

- EXP-03 performed sensitivity analysis per algorithm (Stage A: baseline; Stage B: single-parameter sweeps; Stage C: selected interactions).
- Per-algorithm working selections produced via protocol: **silhouette primary → DBI → CH tiebreaker**.
- Selection status = `WORKING_SELECTED` (not final approved; pending EPIC-08 validation).
- Protocol documented in `docs/research/EXP03_HYPERPARAMETER_REVIEW.md`.

### Quality Metrics

Internal metrics only (no external validation):

| Metric | Description | Status |
|---|---|---|
| Silhouette Score | Mean pairwise distance ratio | PRIMARY |
| Davies-Bouldin Index | Mean cluster similarity ratio | Tiebreaker 1 |
| Calinski-Harabasz Index | Cluster separation vs dispersion | Tiebreaker 2 |
| WCSS | Within-cluster sum of squares (arithmetic centroid) | Diagnostic only |

Metric status schema: `VALID_VALUE`, `NOT_APPLICABLE`, `COMPUTATION_ERROR`, `MISSING`.
Noise handling: DBSCAN noise points (label=-1) are excluded from internal metrics and WCSS.

### Runtime

- Measured as algorithm execution time (excludes metric computation and artifact writing).
- Protocol: n_repeat=5 per configuration for variance estimation.
- Runtime data from EXP-01 through EXP-05.

### Reproducibility

- Verified at EXP-05 Block R: 5/5 algorithms produce identical cluster labels across 5 repeats with seed=42.
- Status: `REPRODUCIBILITY_VERIFIED`.

### Stability

- EXP-05 Block S: seed sensitivity (K-Means, GMM, Fuzzy C-Means × 5 seeds).
- EXP-05 Block N: feature perturbation (Gaussian noise, sigma ∈ {0, 0.01, 0.05} × column std).
- ARI/AMI computation: **deferred to EPIC-08** using `exp05_cluster_labels.parquet` (327,825 rows × 9 columns).

### Interpretation Boundary

> **Prohibited terms (per AGENTS.md §2.5):** "best", "winner", "optimal", "recommended", "final", "superior".

Cross-algorithm comparison is presented as evidence with explicit caveats. Composite scoring is prohibited.

---

## RQ2 — Preprocessing Sensitivity Under Fixed Feature Representation

> **Question:** How does preprocessing strategy affect clustering quality under a fixed customer-level feature representation?

### Population and Unit of Analysis

Same as RQ1 (4,371 customers, R¹⁴).

### Dataset

Same as RQ1.

### Independent Variable

Preprocessing strategy — defined as transformation × scaling configuration applied to the fixed 14-feature set.

### Evidence

EXP-04 Family B: 6 preprocessing scenarios × 5 repeats = 30 runs. All deterministic.

| Scenario | Transformation | Scaling | Role |
|---|---|---|---|
| C0 | none | none | NO_TRANSFORM_NO_SCALING_REFERENCE |
| C1 | none | standard | Candidate |
| C2 | none | minmax | Candidate |
| C3 | none | robust | Candidate |
| C6 | yeo_johnson | standard | Candidate |
| C7 | yeo_johnson | robust | FE06_WORKING_CONFIGURATION_REFERENCE |

### Limitation

- Single algorithm (K-Means) — preprocessing sensitivity may differ across algorithms.
- Single K (K=4) — sensitivity may differ at different cluster counts.
- **RFM-only vs RFM Extended comparison is NOT within scope of reformulated RQ2.** See `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.

---

## RQ3 — Stability and Reproducibility

> **Question:** How reproducible and how robust are the clusterings produced by each algorithm under different seeds and feature-space perturbations?

### Population and Unit of Analysis

Same as RQ1 (4,371 customers, R¹⁴).

### Dataset

Same as RQ1.

### Reproducibility

- EXP-05 Block R: 5 algorithms × n_repeat=5 × seed=42.
- All 5 algorithms: `REPRODUCIBILITY_VERIFIED` (1 unique labels_hash across 5 repeats).
- Status: VERIFIED.

### Seed Stability

- EXP-05 Block S: K-Means, GMM, Fuzzy C-Means × 5 seeds (42, 7, 123, 2024, 1729).
- Agglomerative and DBSCAN are excluded (deterministic — no random axis).
- Raw evidence: 15 runs. ARI/AMI computation deferred to EPIC-08.

### Perturbation Robustness

- EXP-05 Block N: 5 algorithms × (sigma=0, 0.01, 0.05) × 3 perturbation seeds.
- Total: 35 runs.
- Sigma=0 sanity check: reproduces EXP-01 baseline (PASS).
- ARI/AMI computation deferred to EPIC-08.

### Stability Metrics (EPIC-08 owned)

| Metric | Description | Status |
|---|---|---|
| ARI | Adjusted Rand Index | EPIC-08 |
| AMI | Adjusted Mutual Information | EPIC-08 |
| Hungarian matching | Cluster label alignment across runs | EPIC-08 |
| Statistical tests | Paired t-test / Wilcoxon | EPIC-08 plan |
| Confidence intervals | Bootstrap / percentile | EPIC-08 plan |

### Interpretation Boundary

RQ3 does NOT cover:
- Business interpretation of clusters (EPIC-09).
- Customer profiling or segment naming (EPIC-09).
- External validation against ground truth.

---

## RQ Coverage Summary

| RQ | Evidence Available | Answerable? | Status |
|---|---|---|---|
| RQ1 | EXP-01 (baseline), EXP-02 (K-sweep), EXP-03 (hyperparameter) | PARTIAL — quality evidence complete; stability analysis in EPIC-08 | METHODOLOGY_LOCKED |
| RQ2 | EXP-04 Family B (preprocessing sensitivity) | PARTIAL — preprocessing sensitivity on RFM Extended; RFM-only comparison future work | METHODOLOGY_LOCKED |
| RQ3 | EXP-05 Blocks R/S/N (raw evidence) | PARTIAL — evidence complete; ARI/AMI analysis in EPIC-08 | METHODOLOGY_LOCKED |

---

## References

- ADR-0003: `docs/decisions/0003-algorithm-scope.md`
- ADR-0004: `docs/decisions/0004-research-questions.md`
- RFM-only future work: `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`
- Experiment reports: `reports/exp01/` through `reports/exp05/`
