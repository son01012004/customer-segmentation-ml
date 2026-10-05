# METHODOLOGY LOCK STATUS

> **Status:** METHODOLOGY_LOCKED
> **Date:** 2026-09-22
> **Scope:** Methodology decisions spanning FE-01 → FE-06 → EPIC-06 → EXP-01 → EXP-05
> **Audit:** AI Agent — read-only resolution + documentation update
> **Documents created/modified:** 11 files (see §9)
> **No commit / no push / no PR performed.**

---

## 1. Methodology Status

| Trục | Status | Notes |
|---|---|---|
| Algorithm scope | ✅ LOCKED | 5 algorithms; K-Medoids OUT OF SCOPE (ADR-0003) |
| RQ1 | ✅ LOCKED | Algorithm comparison (ADR-0004) |
| RQ2 | ✅ LOCKED | Preprocessing sensitivity; RFM-only is future work (ADR-0004) |
| RQ3 | ✅ LOCKED | Stability / reproducibility (ADR-0004) |
| Dataset version | ✅ LOCKED | FE06-v1.0 = `RESEARCH_WORKING_BASELINE` |
| Feature set | ⚠️ WORKING | 14 features; 6 ELIGIBLE_WORKING_ASSUMPTION |
| Preprocessing config | ⚠️ WORKING | C7 (yeo_johnson + robust + median) = WORKING_ASSUMPTION |
| RFM-only | ⏳ FUTURE WORK | Not in current scope; checklist in `RFM_ONLY_FUTURE_WORK_PLAN.md` |
| K-Medoids | ✅ LOCKED OUT | OUT OF SCOPE (ADR-0003) |
| Cross-algorithm ranking | ⚠️ PENDING | Not allowed until EPIC-08 Phase B + mentor approval |

---

## 2. Locked Decisions

| ID | Decision | Value | ADR | Status |
|---|---|---|---|---|
| **ALG-01** | Algorithm scope | 5 algorithms: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means | ADR-0003 | ✅ LOCKED |
| **ALG-02** | K-Medoids status | OUT OF SCOPE | ADR-0003 | ✅ LOCKED |
| **RQ-01** | RQ1 definition | Algorithm comparison under controlled conditions | ADR-0004 | ✅ LOCKED |
| **RQ-02** | RQ2 definition | Preprocessing sensitivity under fixed feature representation | ADR-0004 | ✅ LOCKED |
| **RQ-03** | RQ3 definition | Stability and reproducibility | ADR-0004 | ✅ LOCKED |
| **DS-01** | Dataset version | FE06-v1.0 = `RESEARCH_WORKING_BASELINE` | — | ✅ LOCKED |
| **DS-02** | Dataset SHA | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | — | ✅ LOCKED |
| **DS-03** | Preprocessing | FE-06 C7 (yeo_johnson + robust + median) | — | ✅ LOCKED |
| **EPIC08-INPUT** | EPIC-08 input | `final_clustering_dataset.parquet` (FE06-v1.0) | — | ✅ LOCKED |
| **EPIC08-EVIDENCE** | EPIC-08 stability evidence | `exp05_cluster_labels.parquet` (327,825 rows) | — | ✅ LOCKED |

---

## 3. Working Assumptions (not yet approved)

| ID | Item | Status | Notes |
|---|---|---|---|
| **WA-01** | FE-06 C7 preprocessing | WORKING_ASSUMPTION | 6/14 features at ELIGIBLE_WORKING_ASSUMPTION |
| **WA-02** | EXP-03 selection protocol (silhouette → DBI → CH) | WORKING_ASSUMPTION | Per-algorithm selections are WORKING_SELECTED |
| **WA-03** | EXP-02 K range [2, 10] step=1 | WORKING_ASSUMPTION | 13 candidates identified |
| **WA-04** | EXP-05 Block S seed set [42, 7, 123, 2024, 1729] | WORKING_ASSUMPTION | 5 seeds |
| **WA-05** | EXP-05 Block N sigma grid [0, 0.01, 0.05] | WORKING_ASSUMPTION | 3 sigma values |
| **WA-06** | EXP-05 Block N perturbation distribution | Gaussian | WORKING_ASSUMPTION |
| **WA-07** | WCSS convention (arithmetic centroid from hard labels) | WORKING_ASSUMPTION | EXP-01 plan §4.2 |
| **WA-08** | Noise exclusion (DBSCAN -1 excluded from metrics) | WORKING_ASSUMPTION | sklearn-aligned |

