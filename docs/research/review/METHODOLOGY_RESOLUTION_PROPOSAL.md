# METHODOLOGY RESOLUTION PROPOSAL — Pre-EPIC-08 Methodology Lock

> **STATUS: RESOLVED** — All HIGH-severity decisions have been locked.
> This document was the analysis and proposal. The resolution is recorded in:
> - `docs/research/review/METHODOLOGY_LOCK_STATUS.md` (locked decisions, rerun impact, EPIC-08 blockers)
> - `docs/decisions/0003-algorithm-scope.md` (ADR-0003)
> - `docs/decisions/0004-research-questions.md` (ADR-0004)
> - `docs/methodology/research_questions.md` (official RQ definitions)
> - `docs/methodology/methodology_overview.md` (study design and protocol)
>
> **Ngôn ngữ:** tiếng Việt. Code/identifier/file name: tiếng Anh theo convention hiện tại.
> **Ngày tạo proposal:** 2026-09-22
> **Ngày resolution:** 2026-09-22
> **Auditor:** AI Agent — read-only analysis + documentation update (no implementation, no rerun, no commit)
>
> **HISTORY:** This document was the ANALYSIS phase. The METHODOLOGY LOCK phase has been executed and is recorded in `METHODOLOGY_LOCK_STATUS.md`.

---

## 1. Executive Summary (from analysis phase)

### 1.1. Trạng thái methodology tại audit time

| Trục | Trạng thái |
|---|---|
| Engineering implementation | 🟢 READY (1105 tests pass, all SHAs verified) |
| Research evidence | 🟢 READY (185 runs SUCCESS, SHA chain intact) |
| Methodology documentation | 🔴 **PARTIAL** — `docs/methodology/` chỉ có README placeholder; ADRs chỉ cover dataset selection |
| Algorithm scope claim | 🔴 **INCONSISTENT** — AGENTS.md / README.md / FE-06 / FE-05 doc claim "4 fixed algorithms (K-Means, K-Medoids, Agglomerative, DBSCAN)" nhưng implementation chỉ có **5 algorithms** (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means); K-Medoids là `NotImplementedError` placeholder |
| RQ definitions | 🔴 **INFERRED** — RQ1/RQ2/RQ3 mapping from experiment plans, không có official methodology docs |
| Pending decisions | 🟡 ~60+ PENDING_REVIEW / WORKING_ASSUMPTION / DEFERRED |
| FE-06 dataset status | 🟡 `TECHNICALLY_GENERATED`, chưa promote thành `RESEARCH_APPROVED_FINAL` |
| EPIC-08 readiness | 🟡 CONDITIONAL — engineering + evidence ready, methodology not yet finalized |

### 1.2. 3 HIGH-severity methodology decisions

| ID | Decision | Severity | Status |
|---|---|---|---|
| **D-KMED-1** | K-Medoids implementation vs documentation update | 🔴 HIGH | Open — affects algorithm scope claim |
| **L-RQ-1** | Official RQ definitions (RQ1/RQ2/RQ3) | 🔴 HIGH | Open — affects whole thesis mapping |
| **EXP04-FS-01** | RFM-only artifact materialization | 🔴 HIGH | DEFERRED — blocks RQ2 evaluation |

### 1.3. Key findings

1. **"Best 4 algorithms" claim trong docs không match implementation thực tế** (đã chạy 5 algorithms, K-Medoids là placeholder). Documentation drift này phải resolve TRƯỚC khi EPIC-08 — vì mọi "cross-algorithm" comparison sẽ bị câu hỏi "tại sao thiếu K-Medoids?"
2. **RFM-only cần ADR trước khi quyết định có materialize hay không.** Nếu KHÔNG materialize, phải ghi rõ RQ2 limitation trong các paper/thesis sections.
3. **~60+ pending decisions có thể phân loại thành 4 nhóm** — không phải tất cả đều cần Mentor quyết trước EPIC-08.
4. **Minimum methodology lock** để EPIC-08 Phase A chạy đúng là **~5 quyết định** (không phải 25+), được identify ở §8.

### 1.4. Recommendation summary

| Phương án | Mức độ ưu tiên | Effort | Risk |
|---|---|---|---|
| **Option B for K-Medoids:** Update docs to reflect 5-algorithm scope (no K-Medoids) | 🔴 HIGH priority | LOW (no rerun required) | LOW |
| **RQ definitions:** Write `docs/methodology/TODO_research_questions.md` (real content) + ADR | 🔴 HIGH priority | LOW-MEDIUM | LOW |
| **RFM-only:** Option C — ghi rõ RQ2 limitation; chưa materialize | 🟡 MEDIUM priority | LOW | MEDIUM (RQ2 PARTIAL forever) |
| **Aggregate other pending decisions** thành EPIC-08 plan + ADR | 🟡 MEDIUM priority | MEDIUM | LOW |

---

## 2. Current Methodology State

### 2.1. Verified engineering state

| Item | Status | Evidence |
|---|---|---|
| `pytest tests/` | 🟢 1105/1105 PASS | test session 2026-09-22 |
| `ruff check .` | 🟢 PASS | 0 errors |
| `black --check .` | 🟢 PASS | 155 files unchanged |
| Input SHA chain | 🟢 Verified (raw → candidates → final matrix) | sha256sum all match documented |
| Algorithm adapters registered | 🟢 5 algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) | `AlgorithmRegistry.list_registered()` |
| Clustering artifacts | 🟢 EXP-01 to EXP-05: 185 runs, all SUCCESS | `experiment_log_*.json`, manifests |
| EXP-05 labels artifact | 🟢 327,825 rows × 9 cols, 75 unique run_ids | `exp05_cluster_labels.parquet` |

### 2.2. Verified research evidence state

| Experiment | Runs | Status | Notes |
|---|---|---|---|
| EXP-01 (Baseline) | 5 | TECHNICALLY_IMPLEMENTED | 5 algorithms × 1 working default |
| EXP-02 (K-sweep) | 37 | TECHNICALLY_IMPLEMENTED | 13 candidates via heuristic |
| EXP-03 (Hyperparameter) | 38 | TECHNICALLY_IMPLEMENTED | All WORKING_SELECTED / TIED |
| EXP-04 (Preprocessing) | 30 | TECHNICALLY_IMPLEMENTED | Family A DEFERRED |
| EXP-05 (Reproducibility) | 75 | TECHNICALLY_IMPLEMENTED | Raw evidence only (no ARI/AMI yet) |
| **Tổng** | **185** | TECHNICALLY_IMPLEMENTED | |

### 2.3. Methodology documentation state

| Doc | Trạng thái | Last meaningful update |
|---|---|---|
| `docs/methodology/README.md` | 🔴 Only mentions TODO placeholders | n/a |
| `docs/methodology/TODO_research_questions.md` | 🔴 Does not exist (placeholder only) | n/a |
| `docs/methodology/TODO_methodology_overview.md` | 🔴 Does not exist (placeholder only) | n/a |
| `docs/methodology/TODO_unit_of_analysis.md` | 🔴 Does not exist (placeholder only) | n/a |
| `docs/decisions/0001-primary-dataset-uci-online-retail.md` | 🟢 Accepted (DS-05) | 2026-09-18 |
| `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md` | 🟢 Accepted (DS-05) | 2026-09-18 |
| `docs/decisions/0003+` (methodology ADRs) | 🔴 Does not exist | n/a |
| `AGENTS.md` (rules) | 🟢 Comprehensive cross-phase rules | multiple updates |
| `README.md` | 🟡 Claims 4 algorithms — INCONSISTENT | initial commit |
| `FE-06 doc` | 🟡 Claims 4 algorithms — INCONSISTENT | 2026-09-20 |
| `EPIC-06 documentation contract` | 🟢 Actually describes 6 algorithms | recent |

**Key inconsistency:** AGENTS.md §3, README.md §1, FE-06 doc §1.5 & §16 all say "bốn thuật toán benchmark cố định (K-Means, K-Medoids, Agglomerative, DBSCAN)". BUT `EPIC-06 documentation contract` defines the ML-06 algorithms as 6 (K-Means, K-Medoids placeholder, Agglomerative, DBSCAN, GMM, FCM). AND `EXP-01 → EXP-05` actually ran 5 algorithms.

**Discrepancy path:**
- AGENTS.md + FE-06 doc + README.md: mention **4** algorithms including K-Medoids
- EPIC-06: added GMM and FCM (so technically **6** adapters planned, but K-Medoids placeholder)
- Implementation: 5 actual working adapters (K-Means, Agglo, DBSCAN, GMM, FCM)
- Experiments: ran 5 algorithms

### 2.4. Decision status taxonomy across repo

| Status | Count (xấp xỉ) | Meaning |
|---|---|---|
| `TECHNICALLY_IMPLEMENTED` | ~15 | Engineering done, methodology acceptable |
| `WORKING_ASSUMPTION` | ~17 | Working default, not methodology-approved |
| `PENDING_REVIEW` | ~25 | Need decision, can proceed |
| `TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING` | 2 | Protocol gave an answer, but the answer is contested |
| `DEFERRED` | 1 (Family A) | Blocked on external ADR |

---

## 3. K-Medoids Decision (DECISION A)

### 3.1. Evidence collected

| Source | Claim | Reality |
|---|---|---|
| `README.md` §1 | "K-Means, K-Medoids, Agglomerative, DBSCAN" | Stale |
| `AGENTS.md` §3 | "K-Means, K-Medoids, Agglomerative Clustering, DBSCAN" | Stale |
| `docs/research/FE06_Transformation_Final_Dataset.md` §1.5, §16 | "K-Means, K-Medoids, Agglomerative, DBSCAN — bốn thuật toán benchmark cố định" | Stale |
| `docs/research/FE05_Customer_Feature_Engineering.md` §11.3 | Same as above | Stale |
| `configs/clustering.yaml` | Lists `kmedoids: enabled: true, k_range: [2..10], metric: "TODO", init: "TODO"` | Placeholder config |
| `src/customer_segmentation/clustering/kmedoids.py` | `raise NotImplementedError("fit_kmedoids is not implemented yet.")` | Placeholder code |
| `src/customer_segmentation/clustering/registry.py` | AlgorithmRegistry | K-Medoids NOT registered (verified) |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | Mentions ML-02, ML-03, ML-04, ML-05, ML-06 = 6 adapters total | Original plan included K-Medoids; later scope expanded |
| ML-02..ML-06 working docs | Document 5 working algorithms (no K-Medoids) | Mismatch with AGENTS.md |
| EXP-01..EXP-05 | Ran 5 algorithms (no K-Medoids) | Concrete evidence of actual scope |

