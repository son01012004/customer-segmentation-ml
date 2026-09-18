# ADR-0002: Backup Dataset — UCI Online Retail II

## Status

Accepted

## Date

2026-09-18

## Task ID

DS-05 (Dataset Selection) + foundation provenance step

## Deciders

Repository foundation owner; review pending by project lead.

## Context

DS-05 selected a **backup** dataset alongside the primary
(UCI Online Retail, see ADR-0001) so that, if the primary file becomes
unavailable, corrupted, or restricted, the project can continue without
re-deciding the dataset question. The backup must come from the same
provider, have the same schema, and apply to the same research scope
(customer-level segmentation on transactional retail data).

This ADR records the **provenance** of the backup dataset and pins the
exact local file the team is working with. It does **not** record any
research statistics about the dataset; that work belongs to FE-01 (Raw
Dataset Audit) and later stages.

## Decision

The repository uses **UCI Online Retail II** as the backup dataset.

The local raw file is:

- **Path**: `data/raw/backup/online_retail_II.xlsx`
- **Verified by**: `file` command (Microsoft Excel 2007+)
- **Size**: 45,622,278 bytes (≈ 44 MB; UCI's own listing reports 43.5 MB)
- **SHA-256**: `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`
- **Provenance check date**: 2026-09-18

## Dataset Role

- **Role**: Backup
- **Initial unit of observation**: transaction-level
- **Modeling unit**: customer-level, after aggregation
- **Feature framework**: RFM + Extended Behavioral Features
- **Primary of this role**: UCI Online Retail (see ADR-0001)

## Provenance

- **Dataset name**: UCI Online Retail II
- **Source provider**: UCI Machine Learning Repository
- **Source URL**: <https://archive.ics.uci.edu/dataset/502/online+retail+ii>
  (verified by fetching the page on 2026-09-18; the URL resolves to
  the official UCI dataset entry and exposes the citation block)
- **UCI dataset ID**: 502
- **DOI**: `10.24432/C5CG6D` — verified directly from the UCI citation
  block on 2026-09-18: *"Chen, D. (2012). Online Retail II [Dataset].
  UCI Machine Learning Repository. <https://doi.org/10.24432/C5CG6D>"*
- **UCI donation date** (as shown on the dataset page): 2019-09-20
- **License**: **CC BY 4.0** (Creative Commons Attribution 4.0
  International). Verified directly from the UCI dataset page on
  2026-09-18: *"This dataset is licensed under a Creative Commons
  Attribution 4.0 International (CC BY 4.0) license."*
- **License redistribution note**: CC BY 4.0 permits sharing and
  adaptation for any purpose provided appropriate credit is given.
  This is a separate question from whether we redistribute the file
  inside this Git repository: **we do not** — raw data stays local and
  git-ignored (see Reproducibility below).
- **Download date**: Not recorded at the team level for this initial
  copy. The file's filesystem mtime is `2023-05-22 15:20:22 +07:00`.
  Future versions of this ADR should record the actual download date
  after each refresh.

## Filename Note (canonical vs. on-disk)

`configs/dataset.yaml` declares the canonical backup filename as
`online_retail_II.xlsx`. The actual file currently on disk is named
`online_retail_II.xlsx`, which already matches the canonical name.
No rename is needed.

## Reproducibility

- The raw dataset file is **not committed** to the Git repository.
  It is excluded by `.gitignore` rule `/data/raw/**`.
- `git check-ignore -v "data/raw/backup/online_retail_II.xlsx"`
  returns:
  `.gitignore:90:/data/raw/**   data/raw/backup/online_retail_II.xlsx`
- Each researcher's local copy must produce the same SHA-256
  (`bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`)
  for results to be comparable across machines.
- Any future re-download of the dataset must be reflected in this ADR
  with the new SHA-256, the new download date, and a short rationale
  recorded under "Notes".

## Notes

- This ADR records **only** what has been verified outside the data
  itself: file existence, file format, file size, SHA-256, and the
  source-page metadata.
- The following are **out of scope** for this ADR and belong to FE-01
  (Raw Dataset Audit) and later stages:
  - row counts, customer counts, transaction counts
  - missing-value, duplicate, and outlier counts
  - data types, date ranges, quantity/monetary distributions
  - any other descriptive statistics
- No "best" algorithm claim is implied by selecting this dataset.
- The primary dataset (UCI Online Retail) is recorded separately in
  ADR-0001.
- The backup dataset should only be used when the primary is
  unavailable. Any switch from primary to backup must itself be
  recorded as a new ADR.