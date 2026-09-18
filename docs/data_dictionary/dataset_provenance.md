# Dataset Provenance

This document records the **provenance** of every raw dataset currently
present in the repository. It is a **structural reference** — it
records only what has been verified outside the data itself (file
existence, file format, size, SHA-256, source URL, license). It does
**not** record any research statistics (row counts, customer counts,
date ranges, distributions, etc.); those belong to FE-01 (Raw Dataset
Audit) and later stages.

If a value in the table below is **`Chưa xác minh`**, it means the
information has not been verified from the official source. Do **not**
fill in research estimates here — create an ADR instead.

## Summary table

| Dataset               | Role    | Local Path                                       | Actual Filename           | File Size (bytes) | File Size (human) | SHA-256                                                              | Source                                                                                                  | License    | Status                                |
| --------------------- | ------- | ------------------------------------------------ | ------------------------- | ----------------- | ----------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------- |
| UCI Online Retail     | Primary | `data/raw/primary/`                              | `Online Retail.xlsx`      | 23,715,344        | ≈ 23 MB           | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`   | UCI Machine Learning Repository — <https://archive.ics.uci.edu/dataset/352/online+retail> (verified 2026-09-18) | CC BY 4.0  | Verified (filename differs from canonical, see Notes) |
| UCI Online Retail II  | Backup  | `data/raw/backup/`                               | `online_retail_II.xlsx`   | 45,622,278        | ≈ 44 MB           | `bcbe73b35f5b7babf197cb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`   | UCI Machine Learning Repository — <https://archive.ics.uci.edu/dataset/502/online+retail+ii> (verified 2026-09-18) | CC BY 4.0  | Verified                              |

### Identifiers

| Dataset               | UCI Dataset ID | DOI                                                  |
| --------------------- | -------------- | --------------------------------------------------- |
| UCI Online Retail     | 352            | Article DOI: `10.1057/dbm.2012.17`. UCI dataset DOI: Chưa xác minh trực tiếp từ trang UCI. |
| UCI Online Retail II  | 502            | `10.24432/C5CG6D` (verified from UCI citation block) |

### File format check

| Dataset               | `file` command output                |
| --------------------- | ------------------------------------ |
| UCI Online Retail     | `Microsoft Excel 2007+`              |
| UCI Online Retail II  | `Microsoft Excel 2007+`              |

### File on-disk mtime (filesystem metadata, not provenance)

| Dataset               | Filesystem mtime          |
| --------------------- | ------------------------- |
| UCI Online Retail     | `2023-05-22 15:20:26 +07:00` |
| UCI Online Retail II  | `2023-05-22 15:20:22 +07:00` |

The mtime reflects when the file landed on this machine. It is **not**
a download timestamp; the actual download date for these copies is
**Chưa xác minh** at the team level.

## Verification commands

The values in this file were obtained with the following commands,
executed on 2026-09-18 from the repository root. They are
**non-mutating** and may be re-run by any reviewer.

```bash
# Format check
file "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# Size
du -b "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# SHA-256
sha256sum "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# Git-ignore check
git check-ignore -v "data/raw/primary/Online Retail.xlsx"
git check-ignore -v "data/raw/backup/online_retail_II.xlsx"
```

## Git safety

Both files are excluded from version control by `.gitignore` rule
`/data/raw/**`. The corresponding `.gitkeep` placeholders in
`data/raw/`, `data/raw/primary/`, and `data/raw/backup/` remain
tracked so the directory layout is preserved.

| File                                       | `git check-ignore` exit | Status |
| ------------------------------------------ | ----------------------- | ------ |
| `data/raw/primary/Online Retail.xlsx`      | 0 (ignored)             | PASS   |
| `data/raw/backup/online_retail_II.xlsx`    | 0 (ignored)             | PASS   |
| `data/raw/primary/.gitkeep`                | 1 (tracked)             | PASS   |
| `data/raw/backup/.gitkeep`                 | 1 (tracked)             | PASS   |

## Notes

- **Canonical filename mismatch (Primary only)**:
  `configs/dataset.yaml` declares the canonical primary filename as
  `online_retail.xlsx`, but the actual file on disk is
  `Online Retail.xlsx`. The file has **not** been renamed. This will
  be reconciled by an ADR during the dataset audit (FE-01).
- **Filename agreement (Backup)**: the backup file
  `online_retail_II.xlsx` already matches the canonical name in
  `configs/dataset.yaml`.
- **License interpretation**: CC BY 4.0 permits sharing and adaptation
  for any purpose with appropriate credit. This **does not** imply that
  raw data should be committed to the repository — raw data stays
  local and git-ignored per the project's data-privacy rules.
- **What is NOT in this file**: row counts, customer counts, transaction
  counts, missing-value, duplicate, or outlier counts, data types,
  date ranges, and any other descriptive statistics. Those belong to
  FE-01 and must not be added here.

## Related ADRs

- `docs/decisions/0001-primary-dataset-uci-online-retail.md`
- `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md`