**Decision evidence:**
- README.md / AGENTS.md / FE-05 / FE-06 docs explicitly mention K-Medoids as a fixed benchmark algorithm.
- K-Medoids file exists but only `raise NotImplementedError(...)` — no actual implementation.
- `configs/clustering.yaml` has `kmedoids: enabled: true` but with `metric: "TODO"` and `init: "TODO"`.
- `AlgorithmRegistry` does NOT register K-Medoids.
- EXP-01..EXP-05 ran exactly 5 algorithms (no K-Medoids in any artifact).
- 185 runs across 5 EXP — all SUCCESS.
- Current repo metadata DOES NOT formally deprecate K-Medoids anywhere.
- The "4 vs 5 vs 6" algorithm count is inconsistent across docs.

### 3.2. Phân tích Option A — Implement K-Medoids + add to benchmark

**Implementation requirements:**

| Aspect | Detail |
|---|---|
| Dependency | Add `scikit-learn-extra` (K-Medoids lives outside sklearn core). Verify `pyproject.toml` + `requirements.txt` aligned. |
| Implementation | Implement `KMedoidsAdapter(BaseClusterAlgorithm)` in `src/customer_segmentation/clustering/kmedoids.py` — fit/predict, supports_random_state, integration with metrics & artifacts |
| Registration | Decorate with `@AlgorithmRegistry.register("kmedoids")` |
| Tests | Add `tests/test_ml07_kmedoids.py` (mirror test_ml02_kmeans.py) — minimum ~15-20 tests |
| Config | Update `configs/clustering.yaml`: replace `metric: "TODO"` + `init: "TODO"` with concrete values (working default: euclidean, random) |
| EPIC-06 docs | Need minor update: align K-Medoids placeholder to working scope |
| FE-05 / FE-06 docs | Need minor update: 4-algorithm mention → 5-algorithm (or 6 if including K-Medoids) |

**Experimental rerun cost (per experiment):**

| Experiment | Impact | Rerun if Option A | Notes |
|---|---|---|---|
| EXP-01 | Add 1 algorithm (K-Medoids) to baseline | +1 run per seed | ~6 runs total (5+1) × n_repeat=5 |
| EXP-02 | Add K-sweep for K-Medoids (K ∈ 2..10) | +9 runs | Comparable to other algorithms |
| EXP-03 | Add K-Medoids Stage A/B/C | ~+15-20 runs | Stage A=1, Stage B=sweep (metric, init), Stage C=K×init |
| EXP-04 | Add K-Medoids to controlled preprocessing test | +30 runs (6 scenarios × 5 repeats) | OR keep K-Means only |
| EXP-05 | Add K-Medoids to Block R, Block N (deterministic algorithms) | +5 runs Block R + ~8 runs Block N | Block S excludes (K-Medoids random_state support needs decision) |

**Approximate total runs added:** **~70-90 runs** (depending on EXP-04 / EXP-05 scope decisions).

**Research timeline cost:** medium (1-2 weeks) for implementation + tests + rerun + new analysis reports.

**Reproducibility impact:**
- All new runs need new SHA chain.
- New `cluster_labels_EXP-0X-kmedoids_*.parquet` artifacts added.
- New `experiment_log_*-kmedoids_*.json` artifacts added.
- Final cluster count goes from 5 to 6 algorithms in all cross-experiment tables.

**Methodological impact:**
- Algorithm scope officially becomes "6 algorithms", matching EPIC-06's actual scope.
- "Cross-algorithm ranking" / "best algorithm" claims must wait for full evaluation including K-Medoids.
- Decision status changes: K-Medoids placeholder → `TECHNICALLY_IMPLEMENTED` after EXP-01..05 rerun.

**Engineering impact:**
- Need ADR for `scikit-learn-extra` dependency.
- Need to update `pyproject.toml` + `requirements.txt` (per AGENTS.md §5 — adding new dep requires ADR).
- Tests must mirror ML-02..ML-06 coverage.

**Research risk:**
- K-Medoids on customer segmentation context: well-known algorithm, expected results. Probably won't change RQ1 conclusion dramatically.
- But might affect EXP-03 selection protocol (depending on how algorithm compares).
- Might affect EXP-05 stability (K-Medoids random_state support depends on implementation).

### 3.3. Phân tích Option B — Update docs to 5-algorithm scope (no K-Medoids)

**Files to update (verified, not modified):**

| File | Change required |
|---|---|
| `README.md` §1 | "clustering (K-Means, K-Medoids, Agglomerative, DBSCAN)" → "clustering (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means)" |
| `AGENTS.md` §3 table | Update Stage row for Clustering; remove "K-Medoids" mention from §3 / §9 if applicable |
| `docs/research/FE06_Transformation_Final_Dataset.md` §1.5, §11.3, §13, §15, §16 | "4 thuật toán" → "5 thuật toán"; "K-Medoids" → "K-Medoids (deferred — out of current scope)" |
| `docs/research/FE05_Customer_Feature_Engineering.md` §11.3, §15 | Same as FE-06 |
| `configs/clustering.yaml` | Mark `kmedoids: enabled: false` with comment "DEFERRED — out of EPIC-06 v1 scope; see ADR-000X" |
| `src/customer_segmentation/clustering/kmedoids.py` | Update docstring to "OUT OF SCOPE — see ADR-000X" rather than "TODO: implement" |
| `docs/research/ML01_Clustering_Experiment_Framework.md` | Update algorithm count references (if any "4 algorithms" claim) |
| New ADR | `docs/decisions/0003-kmedoids-deferred.md` (or numbered appropriately) — documents the scope decision |

**Files verified DOES NOT need updates:**
- `docs/research/EXP01_EXP05_*.md` — already use "5 algorithms" language consistently
- `docs/research/FE-04_Customer_Level_Aggregation.md` — refers to "4 algorithms" in some preamble; need check
- `notebooks/` — only exploratory, not regulatory

**Experimental impact:**
- **Zero.** No rerun required. EXP-01..05 already ran 5 algorithms without K-Medoids.

**Reproducibility impact:**
- **Zero.** All SHAs unchanged, all artifacts unchanged.

**Methodological impact:**
- Algorithm scope officially becomes "5 algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means)".
- K-Medoids explicitly deferred with ADR — explains why some docs disagree.
- RQ1 / RQ2 / RQ3 must be re-evaluated to ensure they don't assume K-Medoids.
- EPIC-08 evaluation runs on 5 algorithms.

**Engineering impact:**
- Low — only documentation updates + new ADR.
- No new dependency.
- No new tests required.
- K-Medoids file can be retained as "deferred / out of scope" or removed (decision).

**Research risk:**
- LOW. Mentor's algorithm choice becomes explicit in ADR.
- K-Medoids could be added in future phase (EPIC-X) without disrupting current work.
- Risk of reviewer confusion addressed by explicit ADR.

### 3.4. So sánh impact

| Dimension | Option A (Implement) | Option B (Document) |
|---|---|---|
| Engineering effort | HIGH (impl + tests + ADR) | LOW (doc update + ADR) |
| Experimental rerun | HIGH (~70-90 runs) | NONE |
| Reproducibility audit | Re-verify SHAs after rerun | No change |
| Documentation effort | MEDIUM | MEDIUM (multiple files) |
| Research timeline | +1-2 weeks | +2-3 days |
| Risk to current research | MEDIUM (rerun might shift some claims) | LOW (no rerun) |
| Methodology cleanliness | MEDIUM (delays RQ conclusions until K-Medoids included) | HIGH (clean algorithm scope immediately) |
| Future flexibility | HIGH (algorithm count stable at 6) | HIGH (can add K-Medoids later) |

### 3.5. Recommendation

**Recommended: Option B — Update docs to 5-algorithm scope.**

**Rationale:**
1. Current evidence (185 runs, 5 algorithms) ALREADY reflects 5-algorithm scope. Option B aligns documentation with evidence.
2. Rerun cost of Option A is significant (~70-90 runs) with no clear research benefit at this stage.
3. K-Medoids can be added in a future phase without disrupting existing artifacts (SHA chain would extend, not break).
4. Methodology cleanliness benefit: explicit ADR + clean docs = less reviewer confusion.
5. Aligns with EPIC-08's "Phase A only" recommendation from prior audit (avoid scope creep).
6. Document all 5 modifications in a single ADR (e.g., `docs/decisions/0003-algorithm-scope-5-algorithms.md`).

**Option A is preferable IF:** Mentor has a specific research claim that requires K-Medoids in the current benchmark (e.g., comparison with K-Medoids is essential to RQ1). Otherwise, Option B is cleaner.

### 3.6. Action items (if Option B approved)

1. Update `README.md` §1 to reflect 5 algorithms.
2. Update `AGENTS.md` §3 / §9 to reflect 5 algorithms.
3. Update `docs/research/FE05_*.md` and `FE06_*.md`.
4. Update `configs/clustering.yaml`: `kmedoids: enabled: false` (with ADR reference).
5. Update `src/customer_segmentation/clustering/kmedoids.py` docstring.
6. Write `docs/decisions/0003-algorithm-scope.md` documenting the decision.
7. NO code change required — just docs.
8. NO rerun required.
9. NO SHA change.

---

## 4. Official Research Questions (DECISION B)

### 4.1. Evidence collected — RQ mapping from repo

| Source | Inferred RQ | Confidence |
|---|---|---|
| Review overview §2 | RQ1: algorithm × K × preprocessing × hyperparameter | HIGH |
| EXP-04 review §2 | RQ2: RFM-only vs RFM Extended feature representation | HIGH |
| EXP-05 review §1 | RQ3: reproducibility / seed sensitivity / robustness | HIGH (but ambiguous — RQ3 might instead be "business interpretation") |
| EXP-01 baseline §A | All RQs need internal metrics baseline | HIGH |
| EPIC-06 contract §7.3-7.4 | EPIC-09 (profiling) inherits from clustering phase | N/A for RQ1/RQ2 |
| AGENTS.md §2.1 | "research questions in `docs/methodology/`", "unit of analysis", "benchmarking protocol" | Specifies the format, not the content |
| README.md §1 | "follows a fixed multi-stage pipeline" + "research methodology" in `docs/methodology/` | Generic |

