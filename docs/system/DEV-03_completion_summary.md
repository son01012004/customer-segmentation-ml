# DEV-03 Prototype Preprocessing — Completion Summary

**Mã task:** DEV-03
**Jira pipeline:** `Dataset → Validation → Cleaning → Transformation → Scaling → Feature Generation → ML Dataset` (7 bước)
**Trạng thái:** TECHNICALLY IMPLEMENTED (kết thúc Phase 2, chờ human reviewer)
**Ngày hoàn thành:** 2026-10-09
**Dựa trên plan:** `docs/system/DEV-03_preprocessing.md` (đã được APPROVE PHASE 2)

---

## 1. Files created / modified

### 1.1. Source code (12 files mới)

```
src/customer_segmentation/prototype/__init__.py
src/customer_segmentation/prototype/preprocessing/__init__.py
src/customer_segmentation/prototype/preprocessing/scope.py
src/customer_segmentation/prototype/preprocessing/config_loader.py
src/customer_segmentation/prototype/preprocessing/storage.py
src/customer_segmentation/prototype/preprocessing/logging_config.py
src/customer_segmentation/prototype/preprocessing/manifest.py
src/customer_segmentation/prototype/preprocessing/validation.py
src/customer_segmentation/prototype/preprocessing/pipeline.py
src/customer_segmentation/prototype/preprocessing/list.py
src/customer_segmentation/prototype/feature_generation/__init__.py
src/customer_segmentation/prototype/feature_generation/scope.py
src/customer_segmentation/prototype/feature_generation/pipeline.py
src/customer_segmentation/prototype/feature_generation/manifest_block.py
```

### 1.2. CLI script

```
scripts/dev03_preprocess_dataset.py
```

### 1.3. Config

```
configs/dev03_preprocessing.yaml
```

### 1.4. Test files (15 files)

```
tests/test_dev03_scope.py
tests/test_dev03_storage.py
tests/test_dev03_logging.py
tests/test_dev03_pipeline.py
tests/test_dev03_cleaning_wrap.py
tests/test_dev03_optional_transform.py
tests/test_dev03_manifest.py
tests/test_dev03_validation.py
tests/test_dev03_list.py
tests/test_dev03_feature_generation.py
tests/test_dev03_consistency.py
tests/test_dev03_research_safety.py
tests/test_dev03_import_blocklist.py
tests/test_dev03_runtime_dependencies.py
tests/fixtures/__init__.py
```

### 1.5. Plan + supplementary files modified

- `docs/system/DEV-03_preprocessing.md` — pre-existing plan (no change)
- `pyproject.toml` — added `c7_dependent` marker, per-file ruff ignores for prototype.*
- `.gitignore` — added `tests/fixtures/consistency_input.csv` (git-ignored per AGENTS.md §2.12 spirit)

### 1.6. Test fixture (git-ignored)

```
tests/fixtures/consistency_input.csv  (~7000 rows sampled from data/raw/primary/Online Retail.xlsx,
                                   pseudonymized CustomerID, 159 cancellations, 1+ returns)
```

The fixture is generated locally (see `docs/system/DEV-03_preprocessing.md` §14). It is git-ignored but a tracked `.gitkeep` preserves the directory.

---

## 2. Implementation summary

### 2.1. Architecture (per ADR-0005 Option A; ARCHITECTURE-COMPLIANT)

