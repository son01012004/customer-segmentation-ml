# Methodology Overview

> **Status:** METHODOLOGY_LOCKED (per ADR-0004)
> **Date:** 2026-09-22
> **Source:** ADR-0004, ADR-0003, and related decisions

This document describes the overall research methodology: study design, benchmarking protocol, and the relationship between Research Questions and Experimental Evidence.

---

## 1. Research Questions

Three Research Questions guide this project (per `docs/methodology/research_questions.md` and ADR-0004):

| RQ | Question | Evidence Phase |
|---|---|---|
| **RQ1** | Algorithm comparison under controlled conditions | EXP-01, EXP-02, EXP-03 |
| **RQ2** | Preprocessing sensitivity under fixed feature representation | EXP-04 |
| **RQ3** | Stability and reproducibility | EXP-05 + EPIC-08 |

---

## 2. Study Design

### 2.1. Dataset

| Field | Value |
|---|---|
| Source | UCI Online Retail (primary, ADR-0001) |
| Backup | UCI Online Retail II (ADR-0002) |
| Raw file | `data/raw/primary/Online Retail.xlsx` |
| Raw SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Cleaning | FE-02 (removes invalid records, duplicates) |
| Customer aggregation | FE-04 (customer-level base) |
| Feature engineering | FE-05 (RFM + extended behavioral features) |
| Transformation | FE-06 (imputation, Yeo-Johnson, RobustScaler) |
| Final matrix | `data/processed/final_clustering_dataset.parquet` (4,371 × 14) |
| Final matrix SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Customer metadata | `data/processed/customer_metadata.parquet` (4,371 × 1, CustomerID) |

### 2.2. Feature Representation

RFM Extended — 14 features (per RQ1 and FE-06 documentation):

- **RFM core**: Recency, Frequency, Monetary
- **Quantity**: TotalQuantity, AverageQuantity, BasketSize
- **Temporal**: TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays
- **Value**: AverageInvoiceValue
- **Diversity**: ProductsPerInvoice
- **Cancellation**: CancellationRate, ReturnRate

Six features are in `ELIGIBLE_WORKING_ASSUMPTION` status (per FE-06 §13). See `docs/methodology/research_questions.md` §RQ1 for full list.

### 2.3. Preprocessing Pipeline (FE-06 C7)

| Step | Method | Details |
|---|---|---|
| Imputation | Median | PurchaseIntervalMean (41.0), PurchaseIntervalStd (32.585) |
| Transformation | Yeo-Johnson | Per-feature lambda, fitted by sklearn |
| Scaling | RobustScaler | median=0, IQR=1 |

Status: `WORKING_ASSUMPTION`. Not promoted to `RESEARCH_APPROVED_FINAL`.

---

## 3. Benchmarking Protocol

### 3.1. Algorithm Scope

Five algorithms (per ADR-0003):

| Algorithm | Adapter | Supports Random Seed | Notes |
|---|---|---|---|
| K-Means | sklearn | Yes (init) | Hard centroid-based |
| Agglomerative | sklearn | No (deterministic) | Ward linkage |
| DBSCAN | sklearn | No (deterministic) | Density-based, noise label=-1 |
| GMM | sklearn | Yes (EM init) | Probabilistic, soft probabilities |
| Fuzzy C-Means | Custom NumPy | Yes (Dirichlet init) | Bezdek update, fuzzy membership |

K-Medoids: **OUT OF SCOPE** (per ADR-0003).

### 3.2. Cluster Count (K)

- Range swept: K ∈ [2, 10], step=1 (EXP-02).
- 13 candidate K values identified via deterministic heuristic (top_n=3, drop_ratio=0.2, min_agreement=2).
- No "best K" claim. K treatment is per-experiment.

### 3.3. Hyperparameter Selection

Per-algorithm sensitivity analysis (EXP-03):

- **Stage A**: Baseline per algorithm (1 run each).
- **Stage B**: Single-parameter sweeps (6–7 runs per algorithm).
- **Stage C**: Selected interactions (K=3 from EXP-02 × parameter) — 3 runs per algorithm.

**Selection protocol**: Silhouette (primary) → Davies-Bouldin (tiebreaker 1) → Calinski-Harabasz (tiebreaker 2).

Selection status = `WORKING_SELECTED` (not final approved). Cross-validation via EPIC-08.

### 3.4. Preprocessing Sensitivity (EXP-04)

Six scenarios × 5 repeats = 30 runs on RFM Extended (14 features) using K-Means (K=4).

| Scenario | Transformation | Scaling |
|---|---|---|
| C0 | none | none |
| C1 | none | standard |
| C2 | none | minmax |
| C3 | none | robust |
| C6 | yeo_johnson | standard |
| C7 | yeo_johnson | robust |

