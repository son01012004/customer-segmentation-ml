# EXP-01 → EXP-05 Pending Decisions

> **Tổng hợp TẤT CẢ pending / deferred / research decisions từ EXP-01 đến EXP-05.**
> Mỗi item dùng format chuẩn với cột `Mentor Decision` để trống để Mentor / team điền.
> KHÔNG tự chọn phương án. KHÔNG tự quyết định.

---

## Cách dùng file này

- Mỗi nhóm (A → K) gom các decision liên quan đến một trục methodology.
- Cột `Status` lấy từ reports gốc (pending_review.json, manifest, analysis.md).
- Cột `Evidence` chỉ đến file / metric / sha cụ thể trong repo.
- Cột `Options / Considerations` liệt kê các phương án khả thi.
- Cột `Mentor Decision` **ĐỂ TRỐNG** để Mentor / team điền.

---

## A. Dataset / preprocessing

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| FE-06-DATASET-01 | FE-06 working dataset version = `FE06-v1.0` (yeo_johnson + robust + median, working default C7) | `WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING` | `docs/research/FE06_Transformation_Final_Dataset.md` §1; `reports/fe06/fe06_run.json` | C7 (current); alternative preprocessing configs C0/C1/C2/C3/C6 (tested in EXP-04) | |
| FE-06-DATASET-02 | Promote `FE06-v1.0` thành `RESEARCH_APPROVED_FINAL`? | PENDING | FE-06 doc §1 "Dataset này KHÔNG phải final approved clustering dataset" | Promote; Keep WORKING_ASSUMPTION; alternate dataset version | |
| EXP04-IMP-01 | Median imputation với FE-06 C7 fitted values (CONTROLLED_REFERENCE_IMPUTATION) | PENDING_REVIEW | `reports/exp04/exp04_pending_review.json` | Median (current); Mean; KNN; Iterative | |
| EXP04-TR-01 | log1p NOT included in EXP-04 scenario matrix (not full-matrix comparable) | PENDING_REVIEW | `reports/exp04/exp04_pending_review.json` | Add log1p; keep exclusion; use only yeo_johnson | |

---

## B. Feature engineering (FE-04, FE-05)

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| FE05-FEATURES-01 | 14 features RFM Extended (Recency, Frequency, Monetary, ..., ReturnRate) | TECHNICALLY_IMPLEMENTED | `docs/research/FE05_Customer_Feature_Engineering.md`; `reports/fe05/feature_eligibility.csv` | Keep 14 features; alternate feature subset | |
| FE05-MONETARY-01 | Monetary definition (current choice) | TECHNICALLY_IMPLEMENTED | `reports/fe05/monetary_definition_comparison.csv` | Multiple definitions compared; current selected | |
| FE05-FREQUENCY-01 | Frequency variants (current choice) | TECHNICALLY_IMPLEMENTED | `reports/fe05/frequency_variants_comparison.csv` | Multiple variants compared; current selected | |
| FE05-QUANTITY-01 | Quantity variants (current choice) | TECHNICALLY_IMPLEMENTED | `reports/fe05/quantity_variants_comparison.csv` | Multiple variants compared; current selected | |
| FE05-VARIANCE-01 | Feature variance analysis (current threshold) | TECHNICALLY_IMPLEMENTED | `reports/fe05/variance_analysis.csv` | Current threshold; alternate threshold | |

---

## C. Feature set (RQ2)

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| **EXP04-FS-01** | RFM-only dataset does not exist → Family A DEFERRED | DEFERRED / PENDING_FE06_MATERIALIZATION | `reports/exp04/exp04_pending_review.json`; `reports/exp04/exp04_deferred.json` | Materialize RFM-only artifact (FE-06 ADR); keep RFM Extended only; drop RQ2 | |
| **EXP04-FS-02** | FE-06 ADR for RFM-only materialization | PENDING_REVIEW | `reports/exp04/exp04_pending_review.json` | Author ADR; defer; cancel | |
| **EXP04-FS-03** | EXP-04-v1 does not claim RQ2 completeness for feature representation | PENDING_REVIEW | `reports/exp04/exp04_pending_review.json` | Accept; rerun EXP-04 after RFM-only materialized | |
| EXP02-FS-01 | EXP-02 runs on RFM Extended only (RFM-only not present) | PENDING_REVIEW (FE-06 ADR needed) | `reports/exp02/exp02_manifest.json` `pending_review_notes` | Same as EXP04-FS-02 | |
| EXP03-FS-01 | EXP-03 runs on RFM Extended only (RFM-only not present) | PENDING_REVIEW (FE-06 ADR needed) | `reports/exp03/exp03_manifest.json` `pending_review_notes` | Same as EXP04-FS-02 | |

---

