# ADR-0001: Primary Dataset — UCI Online Retail

## Status

Accepted

## Date

2026-09-18

## Task ID

DS-05 (Dataset Selection) + foundation provenance step

## Deciders

Repository foundation owner; review pending by project lead.

## Context

The customer-segmentation research project needs a single authoritative
transactional dataset that supports customer-level aggregation for
RFM-style features. DS-05 selected **UCI Online Retail** as the
**primary** dataset and **UCI Online Retail II** as the **backup** dataset.
This ADR records the **provenance** of the primary dataset and pins the
exact file the team is working with. It does **not** record any
research statistics about the dataset; that work belongs to FE-01
(Raw Dataset Audit) and later stages.

## Decision

The repository uses **UCI Online Retail** as the primary dataset.

The local raw file is:

- **Path**: `data/raw/primary/Online Retail.xlsx`
- **Verified by**: `file` command (Microsoft Excel 2007+)
- **Size**: 23,715,344 bytes (≈ 23 MB)
- **SHA-256**: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`
- **Provenance check date**: 2026-09-18

## Dataset Role

- **Role**: Primary
- **Initial unit of observation**: transaction-level
- **Modeling unit**: customer-level, after aggregation
- **Feature framework**: RFM + Extended Behavioral Features
- **Backup of this role**: UCI Online Retail II (see ADR-0002)

## Provenance

- **Dataset name**: UCI Online Retail
- **Source provider**: UCI Machine Learning Repository
- **Source URL**: <https://archive.ics.uci.edu/dataset/352/online+retail>
  (verified by fetching the page on 2026-09-18; the URL resolves to the
  official UCI dataset entry)
- **UCI dataset ID**: 352
- **Article DOI** (the published paper this dataset accompanies):
  `10.1057/dbm.2012.17` — Daqing Chen, Sai Liang Sain, Kun Guo,
  *"Data mining for the online retail industry: A case study of RFM
  model-based customer segmentation using data mining"*, Journal of
  Database Marketing and Customer Strategy Management, Vol. 19, No. 3,
  pp. 197–208, 2012 (verified by web search on 2026-09-18).
- **UCI-assigned dataset DOI**: Chưa xác minh trực tiếp từ trang UCI
  ID 352. (The fetching tool returned only the variable table; the
  citation/DOI block was not visible in the rendered page. To be filled
  in after a manual check of the UCI page. Backup dataset ID 502 has a
  visible DOI `10.24432/C5CG6D` for reference.)
- **License**: **CC BY 4.0** (Creative Commons Attribution 4.0
  International). Verified by web search showing the UCI license footer
  for this dataset on 2026-09-18.
- **License redistribution note**: CC BY 4.0 permits sharing and
  adaptation for any purpose provided appropriate credit is given.
  This is a separate question from whether we redistribute the file
  inside this Git repository: **we do not** — raw data stays local and
  git-ignored (see Reproducibility below).
- **Download date**: Not recorded at the team level for this initial
  copy. The file's filesystem mtime is `2023-05-22 15:20:26 +07:00`.
  Future versions of this ADR should record the actual download date
  after each refresh.

## Filename Note (canonical vs. on-disk)

`configs/dataset.yaml` declares the canonical primary filename as
`online_retail.xlsx`. The actual file currently on disk is
`Online Retail.xlsx` (with capitalised first letters and a space). The
file has **not** been renamed** — the team lead will decide the canonical
filename policy as part of the dataset audit (FE-01). The mismatch is
recorded here for transparency and will be reconciled by an ADR once
the audit is complete.

## Reproducibility

- The raw dataset file is **not committed** to the Git repository.
  It is excluded by `.gitignore` rule `/data/raw/**`.
- `git check-ignore -v "data/raw/primary/Online Retail.xlsx"` returns:
  `.gitignore:90:/data/raw/**   data/raw/primary/Online Retail.xlsx`
- Each researcher's local copy must produce the same SHA-256
  (`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`)
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
- The backup dataset (UCI Online Retail II) is recorded separately in
  ADR-0002.