### 4.2. Reconstructed research logic

From FE-01 → FE-06 → EPIC-06 → EXP-01 → EXP-05 progression:

```
Customer segmentation problem (general)
    ↓
Q1: How do different clustering algorithms compare on this problem?
    (algorithm × K × preprocessing × hyperparameter)
    ↓
Q2: Does feature representation matter? (RFM-only vs RFM Extended)
    ↓
Q3: How stable and reproducible are the segmentations?
    (reproducibility, seed sensitivity, perturbation robustness)
    ↓
Q4 (out of EXP scope): What are the customer characteristics per segment?
    (profiling / business interpretation — EPIC-09+ owns)
```

So inferred RQ1/RQ2/RQ3 map to Q1/Q2/Q3 above. Q4 is scope of EPIC-09 / EPIC-10.

### 4.3. Draft RQ1 (algorithm comparison)

#### RQ1 — Cross-algorithm comparison under controlled conditions

> **RQ1 question:** "How do different clustering algorithms perform on customer-level behavioral feature spaces derived from retail transactional data, under controlled experimental conditions?"

**Definitions required:**

| Dimension | Definition | Current evidence |
|---|---|---|
| **Population / unit of analysis** | Customer-level (one customer = one observation). Each customer is identified by `CustomerID` and represented by a feature vector in `R^14` (14 features). | ✅ Documented in FE-04, FE-05, FE-06 |
| **Dataset** | `data/raw/primary/Online Retail.xlsx` (DS-05 primary) processed through FE-01 → FE-06 pipeline. Result: `final_clustering_dataset.parquet` (4,371 × 14). SHA-256: `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` (FE06-v1.0) | ✅ Verified |
| **Feature representation** | RFM Extended = 14 features: Recency, Frequency, Monetary, TotalQuantity, AverageQuantity, BasketSize, TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays, AverageInvoiceValue, ProductsPerInvoice, CancellationRate, ReturnRate | ⚠️ 6/14 features at `ELIGIBLE_WORKING_ASSUMPTION` (Frequency, AverageQuantity, BasketSize, ActiveDays, CancellationRate, ReturnRate) |
| **Preprocessing** | Median imputation + Yeo-Johnson transformation + RobustScaler (FE-06 C7 = `WORKING_ASSUMPTION`) | ⚠️ C7 `WORKING_ASSUMPTION`, not yet promoted |
| **Algorithm scope** | 5 algorithms registered: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means (per Option B in §3); K-Medoids deferred to ADR-0003 | 🟡 Decision in §3 |
| **Hyperparameter treatment** | EXP-03 sensitivity exploration; per-algorithm working selection via silhouette-primary → DBI → CH protocol; status = `WORKING_SELECTED` (not final) | ⚠️ Protocol is `WORKING_ASSUMPTION` |
| **Cluster-count treatment (K)** | EXP-02 sweep K ∈ [2, 10] step=1 (WORKING_ASSUMPTION); 13 candidates via deterministic heuristic; multiple K per algorithm; no claim of "best K" | ⚠️ K range `WORKING_ASSUMPTION` |
| **Quality metrics** | Internal metrics only: silhouette, DBI, CH, WCSS. External metrics (business interpretation) deferred to EPIC-09. | ✅ Documented in EXP-01 plan §4; metrics correctly implemented |
| **Runtime** | Algorithm execution only (excludes metric computation, artifact writing). n_repeat=5 for variance estimation. | ✅ Documented in EXP-01 plan §3 |
| **Reproducibility** | Verified at EXP-05 Block R (5/5 algorithms reproducible with seed=42). | ✅ Verified |
| **Stability** | EXP-05 Block S (K-Means, GMM, FCM × 5 seeds) + Block N (5 algorithms × 2 sigma × 3 perturbation seeds). ARI/AMI computation deferred to EPIC-08. | 🟡 Raw evidence exists; analysis deferred |
| **Interpretation boundary** | NO claim of "best algorithm" / "winner" / "optimal" / "recommended" / "final". Cross-algorithm comparison allowed ONLY in form of evidence + caveats. Composite scores FORBIDDEN. Per-algorithm WORKING_SELECTED status may be reported with EPIC-08 cross-validation. | 🟡 Per AGENTS.md §2.5; per-algorithm selections in `WORKING_SELECTED` status; cross-algorithm deferred |

**RQ1 status:** Evidence is sufficient for partial answer. Full answer (including "ranked" claim) requires EPIC-08 cross-validation + Mentor approval.

#### RQ1.bis (alternative formulation, if research emphasizes methodology over comparison)

> **RQ1.alt — Methodology benchmarking**
> "Within a fixed preprocessing pipeline and feature representation, what is the relative clustering quality of N candidate algorithms, as measured by internal metrics, and how stable are these results across hyperparameters and random initialization?"

Same as RQ1 but explicitly framed as methodology comparison (with EPIC-08 cross-validation producing relative evidence, not a winner).

### 4.4. Draft RQ2 (feature representation)

#### RQ2 — Feature set sensitivity

> **RQ2 question:** "Does including extended behavioral features (RFM Extended, 14 features) improve clustering quality compared to using only the RFM core features (Recency, Frequency, Monetary)?"

**Definitions required:**

| Dimension | Definition | Current evidence |
|---|---|---|
| **RFM-only definition** | Subset of FE-06 final matrix: only `Recency`, `Frequency`, `Monetary`. Apply same preprocessing (median, Yeo-Johnson, RobustScaler) to these 3 columns only. Output artifact: `final_clustering_dataset_rfmonly.parquet` (4,371 × 3). | 🔴 NOT materialized — Family A EXP-04 DEFERRED |
| **RFM Extended definition** | All 14 features from FE-06 final matrix (current state). | ✅ Materialized |
| **Preprocessing control** | Same pipeline applied to RFM-only and RFM Extended. Same imputation/transformation/scaling parameters (FE-06 C7 baseline). | 🔴 EXP-04 Family A requires same controlled references as Family B (K-Means, K=4, median, seed=42) |
| **Algorithm control** | K-Means only (CONTROLLED_REFERENCE_ALGORITHM). Per EXP-04-ALG-01 PENDING_REVIEW, K-Means is current reference. Other algorithms could be added but EXP-04-v1 doesn't expand. | ⚠️ PENDING_REVIEW |
| **K control** | K=4 (CONTROLLED_REFERENCE_K) for primary comparison. Secondary: K candidates from EXP-02. | ⚠️ EXP-04-K-01 PENDING_REVIEW |
| **Evaluation metrics** | Silhouette, DBI, CH, WCSS (consistent with Family B). Optional: ARI/AMI between RFM-only and RFM Extended clusterings for same customer set (sanity check that cluster structures differ). | 🔴 Same metrics available; ARI/AMI needs implementation in EXP-04 Family A or EPIC-08 |
| **Stability** | Optional: EXP-05-style reproducibility/stability for RFM-only artifact (Block R/S/N). | 🔴 Materialization required |
| **Comparison protocol** | Per-feature-subset comparison of metrics; controlled references identical. NO claim of "best feature set". Document scenarios as `CANDIDATE_SCENARIO` per EXP-04 taxonomy. | 🟡 EXP-04-CONCL-01 PENDING_REVIEW; no promotion to "best" |

**RQ2 status:** 🔴 PARTIAL — Family A DEFERRED. Evidence sufficient for Family B (preprocessing sensitivity) but not Family A (feature set sensitivity).

### 4.5. Draft RQ3

#### Option 1 — RQ3 = Stability / Reproducibility

> **RQ3 question:** "How reproducible and how robust are the clusterings produced by each algorithm under different seeds and feature-space perturbations?"

**Definitions required:**

| Dimension | Definition | Current evidence |
|---|---|---|
| **Reproducibility (Block R)** | EXP-05 Block R: same seed → identical labels_hash. Verified for all 5 algorithms. | ✅ Verified |
| **Seed stability (Block S)** | EXP-05 Block S: K-Means, GMM, FCM × 5 seeds (K-Means, GMM, FCM support random_state; Agglo, DBSCAN deterministic). | ✅ Evidence collected; ARI/AMI computation deferred to EPIC-08 |
| **Perturbation robustness (Block N)** | EXP-05 Block N: in-memory Gaussian noise, sigma = [0, 0.01, 0.05] × std. | ✅ Evidence collected |
| **Stability metrics (deferred)** | ARI (Adjusted Rand Index), AMI (Adjusted Mutual Information), Hungarian matching, cluster-size consistency across blocks. To be computed in EPIC-08. | 🟡 NOT computed yet |
| **Statistical tests** | Paired t-test / Wilcoxon across seeds (if normality holds). Bootstrap CI for stability estimation. | 🟡 EPIC-08 owned |
| **Per-algorithm scope** | All 5 algorithms (or per-algorithm stability report) | 🟡 Block S only on 3 algorithms — protocol decision needed |

**RQ3 status:** Evidence sufficient for raw stability; full stability analysis needs EPIC-08.

#### Option 2 — RQ3 = Business interpretation (preferred from thesis perspective)

> **RQ3 question:** "What are the customer characteristics and behavioral profiles of each cluster identified by the chosen algorithm, and how can these clusters be interpreted in a business context?"

This would be EPIC-09 owned. Might better belong OUTSIDE RQ1/RQ2/RQ3 framework, or as RQ4.

**RECOMMENDATION:** Treat RQ3 = stability. Q4 (business interpretation) belongs to EPIC-09 separately.

### 4.6. RQ vs current evidence matrix