## D. Cluster count (K)

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| **EXP02-KRNG-01** | K range = [2, 10], step=1 | WORKING_ASSUMPTION | `reports/exp02/exp02_pending_review.json` (manifest); `docs/research/EXP02_cluster_number_PLAN.md` §3.1 | Keep [2, 10]; extend to [2, 15]; narrow to [2, 8]; alternate step | |
| EXP02-K-01 | K candidates reused in EXP-03 (controlled reuse of EXP-02 evidence) | TECHNICALLY_IMPLEMENTED | `reports/exp03/exp03_manifest.json` `pending_review_notes` | Accept reuse; rerun K-sweep in EXP-03 | |
| EXP04-K-01 | K=4 (CONTROLLED_REFERENCE_K); no K-sweep | PENDING_REVIEW | `reports/exp04/exp04_pending_review.json` | Keep K=4; allow K from EXP-02 candidates | |
| EXP01-K-01 | EXP-01 baseline K=4 across all algorithms | TECHNICALLY_IMPLEMENTED (working default) | `reports/exp01/exp01_initial_baseline.md`; `configs/exp01_baseline.yaml` | Keep K=4; allow EXP-02 candidate K | |
| EPIC08-K-01 | EPIC-08 stability analysis sử dụng K nào (single K hay multiple K)? | PENDING | (chưa có plan EPIC-08) | EXP-01 K=4; EXP-02 candidate K; full K grid | |

---

## E. Hyperparameter selection

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EXP03-SP-01 | Per-algorithm search space (candidate values) | WORKING_ASSUMPTION | `reports/exp03/exp03_manifest.json` `pending_review_notes` | Keep; extend; narrow | |
| **EXP03-SEL-01** | Selection protocol: silhouette (primary) → DBI → CH | WORKING_ASSUMPTION | `reports/exp03/exp03_hyperparameter_analysis.md` (Research Review & Finalize §1) | Keep; add CH as primary; add runtime as tiebreaker; add stability as tiebreaker | |
| **EXP03-SEL-02** | Agglomerative Stage C K=3 linkage=average — known chaining artifact; status `WORKING_SELECTED` per protocol nhưng KHÔNG final validated | TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING | `reports/exp03/exp03_hyperparameter_analysis.md` (Research Review §2); CH=77.15 vs alternatives CH=5029.13, 5081.40 | Accept WORKING_SELECTED; reject Stage C linkage=average; require CH threshold | |
| **EXP03-KM-01** | K-Means Stage C 3-way tie (silhouette/DBI/CH/WCSS identical đến 17 chữ số thập phân); status `TIED_WORKING_SELECTED`; KHÔNG ép chọn 1 config | TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING | `reports/exp03/exp03_hyperparameter_analysis.md` (Research Review §3) | Keep tie; select one by runtime; resolve in EPIC-08 via stability | |
| EXP03-INT-01 | Selected interactions Stage C là small curated subset | TECHNICALLY_IMPLEMENTED | `reports/exp03/exp03_manifest.json` | Keep curated; expand to full grid | |
| EPIC08-HYPER-01 | EPIC-08 stability analysis chạy trên EXP-01 working defaults hay EXP-03 working selections? | PENDING | (chưa có plan EPIC-08) | EXP-01 defaults; EXP-03 selections; both | |

---

## F. Evaluation metrics

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EXP01-MET-01 | Noise exclusion policy (internal metrics + WCSS exclude noise) | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.3; `reports/exp01/exp01_initial_baseline.md` | Keep exclusion; include noise with separate metric | |
| EXP01-MET-02 | WCSS convention: arithmetic centroid từ hard labels | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.2 | Keep; use GMM Gaussian mean / FCM fuzzy centroid (NOT recommended) | |
| EXP01-MET-03 | n_repeat=5 cho runtime measurement | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §3.3 | Keep 5; increase to 10; decrease to 3 | |
| EXP01-MET-04 | Metric applicability status schema (4 statuses + reason) | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.1 | Keep schema; simplify; expand | |
| EXP01-MET-05 | All-noise DBSCAN: silhouette → NOT_APPLICABLE / ALL_NOISE | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.1 | Keep; alternate (e.g. return NaN) | |
| EXP01-MET-06 | Single-cluster edge case: silhouette → NOT_APPLICABLE / SINGLE_CLUSTER | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.1 | Keep; alternate | |
| EPIC08-METRIC-01 | EPIC-08 có cần thêm metric (vd. ARI/AMI, Davies-Bouldin normalized) không? | PENDING | (chưa có plan EPIC-08) | Keep 4 metrics; add ARI/AMI for stability; add additional | |

---

