# ADR-0004 — Research Questions: RQ1, RQ2, RQ3 Definitions

## Status

Accepted

## Date

2026-09-22

## Task ID

EPIC-07 / EPIC-08

## Deciders

Researcher / Mentor

## Context

The repository previously lacked official Research Question definitions. The `docs/methodology/` directory contained only TODO placeholders. Research questions were inferred from experiment documentation, creating ambiguity about:
- What RQ1, RQ2, and RQ3 actually measure
- What evidence is required to answer each question
- What scope boundaries apply
- How each RQ maps to experimental evidence

Additionally, RQ2 was previously framed as a comparison between "RFM-only" (3 features) and "RFM Extended" (14 features). However, the RFM-only artifact does not exist in the repository, meaning the original RQ2 framing cannot be answered with current evidence. EXP-04 Family A (which would have evaluated RFM-only) was DEFERRED.

Three options were available:
- **Option A**: Materialize RFM-only artifact and execute EXP-04 Family A to enable the original RQ2 framing. Estimated cost: ~30–60 new runs + ~1–2 weeks.
- **Option B**: Reformulate RQ2 to reflect what the existing evidence actually supports. No new artifacts or reruns required.
- **Option C**: Accept RQ2 as permanently incomplete (PARTIAL). Not a clean research state.

## Decision

### RQ1 — Algorithm Comparison Under Controlled Conditions

> **RQ1 question:** How do different clustering algorithms perform on customer-level behavioral feature spaces derived from retail transactional data, under controlled experimental conditions?

**Research scope:**
- **Population / Unit of Analysis**: Customer-level. Each customer is represented by one feature vector in R¹⁴ (14 features). Unit = customer (identified by CustomerID).
- **Dataset**: `data/processed/final_clustering_dataset.parquet` (FE06-v1.0), SHA-256 `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`. 4,371 customers × 14 features.
- **Feature Representation**: RFM Extended = 14 features. Six features are in `ELIGIBLE_WORKING_ASSUMPTION` status (Frequency, AverageQuantity, BasketSize, ActiveDays, CancellationRate, ReturnRate). Feature set is accepted as-is for the current phase.
- **Preprocessing**: FE-06 C7 configuration (median imputation + Yeo-Johnson transformation + RobustScaler). Status = `WORKING_ASSUMPTION`.
- **Algorithm Scope**: Five algorithms (per ADR-0003): K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means. K-Medoids is OUT OF SCOPE.
- **K Treatment**: EXP-02 sweep K ∈ [2, 10] step=1 identified 13 candidates. EXP-03 used K=3 from EXP-02 as a controlled interaction point. K is treated per-experiment; no "best K" claim.
- **Hyperparameter Treatment**: EXP-03 sensitivity analysis produced per-algorithm working selections via protocol (silhouette primary → DBI → CH tiebreaker). Status = `WORKING_SELECTED` (not final approved).
- **Quality Metrics**: Internal metrics only: Silhouette Score, Davies-Bouldin Index, Calinski-Harabasz Index, Within-Cluster Sum of Squares (WCSS). External/business metrics are out of scope.
- **Runtime**: Algorithm execution time, measured per repeat (n_repeat=5). Excludes metric computation and artifact writing.
- **Reproducibility**: Verified at EXP-05 Block R (5/5 algorithms reproducible with seed=42).
- **Stability**: EXP-05 Block S (seed sensitivity) and Block N (feature perturbation) generate raw evidence; ARI/AMI computation deferred to EPIC-08.
- **Interpretation Boundary**: No claim of "best", "winner", "optimal", "recommended", or "final" algorithm. Cross-algorithm comparison is presented as evidence with explicit caveats. Composite scores are prohibited.

**Evidence supporting RQ1:**
- EXP-01: 5 algorithms × 1 configuration = baseline metrics
- EXP-02: 37 runs, K ∈ [2, 10], 13 candidate K values
- EXP-03: 38 runs, hyperparameter sensitivity per algorithm
- EXP-05: Block R/S/N raw stability evidence

---

### RQ2 — Preprocessing Sensitivity Under Fixed Feature Representation

> **RQ2 question:** How does preprocessing strategy affect clustering quality under a fixed customer-level feature representation?

**Rationale for reformulation:**

The original RQ2 framing ("RFM-only vs RFM Extended") cannot be evaluated because the RFM-only artifact does not exist and EXP-04 Family A was DEFERRED. Rather than leaving RQ2 permanently incomplete or delaying the research to materialize RFM-only, RQ2 is reformulated to reflect the evidence that **is** available.

EXP-04 Family B evaluated six preprocessing configurations (C0: none/none, C1: none/standard, C2: none/minmax, C3: none/robust, C6: yeo_johnson/standard, C7: yeo_johnson/robust) on the same 14-feature RFM Extended set using K-Means (K=4). This directly supports a question about preprocessing strategy sensitivity.