| RQ | Current evidence | Missing evidence | Can answer now? | Required future work |
|---|---|---|---|---|
| **RQ1** (algorithm comparison) | EXP-01 baseline metrics (silhouette/DBI/CH/WCSS) for 5 algorithms × K=4; EXP-02 K-sweep (37 runs); EXP-03 hyperparameter sensitivity (38 runs); EXP-05 raw reproducibility evidence | Internal stability (ARI/AMI), runtime statistical comparison, cross-algorithm compound analysis (silhouette + ARI), protocol-validated hyperparameter selections | 🟡 **PARTIAL** — can describe evidence + caveats; cannot make "best/winner" claim | EPIC-08 cross-algorithm analysis with ARI/AMI + statistical tests + CI; EPIC-08 protocol for ranking evidence |
| **RQ2** (feature representation) | Family B only (6 preprocessing scenarios × K-Means K=4); Family A NOT executed | RFM-only artifact, Family A scenarios, cross-subset clustering comparison | 🔴 **PARTIAL** — only preprocessing sensitivity available; feature set sensitivity NOT evaluable | Materialize RFM-only artifact + EXP-04 Family A execution, OR explicitly mark RQ2 PARTIAL with documented limitation |
| **RQ3** (stability) | EXP-05: Block R (25 runs reproducibility, all verified); Block S (15 runs seed sensitivity, raw); Block N (35 runs perturbation, raw). All evidence stored in labels artifact | ARI/AMI computation, Hungarian matching, statistical tests, confidence intervals, cluster-size consistency cross-block | 🟡 **PARTIAL** — raw evidence complete; analysis in EPIC-08 | EPIC-08 Phase A implementation (ARI/AMI + statistical tests + CI) |

### 4.7. Recommendation

**Recommended actions:**