## G. Reproducibility / stability

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EXP05-BLK-01 | Block R = reproducibility verification, NOT stability analysis | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json`; `docs/research/EXP05_stability_reproducibility_PLAN.md` §4 | Keep as reproducibility; expand Block R to include ARI | |
| **EXP05-BLK-02** | Block S chỉ cho 3 algorithms có random axis (K-Means + GMM + FCM) | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep 3 algos; add Agglomerative + DBSCAN with random_state override | |
| **EXP05-BLK-03** | Block N = in-memory perturbation; sigma=[0, 0.01, 0.05]×std | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep grid; extend to [0, 0.01, 0.05, 0.1, 0.2]; narrow | |
| **EXP05-SEED-01** | Seeds for Block S = [42, 7, 123, 2024, 1729] | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep; alternate list; expand to 10 seeds | |
| **EXP05-PERT-01** | Perturbation distribution = Gaussian, column-wise std scaled | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep Gaussian; test uniform; test adversarial | |
| **EXP05-PERT-02** | sigma=0 sanity run must reproduce EXP-01 baseline (cluster_labels identical) | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep sanity check; allow tolerance | |
| EXP05-ART-01 | Labels artifact schema (run_id, block, algorithm, seed, sigma, perturbation_seed, repeat_index, CustomerID, cluster_label) | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep schema; expand (add soft_probabilities, soft_membership) | |
| EXP05-AGG-01 | Aggregate uses mean/std/min/max/CV; no composite scoring | TECHNICALLY_IMPLEMENTED | `reports/exp05/exp05_pending_review.json` | Accept; alternate aggregation | |
| **EXP05-DEC-01** | Decision status taxonomy (REPRODUCIBILITY_VERIFIED / REPRODUCIBILITY_FAILED / STABILITY_EVIDENCE_GENERATED / PERTURBATION_EVIDENCE_GENERATED / SIGMA_ZERO_BASELINE_MATCH / SIGMA_ZERO_BASELINE_MISMATCH / PENDING_REVIEW) | WORKING_ASSUMPTION | `reports/exp05/exp05_pending_review.json` | Keep; expand; simplify | |
| EPIC08-STAB-01 | EPIC-08 stability analysis methodology (ARI/AMI computation, Hungarian matching, statistical tests, confidence intervals) | PENDING | (chưa có plan EPIC-08) | Multiple alternatives — cần plan | |
| EPIC08-STAB-02 | EPIC-08 confidence interval method (bootstrap, percentile, ...) | PENDING | (chưa có plan EPIC-08) | Bootstrap; percentile; Bayesian | |
| EPIC08-STAB-03 | EPIC-08 statistical test (paired t-test, Wilcoxon, ...) | PENDING | (chưa có plan EPIC-08) | Parametric; non-parametric; multiple testing correction | |

---

## H. DBSCAN noise handling

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EXP01-MET-01 | DBSCAN noise (-1) excluded from internal metrics + WCSS | PENDING_REVIEW (FE-06 mirror) | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.3 | Keep exclusion; include noise in metrics with separate status | |
| EXP01-MET-05 | All-noise DBSCAN: silhouette → NOT_APPLICABLE / ALL_NOISE | PENDING_REVIEW | `docs/research/EXP01_baseline_experiment_PLAN.md` §4.1 | Keep; return NaN | |
| EXP02-DBSCAN-01 | DBSCAN contributes only via 1 diagnostic entry (no K-sweep) | WORKING_ASSUMPTION | `reports/exp02/exp02_manifest.json` | Keep diagnostic only; add eps-sweep | |
| EXP04-DBSCAN-01 | DBSCAN noise ratio 0.7268 ở baseline (eps=0.5, min_samples=5) — chấp nhận? | PENDING_REVIEW | `reports/exp01/exp01_initial_baseline.md` (DBSCAN row); `reports/exp04/exp04_manifest.json` (not directly in scope) | Keep default; tune eps/min_samples for EPIC-08 | |
| EPIC08-DBSCAN-01 | EPIC-08 xử lý DBSCAN noise ratio 0.7268 như thế nào? | PENDING | (chưa có plan EPIC-08) | Exclude noise points from analysis; analyze noise separately | |

---

## I. Runtime protocol

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EXP01-RUNTIME-01 | Runtime đo algorithm execution only (KHÔNG bao gồm metric computation / artifact writing) | TECHNICALLY_IMPLEMENTED | `docs/research/EXP01_baseline_experiment_PLAN.md` §3 | Accept; include full wall time | |
| EXP01-RUNTIME-02 | Metric computation time recorded riêng (`metrics.runtime["metric_computation"]`) | TECHNICALLY_IMPLEMENTED | `docs/research/EXP01_baseline_experiment_PLAN.md` §3.4 | Accept; drop metric computation time | |
| EXP01-RUNTIME-03 | Artifact/report writing time excluded khỏi runtime | TECHNICALLY_IMPLEMENTED | `docs/research/EXP01_baseline_experiment_PLAN.md` §3.1 | Accept; include total wall time | |
| EPIC08-RUNTIME-01 | EPIC-08 runtime comparison methodology | PENDING | (chưa có plan EPIC-08) | Mean; median; percentile; with CI | |

---

## J. Business interpretation

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EPIC08-BIZ-01 | EPIC-08 có cần business validation (qua segment profile / RFM heatmap) không? | PENDING | (chưa có plan EPIC-08) | EPIC-08 only metrics; EPIC-08 + EPIC-09 collaboration | |
| EPIC09-NAMING-01 | Segment naming ("Champions", "Loyal", ...) | PENDING | (EPIC-09 chưa có plan) | RFM-based naming; data-driven naming; no naming | |
| EPIC08-CLAIM-01 | EPIC-08 có thể claim "most stable algorithm" / "best stability" không? | PENDING | AGENTS.md §2.5 cấm "best" | Yes với methodology; No (cấm best); Yes chỉ với caveat | |
| EXP-METRIC-BIZ-01 | Internal metrics có ý nghĩa business không? (silhouette cao = clusters tốt cho business?) | PENDING | AGENTS.md §2.5 cấm tự mapping | No mapping; require business validation; require EPIC-09 collaboration | |

---

## K. EPIC-08 methodology (general)

| ID | Decision / Question | Current Status | Evidence | Options / Considerations | Mentor Decision |
|----|---------------------|----------------|----------|---------------------------|-----------------|
| EPIC08-PLAN-01 | EPIC-08 plan có được phép dựa trên EXP-05 labels artifact không? | PENDING | `reports/exp05/exp05_cluster_labels.parquet` (327825 rows) | Yes (artifact đã sinh ra); require additional evidence | |
| EPIC08-CROSS-ALG-01 | EPIC-08 có được cross-algorithm ranking / "most stable algorithm" không? | PENDING | AGENTS.md §2.5 | Yes sau full evaluation; No (chỉ evidence); Yes với caveat | |
| EPIC08-WORKING-01 | EPIC-08 chạy trên EXP-01 working defaults hay EXP-03 working selections? | PENDING | (chưa có plan EPIC-08) | EXP-01 defaults; EXP-03 selections; both | |
| EPIC08-INPUT-01 | EPIC-08 input là `final_clustering_dataset.parquet` (FE-06) hay `customer_candidates.parquet` (FE-05)? | PENDING | EXP-04 uses FE-05 | FE-06 output (mirror EXP-05); FE-05 output (mirror EXP-04); both | |
| EPIC08-VIZ-01 | EPIC-08 research comparison visualization (silhouette plot, comparison dashboard) có scope gì? | PENDING | EPIC-06 contract §9.2 | Multiple types; specific subset | |
| EPIC08-FAMILY-A-01 | EPIC-08 có cần EXP-04 Family A evidence trước khi chạy không? | PENDING | Family A DEFERRED | Yes (block EPIC-08); No (EPIC-08 có thể chạy trên RFM Extended) | |
| EPIC08-PROFILE-01 | EPIC-08 có overlap với EPIC-09 customer profiling không? | PENDING | EPIC-06 contract §7.3-§7.4 | No overlap; some collaboration; EPIC-08 defers segment analysis to EPIC-09 | |

---

## Phụ lục — Trạng thái decisions chưa được resolve

Tổng cộng có **~60+ decisions** ở trạng thái pending / WORKING_ASSUMPTION / TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING / DEFERRED.

Phân loại theo status:

| Status | Count (xấp xỉ) |
|--------|----------------|
| WORKING_ASSUMPTION | ~17 |
| PENDING_REVIEW | ~25 |
| DEFERRED | 1 (Family A) |
| TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING | 2 (EXP03-SEL-02, EXP03-KM-01) |
| TECHNICALLY_IMPLEMENTED (engineering, accepted) | ~15 |

(Count là ước lượng dựa trên `pending_review.json` và manifest analysis. Count chính xác cần verify từng file.)

---

## Phụ lục — Cross-reference các report

| Experiment | Pending review source |
|------------|----------------------|
| EXP-01 | `docs/research/EXP01_baseline_experiment_PLAN.md` §10 (8 items) |
| EXP-02 | `reports/exp02/exp02_manifest.json` `pending_review_notes` (6 items) |
| EXP-03 | `reports/exp03/exp03_manifest.json` `pending_review_notes` (7 items) |
| EXP-04 | `reports/exp04/exp04_pending_review.json` (8 items) |
| EXP-05 | `reports/exp05/exp05_pending_review.json` (9 items) |

Một số EXP-01/02/03 pending_review_notes nằm trong `manifest.json` thay vì file `pending_review.json` riêng.

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
