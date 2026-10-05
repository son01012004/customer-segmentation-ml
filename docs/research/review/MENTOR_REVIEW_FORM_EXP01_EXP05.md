# Mentor Review Form — EXP-01 → EXP-05

> **Form review để Mentor / nghiên cứu viên điền.**
> Vui lòng điền trực tiếp vào file này và commit.
> Để trống nếu chưa có quyết định.
> Ngày review: ___________

---

## 1. Overall assessment

Đánh dấu vào ô phù hợp:

- [ ] Technical implementation acceptable
- [ ] Technical implementation needs revision
- [ ] Research methodology acceptable
- [ ] Research methodology needs revision

**Comments (overall):**

_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## 2. EXP-01 review

### 2.1. Technical implementation

- [ ] PASS — implementation đúng, tests pass, lint clean, format clean
- [ ] NEEDS REVISION — cần fix technical issues

**Comments:**
_________________________________________________________________

### 2.2. Methodology

- [ ] Working defaults acceptable (kmeans K=4 / agglomerative ward / dbscan eps=0.5 min_samples=5 / gmm full / fcm m=2.0)
- [ ] Need revision

**Comments:**
_________________________________________________________________

### 2.3. Noise exclusion policy

- [ ] Accept (internal metrics + WCSS exclude DBSCAN noise)
- [ ] Reject — need alternative

**Comments:**
_________________________________________________________________

### 2.4. WCSS convention

- [ ] Accept (arithmetic centroid từ hard labels)
- [ ] Reject — need alternative

**Comments:**
_________________________________________________________________

### 2.5. Metric status schema

- [ ] Accept (VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING + reason)
- [ ] Reject — need alternative

**Comments:**
_________________________________________________________________

### 2.6. Other decisions

_________________________________________________________________
_________________________________________________________________

---

## 3. EXP-02 review

### 3.1. Technical implementation

- [ ] PASS — implementation đúng, tests pass
- [ ] NEEDS REVISION — cần fix technical issues

**Comments:**
_________________________________________________________________

### 3.2. K range

- [ ] Accept [2, 10] step=1
- [ ] Extend to: ___________
- [ ] Narrow to: ___________

**Comments:**
_________________________________________________________________

### 3.3. Candidate heuristic constants

- [ ] Accept (top_n=3, drop_ratio=0.2, min_agreement=2)
- [ ] Modify: ___________

**Comments:**
_________________________________________________________________

### 3.4. Disagreement between indicators

- [ ] Accept protocol hiện tại (KHÔNG tự resolve disagreement)
- [ ] Need protocol adjustment

**Comments:**
_________________________________________________________________

### 3.5. DBSCAN diagnostic

- [ ] Accept (1 diagnostic entry, no K-sweep)
- [ ] Need eps-sweep riêng cho DBSCAN

**Comments:**
_________________________________________________________________

### 3.6. RFM-only gap

- [ ] EXP-02 chỉ chạy trên RFM Extended acceptable (RQ2 PARTIAL)
- [ ] Need RFM-only artifact materialized first (FE-06 ADR)

**Comments:**
_________________________________________________________________

### 3.7. Other decisions

_________________________________________________________________
_________________________________________________________________

---

## 4. EXP-03 review

### 4.1. Technical implementation

- [ ] PASS — implementation đúng, tests pass
- [ ] NEEDS REVISION

**Comments:**
_________________________________________________________________

### 4.2. Selection protocol

- [ ] Accept (silhouette primary → DBI → CH)
- [ ] Modify to: ___________

**Comments:**
_________________________________________________________________

### 4.3. K-Means 3-way tie (EXP03-KM-01)

- [ ] Accept `TIED_WORKING_SELECTED` (giữ status quo)
- [ ] Need tiebreaker khác
- [ ] Resolve in EPIC-08

**Comments:**
_________________________________________________________________

### 4.4. Agglomerative Stage C linkage=average (EXP03-SEL-02)

- [ ] Accept `WORKING_SELECTED` per protocol (CH=77.15 known disagreement)
- [ ] Reject Stage C linkage=average — require CH threshold
- [ ] Resolve in EPIC-08

**Comments:**
_________________________________________________________________

### 4.5. Per-algorithm working selections

- [ ] Accept (K-Means Stage C K=3 n_init=1; Agglomerative Stage C K=3 linkage=average; DBSCAN Stage B min_samples=10; GMM Stage B covariance_type=tied; FCM Stage C K=3 m=1.5)
- [ ] Modify: ___________