1. Write `docs/methodology/research_questions.md` with RQ1/RQ2/RQ3 draft definitions (use §4.3-4.5 above as starting point).
2. Create ADR `docs/decisions/0004-research-questions.md` documenting the RQ definitions.
3. Treat RQ3 as stability (not business interpretation — that's EPIC-09).
4. Mark RQ2 PARTIAL in writing until Family A is materialized (or until RQ2 limitation is formalized).
5. RQ1 evidence sufficient for partial answer; full answer requires EPIC-08 cross-validation.

---

## 5. RFM-only Decision (DECISION C)

### 5.1. Context

EXP-04 Family A (RFM-only vs RFM Extended feature set comparison) was DEFERRED because RFM-only artifact does not exist. EXP-04-v1 only executed Family B (preprocessing sensitivity).

### 5.2. Phân tích Option 1 — Materialize RFM-only artifact

**What RFM-only artifact would look like:**

| Aspect | Proposal |
|---|---|
| Feature definitions | 3 features: `Recency`, `Frequency`, `Monetary` (RFM core). Definitions identical to current FE-06 (Frequency = `nunique(InvoiceNo)`, Monetary = `MonetarySigned`). |
| Source | `customer_candidates.parquet` (FE-05) — same input as Family B uses |
| Aggregation | Customer-level (pre-existing in FE-05/FE-06 pipeline; no re-aggregation needed) |
| Reference date | `2011-12-10T12:50:00` (FE-05 snapshot_max) — same as RFM Extended |
| Frequency definition | `nunique(InvoiceNo)` (FREQ-01, current default) |
| Monetary definition | `MonetarySigned` (current default) |
| Preprocessing | Reuse FE-06 C7 pipeline fitted parameters (median, Yeo-Johnson, RobustScaler). For 3-feature subset, fit NEW pipeline on 3 features (avoid using lambda values fitted on 14 features). |
| Scaling | Same RobustScaler (median=0, IQR=1) — fit on RFM-only 3 features only |
| Output | `data/processed/final_clustering_dataset_rfmonly.parquet` — (4,371 × 3) numeric |
| Artifact metadata | `data/processed/customer_metadata_rfmonly.parquet` (CustomerID) for parity |
| Provenance | New ADR `docs/decisions/0005-rfm-only-materialization.md` |
| SHA chain | New SHA-256 for rfm-only matrix; input SHA unchanged |

**Relationship to FE-06:**
- RFM-only is a SUBSET of FE-06 final matrix, but with INDEPENDENT preprocessing pipeline.
- It would NOT modify `final_clustering_dataset.parquet` (FE-06 output is READ-ONLY).
- It would be a NEW artifact: `final_clustering_dataset_rfmonly.parquet`.

**EXP-04 Family A scenarios required:**

Same scenario matrix as Family B (6 full-matrix scenarios):
| Scenario ID | Transformation | Scaling | Comparison |
|---|---|---|---|
| EXP04-A-S01 | none | none | Family A baseline (no preprocessing) |
| EXP04-A-S02 | none | standard | Family A candidate |
| EXP04-A-S03 | none | minmax | Family A candidate |
| EXP04-A-S04 | none | robust | Family A candidate |
| EXP04-A-S05 | yeo_johnson | standard | Family A candidate |
| EXP04-A-S06 | yeo_johnson | robust | Family A candidate |

Total: 6 scenarios × 5 repeats = 30 runs.

**EXP-04 Family B comparison vs Family A:**

For each preprocessing scenario, compare:
- RFM-only (3 features) metrics
- RFM Extended (14 features) metrics
- Difference / Δ-metric (sanity check that features contribute)

**Research impact:**
- RQ2 becomes evaluable.
- Effect on existing EXP-04 review: need rerun with new comparison dimension.

**Implementation cost:**
- Data: 1 new artifact (read customer_candidates.parquet, apply FE-06 pipeline on 3-feature subset).
- Code: 1 new function in `src/customer_segmentation/transformation/` (RFM-only pipeline).
- Config: 1 new entry in `configs/transformation.yaml`.
- ADR: 1 new file in `docs/decisions/`.
- Tests: 1 new test file for RFM-only pipeline (~5-10 tests).
- Experiment rerun: ~30 new EXP-04 Family A runs + 30-90 EXP-04 cross-comparison runs.

**Engineering impact:**
- New artifact requires new SHA verification.
- New pipeline function requires new tests.
- Memory: 4371 × 3 = 13K cells (vs 4371 × 14 = 61K cells for full matrix). Negligible.

**Research timeline:** Medium (1-2 weeks).

**Future work after RFM-only materialize:**
- EXP-04 Family A executes.
- RQ2 becomes COMPLETE (preprocessing sensitivity + feature set sensitivity).
- EPIC-08 inherits RFM-only artifact and RFM Extended both. Cross-subset analysis becomes possible.

### 5.3. Phân tích Option 2 — NOT materialize, document RQ2 limitation

**Documentation required:**

1. Update `docs/research/FE06_Transformation_Final_Dataset.md` to explicitly state: "RFM-only artifact was NOT materialized. RQ2 evaluation limited to RFM Extended feature set. This is a documented limitation of the current thesis scope."
2. Add formal limitation in EPIC-08 report / paper: "RQ2 PARTIAL — feature representation comparison limited to within-feature-set variations; RFM-only vs RFM Extended comparison deferred."
3. Note in thesis discussion section.

**Research impact:**
- RQ2 remains PARTIAL.
- Future reviewer / mentor question: "Why doesn't this paper compare RFM-only vs RFM Extended?"
- Answer: documented scope decision; can be added in future phase.

**Engineering impact:**
- NONE. No new artifact, no new code, no rerun.

**Methodology impact:**
- Negative: thesis conclusion weaker (no feature representation claim).
- Positive: scope is clean, no partial experimental claims.

### 5.4. Phân tích Option 3 — Hybrid: document RQ2 limitation NOW, defer to future work

**Synthesis:**

| Time | Action |
|---|---|
| NOW | Document RQ2 as PARTIAL with explicit limitation language. Decision: NOT materialize RFM-only in current phase. |
| Future phase | If thesis / paper reviewer requests RFM-only comparison, materialize later as a separate workstream with new ADR. |

**This is essentially Option 2 with future workstream explicitly planned.**

**Implementation cost:** Same as Option 2 (NEAR-ZERO, just docs).

**Research impact:** Same as Option 2 (RQ2 remains PARTIAL).

**Flexibility:** Higher than Option 2 — future work clearly scoped.

### 5.5. So sánh

| Dimension | Option 1 (Materialize) | Option 2 (Document only) | Option 3 (Hybrid) |
|---|---|---|---|
| Engineering effort | HIGH (impl + tests + ADR + rerun) | LOW (docs only) | LOW (docs only) |
| Reruns | ~30-120 runs | 0 | 0 |
| RQ2 completeness | ✅ COMPLETE (after rerun) | ❌ PARTIAL forever | ❌ PARTIAL now; COMPLETE in future |
| Research timeline | +1-2 weeks | +1 day | +1 day |
| Thesis strength | HIGHER (RQ2 evaluable) | LOWER (RQ2 documented limitation) | LOWER now; HIGHER if future work happens |
| Future flexibility | HIGH (artifact exists) | LOW (must re-materialize later) | MEDIUM (plan documented but not executed) |
| Reviewer confidence | HIGH | MEDIUM (need explanation) | MEDIUM |

### 5.6. Recommendation

**Recommended: Option 2 (NOT materialize now, document limitation).**

**Rationale:**
1. Current thesis scope only requires RFM Extended for clustering work. RQ2 PARTIAL is acceptable for this phase.
2. Implementation cost of Option 1 is significant (~30-120 reruns) with no immediate research benefit.
3. RFM-only can be added in a future workstream if reviewer requests.
4. Documenting the limitation explicitly is cleaner than partial-future-work references.
5. Aligns with "minimum methodology lock" philosophy — only materialize what's necessary for EPIC-08.

**Option 1 is preferable IF:** RQ2 completeness is MANDATORY before publication / thesis submission. In that case, materialize ASAP.

### 5.7. Action items (if Option 2 approved)

1. Update `reports/exp04/exp04_pending_review.json` to add new ADR reference (`pending_rfm_only_materialization.md`).
2. Update `docs/research/FE06_Transformation_Final_Dataset.md` with explicit "RFM-only NOT materialized; RQ2 PARTIAL limitation" section.
3. Update `docs/research/EXP04_PREPROCESSING_FEATURE_REVIEW.md` with explicit future-work reference.
4. Add `docs/research/TODO_rfm_only_future_work.md` with materialization checklist (for future reference, not action).
5. NO code, no config, no rerun.
6. NO SHA change.

---

## 6. Pending Decision Consolidation

### 6.1. Classification rubric

Pending decisions from `EXP01_EXP05_PENDING_DECISIONS.md`, the full audit, and per-experiment pending_review notes fall into 4 categories:

1. **MUST DECIDE BEFORE EPIC-08** — blocks EPIC-08 implementation or interpretation
2. **CAN BE DECIDED DURING EPIC-08** — EPIC-08 plan can decide
3. **CAN REMAIN LIMITATION** — accepted in current thesis; documented
4. **NOT ACTUALLY A RESEARCH DECISION** — implementation detail / engineering choice

### 6.2. Categorized pending decisions

#### MUST DECIDE BEFORE EPIC-08

| ID | Decision | Why blocking |
|---|---|---|
| **EPIC08-INPUT-01** | EPIC-08 input: FE-06 vs FE-05 | Determines stability analysis scope |
| **EPIC08-WORKING-01** | EPIC-08 use EXP-01 working defaults or EXP-03 working selections | Determines which configs to compare |
| **EPIC08-METRIC-01** | Add ARI/AMI to stability analysis | Required for RQ3 (stability) |
| **EPIC08-STAB-01/02/03** | Stability methodology (ARI/AMI computation, statistical tests, CI) | EPIC-08 plan content |
| **EPIC08-RUNTIME-01** | Runtime comparison methodology | EPIC-08 plan content |
| **EPIC08-CROSS-ALG-01** | EPIC-08 allowed cross-algorithm ranking | Determines RQ1 final answer format |
| **EPIC08-BIZ-01** | EPIC-08 business validation scope | Boundary with EPIC-09 |
| **D-KMED-1** (§3) | K-Medoids scope decision | Algorithm scope consistency |
| **L-RQ-1** (§4) | RQ definitions | Thesis mapping |
| **EXP04-FS-01** (§5) | RFM-only materialization | RQ2 completeness |

#### CAN BE DECIDED DURING EPIC-08

| ID | Decision | Reason deferral |
|---|---|---|
| **EPIC08-VIZ-01** | Visualization scope (silhouette plot, comparison dashboard) | Implementation detail of EPIC-08 phase B |
| **EPIC08-PROFILE-01** | EPIC-08 overlap with EPIC-09 customer profiling | Can be deferred until EPIC-09 plan |
| **EXP03-SEL-02** | Agglomerative Stage C K=3 linkage=average (CH disagreement) | EPIC-08 cross-metric analysis will resolve |
| **EXP03-KM-01** | K-Means 3-way tie (TIED_WORKING_SELECTED) | EPIC-08 stability can resolve (K-Means deterministic) |
| **EXP03-FCM-01** / D-FCM-1 | FCM m=1.5 vs m ≥ 2.0 | EPIC-08 stability analysis on FCM configs can resolve |
| **EXP-04-DBSCAN-01** / D-DBSCAN-1 | DBSCAN baseline noise_ratio 0.7268 | EPIC-08 stability can analyze |
| **EXP-03-SEL-01** | Selection protocol silhouette-primary → DBI → CH | EPIC-08 can validate or revise |
| **EXP01-RUNTIME-01/02/03** | Runtime protocol details | Already TECHNICALLY_IMPLEMENTED, deferred for documentation |
| **EXP01-MET-01..06** | Metric status schema details | Already TECHNICALLY_IMPLEMENTED, deferred for documentation |

#### CAN REMAIN LIMITATION

| ID | Decision | Documented limitation |
|---|---|---|
| **EXP04-FS-01** (per §5) | RFM-only NOT materialized | RQ2 PARTIAL — limitation language in thesis |
| **EXP04-ALG-01** | EXP-04 only K-Means | Scope = preprocessing on K-Means only |
| **EXP04-K-01** | EXP-04 K=4 only | Scope = preprocessing at K=4 |
| **EXP04-TR-01** | log1p NOT in EXP-04 scenarios | Documented in EXP-04 review |
| **EXP05-BLK-02** | Block S only 3 algorithms | Deterministic algorithms excluded by design |
| **EXP05-BLK-03** | Sigma grid [0, 0.01, 0.05] | Working assumption, sensitivity low |
| **EXP05-PERT-02** | sigma=0 sanity check | Working assumption; verified |
| **EXP05-DEC-01** | Decision status taxonomy | Working assumption for EP-IC-08 |
| **EXP-METRIC-BIZ-01** | Internal metrics ↔ business interpretation | NO mapping allowed (AGENTS.md §2.5) |
| **EXP04-C0-hi-silhouette** | C0 silhouette = 0.9465 (raw data artifact) | Documented in EXP-04 review |
| **EXP-DBSCAN-high-noise** | DBSCAN 72.68% noise ratio | Documented in EXP-01 review; per-algorithm |
| **RFM feature standardization** | RFM standard vs signed Monetary | Working assumption: MonetarySigned |

#### NOT ACTUALLY A RESEARCH DECISION (engineering detail)

| ID | Decision | Why not research |
|---|---|---|
| **EXP01-MET-04** | Metric status schema (4 enum values) | Engineering |
| **EXP01-K-01** | EXP-01 K=4 working default | Engineering working default, can be revised |
| **EXP01-MET-01** | Noise exclusion policy | Engineering convention, sklearn-aligned |
| **EXP01-MET-02** | WCSS convention (arithmetic centroid from hard labels) | Engineering convention, documented |
| **EXP01-MET-03** | n_repeat=5 for runtime | Engineering choice |
| **EXP01-MET-05/06** | ALL_NOISE / SINGLE_CLUSTER edge case handling | Engineering edge case |
| **EXP02-KRNG-01** | K range [2, 10] step=1 | Working assumption; can rerun |
| **EXP02 candidate heuristic constants** | top_n=3, drop_ratio=0.2, min_agreement=2 | Working assumption; can revise |
| **EXP05-BLK-01** | Block R = reproducibility only (no stability analysis) | Scope clarification |
| **EXP05-ART-01** | Labels artifact schema (9 columns) | Engineering schema |
| **EXP05-AGG-01** | Aggregate uses mean/std/min/max/CV | Engineering aggregation |
| **EPIC-06 framework details** | AlgorithmRegistry, BaseClusterAlgorithm, ExperimentRunner | Engineering framework |
| **D-KMED-1 §3 implementation (if Option B)** | Documentation update | Engineering doc only |

### 6.3. Decision count by category

| Category | Count |
|---|---|
| MUST DECIDE BEFORE EPIC-08 | ~10 |
| CAN BE DECIDED DURING EPIC-08 | ~9 |
| CAN REMAIN LIMITATION | ~12 |
| NOT ACTUALLY A RESEARCH DECISION | ~13 |
| **Total** | **~44** (vs ~60+ originally) |

This significantly reduces decision noise: only ~10 truly block EPIC-08; ~22 are documentation / methodology-naming decisions.

---

## 7. Rerun Impact Matrix

### 7.1. Decision → rerun mapping

| Decision change | Affected artifact | Affected experiment | Affected report | Downstream impact | Rerun required? |
|---|---|---|---|---|---|
| **K-Medoids implementation** (Option A) | NEW `final_clustering_dataset_kmedoids.parquet`? No — same input matrix; new cluster labels per algorithm | EXP-01 (+1 run), EXP-02 (+9 runs), EXP-03 (+~15-20 runs), EXP-04 (+30 runs if expanded), EXP-05 (+~13 runs) | All EXP reports; cross-experiment tables | EPIC-08 must include K-Medoids in stability analysis | **YES**, very large (~70-90 runs) |
| **K-Medoids deprecation** (Option B §3.7) | None | None | Documentation updates | EPIC-08 runs on 5 algorithms | **NO** |
| **RQ definitions change** (e.g., add RQ4) | None | None | None | EPIC plan update; new analysis scope | **DEPENDS** — only if RQ4 needs new data |
| **RQ definitions clarification** (e.g., RQ3 = stability not business) | None | None | Doc-only | Interpret existing evidence under clarified RQ | **NO** |
| **Materialize RFM-only** (Option 1 §5.2) | NEW `final_clustering_dataset_rfmonly.parquet` | EXP-04 Family A (+30 runs cross-comparison); possibly EXP-05 block for RFM-only | EXP-04 report updated | EPIC-08 cross-subset analysis | **YES**, ~30-60 runs |
| **NOT materialize RFM-only** (Option 2 §5.7) | None | None | Doc-only | EPIC-08 RFM Extended only | **NO** |
| **FE-06 promote to RESEARCH_APPROVED_FINAL** (FE-06-DATASET-02) | None (just status change) | None | Doc only | EPIC-08 marks FE-06 final as approved | **NO** |
| **Feature definition change** (e.g., Frequency variant change) | NEW `customer_candidates.parquet`; NEW `final_clustering_dataset.parquet` | EXP-01, EXP-02, EXP-03, EXP-05 (all use FE-06); EXP-04 (uses FE-05) | All EXP reports; final matrix SHA change | EPIC-08 must rerun on new matrix | **YES**, large ~150+ runs |
| **Imputation change** (e.g., median → KNN) | NEW `final_clustering_dataset.parquet` | Same as feature change | Same | Same | **YES**, large |
| **Transformation change** (e.g., Yeo-Johnson → log1p) | Same | Same | Same | Same | **YES**, large |
| **Scaling change** (e.g., RobustScaler → StandardScaler) | Same | Same | Same | Same | **YES**, large |
| **K range change** (e.g., [2, 10] → [2, 15]) | Same | EXP-02 (K-sweep); EPIC-08 (uses EXP-02 candidates) | EXP-02 report | EPIC-08 candidates | **YES**, partial (~28+ runs for new K values) |
| **Working K change** (e.g., EXP-01 K=4 → K=3) | Same | EXP-01, EXP-04 (controlled_ref_K), EXP-05 (Block R uses EXP-01) | All | EPIC-08 uses new EXP-01 baseline | **YES**, medium (~50-100 runs) |
| **Hyperparameter change** (e.g., EXP-03 protocol revision) | Same | EXP-03 only | EXP-03 report | EPIC-08 might need update | **YES**, ~30-60 runs (rerun Stage B/C) |
| **Selection protocol adjustment** (silhouette → other primary) | Same | EXP-03 only | EXP-03 report | EPIC-08 selections may change | **YES** if protocol changes working selections, else NO |
| **DBSCAN noise policy change** | Same | EXP-01, EXP-05 Block S (DBSCAN excluded due to determinism) | EXP-01, EXP-05 reports | EPIC-08 DBSCAN handling | **MAYBE**, depending on policy change scope |
| **Agglomerative configuration change** (linkage revision) | Same | EXP-03 Stage B/C; EPIC-08 uses selection | EXP-03 report | EPIC-08 analysis | **YES**, partial (~10-20 runs) |
| **Metric status schema change** (e.g., add new enum value) | Same | None directly | Engineering | EPIC-08 might need to handle new status | **NO** (engineering-only) |
| **Statistical test change** (paired t-test → Wilcoxon) | Same | None | EPIC-08 only | EPIC-08 plan | **NO** (EPIC-08 owned) |
| **CI method change** (bootstrap → percentile) | Same | None | EPIC-08 only | EPIC-08 plan | **NO** (EPIC-08 owned) |
| **Seed list change** (e.g., Block S seeds) | Same | EXP-05 Block S | EXP-05 report | EPIC-08 stability on new seeds | **YES**, partial (15 runs Block S) |
| **Sigma grid change** (Block N) | Same | EXP-05 Block N | EXP-05 report | EPIC-08 stability on new sigmas | **YES**, partial (~20-50 runs Block N) |

### 7.2. Estimated rerun cost per category

| Decision category | Estimated reruns | Wall-clock time |
|---|---|---|
| K-Medoids Option A | 70-90 runs | 1-2 weeks |
| Materialize RFM-only | 30-60 runs | 1-2 weeks |
| Feature / imputation / transformation / scaling change | 150+ runs | 2-3 weeks |
| K range expansion | 30+ runs | Few days |
| Working K change | 50-100 runs | 1 week |
| Hyperparameter re-sweep | 30-60 runs | Few days |
| Algorithm configuration change | 10-50 runs | Few days |
| Seed/sigma list change | 20-50 runs | Few days |

### 7.3. Cumulative rerun warning

**If multiple HIGH-severity decisions change simultaneously:**
- K-Medoids + RFM-only + Feature change = 250+ runs
- ≈ 3-4 weeks full rerun

**Recommendation:** Decide decision-by-decision, NOT batch.

---

## 8. Minimum Methodology Lock

### 8.1. Philosophy

"Minimum methodology lock" = smallest set of decisions needed to enable EPIC-08 Phase A implementation WITHOUT forcing rerun of EXP-01..05.

### 8.2. Required decisions (Phase A)

| Decision | Required before EPIC-08? | Why |
|---|---|---|
| **Algorithm scope** | YES | Must know whether EPIC-08 runs on 5 algorithms or 6 algorithms |
| **RQ definitions** | YES (written form) | Must know what RQ1/RQ2/RQ3 evaluate |
| **RFM-only materialization** | NO (defer) | RQ2 PARTIAL acceptable; EPIC-08 doesn't need RFM-only |
| **EPIC-08 input source** | YES | FE-06 final matrix vs FE-05 candidates determines stability analysis scope |
| **EPIC-08 working config source** | YES | EXP-01 defaults vs EXP-03 selections determines which configs to compare |
| **ARI/AMI addition** | YES | Required for RQ3 stability analysis |
| **Statistical test choice** | NO (in EPIC-08 plan) | EPIC-08 plan can decide |
| **CI method** | NO (in EPIC-08 plan) | EPIC-08 plan can decide |
| **Agglomerative selection** | NO (defer) | EPIC-08 cross-metric analysis will resolve |
| **K-Means tie** | NO (defer) | K-Means deterministic; tie doesn't affect stability |
| **DBSCAN noise** | NO (defer) | EPIC-08 can analyze as-is |
| **FCM m** | NO (defer) | EPIC-08 can analyze FCM configs |
| **EXP-04 RFM-only** | NO (defer per §5) | EPIC-08 can run RFM Extended only |
| **EPIC-08 business validation** | NO (defer) | EPIC-09 owns |

### 8.3. Minimum lock set = 4 decisions

| # | Decision | Action required before EPIC-08 |
|---|---|---|
| 1 | Algorithm scope = 5 algorithms (no K-Medoids) per Option B (§3.7) | ADR + docs |
| 2 | RQ1 = algorithm comparison; RQ2 = feature set sensitivity; RQ3 = stability (per §4) | Write `docs/methodology/research_questions.md` + ADR |
| 3 | EPIC-08 input = `final_clustering_dataset.parquet` (FE-06 C7) | Plan + ADR |
| 4 | EPIC-08 working config = EXP-01 working defaults + EXP-03 selections (both, compare) | Plan + ADR |

### 8.4. Deferred decisions (resolved during EPIC-08)

| Category | Decisions | EPIC-08 ownership |
|---|---|---|
| ARI/AMI computation method | Statistical method | EPIC-08 plan |
| Statistical test choice | Parametric vs non-parametric | EPIC-08 plan |
| CI method | Bootstrap vs percentile | EPIC-08 plan |
| Runtime comparison protocol | Mean/median/CI | EPIC-08 plan |
| EPIC-08 cross-algorithm ranking | Yes/no with caveats | Plan + mentor input |
| Agglomerative Stage C K=3 linkage=average | Resolve via cross-metric | EPIC-08 analysis |
| K-Means 3-way tie | Document + justify | EPIC-08 analysis |
| FCM m=1.5 vs m≥2.0 | Document + analyze | EPIC-08 analysis |
| DBSCAN noise handling | Analyze as-is | EPIC-08 analysis |

### 8.5. Recommended EPIC-08 plan ownership summary

```
EPIC-08 Phase A (can start AFTER §8.3 decisions)
├── ARI / AMI / Hungarian computation
├── Statistical tests (paired t-test, Wilcoxon)
├── Confidence intervals (bootstrap / percentile)
├── Runtime statistical comparison
├── Cluster-size consistency cross-block
├── Diagnostic visualizations
│   ├── Silhouette plots
│   └── Comparison dashboards
└── Inputs: FE-06 final matrix + EXP-05 labels artifact

EPIC-08 Phase B (after Phase A + mentor review)
├── Cross-algorithm ranking (only if AGENTS.md §2.5 permits)
├── Working algorithm config selection
├── RFM Extended vs RFM-only comparison (only if RFM-only materialized)
├── "Most stable algorithm" claim (only if methodology permits)
└── Segment profile / business validation (only if EPIC-09 ready)
```

---

## 9. EPIC-08 Boundary

### 9.1. Phase A (independent of mentor decisions; can start NOW)

| Task | Scope | Output |
|---|---|---|
| ARI/AMI computation | All 5 algorithms using EXP-05 labels artifact | `reports/epic08/stability_ari_ami.csv` |
| Hungarian matching | Block S (across seeds), Block N (across perturbation seeds) | `reports/epic08/hungarian_matching.csv` |
| Block R reproducibility metric | Already verified — EPIC-08 documents it | Reference existing EXP-05 report |
| Statistical tests (paired t-test / Wilcoxon) | Across seeds (Block S), across perturbation seeds (Block N) | `reports/epic08/statistical_tests.csv` |
| Confidence intervals | Bootstrap on ARI distributions | `reports/epic08/ci_estimates.csv` |
| Runtime statistical comparison | EXP-01 runtime + per-run variance | `reports/epic08/runtime_comparison.csv` |
| Cluster-size consistency analysis | Cross-block (Block R/S/N) | `reports/epic08/cluster_size_consistency.csv` |
| Diagnostic visualizations | Silhouette plots, ARI distributions, runtime bars | `reports/figures/epic08_*.png` |

**Inputs:** EXP-05 `exp05_cluster_labels.parquet` (327,825 rows × 9 cols) + EXP-01 baseline metrics + FE-06 dataset version metadata.

**Outputs:** Aggregated stability metrics per algorithm, runtime comparison tables, diagnostic plots.

### 9.2. Phase B (requires mentor decisions)

| Task | Blocking decision |
|---|---|
| Cross-algorithm ranking (e.g., "K-Means more stable than Agglo on RFM Extended") | EPIC08-CROSS-ALG-01 + AGENTS.md §2.5 |
| Working algorithm config selection across all 5 algorithms | EPIC08-WORKING-01 |
| "Most stable algorithm" claim | EPIC08-CLAIM-01 + AGENTS.md §2.5 |
| RFM Extended vs RFM-only cross-subset analysis | EXP04-FS-01 (RFM-only materialization) |
| Segment profile / business interpretation | EPIC09 owned |
| Cluster naming (Champions / Loyal / etc.) | EPIC09 owned (NOT EPIC-08) |

### 9.3. NOT in EPIC-08 scope

| Task | Owner | Reason |
|---|---|---|
| Run additional experiments (RFM-only, K-Medoids, more algorithms) | EPIC-X (future) | Out of EPIC-08 scope |
| Re-run EXP-01..05 | Mentor decision | Only if upstream decision changes |
| Customer profiling / segment characteristics | EPIC-09 | Out of EPIC-08 |
| Visualization for paper / thesis | EPIC-10 | Out of EPIC-08 |
| Deployment / API / production | Out of repo | Out of scope |
| New ADR for scikit-learn-extra dependency | Out of scope unless Option A | Engineering dep mgmt |

### 9.4. EPIC-08 boundary discipline

**EPIC-08 must NOT:**
- Re-sweep K, hyperparameters, or preprocessing.
- Add new algorithms.
- Add new metrics beyond what's agreed in Phase A.
- Make "best algorithm" or "winner" claims.
- Translate internal metrics to business interpretation.
- Profile customers (EPIC-09).
- Auto-drop features (FE-05/FE-06).
- Invent data, configs, or statistics.

**EPIC-08 MAY:**
- Compute ARI/AMI on existing labels.
- Apply statistical tests across existing seeds / perturbations.
- Aggregate runtime statistics from existing per-run data.
- Generate diagnostic visualizations.
- Document evidence under AGENTS.md §2.5 constraints.

---

## 10. Proposed Methodology Baseline

### 10.1. Locked decisions (after §8.3 minimum lock)

| Decision | Locked value | Source |
|---|---|---|
| Algorithm scope | 5 algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) | ADR-0003 (this proposal Option B) |
| RQ1 | Cross-algorithm comparison under controlled conditions | methodology/research_questions.md §RQ1 |
| RQ2 | Feature set sensitivity (RFM-only vs RFM Extended) | methodology/research_questions.md §RQ2 (RQ2 PARTIAL accepted) |
| RQ3 | Stability / reproducibility / robustness | methodology/research_questions.md §RQ3 |
| FE-06 input dataset | `final_clustering_dataset.parquet` (FE06-v1.0) | already locked, FE-06 §13 |
| Working preprocessing | C7 (yeo_johnson + robust + median) — `WORKING_ASSUMPTION` | already in use; default for EPIC-08 |
| Feature set | 14 features (CANDIDATE only); 6 PENDING_REVIEW features included as `ELIGIBLE_WORKING_ASSUMPTION` | FE-06 §13 |
| EXP-01 baseline configs | `WORKING_ASSUMPTION` for EXP-01 K=4 + per-algorithm defaults | EXP-01 review |
| EXP-03 selection protocol | silhouette-primary → DBI → CH | EXP-03 plan §2.2 |
| EXP-03 working selections | (per-algorithm) | EXP-03 review |
| EXP-05 blocks | R/S/N raw evidence only | EXP-05 review |
| Metric set | silhouette / DBI / CH / WCSS + status schema | EXP-01 plan §4 |
| Runtime protocol | algorithm execution only; n_repeat=5 | EXP-01 plan §3 |

