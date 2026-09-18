# Data Dictionary

The full data dictionary will be created **after** the raw dataset audit
(notebooks/01_dataset_audit) and the FE-01 feature engineering stage.

It will document, for both the primary and backup datasets:

- **Transactional-level columns**: name, dtype, description, allowed
  value range, missing-value policy.
- **Customer-level feature columns** produced by the feature engineering
  pipeline (RFM + extended behavioral features): formula, units, allowed
  range.
- **Clustering-output columns** (e.g. cluster label, cluster probability).

## Status

| Section                                | Owner | Status   |
| -------------------------------------- | ----- | -------- |
| Raw transactional columns (primary)    | TBD   | Pending  |
| Raw transactional columns (backup)     | TBD   | Pending  |
| Customer-level feature columns (FE-01) | TBD   | Pending  |
| Clustering-output columns              | TBD   | Pending  |

Until those sections are filled, do **not** reference column semantics
in any downstream document without an explicit ADR in `../decisions/`.