**Comments:**
_________________________________________________________________

### 4.6. Search space per-algorithm

- [ ] Accept current
- [ ] Extend to: ___________
- [ ] Narrow to: ___________

**Comments:**
_________________________________________________________________

### 4.7. Fuzzy C-Means m=1.5

- [ ] Accept (silhouette=0.6296; m=1.5 tiệm cận hard K-Means)
- [ ] Reject — require m ≥ 2.0
- [ ] Other: ___________

**Comments:**
_________________________________________________________________

### 4.8. Other decisions

_________________________________________________________________
_________________________________________________________________

---

## 5. EXP-04 review

### 5.1. Technical implementation

- [ ] PASS — implementation đúng, tests pass, determinism verified
- [ ] NEEDS REVISION

**Comments:**
_________________________________________________________________

### 5.2. Family A (Feature Set Sensitivity)

- [ ] Accept DEFERRED status (RQ2 PARTIAL)
- [ ] Need FE-06 ADR materialize RFM-only artifact
- [ ] Drop RQ2

**Comments:**
_________________________________________________________________

### 5.3. Controlled references

- [ ] Accept (K-Means, K=4, median imputation, seed=42)
- [ ] Modify: ___________

**Comments:**
_________________________________________________________________

### 5.4. log1p exclusion

- [ ] Accept (log1p NOT included)
- [ ] Need add log1p to scenario matrix

**Comments:**
_________________________________________________________________

### 5.5. Decision status taxonomy

- [ ] Accept (CANDIDATE_SCENARIO / TIED_SCENARIOS / PENDING_REVIEW / DEFERRED)
- [ ] Modify: ___________

**Comments:**
_________________________________________________________________

### 5.6. C0 silhouette artifact (raw data, no transform/scale)

- [ ] Accept description as-is
- [ ] Need explicit warning / clarification

**Comments:**
_________________________________________________________________

### 5.7. Other decisions

_________________________________________________________________
_________________________________________________________________

---

## 6. EXP-05 review

### 6.1. Technical implementation

- [ ] PASS — implementation đúng, tests pass, labels artifact schema correct
- [ ] NEEDS REVISION

**Comments:**
_________________________________________________________________

### 6.2. Block R (Reproducibility)

- [ ] Accept evidence (5/5 algorithms REPRODUCIBILITY_VERIFIED)
- [ ] Need additional verification

**Comments:**
_________________________________________________________________

### 6.3. Block S (Seed stability)

- [ ] Accept seeds [42, 7, 123, 2024, 1729]
- [ ] Need more seeds (vd. 10)
- [ ] Need to include Agglomerative + DBSCAN with random_state override

**Comments:**
_________________________________________________________________

### 6.4. Block N (Perturbation)

- [ ] Accept sigma_grid [0, 0.01, 0.05]
- [ ] Extend to: ___________
- [ ] Need more perturbation seeds

**Comments:**
_________________________________________________________________

### 6.5. Perturbation distribution

- [ ] Accept Gaussian
- [ ] Need test alternative distributions

**Comments:**
_________________________________________________________________

### 6.6. Labels artifact

- [ ] Accept schema và 327825 rows
- [ ] Need expand schema (vd. soft_probabilities, soft_membership)

**Comments:**
_________________________________________________________________

### 6.7. Decision status taxonomy

- [ ] Accept (REPRODUCIBILITY_VERIFIED / STABILITY_EVIDENCE_GENERATED / PERTURBATION_EVIDENCE_GENERATED / SIGMA_ZERO_BASELINE_MATCH / PENDING_REVIEW)
- [ ] Modify: ___________

**Comments:**
_________________________________________________________________

### 6.8. EXP-05 chỉ chạy trên EXP-01 working defaults

- [ ] Accept (EXP-03 working selections chưa được test cho stability)
- [ ] Need rerun EXP-05 với EXP-03 working selections

**Comments:**
_________________________________________________________________

### 6.9. Other decisions

_________________________________________________________________
_________________________________________________________________

---

## 7. Methodology decisions (cross-experiment)

### 7.1. Cluster-count methodology

- [ ] Accept EXP-02 13 candidates as input cho EPIC-08
- [ ] Need rerun K-sweep
- [ ] Other: ___________

### 7.2. Hyperparameter selection methodology