### 10.2. Deferred decisions (during EPIC-08)

| Decision | Deferred to | Reason |
|---|---|---|
| K-Means 3-way tie | EPIC-08 stability analysis | K-Means deterministic |
| Agglomerative Stage C K=3 linkage=average | EPIC-08 cross-metric | Cross-metric resolves CH vs silhouette |
| FCM m=1.5 vs m≥2.0 | EPIC-08 stability per FCM config | Per-config stability |
| DBSCAN noise handling | EPIC-08 analysis | Per-algorithm |
| Working algorithm config for EPIC-08 | Phase B decision | Mentor review |

### 10.3. Documented limitations (accepted in current thesis)

| Limitation | Documented in | Acceptance |
|---|---|---|
| RQ2 PARTIAL (RFM-only not materialized) | FE-06 doc, EXP-04 review | Accepted per Option 2 §5 |
| EXP-04 K-Means only | EXP-04 review | Accepted |
| EXP-04 K=4 only | EXP-04 review | Accepted |
| EXP-04 log1p not in scenarios | EXP-04 review | Accepted |
| EXP-05 Block S only 3 algorithms | EXP-05 review | Accepted |
| EXP-05 sigma grid [0, 0.01, 0.05] | EXP-05 review | Accepted |
| DBSCAN 72.68% noise ratio | EXP-01 review | Per-algorithm characteristic |
| EXP-04 C0 silhouette=0.9465 artifact | EXP-04 review | Documented |
| "Best/winner/optimal" claims forbidden | AGENTS.md §2.5 | Always |