**Research scope:**
- **Population / Unit of Analysis**: Same as RQ1 (customer-level, 4,371 customers).
- **Dataset**: Same as RQ1.
- **Feature Representation**: RFM Extended (14 features), fixed. Same as RQ1.
- **Independent Variable**: Preprocessing strategy (transformation × scaling configuration).
- **Dependent Variables**: Internal quality metrics (silhouette, DBI, CH, WCSS) and runtime.
- **Algorithm**: K-Means only (controlled reference per EXP-04 design). Not a comparison across algorithms.
- **K**: K=4 (controlled reference per EXP-04 design).
- **Evidence**: 30 runs across 6 scenarios × 5 repeats from EXP-04 Family B.

**What RQ2 does NOT ask:**
- Does not compare RFM-only vs RFM Extended (this requires RFM-only artifact).
- Does not identify a "best preprocessing configuration".
- Does not make a cross-algorithm preprocessing claim.

**Limitation of reformulated RQ2:**
- Single-algorithm (K-Means) — preprocessing sensitivity may differ across algorithms.
- Single-K (K=4) — sensitivity may differ at different cluster counts.
- RFM-only comparison is **FUTURE WORK**. See `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.

**Evidence supporting reformulated RQ2:**
- EXP-04 Family B: 6 preprocessing scenarios × 5 repeats = 30 runs, all deterministic, all successful.

---

### RQ3 — Stability and Reproducibility

> **RQ3 question:** How reproducible and how robust are the clusterings produced by each algorithm under different seeds and feature-space perturbations?

**Research scope:**
- **Population / Unit of Analysis**: Same as RQ1 (customer-level).
- **Dataset**: Same as RQ1.
- **Reproducibility (Block R)**: Same seed + same config + same input → identical output. Verified for all 5 algorithms at EXP-05.
- **Seed Stability (Block S)**: K-Means, GMM, Fuzzy C-Means × 5 seeds. Agglomerative and DBSCAN are deterministic (no seed axis). Raw evidence available; ARI/AMI computation deferred to EPIC-08.
- **Perturbation Robustness (Block N)**: All 5 algorithms × Gaussian feature perturbation (sigma = 0, 0.01, 0.05 × column std). Raw evidence available; ARI/AMI computation deferred to EPIC-08.
- **Stability Metrics**: ARI (Adjusted Rand Index), AMI (Adjusted Mutual Information), Hungarian cluster matching. Computed in EPIC-08 using `exp05_cluster_labels.parquet`.
- **Statistical Tests**: Paired t-test / Wilcoxon across seeds and perturbation levels. Chosen in EPIC-08 plan.
- **Confidence Intervals**: Bootstrap or percentile. Chosen in EPIC-08 plan.

**What RQ3 does NOT cover:**
- Business interpretation of clusters (belong to EPIC-09).
- Customer profiling or segment naming (belong to EPIC-09).
- External validation against ground truth (not applicable; unsupervised).

**Evidence supporting RQ3:**
- EXP-05: 75 runs total (Block R: 25, Block S: 15, Block N: 35). Labels artifact: 327,825 rows × 9 columns.

---

## Consequences

### Easier

- All three research questions now have official, written definitions.
- Evidence-to-RQ mapping is explicit and auditable.
- EPIC-08 can proceed with clear evaluation criteria.
- No ambiguity about what constitutes a "complete" answer to each RQ.

### Harder or Riskier

- RQ2 reformulation means the original "RFM-only vs RFM Extended" question is not answered. This must be clearly stated in any thesis or publication.
- RQ2 is scoped to preprocessing sensitivity on RFM Extended only — a narrower question than originally implied.

## Alternatives Considered

### Option A for RQ2: Materialize RFM-only

- **Estimated impact**: ~30–60 new runs + ~1–2 weeks.
- **Decision**: Rejected for current phase. The reformulated RQ2 is answerable with existing evidence. RFM-only materialization is future work.

### Option B for RQ2: Accept PARTIAL status indefinitely

- **Decision**: Rejected. An indefinite PARTIAL status creates ambiguity for EPIC-08 and for thesis/paper readers.

### Option C for RQ2: Reformulate RQ2 (CHOSEN)

- **Estimated impact**: Zero new runs. Documentation updates only.
- **Decision**: Accepted. The reformulated question accurately reflects the available evidence while being methodologically honest.

## Future Work

- RFM-only materialization and RFM-only vs RFM Extended comparison: see `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.
- K-Medoids implementation: see ADR-0003.

## References

- `docs/methodology/research_questions.md` — official RQ definitions
- `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis leading to these decisions
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` — resolution status
- `docs/decisions/0003-algorithm-scope.md` — ADR-0003 (algorithm scope)
- EXP-01 through EXP-05 reports in `reports/exp01/` through `reports/exp05/`