C7 mirrors FE-06 working configuration.

### 3.5. Reproducibility and Stability (EXP-05)

Three evidence blocks:

| Block | Content | Runs |
|---|---|---|
| Block R | Reproducibility verification (seed=42, n_repeat=5) | 25 |
| Block S | Seed sensitivity (5 seeds × 3 algorithms) | 15 |
| Block N | Feature perturbation (3 sigmas × 3 perturbation seeds × 5 algorithms) | 35 |

All evidence stored in `reports/exp05/exp05_cluster_labels.parquet` (327,825 rows × 9 columns).

### 3.6. Evaluation Metrics

| Metric | Role | Direction |
|---|---|---|
| Silhouette Score | Primary quality | Higher = better |
| Davies-Bouldin Index | Secondary quality | Lower = better |
| Calinski-Harabasz Index | Secondary quality | Higher = better |
| WCSS | Diagnostic only | Lower = more compact (diagnostic) |
| ARI / AMI | Stability (EPIC-08) | Higher = more similar |
| Runtime | Computational cost | Lower = faster |

**Prohibited**: Composite scores, weighted rankings, "best"/"optimal"/"winner" claims (AGENTS.md §2.5).

---

## 4. Experiment Pipeline

```
DS-05: Dataset selection (DONE)
  └─ ADR-0001, ADR-0002

FE-01: Raw data audit (DONE)
FE-02: Data cleaning (DONE)
FE-03: Outlier analysis (DONE, diagnostic only)
FE-04: Customer aggregation (DONE)
FE-05: Feature engineering (DONE)
FE-06: Transformation + Scaling (DONE)
  └─ Final matrix: SHA ba54033e...

EPIC-06: Clustering adapters (DONE)
  └─ 5 algorithms registered (ADR-0003)
  └─ ADR-0004 defines RQ1–RQ3

EPIC-07: Controlled experiments (DONE)
  ├─ EXP-01: Baseline (5 runs)
  ├─ EXP-02: K-sweep (37 runs)
  ├─ EXP-03: Hyperparameter sensitivity (38 runs)
  ├─ EXP-04: Preprocessing sensitivity (30 runs, Family B only)
  └─ EXP-05: Reproducibility + stability evidence (75 runs)
  Total: 185 runs

EPIC-08: Stability analysis + evaluation (PENDING)
  ├─ Phase A: ARI/AMI, statistical tests, CI, runtime
  └─ Phase B: Cross-algorithm analysis (conditional on mentor approval)

EPIC-09: Customer profiling (PENDING)
EPIC-10: Visualization (PENDING)
```

---

## 5. Interpretation Boundaries

### 5.1. What the methodology supports

- Internal quality metric comparison (silhouette, DBI, CH, WCSS) across algorithms, K values, and preprocessing configurations.
- Reproducibility verification (determinism with fixed seed).
- Seed stability evidence (how labels change across seeds).
- Perturbation robustness evidence (how labels change under feature noise).
- ARI/AMI computed in EPIC-08 from EXP-05 labels artifact.

### 5.2. What the methodology does NOT support

- **"Best algorithm" / "winner" / "optimal" / "recommended" / "final" claims** (AGENTS.md §2.5).
- Business interpretation of clusters (EPIC-09).
- Customer profiling or segment naming (EPIC-09).
- RFM-only vs RFM Extended comparison (RQ2 reformulated; RFM-only future work).
- External validation against ground truth (unsupervised setting).
- Deployment or production recommendations.
- Generalization beyond the dataset scope (single retail dataset).

---

## 6. Reproducibility Requirements

Each experiment records:

- Input SHA-256 (dataset, config)
- Output SHA-256
- Library versions (numpy, pandas, scipy, scikit-learn, pyarrow)
- Python version and platform
- Random seed protocol
- Execution metadata (timestamp, duration)

SHA chain: raw file → FE-05 candidates → FE-06 final matrix → EXP artifacts.

---

## 7. ADR Chain

| ADR | Decision | Status |
|---|---|---|
| ADR-0001 | Primary dataset = UCI Online Retail | Accepted |
| ADR-0002 | Backup dataset = UCI Online Retail II | Accepted |
| ADR-0003 | Algorithm scope = 5 algorithms (K-Medoids deferred) | Accepted |
| ADR-0004 | Research Questions RQ1, RQ2, RQ3 | Accepted |

---

## 8. References

- `docs/methodology/research_questions.md` — RQ definitions
- `docs/decisions/0003-algorithm-scope.md` — ADR-0003
- `docs/decisions/0004-research-questions.md` — ADR-0004
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` — current status
- `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md` — future work