---

## 11. Remaining Uncertainty

### 11.1. Things this audit CANNOT determine

1. **Mentor's actual research preference** for K-Medoids implementation (Option A) vs documentation update (Option B).
2. **Mentor's RQ2 decision** — is RQ2 evaluation MANDATORY or can RQ2 stay PARTIAL?
3. **Mentor's expectation** for cross-algorithm ranking in EPIC-08.
4. **Thesis scope** — is RFM-only comparison required for publication?
5. **Future reviewer feedback** — could change Option A/B/C preferences later.

### 11.2. Open questions for Mentor

1. **K-Medoids**: Option A (implement + add) or Option B (update docs)?
2. **RQ definitions**: Use §4 drafts as starting point, or extend further?
3. **RQ2**: Materialize RFM-only (Option 1) or accept PARTIAL limitation (Option 2)?
4. **EPIC-08 cross-algorithm ranking**: Allowed with caveats, or forbidden?
5. **Working algorithm config for EPIC-08 stability**: EXP-01 defaults, EXP-03 selections, or both?
6. **Statistical tests**: Parametric (t-test) or non-parametric (Wilcoxon) or both?
7. **CI method**: Bootstrap or percentile?
8. **Runtime CI**: Required?

### 11.3. Risks remaining after minimum lock

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Mentor decides K-Medoids Option A after we adopt Option B | LOW | LOW | K-Medoids can be added in future EPIC-X with new ADR |
| Mentor decides RFM-only materialization | LOW | MEDIUM | ~30-60 reruns; documented time budget |
| Feature / preprocessing change request | LOW | HIGH | Re-verify SHAs, rerun affected EXP |
| EPIC-08 reveals unexpected instability | MEDIUM | MEDIUM | EPIC-08 protocol allows reporting, not promotion |
| Reviewer asks for full cross-algorithm ranking | MEDIUM | HIGH | AGENTS.md §2.5 + Mentor decision controls this |
| RQ definitions need revision | LOW | MEDIUM | Update RQ docs, no rerun needed |
| Working K needs change (e.g., K=4 → K=3) | LOW | HIGH | ~50-100 reruns for EXP-01/04/05 |
| Working preprocessing needs change (e.g., C7 → C6) | LOW | HIGH | Full rerun |

---

## 12. Proposed Decision Sequence

### 12.1. Decision sequence (dependency-driven)

The sequence below is derived from the dependency graph:

```
Step 1: Lock algorithm scope (K-Medoids decision)
   ↓ (affects RQ1 and EPIC-08 plan)
Step 2: Lock RQ definitions (RQ1, RQ2, RQ3)
   ↓ (RQ2 defines whether RFM-only needed)
Step 3: Lock RFM-only scope (materialize vs limitation)
   ↓ (affects EXP-04 Family A and EPIC-08)
Step 4: Write EPIC-08 plan with locked upstream decisions
   ↓ (defines Phase A scope)
Step 5: Implement EPIC-08 Phase A (independent computation)
   ↓ (outputs stability evidence)
Step 6: Mentor review of Phase A outputs
   ↓ (validates Phase B feasibility)
Step 7: Implement EPIC-08 Phase B (cross-algorithm analysis)
   ↓ (decisions about ranking, claims, etc. resolved here)
Step 8: Integrate EPIC-08 outputs into report / paper / thesis
   ↓
Step 9: EPIC-09 (profiling) + EPIC-10 (visualization)
```

### 12.2. Detailed sequence

#### Sequence Step 1 — Lock Algorithm Scope (HIGH priority)

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 1.1 | Mentor decides Option A (implement) or Option B (update docs) for K-Medoids | Mentor | Decision | 1 day |
| 1.2 (Option B) | Update README.md, AGENTS.md, FE-05/06 docs, configs | Maintainer | Doc PR | 1-2 days |
| 1.3 (Option B) | Write ADR `docs/decisions/0003-algorithm-scope.md` | Maintainer | ADR | 1 day |
| 1.4 (Option A) | Implement `KMedoidsAdapter`, register, tests, config, ADR | Engineer | Code PR | 1-2 weeks |
| 1.5 (Option A) | Rerun EXP-01..05 with K-Medoids included | Engineer | New EXP artifacts | 1-2 weeks |

#### Sequence Step 2 — Lock RQ Definitions (HIGH priority, parallel with Step 1)

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 2.1 | Write `docs/methodology/research_questions.md` (real content; replace TODO) | Researcher | Doc PR | 1-2 days |
| 2.2 | Include RQ1 (cross-algorithm), RQ2 (feature representation), RQ3 (stability) per §4 | Researcher | Doc PR | (same as 2.1) |
| 2.3 | Write `docs/methodology/methodology_overview.md` (replace TODO) | Researcher | Doc PR | 1 day |
| 2.4 | Write `docs/methodology/unit_of_analysis.md` (replace TODO) | Researcher | Doc PR | 1 day |
| 2.5 | Write ADR `docs/decisions/0004-research-questions.md` | Researcher | ADR | 1 day |

#### Sequence Step 3 — Lock RFM-only Scope (HIGH priority, parallel)

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 3.1 | Mentor decides materialize RFM-only (Option 1) or limitation (Option 2) | Mentor | Decision | 1 day |
| 3.2 (Option 2) | Update FE-06 doc, EXP-04 review with explicit RQ2 PARTIAL limitation | Researcher | Doc PR | 1 day |
| 3.3 (Option 2) | Add `docs/research/TODO_rfm_only_future_work.md` with materialization checklist | Researcher | Reference doc | 1 day |
| 3.4 (Option 1) | Implement RFM-only pipeline in `src/customer_segmentation/transformation/` | Engineer | Code PR | 1-2 days |
| 3.5 (Option 1) | Write ADR `docs/decisions/0005-rfm-only-materialization.md` | Engineer | ADR | 1 day |
| 3.6 (Option 1) | Materialize `final_clustering_dataset_rfmonly.parquet` | Engineer | New artifact | 1 day |
| 3.7 (Option 1) | Rerun EXP-04 Family A | Engineer | New EXP-04 artifacts | 1-2 weeks |
| 3.8 (Option 1) | Update RQ2 from PARTIAL to COMPLETE | Researcher | Doc update | 1 day |

#### Sequence Step 4 — Write EPIC-08 Plan

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 4.1 | Write `docs/research/EPIC08_stability_evaluation_PLAN.md` using §8 + §9 as scaffold | Engineer | Plan doc | 1-3 days |
| 4.2 | Include Phase A scope (ARI/AMI, statistical tests, CI, runtime, viz) | Engineer | Same as 4.1 | (same) |
| 4.3 | Include Phase B scope (cross-algorithm ranking, claims) with PENDING_REVIEW flags | Engineer | Same as 4.1 | (same) |
| 4.4 | Reference EXP-05 labels artifact + FE-06 dataset version | Engineer | Same as 4.1 | (same) |
| 4.5 | ADR for EPIC-08 scope (input selection, working config selection) | Engineer | ADR | 1 day |