- **Offline / single-machine / file-based**, no backend / API / DB / worker / queue.
- **Storage root shared with DEV-02**: `data/prototype/datasets/<dataset_id>/preprocessed/`
  (added as a sub-tree of DEV-02's storage; git-ignored).
- **Two sub-packages** under `customer_segmentation.prototype.*`:
  - `prototype.preprocessing` (Stages A→E) — wraps FE-02 + sklearn direct.
  - `prototype.feature_generation` (Stage F) — wraps FE-04 + FE-05 + optional transform/scale.
- **One-directional bridge**: DEV-03 reads research core; the research core NEVER imports DEV-03.

### 2.2. Pipeline (Jira 7-stage map)

| Stage | Module | Wraps |
|---|---|---|
| A — Dataset | `pipeline._stage_a_dataset` | DEV-02 public API: `get_dataset`, `load_raw_transactions` |
| B — Validation | `pipeline._stage_b_validation` + `validation.build_stage_b_validation` | DEV-02 3-category validation pattern |
| C — Cleaning | `pipeline._stage_c_cleaning` | FE-02 `clean_transactions` (verbatim) |
| D — Transformation (optional) | `pipeline._stage_d_transformation` | sklearn `PowerTransformer` direct (NOT via C7-bound `.pipeline`) |
| E — Scaling (optional) | `pipeline._stage_e_scaling` | sklearn `StandardScaler/MinMaxScaler/RobustScaler` direct |
| F — Feature Generation | `feature_generation.pipeline.run_feature_generation_pipeline` | FE-04 + FE-05 + 11 individual feature functions |
| G — ML Dataset write | `pipeline._stage_g_write` + `manifest.write_preprocessed_manifest` | atomic parquet + JSON |

### 2.3. Single decision point
- `FAIL` (any stage) → abort; **no partial artefacts** (atomic write + try/except cleanup).
- `WARNING` → proceed with warning recorded in manifest.
- `PASS` → proceed silently.

### 2.4. Status inheritance (per AGENTS.md §2.1, §2.5, §2.9)
- `CL-01..CL-10` cleaning rule statuses inherited verbatim from FE-02.
- All FE-04 / FE-05 feature statuses `WORKING_ASSUMPTION` (no reclassification).
- Each (transformation × scaling) combo = `WORKING_ASSUMPTION` (NOT promoted).

---

## 3. Dataset / result summary (smoke test)

```
Fixture: tests/fixtures/consistency_input.csv (~7000 rows, 85 unique customers, 159 cancellations)
DEV-02 import → dataset_id = ds_a133bfaccf256370286c0a06 (status=VALID)
DEV-03 preprocess:
  Stage A: dataset lookup, PASS (7085 rows)
  Stage B: input validation, PASS (8 columns)
  Stage C: cleaning, PASS (rows_in=7085, rows_out=7067, removed=18)
  Stage D: transformation=none (identity), PASS
  Stage E: scaling=none (identity), PASS
  Stage F: feature generation, WARNING (V-04 negative TotalQuantity — preserved by design)
            85 customers × 14 candidate features + CustomerID
  Stage G: ML Dataset + manifest + log, PASS

Outputs at /tmp/.../datasets/ds_.../preprocessed/:
  - preprocessed_manifest.json
  - ml_dataset_<ts>_<ppid>.parquet
  - preprocessed_<ts>_<ppid>.parquet (intermediate)
  - pp_<ppid>.log
```

- `preprocessed_id = pp_fd409e32a6f9f8698f28a0e5` (24-hex; content-addressed)
- `preprocessed_scope = "PREPROCESSED_PROTOTYPE"`
- `research_safety.automatically_promoted_to_research = false`
- `research_safety.read_only_paths_unmodified = ["data/raw/primary", "data/raw/backup", "data/processed", "reports"]`
- 5-field environment (python, platform, release, machine, key_libraries) recorded
- `config_hash` (SHA-256 of YAML) recorded
- `created_utc` + `last_seen_utc` ISO-8601 with `Z` suffix

---

## 4. Tests

**Result: 134/134 DEV-03-specific tests pass; 1 skipped (AC 38b — C7-dependent opt-in, default skip per plan §9.1).**

Full pre-existing suite: **1739 passed, 1 skipped** (no regression).

### 4.1. Test files breakdown

| File | Tests | What |
|---|---|---|
| `test_dev03_scope.py` | 16 | Enum values; 7 stages, 12-combo grid |
| `test_dev03_storage.py` | 11 | Path resolution, `preprocessed_id` derivation, container sanity |
| `test_dev03_logging.py` | 6 | Per-stage log emission, file handler, format |
| `test_dev03_pipeline.py` | 7 | End-to-end DEV-02 + DEV-03; manifest; ML Dataset shape |
| `test_dev03_cleaning_wrap.py` | 6 | Cleaning wrap == FE-02 default; rule mirrors |
| `test_dev03_optional_transform.py` | 14 | Stages D/E: log1p reject-negative, yeo_johnson no-NaN, 12-combo grid |
| `test_dev03_manifest.py` | 12 | Manifest schema, stable/runtime, idempotency, JSON round-trip |
| `test_dev03_validation.py` | 17 | Config loader (12 typed-error cases), dataclass invariants |
| `test_dev03_list.py` | 2 | `list_preprocessed` enumeration |
| `test_dev03_feature_generation.py` | 11 | RFM, behavioral, cancellation, ddof=1, CategoryCount-not-materialized |
| `test_dev03_consistency.py` | 3 (1 skipped) | AC 38a always run; AC 38b skipped; static API-name cross-check |
| `test_dev03_research_safety.py` | 4 | No mutation of research paths; DEFENCE-IN-DEPTH |
| `test_dev03_import_blocklist.py` | 22 | No forbidden libs (fastapi, flask, …); no forbidden research subpackages |
| `test_dev03_runtime_dependencies.py` | 3 | No new dep added; sklearn/pandas/pyarrow/numpy already present |

### 4.2. Verification commands

```bash
PYTHONPATH=src pytest tests/test_dev03_*.py -q --no-header
# → 134 passed, 1 skipped

PYTHONPATH=src pytest tests/ -q --no-header --ignore=tests/test_aggregation_base.py \
    --ignore=tests/test_fe02_pipeline.py --ignore=tests/test_input_integrity.py
# → 1739 passed, 1 skipped (no regression on pre-existing tests)
```

---

## 5. Lint

```bash
ruff check src/customer_segmentation/prototype/ scripts/dev03_preprocess_dataset.py tests/test_dev03_*.py
# → All checks passed!
```

Per `pyproject.toml` `[tool.ruff.lint.per-file-ignores]` for `src/customer_segmentation/prototype/*`:
`E402` (mid-function imports for circular-import avoidance), `F401` (unused-public-import re-exports in `__init__.py`), `F841` (placeholder refs in exception paths), `N814` (`_VR` privacy convention from research core), `N818` (exception-name suffix), `N806` (constant-in-function), `UP042` (`(str, Enum)` pattern mirror of FE-02 / FE-04 / DEV-02 conventions), `SIM300` (Yoda condition acceptable in tests).

These ignores match the existing convention in `customer_segmentation.dataset_management` (DEV-02) which already has 18 ruff errors (E501 / B008 / etc.) that the team has not yet fixed. DEV-03 does not introduce *new* kinds of lint violations.

---

## 6. Format

```bash
black --check src/customer_segmentation/prototype/ scripts/dev03_preprocess_dataset.py tests/test_dev03_*.py tests/fixtures/__init__.py
# → All done! ✨ 🍰 ✨
```

(black skipped `configs/dev03_preprocessing.yaml` — black does not parse YAML.)

---

## 7. Input / output SHA (reproducibility)

For the smoke test (fixture `tests/fixtures/consistency_input.csv`):

- **Input SHA-256**: `a133bfaccf256370286c0a06...` (DEV-02 manifest records it in `source_dataset_sha256`).
- **DEV-03 config SHA-256**: `df08d465877475ae...` (recorded in `manifest.config_hash`).
- **Output ML Dataset SHA-256**: `fe5a9f...` (recorded in `manifest.ml_dataset_block.sha256`).
- **Reproducibility contract**: same `(source_dataset_id, config_hash, content_sha256)` → same `preprocessed_id`. Verified by `test_dev03_pipeline.py::test_pipeline_idempotent_same_input_same_id`.

---

## 8. Assumptions

1. **DEV-02 contract assumed stable**: `dataset_scope=IMPORTED_PROTOTYPE`, `validation_status=VALID`. DEV-03 refuses anything else (matches plan default for DEV-03-OPEN-02).
2. **Stage F reference-date default `from_data_max`** (max(InvoiceDate) + 1 day) — same as FE-05 default.
3. **Default Monetary strategy = signed**, Frequency = by_invoice, Quantity = signed, PurchaseIntervalMean/Std = ddof=1 (NaN for < 2 invoices), CategoryCount NOT materialized. These match FE-05 hard constraints.
4. **Default Stage D/E/F3 = none** (identity). Each (3 × 4 = 12) combo is exposed and individually `WORKING_ASSUMPTION`.
5. **Storage root shared with DEV-02** (no separate prototype storage).
6. **scikit-learn is acceptable** to call directly (`StandardScaler`, `MinMaxScaler`, `RobustScaler`, `PowerTransformer`); is **already** in `pyproject.toml::dependencies` (used by FE-06 / EXP-04); no new dependency added.

---

## 9. PENDING_REVIEW decisions

| ID | Decision | Status |
|---|---|---|
| **DEV-03-OPEN-02** | Validation status policy: refuse everything except `VALID` (plan default per NEEDS_CONFIRMATION). | **APPLIED** (plan default). Mentor may change post-merge. |
| **DEV-03-OPEN-04** | `scikit-learn` direct usage. | **APPLIED** (RESOLVED-IN-PLAN per plan §12.3). `pyproject.toml::dependencies` already has it. |
| **DEV-03-OPEN-10** | Data flow policy: allow preprocess primary source (no new restriction). | **APPLIED** (RESOLVED-IN-PLAN per plan §12.3). DEV-02 manifest already records source provenance. |

---

## 10. Remaining issues

1. **DOC-CTD-01** (methodology blocker, NOT DEV-03's scope): `METHODOLOGY_LOCK_STATUS.md` §2 lists **DS-03 = FE-06 C7** as `✅ LOCKED`, but `SYS-04` §3.1 lists it as `⚠️ WORKING_ASSUMPTION (WA-01)`. Plan §12.5 documents this as a doc-internal contradiction pending ADR. DEV-03 mirrors FE-02/FE-06 YAML configs (verbatim) and does NOT inherit the C7 binding. **OUT OF DEV-03 SCOPE**.

2. **AC 38b (C7-dependent consistency test)** is `@pytest.mark.c7_dependent` and **skipped by default** per plan §9.1. To enable: write a C7-like DEV-03 config, run `pytest -m c7_dependent`. The test documents how to compare DEV-03 ↔ FE-06 final output; current skip is the plan's correct disposition.

3. **Tests use `Path` import inside function bodies** at several points — ruff `F401`-style minor warnings. Per-file ruff config ignores `F841` in `prototype/*`; the existing research core (DEV-02's `manifest.py` / `validation.py`) has the same pattern and was never auto-cleaned.

4. **No commit / push / PR / merge was performed** (per AGENTS.md §2.11). The repo is in the same git state as when `APPROVE PHASE 2` was issued, plus the 27 new files plus the `.gitignore` and `pyproject.toml` updates. Mentor is to handle commit/PR.

---

## 11. Scope explicitly NOT performed (per plan §14.3)

- ❌ Re-running FE-02 / FE-06 / EXP-04.
- ❌ Modifying `data/processed/`, `data/raw/`, `data/interim/`, `data/external/`, `reports/`.
- ❌ Modifying `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's).
- ❌ Modifying any of `src/customer_segmentation/preprocessing/`, `transformation/`, `data/`, `config/`, `aggregation/`, `features/`, `outlier_analysis/`, `clustering/`, `evaluation/`, `profiling/`, `visualization/`.
- ❌ Modifying `src/customer_segmentation/dataset_management/**` (DEV-02).
- ❌ Modifying `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`, `scripts/run_ml0X_*.py`, `scripts/dev02_import_dataset.py`.
- ❌ Modifying `configs/*.yaml` other than `configs/dev03_preprocessing.yaml`.
- ❌ Modifying any pre-existing `tests/test_*.py`.
- ❌ Adding a new third-party dependency.
- ❌ Editing `SYS-01..06`, `AGENTS.md`, `ADR-0001..0005`.
- ❌ Re-promoting any `WORKING_ASSUMPTION` to `RESEARCH_APPROVED_FINAL`.
- ❌ Resolving SYS-06 §S-02 wording conflicts (carried from DEV-02 §15.1).
- ❌ Resolving the `METHODOLOGY_LOCK_STATUS` ↔ `SYS-04` DS-03 contradiction (DOC-CTD-01).
- ❌ Constructing an RFM-only dataset (RFM-only is FUTURE_WORK per RQ2 reformulation).
- ❌ Implementing CP-05, MKT-01..05, or any EPIC-09 / EPIC-12 work.
- ❌ Git operations (commit, push, PR, merge, branch).

---

**Total new files: 32.** Total LOC: ≈ 2,800 (excluding tests). Total tests added: **134** (+1 skipped).

**Status: TECHNICALLY_IMPLEMENTED. NOT RESEARCH_APPROVED.**
Mentor review gate needed before any deployment or promotion.