- [ ] Accept EXP-03 selection protocol (silhouette primary)
- [ ] Need revision: ___________

### 7.3. Metric selection

- [ ] 4 metrics (silhouette/DBI/CH/WCSS) acceptable cho EPIC-08
- [ ] Need add additional metrics (vd. ARI/AMI, normalized DBI)

### 7.4. DBSCAN noise handling

- [ ] Accept current policy (exclude noise from internal metrics + WCSS)
- [ ] Need alternative
- [ ] Need tune eps/min_samples before EPIC-08

### 7.5. Reproducibility vs stability vs robustness

- [ ] EXP-05 cung cấp đủ evidence (3 blocks) cho EPIC-08
- [ ] Need additional evidence
- [ ] Other: ___________

### 7.6. Seed sensitivity

- [ ] Accept Block S scope (3 algorithms × 5 seeds)
- [ ] Need expand

### 7.7. Preprocessing sensitivity

- [ ] EXP-04 6 scenarios enough cho EPIC-08
- [ ] Need additional scenarios

### 7.8. RFM vs RFM Extended

- [ ] EXP-04 Family A DEFERRED acceptable; EPIC-08 chỉ chạy RFM Extended
- [ ] Need RFM-only artifact materialized first

### 7.9. Whether/when RFM-only should be materialized

- [ ] Materialize before EPIC-08
- [ ] Defer to later EPIC
- [ ] Drop RQ2

### 7.10. Runtime evaluation protocol

- [ ] n_repeat=5 × 5 algorithms acceptable cho runtime comparison
- [ ] Need more repeats
- [ ] Other: ___________

### 7.11. Business validation boundary

- [ ] EPIC-08 chỉ metrics, business validation thuộc EPIC-09
- [ ] Need EPIC-08 + EPIC-09 collaboration
- [ ] Other: ___________

---

## 8. EPIC-08 readiness

Đánh dấu vào lựa chọn:

- [ ] **Ready for EPIC-08** — có thể bắt đầu implement EPIC-08 dựa trên evidence hiện có
- [ ] **EPIC-08 needs methodology revision first** — EPIC-08 plan cần revision trước
- [ ] **Additional experiments required** — cần chạy thêm experiments
- [ ] **Additional documentation required** — cần viết thêm tài liệu

### 8.1. Nếu additional experiments required, experiments nào?

_________________________________________________________________
_________________________________________________________________

### 8.2. Nếu additional documentation required, documentation gì?

_________________________________________________________________
_________________________________________________________________

### 8.3. EPIC-08 ownership questions

- ARI/AMI computation method: ___________
- Hungarian matching method: ___________
- Statistical test (paired t-test, Wilcoxon, ...): ___________
- Confidence interval method (bootstrap, percentile, ...): ___________
- Cross-algorithm comparison allowed: ___________
- "Most stable algorithm" claim allowed: ___________

---

## 9. Mentor comments

Không gian tự do cho Mentor:

_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## 10. Approval

| Field | Value |
|-------|-------|
| **Reviewer** | |
| **Date** | |
| **Decision** | APPROVE / APPROVE WITH REVISION / REJECT / DEFER |
| **Comments** | |

---

## Appendix — Quick reference

| Experiment | Total runs | Status |
|------------|-----------|--------|
| EXP-01 | 5 | TECHNICALLY_IMPLEMENTED |
| EXP-02 | 37 | TECHNICALLY_IMPLEMENTED |
| EXP-03 | 38 | TECHNICALLY_IMPLEMENTED |
| EXP-04 | 30 | TECHNICALLY_IMPLEMENTED (Family A DEFERRED) |
| EXP-05 | 75 | TECHNICALLY_IMPLEMENTED (raw evidence only) |
| **Tổng** | **185** | |

| Test summary | Result |
|--------------|--------|
| pytest tests/ | 1105/1105 PASS |
| pytest tests/test_exp0X_*.py | 208/208 PASS |
| ruff check . | PASS |
| black --check . | PASS |

| Input SHA | Value |
|-----------|-------|
| final_clustering_dataset.parquet (FE-06) | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| customer_candidates.parquet (FE-05) | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` |
| customer_metadata.parquet | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` |
| configs/clustering.yaml | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` |
| configs/exp05_*.yaml | `3dec62060a5a6d1c09443debc51802f6f321e91f7dbbd792962e9b519afcda9e` |

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