#### Sequence Step 5 — Implement EPIC-08 Phase A

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 5.1 | Implement ARI / AMI computation (using sklearn.metrics.adjusted_rand_score / adjusted_mutual_info_score) | Engineer | Code | 1-3 days |
| 5.2 | Implement Hungarian matching (using scipy.optimize.linear_sum_assignment) | Engineer | Code | 1-2 days |
| 5.3 | Implement statistical tests (scipy.stats.ttest_rel, wilcoxon) | Engineer | Code | 1-2 days |
| 5.4 | Implement bootstrap CI (numpy.random.choice with replacement) | Engineer | Code | 1-2 days |
| 5.5 | Implement runtime statistical comparison (mean, std, CI on existing per-run data) | Engineer | Code | 1 day |
| 5.6 | Implement cluster-size consistency analysis | Engineer | Code | 1 day |
| 5.7 | Generate diagnostic visualizations (silhouette plot, ARI distribution, runtime bars) | Engineer | Figures | 1-2 days |
| 5.8 | Write tests for EPIC-08 functions | Engineer | Tests | 1-2 days |
| 5.9 | Run `scripts/run_epic08_phase_a.py` and produce outputs | Engineer | EPIC-08 outputs | 1 day |
| 5.10 | Write `docs/research/epic08/EPIC08_PHASE_A_REPORT.md` | Engineer | Report | 1 day |

#### Sequence Step 6 — Mentor Review of Phase A

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 6.1 | Submit Phase A outputs to Mentor | Engineer | Submission | 1 day |
| 6.2 | Mentor reviews outputs, validates methodology | Mentor | Review | 1-2 weeks |
| 6.3 | Mentor decides on Phase B feasibility (cross-algorithm ranking, claims) | Mentor | Decision | (same as 6.2) |

#### Sequence Step 7 — Implement EPIC-08 Phase B (only if Mentor approves)

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 7.1 | Implement cross-algorithm ranking (with explicit caveats) | Engineer | Code | 2-3 days |
| 7.2 | Resolve Agglomerative disagreement (silhouette vs CH) via ARI + runtime | Engineer | Analysis | 2-3 days |
| 7.3 | Resolve K-Means tie via stability + ARI | Engineer | Analysis | 1 day |
| 7.4 | DBSCAN noise analysis (per-algorithm) | Engineer | Analysis | 2 days |
| 7.5 | FCM per-config analysis | Engineer | Analysis | 2 days |
| 7.6 | Write `docs/research/epic08/EPIC08_PHASE_B_REPORT.md` | Engineer | Report | 1 week |

#### Sequence Step 8 — Integrate into Thesis

| # | Action | Owner | Output | Time |
|---|---|---|---|---|
| 8.1 | Cross-link EPIC-08 outputs to thesis sections | Researcher | Thesis update | 1-2 days |
| 8.2 | Address RQ1, RQ2 (PARTIAL/COMPLETE), RQ3 in thesis | Researcher | Thesis section | 1 week |
| 8.3 | Document decisions made in thesis appendix | Researcher | Appendix | 1-2 days |

#### Sequence Step 9 — EPIC-09 + EPIC-10 (separate plans)

EPIC-09 (profiling) and EPIC-10 (visualization) own by separate workstreams.

### 12.3. Timeline summary

| Step | Estimated time | Parallel? |
|---|---|---|
| Step 1 (algorithm scope) | 1-2 days (Option B) or 2-4 weeks (Option A) | Parallel with Step 2 |
| Step 2 (RQ definitions) | 1 week | Parallel with Step 1 |
| Step 3 (RFM-only) | 1 day (Option 2) or 2-3 weeks (Option 1) | Parallel with Step 1, 2 |
| Step 4 (EPIC-08 plan) | 1 week | After Step 1-3 |
| Step 5 (Phase A implementation) | 2-3 weeks | After Step 4 |
| Step 6 (Mentor review) | 1-2 weeks | After Step 5 |
| Step 7 (Phase B implementation, optional) | 2-3 weeks | After Step 6 |
| Step 8 (Thesis integration) | 2 weeks | After Step 7 |
| **Total** | **3-9 weeks (Option A+1) or 6-12 weeks (Option A+1)** | |

### 12.4. Critical path

The CRITICAL PATH (longest dependency) is:
```
Step 1 (algorithm scope, Option A) 
  → Step 2 (RQ) (parallel)
  → Step 3 (RFM-only, Option 1) (parallel)
  → Step 4 (EPIC-08 plan)
  → Step 5 (Phase A)
  → Step 6 (Mentor review)
  → Step 7 (Phase B)
  → Step 8 (Thesis)
```

If Option B (algorithm scope) + Option 2 (RFM-only), the path becomes significantly shorter (~6 weeks total).

---

## 13. PROPOSED DECISION SEQUENCE

### 13.1. Final recommended sequence

The recommendation is **6-step minimum**:

```
Step 1: PARALLEL
  1a. Mentor decides K-Medoids: Option A (implement + rerun) or Option B (update docs).
  1b. Researcher writes RQ definitions (RQ1, RQ2, RQ3) per §4 + ADRs.
  1c. Mentor decides RFM-only: Materialize (Option 1) or limitation (Option 2).

Step 2: Execute Step 1 decisions
  2a. If 1a = Option A → implement K-Medoids + rerun EXP-01..05.
  2b. If 1a = Option B → write ADR-0003-algorithm-scope.md + update docs.
  2c. Write ADR-0004-research-questions.md based on 1b.
  2d. If 1c = Option 1 → materialize RFM-only artifact + rerun EXP-04 Family A.
  2e. If 1c = Option 2 → write ADR-0005-rfm-only-limitation.md + update docs.

Step 3: Write EPIC-08 PLAN
  3a. Write docs/research/EPIC08_stability_evaluation_PLAN.md
  3b. Reference EXP-05 labels artifact + FE-06 dataset version
  3c. ADRs for EPIC-08 input source + working config selection

Step 4: Implement EPIC-08 Phase A (independent computation)
  4a. ARI/AMI + Hungarian matching
  4b. Statistical tests + CIs
  4c. Runtime comparison + cluster-size consistency
  4d. Diagnostic visualizations
  4e. Tests + scripts
  4f. Generate EPIC08_PHASE_A_REPORT.md

Step 5: Mentor review of Phase A
  5a. Review outputs
  5b. Decide Phase B feasibility (cross-algorithm ranking, claims)

Step 6: Implement EPIC-08 Phase B (conditional on Step 5 approval)
  6a. Cross-algorithm ranking (if allowed)
  6b. Resolve algorithm-specific decisions
  6c. Generate EPIC08_PHASE_B_REPORT.md

Then: EPIC-09 (profiling) and EPIC-10 (visualization) follow.
```

### 13.2. Decision matrix for Step 1

| If you want... | Then take | Effort | Risk |
|---|---|---|---|
| Cleanest scope, fastest path, doc-consistency | **Option B (K-Medoids docs)** + **Option 2 (RFM-only limitation)** | LOW | LOW |
| Full algorithm benchmark | **Option A (K-Medoids implement)** + **Option 2 (RFM-only limitation)** | HIGH for K-Medoids | MEDIUM |
| Full feature representation analysis | **Option B (K-Medoids docs)** + **Option 1 (RFM-only materialize)** | MEDIUM for RFM-only | MEDIUM |
| Maximum research completeness | **Option A + Option 1** | HIGH | MEDIUM |

**Default recommendation:** Option B + Option 2 (cleanest, fastest).

### 13.3. Parallelization opportunity

Steps 1a, 1b, 1c can run in parallel (they don't depend on each other output-wise, only need Mentor decisions).

Steps 2a + 2b + 2c + 2d + 2e can also be parallelized (different agents can implement different ADRs).

Step 3 (EPIC-08 plan) requires all of Step 2 complete.

---

## 14. Files NOT Modified by this Audit

This audit is **read-only**. The following files were NOT modified:

- ❌ Any code file in `src/customer_segmentation/`
- ❌ Any config file in `configs/`
- ❌ Any artifact in `data/processed/` or `data/raw/`
- ❌ Any report in `reports/`
- ❌ Any existing documentation file (AGENTS.md, README.md, FE-*.md, EPIC-*.md, EXP-*.md)
- ❌ Any ADR in `docs/decisions/`
- ❌ Any test file in `tests/`

Only NEW file created:
- ✅ `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` (this file)

Per AGENTS.md §2.11 — no commit, no push, no PR performed.

---

## 15. Provenance

Tất cả số liệu trong tài liệu này được verify trực tiếp từ:

- `docs/research/review/FULL_RESEARCH_READINESS_AUDIT_FE01_EXP05.md` — parent audit
- `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md` — pending decisions inventory
- `docs/research/review/EXP01_EXP05_REVIEW_OVERVIEW.md` — review overview
- `docs/research/review/MENTOR_REVIEW_FORM_EXP01_EXP05.md` — mentor review template
- `docs/research/review/EXP01_EXP02_RESULTS_REVIEW.md` — EXP-01/02 review
- `docs/research/review/EXP03_HYPERPARAMETER_REVIEW.md` — EXP-03 review
- `docs/research/review/EXP04_PREPROCESSING_FEATURE_REVIEW.md` — EXP-04 review
- `docs/research/review/EXP05_REPRODUCIBILITY_STABILITY_REVIEW.md` — EXP-05 review
- `docs/research/FE05_Customer_Feature_Engineering.md` — FE-05 doc
- `docs/research/FE06_Transformation_Final_Dataset.md` — FE-06 doc
- `docs/decisions/0001-primary-dataset-uci-online-retail.md` — ADR-0001
- `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md` — ADR-0002
- `AGENTS.md` — global rules
- `README.md` — project overview
- `configs/clustering.yaml` — clustering config
- `src/customer_segmentation/clustering/registry.py` — algorithm registry
- `src/customer_segmentation/clustering/kmedoids.py` — K-Medoids placeholder

No data invented. No methodology decision imposed. All recommendations require Mentor approval.

---

**METHODOLOGY_RESOLUTION_PROPOSAL: COMPLETED.**

**Status:** 🟡 AWAITING MENTOR REVIEW.

**No code/config/artifact modification.** No commit. No push. No PR.

**Created:** 2026-09-22

**Auditor:** AI Agent (read-only analysis)

**Awaiting:** Mentor decision on Step 1 (algorithm scope + RQ definitions + RFM-only).
