# RFM-Only Materialization — Future Work Plan

> **Status:** FUTURE_WORK (not in current research scope)
> **Date:** 2026-09-22
> **Source:** ADR-0004 (RQ2 reformulation)
> **Owner:** Mentor / future researcher

---

## Context

The original RQ2 question ("Does including extended behavioral features (RFM Extended, 14 features) improve clustering quality compared to using only the RFM core features (Recency, Frequency, Monetary)?") requires a RFM-only artifact that does not currently exist in the repository.

During the EPIC-07 / EPIC-08 methodology lock, RQ2 was reformulated to:

> **RQ2 (reformulated):** How does preprocessing strategy affect clustering quality under a fixed customer-level feature representation?

This reformulated RQ2 is answerable with the existing EXP-04 Family B evidence (6 preprocessing scenarios × 5 repeats = 30 runs).

The original RFM-only comparison is documented as future work.

---

## What RFM-Only Materialization Would Require

### Feature Definitions

RFM-only artifact = only 3 features:

| Feature | Definition | Source |
|---|---|---|
| `Recency` | Days from `LastPurchaseDate` to `ReferenceDate` | Same as current FE-06 |
| `Frequency` | `nunique(InvoiceNo)` (FREQ-01) | Same as current FE-06 |
| `Monetary` | `MonetarySigned` = `sum(LineRevenue)` | Same as current FE-06 |

### Implementation Steps

| # | Step | Details | Estimated Effort |
|---|---|---|---|
| 1 | Write ADR | `docs/decisions/0005-rfm-only-materialization.md` | 1 day |
| 2 | Implement pipeline | New function in `src/customer_segmentation/transformation/` — read 3 features from `customer_candidates.parquet`, apply independent FE-06 C7 pipeline (fit on 3 features only) | 1-2 days |
| 3 | Tests | `tests/test_pipeline_rfm_only.py` (~5-10 tests) | 1 day |
| 4 | Config | Update `configs/transformation.yaml` with RFM-only entry | 1 hour |
| 5 | Execute | Generate `data/processed/final_clustering_dataset_rfmonly.parquet` | 1 hour |
| 6 | Verify | SHA-256, shape (4371, 3), no NaN, no Inf | 1 hour |
| 7 | EXP-04 Family A | 6 scenarios × 5 repeats = 30 runs | 1-2 days |
| 8 | Update RQ2 | Revert RQ2 to original framing (RFM-only vs RFM Extended) | 1 day |
| 9 | Reports | Update RQ2 section in methodology docs and thesis | 1 day |
| **Total** | | | **~1-2 weeks** |

### Key Constraints

1. **Independent preprocessing pipeline**: RFM-only must have its own Yeo-Johnson + RobustScaler fit (fit on 3 features only; do NOT reuse FE-06 C7 lambda values from 14-feature fit).
2. **Same ReferenceDate**: `2011-12-10T12:50:00` (same as FE-05/FE-06).
3. **Same Frequency definition**: `nunique(InvoiceNo)` (FREQ-01, current default).
4. **Same Monetary definition**: `MonetarySigned` (current default).
5. **READ-ONLY input**: `customer_candidates.parquet` SHA unchanged.
6. **Separate artifact**: `final_clustering_dataset_rfmonly.parquet` (NOT overwrite `final_clustering_dataset.parquet`).
7. **No rerun of FE-01 through FE-06**: RFM-only derivation is downstream from FE-05 candidates.

### EXP-04 Family A Scenario Matrix

Same as Family B (6 full-matrix scenarios):

| Scenario | Transformation | Scaling | Role |
|---|---|---|---|
| A-S01 | none | none | A baseline |
| A-S02 | none | standard | Candidate |
| A-S03 | none | minmax | Candidate |
| A-S04 | none | robust | Candidate |
| A-S05 | yeo_johnson | standard | Candidate |
| A-S06 | yeo_johnson | robust | Candidate |

Controls: K-Means, K=4, median imputation, seed=42.

Total: 30 runs.

### Expected Outcomes

If RFM-only is materialized and Family A executed:

- RFM-only metrics for each scenario (silhouette, DBI, CH, WCSS).
- Cross-comparison: RFM-only vs RFM Extended for each scenario.
- Δ-metric (difference in quality metrics between RFM-only and RFM Extended).
- ARI/AMI between RFM-only clustering and RFM Extended clustering for same customer set.

### When to Decide

This is a **mentor decision**. If a thesis reviewer or publication review requires the RFM-only comparison, this plan can be executed. Until then, it is future work.

---

## Checklist

- [ ] Write `docs/decisions/0005-rfm-only-materialization.md` ADR
- [ ] Implement `src/customer_segmentation/transformation/rfm_only_pipeline.py`
- [ ] Add `configs/transformation.yaml` entry for RFM-only
- [ ] Write `tests/test_pipeline_rfm_only.py`
- [ ] Execute pipeline: `final_clustering_dataset_rfmonly.parquet`
- [ ] Verify SHA-256, shape, no NaN, no Inf
- [ ] Run EXP-04 Family A (30 runs)
- [ ] Update `docs/methodology/research_questions.md` RQ2 section
- [ ] Update ADR-0004 with RQ2 completion status
- [ ] Update thesis / paper with RFM-only evidence

---

## References

- ADR-0004: `docs/decisions/0004-research-questions.md`
- FE-06 documentation: `docs/research/FE06_Transformation_Final_Dataset.md`
- EXP-04 review: `docs/research/review/EXP04_PREPROCESSING_FEATURE_REVIEW.md`