These are accepted as working defaults. They may be revised via a new ADR.

---

## 4. Deferred Decisions (resolved in EPIC-08 plan)

| ID | Decision | Deferred to | Reason |
|---|---|---|---|
| **EPIC08-ARI** | ARI/AMI computation method | EPIC-08 plan | Implementation detail |
| **EPIC08-STAT** | Statistical test (paired t-test vs Wilcoxon) | EPIC-08 plan | Implementation detail |
| **EPIC08-CI** | Confidence interval method (bootstrap vs percentile) | EPIC-08 plan | Implementation detail |
| **EPIC08-RUNTIME** | Runtime comparison protocol | EPIC-08 plan | Implementation detail |
| **EPIC08-CONFIG** | Use EXP-01 defaults vs EXP-03 selections | EPIC-08 plan | Plan-level decision |
| **EPIC08-VIZ** | Visualization scope | EPIC-08 plan | Implementation detail |

---

## 5. Limitations (explicit, accepted)

| ID | Limitation | Documented in | Notes |
|---|---|---|---|
| **LIM-01** | RFM-only vs RFM Extended comparison NOT evaluated | ADR-0004, RFM_ONLY_FUTURE_WORK_PLAN.md | RQ2 reformulated; future work |
| **LIM-02** | K-Medoids not in benchmark | ADR-0003 | OUT OF SCOPE |
| **LIM-03** | EXP-04 preprocessing sensitivity on K-Means only | EXP-04 review | Not cross-algorithm |
| **LIM-04** | EXP-04 preprocessing sensitivity on K=4 only | EXP-04 review | Not K-sweep |
| **LIM-05** | EXP-04 log1p NOT included | EXP-04 review | Not full-matrix comparable |
| **LIM-06** | EXP-05 Block S only 3 algorithms (deterministic excluded) | EXP-05 review | By design |
| **LIM-07** | DBSCAN noise ratio 0.7268 at baseline | EXP-01 review | Per-algorithm characteristic |
| **LIM-08** | C0 silhouette = 0.9465 (raw data artifact) | EXP-04 review | Un-standardized data |
| **LIM-09** | Agglomerative CH=77.15 at K=3 linkage=average | EXP-03 review | Chaining artifact; WORKING_SELECTED |
| **LIM-10** | FCM m=1.5 close to K-Means limit (m=1) | EXP-03 review | WORKING_SELECTED |
| **LIM-11** | No "best/winner/optimal/recommended/final" claims allowed | AGENTS.md §2.5 | Always |

---

## 6. Rerun Impact

| Decision changed? | Existing artifact affected? | Rerun required? | Experiments |
|---|---|---|---|
| Algorithm scope → K-Medoids OUT | No (K-Medoids was never run) | NO | None |
| RQ definitions → reformulated | No | NO | None |
| RFM-only → future work | No | NO | None |
| FE-06 dataset status → RESEARCH_WORKING_BASELINE | No (status label only) | NO | None |
| EPIC-08 input → final_clustering_dataset.parquet | No (no code change) | NO | None |
| Preprocessing config change | Yes | YES | All EXP |
| Feature set change | Yes | YES | All EXP |
| K range change | Yes | YES | EXP-02, EPIC-08 |
| EXP-03 selection protocol change | Yes | YES | EXP-03 |
| EXP-05 seed/sigma change | Yes | YES | EXP-05 |

**Conclusion:** No rerun required for any locked decision. No existing artifact SHA changes.

---

## 7. EPIC-08 Blockers

### CAN START EPIC-08 PLAN?

**YES** — All required methodology is locked:
- ✅ Algorithm scope locked (5 algorithms, ADR-0003)
- ✅ RQ1/RQ2/RQ3 locked (ADR-0004)
- ✅ EPIC-08 input locked (`final_clustering_dataset.parquet`)
- ✅ No HIGH methodology decision remains open

### CAN START EPIC-08 IMPLEMENTATION?

**YES** — Phase A can start immediately:
- ✅ ARI/AMI computation (using sklearn.metrics)
- ✅ Hungarian matching (using scipy.optimize.linear_sum_assignment)
- ✅ Statistical tests (scipy.stats.ttest_rel, wilcoxon)
- ✅ Confidence intervals (bootstrap or percentile)
- ✅ Runtime comparison
- ✅ Cluster-size consistency analysis
- ✅ Diagnostic visualizations

### REMAINING BLOCKERS

None for Phase A.

For Phase B (cross-algorithm ranking, "most stable" claims):
- ⚠️ EPIC08-CROSS-ALG-01: Cross-algorithm ranking allowed? (AGENTS.md §2.5)
- ⚠️ EPIC08-CLAIM-01: "Most stable algorithm" claim allowed?

These are mentor decisions, not technical blockers.

---

## 8. Decisions Explicitly NOT Locked

The following are intentionally left as open decisions for EPIC-08 plan or future phases:

| Decision | Reason not locked |
|---|---|
| K-Medoids implementation | OUT OF SCOPE (ADR-0003); can be revisited in future phase |
| RFM-only materialization | Future work; reformulated RQ2 is answerable without it |
| Cross-algorithm ranking | AGENTS.md §2.5 restriction; requires mentor decision |
| "Most stable algorithm" claim | AGENTS.md §2.5 restriction; requires mentor decision |
| Business interpretation / profiling | EPIC-09 scope |
| Segment naming | EPIC-09 scope |
| External validation | Not applicable (unsupervised) |

---

## 9. Files Created or Modified

### Created

| File | Description |
|---|---|
| `docs/decisions/0003-algorithm-scope.md` | ADR-0003: K-Medoids OUT OF SCOPE |
| `docs/decisions/0004-research-questions.md` | ADR-0004: RQ1, RQ2, RQ3 definitions |
| `docs/methodology/research_questions.md` | Official RQ definitions |
| `docs/methodology/methodology_overview.md` | Study design and benchmarking protocol |
| `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md` | RFM-only materialization checklist |
| `docs/research/review/METHODOLOGY_LOCK_STATUS.md` | This file |
| `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` | Updated: RESOLVED status |

### Modified

| File | Change |
|---|---|
| `README.md` | Updated pipeline diagram: 5 algorithms, EPIC-08 pending, K-Medoids OUT OF SCOPE |
| `AGENTS.md` §2.1 | Updated benchmark algorithms list (removed K-Medoids, added GMM, FCM) |
| `docs/research/FE05_Customer_Feature_Engineering.md` | 3 replacements: "4 algorithms" → "5 algorithms" + K-Medoids OUT OF SCOPE |
| `docs/research/FE06_Transformation_Final_Dataset.md` | 5 replacements: "4 thuật toán" → "5 algorithms" + K-Medoids OUT OF SCOPE |
| `configs/clustering.yaml` | `kmedoids: enabled: false` with ADR reference |
| `src/customer_segmentation/clustering/kmedoids.py` | Updated docstring: OUT OF SCOPE per ADR-0003 |
| `docs/methodology/README.md` | Updated: replaced TODO placeholders with actual documents |

### Not Modified (verified no contradiction)

- `docs/research/EXP01_EXP05_REVIEW_OVERVIEW.md` — already consistent (5 algorithms)
- `docs/research/EXP01_EXP02_RESULTS_REVIEW.md` — already consistent
- `docs/research/EXP03_HYPERPARAMETER_REVIEW.md` — already consistent
- `docs/research/EXP04_PREPROCESSING_FEATURE_REVIEW.md` — already consistent
- `docs/research/EXP05_REPRODUCIBILITY_STABILITY_REVIEW.md` — already consistent
- `docs/decisions/0001-*.md` and `0002-*.md` — dataset ADRs, unaffected
- All experiment reports in `reports/exp*/` — unchanged

---

## 10. ADR Chain

| ADR | Title | Status |
|---|---|---|
| ADR-0001 | Primary dataset = UCI Online Retail | Accepted |
| ADR-0002 | Backup dataset = UCI Online Retail II | Accepted |
| ADR-0003 | Algorithm scope = 5 algorithms (K-Medoids OUT OF SCOPE) | Accepted |
| ADR-0004 | Research Questions RQ1, RQ2, RQ3 definitions | Accepted |

---

**METHODOLOGY_LOCK_STATUS: RESOLVED**

**Date:** 2026-09-22
**Auditor:** AI Agent (read-only resolution + documentation update)
**No code implementation. No experiment execution. No commit. No push. No PR.**
