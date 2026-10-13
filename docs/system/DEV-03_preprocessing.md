# DEV-03 — Prototype Preprocessing

> **Mã task:** DEV-03 (Jira scope confirmed by user 2026-10-09, see §13.1 DEV-03-OPEN-01 status `RESOLVED`).
> **Jira pipeline (confirmed):** `Dataset → Validation → Cleaning → Transformation → Scaling → Feature Generation → ML Dataset` (7 bước).
> **Jira Acceptance Criteria (confirmed):**
> 1. Pipeline chạy được end-to-end.
> 2. Có configuration (single source of truth via YAML).
> 3. Có logging (mỗi stage emit log entry).
> 4. Có output Dataset (`data/prototype/<dataset_id>/preprocessed/...`).
> 5. Kết quả nhất quán với nghiên cứu (so với FE-02/04/05/06 canonical output trên cùng input).
> **Tên:** Prototype Preprocessing Pipeline (Jira scope: 7 bước).
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config, no ADR, no
> SYS edit, no Git op). Phase 2 (implementation) yêu cầu human approval gate.
> **Ngày:** 2026-10-09 (revised 2026-10-09 after Jira scope confirmed).
> **Phạm vi:** Add a **prototype-layer** capability to chạy một 7-step
> preprocessing pipeline (Dataset lookup → Validation → Cleaning → Transformation →
> Scaling → Feature Generation → ML Dataset write) trên datasets imported qua
> DEV-02. Output = `data/prototype/<dataset_id>/preprocessed/` (cả
> preprocessed artefact + ML Dataset customer-level feature matrix) + một
> `PreprocessedManifest` JSON. **Does NOT** modify the canonical FE-02
> cleaning artefacts, FE-04 aggregation, FE-05 features, FE-06 transformation,
> EXP-04 evidence, hoặc bất kỳ research methodology / RQ / algorithm scope nào.
> **Architecture:** Option A (ADR-0005) — offline, single-machine, file-based.
> No backend, no API, no database, no worker, no queue.
> **Kế thừa:** DEV-02 contract (§14 of `docs/system/DEV-02_dataset_management.md`)
> là input contract bắt buộc. DEV-03 phải consume the DEV-02 public API.

---

## 1. Mục tiêu

DEV-03 cung cấp **prototype preprocessing pipeline** cho downstream prototype
DEVs (DEV-04 → DEV-09) cần operate trên user-supplied dataset đã qua
DEV-02 import. Pipeline mirror đúng 7 bước mà Jira đã confirm:

`Dataset → Validation → Cleaning → Transformation → Scaling → Feature Generation → ML Dataset`

Cụ thể từng bước trong prototype layer (mapping sang research-core module):

| # | Jira step | DEV-03 stage | Wraps / reuses (research core) |
|---|---|---|---|
| 1 | **Dataset** | Stage A: input lookup | `dataset_management.get_dataset` + `data.loader.load_raw_transactions` |
| 2 | **Validation** | Stage B: input validation | `data.audit.basic_overview` + `preprocessing.cleaning.coerce_dtypes` + structural checks (row/column count, schema compatibility) |
| 3 | **Cleaning** | Stage C: cleaning pipeline | `preprocessing.cleaning.clean_transactions` (5 sub-stages B0..B4: coerce_dtypes, invalid_records, duplicates, missing_values, outliers) |
| 4 | **Transformation** | Stage D: optional transformation | `sklearn.preprocessing.PowerTransformer` (yeo_johnson / log1p) — direct, NOT via `transformation.pipeline` (C7-bound) |
| 5 | **Scaling** | Stage E: optional scaling | `sklearn.preprocessing.{StandardScaler, MinMaxScaler, RobustScaler}` — direct, NOT via `transformation.scaling` (C7-bound) |
│  6 | **Feature Generation** | Stage F: feature generation | `aggregation.base_dataset.aggregate_customer_base` (FE-04) + `features.candidate_dataset.build_candidate_features` (FE-05) + supporting RFM (`features.rfm.{compute_recency, materialize_frequency, materialize_monetary}`) + behavioral (`features.transaction_behavior.{compute_tenure_days, compute_purchase_interval, compute_active_days, compute_average_invoice_value, compute_signed_quantity_set}`) + diversity (`features.diversity.compute_diversity_features`) + cancellation (`features.cancellation.compute_cancellation_features`) |
| 7 | **ML Dataset** | Stage G: write | `transformation.versioning.compute_file_sha256` + atomic parquet write + `PreprocessedManifest` JSON |

Mỗi step trong plan này **wrap** research core, không fork. Step nào bị
"tắt" trong config (e.g. outlier off, transformation none) thì stage đó
vẫn chạy nhưng là no-op + record trong manifest. Step nào lỗi → abort
trước step tiếp theo, không ghi partial artefact.

Phân biệt rõ với research core (FE-02 / FE-04 / FE-05 / FE-06):

| Concern | Research core (FE-02..06) | DEV-03 (prototype) |
|---|---|---|
| Input | `data/raw/primary/Online Retail.xlsx` (READ-ONLY) | `data/prototype/datasets/<dataset_id>/<original_filename>` (từ DEV-02) |
| Output | `data/processed/transactions_clean.parquet` (FE-02) → `data/processed/.../base_dataset.parquet` (FE-04) → `data/processed/.../candidate_features.parquet` (FE-05) → `data/processed/final_clustering_dataset.parquet` (FE-06) (git-ignored, content-addressed) | `data/prototype/<dataset_id>/preprocessed/...` (git-ignored, content-addressed) — gồm cả cleaned parquet + customer-level ML dataset |
| Owner | Research core (`src/customer_segmentation/preprocessing/`, `aggregation/`, `features/`, `transformation/`) | Prototype layer (`src/customer_segmentation/prototype/preprocessing/`, `prototype/feature_generation/`, NEW packages) |
| Promotion gate | Mentor + ADR (research methodology change) | KHÔNG promote — DEV-03 là optional prototype capability |
| Methodology status | FE-06 C7 = `WORKING_ASSUMPTION` (DS-03 in SYS-04) per SYS-04 §3.1 / METHODOLOGY_LOCK_STATUS §2 (mâu thuẫn xem §12.5 DOC-CTD-01, chưa resolved) | DEV-03 defaults = `WORKING_ASSUMPTION` (mirroring FE-02 / FE-04 / FE-05 defaults; KHÔNG bind vào C7 — C7 chỉ là một trong các transformation options) |
| Rerun impact | Rerun = full research rerun | Re-preprocess = idempotent re-write to same `preprocessed_id` |
| Logging | Standard `print` / per-script logging | Per-stage log file under `data/prototype/<dataset_id>/preprocessed/<preprocessed_id>.log` (configurable level + output) |

## 2. Nguồn tài liệu đã đọc

> Tất cả paths dưới đây là relative-to-repo-root. Mỗi phát biểu trong plan
> trích từ doc X phải đính kèm section reference. Plan **không** dùng
> statement nào không có nguồn (AGENTS.md §2.1, §2.7).

| Tài liệu | Vai trò cho DEV-03 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules (binding) | Toàn bộ |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture contract (Option A) | Toàn bộ |
| `docs/system/DEV-01_project_setup.md` | Verification + architecture boundary pattern | Toàn bộ |
| `docs/system/DEV-02_dataset_management.md` | Downstream contract, manifest schema, coupling rules | Toàn bộ (1491 dòng) |
| `docs/system/SYS-01_requirements.md` | Functional / non-functional requirements | Toàn bộ (1036 dòng) |
| `docs/system/SYS-02_architecture.md` | Layered batch pipeline, ADR-0005 consistency | §1-§3 (head) |
| `docs/system/SYS-03_data_model.md` | Storage layer, entity mapping | §1-§3 (head) |
| `docs/system/SYS-04_ml_processing_pipeline.md` | Stage boundaries, E-PPC, FE-06 C7 status | Toàn bộ (~1500 dòng) |
| `docs/system/SYS-05_api_design.md` | API design (FUTURE_WORK per ADR-0005) | §1 (head) |
| `docs/system/SYS-06_ui_ux_design.md` | UI/UX scope + 4 documented SYS-06 conflicts | §1-§3, §8-§10 |
| `docs/data_dictionary/dataset_provenance.md` | Dataset identity, SHA-256, license | Toàn bộ |
| `docs/data_dictionary/dataset_schema.csv` | Raw transaction-level schema (8 columns) | Toàn bộ |
| `docs/data_dictionary/initial_data_profile.md` | FE-01 audit findings, cancellation handling | Toàn bộ |
| `docs/methodology/methodology_overview.md` | FE-06 C7, RQ definitions, EXP-04 coverage | Toàn bộ |
| `docs/methodology/research_questions.md` | RQ1/RQ2/RQ3, feature status | Toàn bộ |
| `docs/research/review/METHODOLOGY_LOCK_STATUS.md` | Locked decisions, WA-01..08 | Toàn bộ |
| `docs/research/EXP01..05_*.md`, `FE04..06_*.md`, `ML01..06_*.md` | FE / EXP / ML evidence (skim FE-04, FE-05, FE-06 in depth — see §3 for reuse) | FE-04 §1, §2; FE-05 §1, §2; FE-06 §13 |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | Adapter / registry contract | Skim (header) |
| `docs/research/EPIC09_CP05_PLAN.md` | EPIC-09 scope (out of DEV-03) | Skim (header) |
| `configs/preprocessing.yaml` | FE-02 cleaning config (mirror for DEV-03 cleaning defaults) | Toàn bộ |
| `configs/aggregation.yaml` | FE-04 aggregation config (mirror for DEV-03 feature-generation defaults) | Toàn bộ |
| `configs/feature_engineering.yaml` | FE-05 features config (mirror for DEV-03 feature-generation defaults) | Toàn bộ |
| `configs/transformation.yaml` | FE-06 C0..C7 (mirror for DEV-03 options) | Toàn bộ |
| `configs/exp04_preprocessing_feature_set.yaml` | EXP-04 sweep (6 scenarios) | Toàn bộ |
| `configs/dev02_dataset_management.yaml` | DEV-02 contract (input for DEV-03) | Skim (structure) |
| `src/customer_segmentation/preprocessing/{cleaning,invalid_records,duplicates,missing_values,outliers}.py` | Reusable building blocks for Stage C (cleaning) | Toàn bộ |
| `src/customer_segmentation/aggregation/{base_dataset,config_loader,validation}.py` | Reusable building blocks for Stage F (aggregation / FE-04) | Toàn bộ |
| `src/customer_segmentation/features/{candidate_dataset,rfm,behavioral,cancellation,config_loader,validation}.py` | Reusable building blocks for Stage F (feature engineering / FE-05) | Toàn bộ |
| `src/customer_segmentation/data/{audit,validator,loader,schema}.py` | Reusable audit / validator / loader | Toàn bộ |
| `src/customer_segmentation/transformation/versioning.py` | SHA-256 utility (reused by DEV-02) | Toàn bộ |
| `src/customer_segmentation/config/loader.py` | YAML loader convention (mirrored) | Toàn bộ |
| `src/customer_segmentation/dataset_management/**` | Pattern to mirror (package structure, coupling rules) | Toàn bộ (1491 dòng của plan) |
| `scripts/run_fe02_cleaning.py`, `run_fe04_aggregation.py`, `run_fe05_feature_engineering.py`, `run_fe06_transformation.py` | FE-04/05/06 orchestrators (pattern reference, NOT a 1:1 template) | Toàn bộ (Stage F wrap logic) |
| `tests/test_dev02_*.py` (12 files) | Test pattern to mirror | File names + section headers |
| `tests/test_aggregation*.py`, `test_features*.py`, `test_candidate_dataset*.py` | Existing FE-04 / FE-05 tests (NOT modified; used as cross-check for reuse) | File names only |
| `conftest.py` | Test PYTHONPATH setup (mirrored) | Toàn bộ |
| `.gitignore` | Git-ignore rules — `data/prototype/**` already covered (post DEV-02 §7.3 fix) | §data rules |

> **NOT read in depth** (out of plan scope): `notebooks/**`,
> `reports/fe0*/**`, `reports/exp0*/**`, `reports/evaluation/**`,
> `scripts/run_fe0X_*.py` (other than FE-02), `tests/test_*.py`
> (other than test_dev02_*), `src/customer_segmentation/clustering/**`,
> `src/customer_segmentation/evaluation/**`, `src/customer_segmentation/profiling/**`,
> `docs/system/ui-prototype/**`, `docs/research/algorithm_theory_v3_exports/**`.
> These are research-core / downstream-DEV / reporting artifacts; DEV-03 only
> READS the public APIs of the research core (per §3.2 coupling rules) and
> writes only to its own `data/prototype/<dataset_id>/preprocessed/` sub-tree.

## 3. Hiện trạng source code / module / config / test

### 3.1. Source code đã tồn tại (research core, READ-ONLY đối với DEV-03)

```
src/customer_segmentation/
├── preprocessing/                          (RESEARCH CORE — toàn bộ READ-ONLY; reused by Stage C)
│   ├── __init__.py                         (package docstring)
│   ├── cleaning.py                         (PipelineConfig + clean_transactions + 5 stages)
│   ├── invalid_records.py                  (InvalidRecordRules + apply_invalid_rules + 7 helpers)
│   ├── duplicates.py                       (drop_duplicates + analyse_subset_duplicates + exact_duplicate_analysis)
│   ├── missing_values.py                   (handle_missing + summarise_missing + IDENTIFIER_COLUMNS guard)
│   └── outliers.py                         (detect_outliers + treat_outliers + iqr/zscore/winsorize)
├── data/                                   (READ-ONLY; reused by Stage A + B)
│   ├── audit.py                            (basic_overview + missing/numerical/categorical/identifier profile)
│   ├── loader.py                           (load_raw_transactions + list_sheet_names)
│   ├── validator.py                        (ValidationResult — currently a placeholder; per its TODO)
│   └── schema.py                           (column schema definitions)
├── transformation/                         (READ-ONLY; only .versioning reused; .pipeline/.scaling MUST NOT be reused — C7-bound)
│   ├── versioning.py                       (compute_file_sha256, compute_df_sha256, FE06_VERSION)
│   ├── scaling.py                          (StandardScaler / MinMaxScaler / RobustScaler wrappers — MUST NOT be reused by DEV-03)
│   ├── feature_eligibility.py              (CANDIDATE gate)
│   ├── pipeline.py                         (compose imputation + transform + scale — MUST NOT be reused by DEV-03)
│   ├── config_loader.py                    (transformation config)
│   ├── skewness.py, analysis.py, ...       (other utilities)
│   ├── fill_strategy.py, imputation_semantics.py, validators.py
│   └── redundancy_analysis.py, report.py
├── config/                                 (READ-ONLY; pattern reuse only)
│   ├── loader.py                           (load_preprocessing_config + KEY_ANNOTATIONS)
│   └── outlier_loader.py                   (outlier config loader)
├── aggregation/                            (RESEARCH CORE — READ-ONLY; reused by Stage F — FE-04)
│   ├── __init__.py                         (public API: aggregate_customer_base, validate_base_dataset, write_reports, ...)
│   ├── base_dataset.py                     (CustomerBaseResult, aggregate_customer_base, compute_line_revenue, build_base_schema)
│   ├── config_loader.py                    (load_aggregation_config, AggregationConfig, AggregationSpec, ...)
│   ├── report.py                           (write_reports)
│   └── validation.py                       (validate_base_dataset, ValidationResult, V-01..V-12)
├── features/                               (RESEARCH CORE — READ-ONLY; reused by Stage F — FE-05)
│   ├── __init__.py                         (public API: RFM, behavioral, cancellation, candidate_dataset, validation)
│   ├── rfm.py                              (compute_reference_date, compute_recency, FrequencyVariants, MonetaryVariants, ...)
│   ├── candidate_dataset.py                (build_candidate_features, validate_candidate_dataset, CandidateDatasetResult)
│   ├── behavioral.py                       (STUB — `build_behavioral_features` raises `NotImplementedError`; NOT reused by DEV-03)
│   ├── cancellation.py                     (compute_cancellation_features, compute_cancellation_rate, compute_return_rate)
│   ├── config_loader.py                    (load_feature_engineering_config, FeatureEngineeringConfig, ...)
│   ├── selection.py, analysis.py, monetary_comparison.py, transaction_behavior.py, diversity.py
│   ├── report.py, validation.py
├── outlier_analysis/, clustering/,
├── evaluation/ (eva03 already implemented), profiling/, visualization/
├── dataset_management/                     (DEV-02 PACKAGE — pattern to mirror)
│   ├── __init__.py, scope.py, storage.py, importer.py,
│   ├── manifest.py, validation.py, list.py
└── __init__.py
```

### 3.2. Configs hiện có

```
configs/
├── aggregation.yaml, clustering.yaml, dataset.yaml, eva03_stability_evaluation.yaml,
├── exp01..05_*.yaml, experiment.yaml, feature_engineering.yaml, features.yaml,
├── outlier.yaml, preprocessing.yaml, transformation.yaml
└── dev02_dataset_management.yaml           (DEV-02 config — precedent for DEV-03)
```

### 3.3. Scripts hiện có

```
scripts/
├── run_fe01..fe06_*.py                     (FE-* research orchestrators — NOT to be modified)
├── run_exp01..exp05_*.py                   (EXP-* orchestrators — NOT to be modified)
├── run_ml02..ml06_*.py, run_eva0X.py, run_cp0X.py
├── build_*.py, generate_*.py, audit_dataset.py
└── dev02_import_dataset.py                 (DEV-02 CLI — pattern to mirror; NEW scripts for DEV-03)
```

### 3.4. Tests hiện có

```
tests/
├── test_*.py (research core tests — pre-existing, NOT to be modified)
├── test_dev02_*.py (12 files — pattern to mirror for DEV-03)
└── test_fill_strategy.py, test_outlier_*.py, test_exp04_*.py (research tests)
```

### 3.5. Trạng thái feature / configuration

| Item | Status | Source | Implication for DEV-03 |
|---|---|---|---|
| FE-02 cleaning rules | `WORKING_ASSUMPTION` (CL-06, CL-08 = `PENDING_MENTOR_REVIEW`) | `configs/preprocessing.yaml` | DEV-03 Stage C mirrors these defaults; status inheritance is **not** automatic (per-row rule re-marked) |
| FE-06 C7 (yeo_johnson + robust + median) | `WORKING_ASSUMPTION` (DS-03, WA-01) per SYS-04 §3.1; `LOCKED` per METHODOLOGY_LOCK_STATUS §2 — **mâu thuẫn, xem §12.5 DOC-CTD-01** | SYS-04, METHODOLOGY_LOCK_STATUS, `configs/transformation.yaml` | DEV-03 Stage D/E does **NOT** bind to C7; C7 is one option in the grid (yeo_johnson × robust), each combo marked `WORKING_ASSUMPTION` |
| EXP-04 scenarios C0..C3, C6, C7 | `EXPERIMENTAL` (C0..C3, C6) / `WORKING_ASSUMPTION` (C7) | `configs/exp04_preprocessing_feature_set.yaml` | DEV-03 may surface the SAME options (none/log1p/yeo_johnson × none/standard/minmax/robust) but each must be `WORKING_ASSUMPTION` |
| FE-04 aggregation rules | `WORKING_ASSUMPTION` (V-01..V-12 in research core) | `configs/aggregation.yaml`, `aggregation/validation.py` | DEV-03 Stage F (aggregation step) wraps `aggregate_customer_base` + `validate_base_dataset`; status inheritance verbatim (no reclassify) |
| FE-05 features (RFM, behavioral, cancellation) | `WORKING_ASSUMPTION` (RFM Monetary: ONE materialised default; Frequency: ONE materialised default; PurchaseInterval ddof=1 NaN semantics; CategoryCount NOT materialised) | `configs/feature_engineering.yaml`, `features/__init__.py` docstring | DEV-03 Stage F (features step) wraps `build_candidate_features`; selection gates và NaN semantics inherited verbatim (no reclassify) |
| FE-05 selection gates (evidence-based, no score/rank/weight) | `WORKING_ASSUMPTION` (gates only, no "best" / "winner") | `features/selection.py` | DEV-03 Stage F does **NOT** introduce score/rank/weight; no selection language (mirror AGENTS.md §2.5, §2.6) |
| K-Medoids | OUT OF SCOPE (ADR-0003) | `docs/decisions/0003-algorithm-scope.md` | Not relevant to DEV-03 (no clustering) |
| RFM-only | FUTURE WORK (RQ2 reformulated) | `docs/methodology/research_questions.md` RQ2 limitation | Not relevant to DEV-03 Stage F defaults (RFM is included in FE-05; RFM-only reformulation is future work — DEV-03 just wraps what FE-05 ships) |
| Outlier policy | `PENDING_MENTOR_REVIEW` | `configs/preprocessing.yaml` outlier_action = "none" default | DEV-03 Stage C must keep `outlier_action: none` as default; any change requires ADR |
| Cancellation / return flagging | `PENDING_MENTOR_REVIEW` (CL-06, CL-08) | `configs/preprocessing.yaml` | DEV-03 Stage C must keep `flag_*_cancellations/returns: true` as default; any change requires ADR |

## 4. Luồng dữ liệu trước và sau preprocessing

### 4.1. Trước DEV-03 (sau DEV-02)

```
                       DEV-02 (completed)
                            │
                            ▼
  data/prototype/datasets/<dataset_id>/
    ├── <original_filename>                 e.g. foo.csv
    └── manifest.json                       {dataset_id, sha256, dataset_scope=IMPORTED_PROTOTYPE, ...}
```

Downstream prototype DEVs (DEV-04..09) hiện không có cách nào apply
preprocessing lên dataset imported — họ chỉ có thể load raw CSV/Parquet
mà không qua cleaning/transform/scale.

### 4.2. Sau DEV-03 (khi implemented)

```
                       DEV-02 (completed)
                            │
                            ▼
  data/prototype/datasets/<dataset_id>/
    ├── <original_filename>                 e.g. foo.csv
    └── manifest.json                       {dataset_id, sha256, dataset_scope=IMPORTED_PROTOTYPE, ...}
                            │
                            │  (DEV-03 reads via DEV-02 public API)
                            ▼
                       DEV-03 (this plan, 7 stages)
                            │
                            ▼
  data/prototype/datasets/<dataset_id>/preprocessed/
    ├── preprocessed_<timestamp>_<hex>.parquet       (cleaned transaction-level data, post Stage C)
    ├── ml_dataset_<timestamp>_<hex>.parquet         (customer-level feature matrix, post Stage F = ML Dataset)
    ├── preprocessed_<preprocessed_id>.log           (per-stage log, configurable)
    └── preprocessed_manifest.json                   {preprocessed_id, source_dataset_id, sha256,
                                                      dataset_scope=PREPROCESSED_PROTOTYPE, ...}
```

Lưu ý: DEV-03 KHÔNG touch `data/prototype/datasets/<dataset_id>/manifest.json`
của DEV-02 — nó chỉ tạo sub-tree MỚI `preprocessed/` song song. Cả
`preprocessed_*.parquet` (cleaned, intermediate) và `ml_dataset_*.parquet`
(customer-level final) đều nằm trong cùng sub-tree. ML Dataset = final
output cho downstream prototype DEVs (DEV-04..09).

### 4.3. Sequence per single preprocessing run (7 stages, mapping Jira 1:1)

```
┌─ Stage A: Dataset (input lookup) ─────────────────┐  ← Jira step 1
│  - get_dataset(storage_root, dataset_id)            │
│  - verify dataset_scope == IMPORTED_PROTOTYPE       │
│  - verify validation_status == VALID                │
│  - read artefact_path to in-memory DataFrame       │
│  - log: stage_A.start / stage_A.input.rows / ...  │
│  → on FAIL: abort with error; no write             │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage B: Validation (input validation) ───────────┐  ← Jira step 2
│  - audit (basic_overview): row_count, col_count,    │
│    missing fraction, dtypes                          │
│  - coerce_dtypes (no row removal)                    │
│  - structural checks: row_count>0, col_count>0,     │
│    required columns present, dtypes match schema    │
│  - record dataset_profile in manifest (pre-clean)   │
│  → on FAIL: abort with error; no write              │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage C: Cleaning (5 sub-stages) ─────────────────┐  ← Jira step 3
│  C0: coerce_dtypes (already done at Stage B; idempotent)
│  C1: invalid_records (drop + flag)                 │
│  C2: duplicates (exact-row drop, optional subset)  │
│  C3: missing_values (keep / drop / impute_*)       │
│  C4: outliers (none by default; iqr / zscore /     │
│      winsorize)                                    │
│  - log per sub-stage: rows_in / rows_out / dropped │
│  → on FAIL: abort; no write                        │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage D: Transformation (optional) ──────────────┐  ← Jira step 4
│  - if config.transformation == "none": no-op      │
│  - elif config.transformation == "log1p":         │
│      - reject if any numeric column has negative  │
│        values (FE-06 A2 rule inherited)            │
│      - np.log1p(numeric_columns)                   │
│  - elif config.transformation == "yeo_johnson":   │
│      - sklearn PowerTransformer(method="yeo-johnson")
│  → on FAIL: abort; no write                       │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage E: Scaling (optional) ─────────────────────┐  ← Jira step 5
│  - if config.scaling == "none": no-op             │
│  - elif config.scaling in                          │
│    {"standard","minmax","robust"}:                │
│      - sklearn StandardScaler / MinMaxScaler /     │
│        RobustScaler on numeric_columns             │
│  → on FAIL: abort; no write                       │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage F: Feature Generation (aggregation + features) ─┐  ← Jira step 6
│  F1: aggregation                                     │
│      - aggregate_customer_base(...) → customer-level │
│        base dataset (FE-04)                          │
│      - validate_base_dataset(...) (V-01..V-12)       │
│  F2: feature engineering                            │
│      - compute_reference_date (from config)         │
│      - compute_recency / Frequency / Monetary       │
│        (RFM, FE-05)                                 │
│      - compute_tenure_days / compute_purchase_interval /     │
│        compute_active_days / compute_average_invoice_value /   │
│        compute_signed_quantity_set (FE-05 transaction_behavior) │
│      - compute_diversity_features (FE-05 diversity, │
│        wraps compute_products_per_invoice)          │
│      - compute_cancellation_features (FE-05)        │
│      - build_candidate_features(...) → candidate    │
│        feature matrix (FE-05)                       │
│      - validate_candidate_dataset(...)              │
│  F3: optional transform / scale applied to          │
│      candidate feature matrix (post-aggregation,    │
│      if config.stage_f_transform != "none")         │
│  → on FAIL: abort; no write                         │
└─────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage G: ML Dataset write + final validation ─────┐  ← Jira step 7
│  G1: final 3-category validation of ML Dataset     │
│      (file_level + structural + data_quality)      │
│  G2: preprocessed_id = pp_<sha256-prefix-24>      │
│  G3: atomic write ml_dataset_<ts>_<hex>.parquet    │
│      (the canonical ML Dataset)                    │
│  G4: atomic write preprocessed_<ts>_<hex>.parquet  │
│      (intermediate cleaned transaction-level,      │
│      optional — only if config.emit_intermediate)  │
│  G5: atomic write preprocessed_manifest.json       │
│  G6: atomic write preprocessed_<id>.log            │
│  → on FAIL: temp file unlinked, no partial artefact│
└─────────────────────────────────────────────────────┘
```

> **Note on Stage F3 (post-aggregation transform/scale):** If the user
> configures both (a) Stage D/E transform/scale on the transaction-level
> data AND (b) Stage F3 transform/scale on the customer-level feature
> matrix, BOTH apply. The default config has (a) off (transformation=none,
> scaling=none on transaction-level) and (b) off (transformation=none,
> scaling=none on customer-level). At least ONE of (a) or (b) may be
> non-none, but the plan defaults to "all none = identity" for the
> prototype defaults. This is a config-only choice; the plan does not
> recommend any specific combo.

## 5. Thiết kế đề xuất và lý do

### 5.1. Placement

Tạo **mới** hai sub-packages trong `src/customer_segmentation/prototype/`:
- `src/customer_segmentation/prototype/preprocessing/` — wraps Stages A→E
  (Dataset → Validation → Cleaning → Transformation → Scaling). Đây là
  package đã có trong plan trước (revised 2026-10-08).
- `src/customer_segmentation/prototype/feature_generation/` — wraps Stage F
  (Feature Generation = aggregation + RFM/behavioral/cancellation features).
  Sub-package MỚI, added theo Jira scope revision 2026-10-09.

Cả hai song song với `src/customer_segmentation/dataset_management/` (DEV-02).
Lý do:

- DEV-02 đã đặt `dataset_management` ở top-level `customer_segmentation`,
  không phải dưới `research` hay `prototype`. Plan này mirror đặt
  `prototype.preprocessing` + `prototype.feature_generation` cùng cấp.
- **Lý do cấp mới (`prototype.*`)** chứ không phải
  `customer_segmentation.preprocessing_prototype.*`:
  - Các sub-package có concern khác nhau: preprocessing (cleaning + transform + scale
    trên transaction-level) vs feature_generation (aggregation + RFM/behavioral
    trên customer-level). Tách riêng để mỗi sub-package có single concern.
  - DEV-04..09 có thể cùng pattern; một namespace `prototype.*` gom tất cả
    prototype-layer packages lại.
  - Tránh đụng với tên `customer_segmentation.preprocessing` (research core).
- **Lý do KHÔNG đặt tại `customer_segmentation.preprocessing`**:
  research core là READ-ONLY đối với các DEV-0X (per AGENTS.md §2.2
  Phase isolation, §2.13 Code organization).
- **Lý do TÁCH preprocessing vs feature_generation thành 2 sub-package
  (không gộp thành 1)**:
  - Preprocessing operates on transaction-level (FE-02, FE-06); feature
    generation operates on customer-level (FE-04, FE-05). Domain boundary
    is sharp.
  - Mỗi sub-package có thể test độc lập; consistency test (AC §8) ghép
    cả hai lại.
  - DEV-04 (nếu sau này cần custom feature engineering) có thể tái sử dụng
    `prototype.feature_generation/` mà không kéo theo preprocessing.

### 5.2. Coupling rules

#### 5.2.1. `customer_segmentation.prototype.preprocessing` MAY import from:

- `customer_segmentation.preprocessing.{cleaning,invalid_records,duplicates,missing_values,outliers}`
  (READ-ONLY — wrap-and-call, NOT fork). Reused by Stage C.
- `customer_segmentation.data.{audit,loader,schema,validator}` (READ-ONLY —
  reuse for Stage A + B).
- `customer_segmentation.transformation.versioning` (READ-ONLY — reuse
  `compute_file_sha256`, `compute_df_sha256`).
- `customer_segmentation.config.loader` (pattern reuse only — DEV-03
  mirrors the frozenset-based enum + typed-error convention, does NOT
  call the existing `load_preprocessing_config` directly because DEV-03
  has its own YAML schema).
- `customer_segmentation.dataset_management.{scope,storage,manifest,validation,list}`
  (READ-ONLY — DEV-03 consumes the DEV-02 contract).
- stdlib + `pandas` + `pyarrow` + `PyYAML` (already in `pyproject.toml`).

#### 5.2.2. `customer_segmentation.prototype.feature_generation` MAY import from:

- `customer_segmentation.aggregation.{base_dataset,config_loader,validation,report}`
  (READ-ONLY — wrap-and-call, NOT fork). Reused by Stage F1.
- `customer_segmentation.features.{rfm,behavioral,cancellation,candidate_dataset,config_loader,validation,selection}`
  (READ-ONLY — wrap-and-call, NOT fork). Reused by Stage F2.
- `customer_segmentation.prototype.preprocessing` (READ-ONLY — để lấy
  cleaned transaction-level data từ Stage C output; **chỉ** khi CLI
  orchestrate cả hai sub-packages trong cùng một run, không bắt buộc).
- `customer_segmentation.data.audit` (READ-ONLY — reuse for after-feature
  profile in manifest).
- `customer_segmentation.transformation.versioning` (READ-ONLY — reuse
  `compute_file_sha256`, `compute_df_sha256`).
- `customer_segmentation.dataset_management` (READ-ONLY — pattern reuse
  cho manifest schema).
- stdlib + `pandas` + `pyarrow` + `PyYAML`.

#### 5.2.3. Cả hai sub-packages MUST NOT import from:

- `customer_segmentation.transformation.scaling` /
  `transformation.pipeline` (research transformation — too tightly bound
  to FE-06 C7 semantics; if scaling is needed, DEV-03 calls
  `sklearn.preprocessing.{StandardScaler, MinMaxScaler, RobustScaler,
  PowerTransformer}` directly with `WORKING_ASSUMPTION` semantics, NOT
  the research wrappers). Đây là nguồn của mâu thuẫn C7 (xem §12.5
  DOC-CTD-01) — DEV-03 deliberately avoids inheriting the C7 binding
  by NOT calling the research wrapper; instead it calls sklearn
  primitives with explicit `WORKING_ASSUMPTION` status annotation.
- `customer_segmentation.clustering`, `.evaluation`, `.profiling`,
  `.outlier_analysis`, `.visualization` (out of DEV-03 scope per AGENTS.md
  §2.4).
- `customer_segmentation.transformation` **except** `.versioning`
  (documented reuse).
- Any backend / API / database / queue library (per ADR-0005).
- Must NOT add new third-party dependency. DEV-03 reuses
  `pandas` + `pyarrow` + `PyYAML` + `numpy` + `scikit-learn` (the
  latter is **already in `pyproject.toml::dependencies`**, used by
  research core, and is needed for `StandardScaler` / `MinMaxScaler` /
  `RobustScaler` / `PowerTransformer` for the optional transform/scale
  stage). Verify before committing — see §13.1 DEV-03-OPEN-04.

### 5.3. Module structure

```
src/customer_segmentation/prototype/
    __init__.py          — package marker for prototype.* namespace.
    preprocessing/       — Stages A→E (Dataset → Validation → Cleaning → Transformation → Scaling)
        __init__.py     — public API exports (PreprocessedScope enum,
                           PreprocessingStage enum, ValidationStatus enum,
                           preprocess_dataset, list_preprocessed, ...).
        scope.py        — PreprocessedScope, PreprocessingStage,
                           TransformationMethod, ScalingMethod, ImputationMethod,
                           OutlierAction, OutlierMethod enums + frozen sets.
        storage.py      — path resolution, preprocessed_id derivation,
                           container sanity, idempotency lookup.
        pipeline.py     — single-pipeline driver (Stage A → E).
        manifest.py     — PreprocessedManifest dataclass + JSON I/O +
                           stable/runtime field classification. Shared schema
                           used by both sub-packages.
        validation.py   — input validation (Stage B) + 3-category
                           post-pipeline validation.
        list.py         — enumerate preprocessed artefacts for a dataset_id.
        config_loader.py — YAML loader for configs/dev03_preprocessing.yaml
                            (mirrors config.loader frozenset + typed-error).
    feature_generation/  — Stage F (Feature Generation = aggregation + RFM/behavioral/cancellation)
        __init__.py     — public API exports (FeatureGenerationScope enum,
                           generate_features, ...).
        scope.py        — FeatureGenerationScope, FeatureStatus enums +
                           frozen sets.
        pipeline.py     — single-stage driver (Stage F1 aggregation + F2
                           features + F3 optional transform/scale on customer-level).
        manifest_block.py — FeatureGenerationBlock dataclass (lives under
                              PreprocessedManifest; separate file for
                              clean separation).
```

> **Lý do KHÔNG tạo thêm `errors.py`, `cli.py`, `__main__.py`**:
> mirror DEV-02 §3.5 — typed exceptions colocation với module raise;
> CLI là một script thin; không có `python -m` surface.
>
> **Lý do `manifest.py` ở `preprocessing/` (không ở `prototype/`)**: là
> shared schema, nhưng Stage G (ML Dataset write) thuộc preprocessing
> orchestration; feature_generation chỉ contribute `feature_generation_block`
> vào schema đó. Tách `manifest_block.py` trong feature_generation/ để
> feature_generation có ownership rõ ràng trên block của mình.

### 5.4. Reuse vs new

#### 5.4.1. Preprocessing sub-package — reused symbols

| Reused symbol | From | Used by DEV-03 for | Reuse rationale |
|---|---|---|---|
| `coerce_dtypes(df)` | `preprocessing.cleaning` | Stage C0 / B | Same 4-column coercion logic (InvoiceDate, CustomerID, InvoiceNo, StockCode) — research core đã freeze; DEV-03 chỉ wrap-and-call. |
| `InvalidRecordRules(...)` + `apply_invalid_rules(df, rules)` | `preprocessing.invalid_records` | Stage C1 | Same 7-rule set (CL-01..CL-10) — re-implement would violate research-core reuse. |
| `drop_duplicates(df, subset, keep, rule_id)` | `preprocessing.duplicates` | Stage C2 | Same semantics; reuse CL-09 rule_id for traceability. |
| `handle_missing(df, cols, strategy)` + `summarise_missing(df)` | `preprocessing.missing_values` | Stage C3 | Same strategy set (`drop`, `impute_zero`, `impute_median`, `impute_mean`, `keep`) + IDENTIFIER_COLUMNS guard. |
| `detect_outliers(df, cols, method, ...)` + `treat_outliers(df, ...)` + `summarise_outliers(df, ...)` | `preprocessing.outliers` | Stage C4 (off by default) | Same iqr / zscore / winsorize methods; same 3 actions. |
| `basic_overview`, `missing_profile`, `numerical_profile`, `categorical_profile` | `data.audit` | Stage B input audit + manifest | Mirror DEV-02 reuse pattern. |
| `load_raw_transactions(path)` | `data.loader` | Stage A loading | DEV-03 reuses for both CSV / Parquet. |
| `compute_file_sha256`, `compute_df_sha256` | `transformation.versioning` | preprocessed_id derivation, artefact SHA | Same SHA-256 contract as DEV-02 and FE-06. |
| `frozenset`-based enum + typed-error convention | `config.loader` | scope.py enums + config_loader.py | Mirror convention; no new pattern. |
| DEV-02 public API (`get_dataset`, `resolve_storage_root`, `DatasetScope`, `ValidationStatus`, `Manifest`) | `dataset_management` | Stage A input lookup | DEV-03 MUST consume the DEV-02 contract. |

#### 5.4.2. Feature generation sub-package — reused symbols

> **Sửa đổi 2026-10-09 (re-audit):** Reference `features.behavioral.build_behavioral_features` (stub, `NotImplementedError`) đã được thay bằng các function thực tế trong `features.transaction_behavior` + `features.diversity`. Stage F2 orchestration mirror đúng `scripts/run_fe05_feature_engineering.py:395-430`.

| Reused symbol | From | Used by DEV-03 for | Reuse rationale |
|---|---|---|---|
| `aggregate_customer_base(df, config) -> CustomerBaseResult` | `aggregation.base_dataset:179` | Stage F1 (aggregation) | Single function materialises customer-level base dataset (FE-04) with V-01..V-12 validation hooks. Re-implementing 12 validation rules + 9 aggregation specs would diverge from research. |
| `validate_base_dataset(df, config) -> ValidationResult` | `aggregation.validation:332` | Stage F1 (post-aggregation validation) | Mirror DEV-03's 3-category validation semantics; reuse V-01..V-11 verbatim (V-12 enforced by orchestrator). |
| `load_aggregation_config(path) -> AggregationConfig` | `aggregation.config_loader:440` | Stage F1 config loading | DEV-03's `feature_generation.config_loader` reads its own YAML but exposes the same fields as `AggregationConfig` (composition, not inheritance). |
| `compute_reference_date(df_transactions) -> datetime` | `features.rfm:36` | Stage F2 RFM Recency reference date | Deterministic: `max(InvoiceDate) + 1 day`. Inherited verbatim. |
| `compute_recency(df_base, reference_date, ...) -> pd.DataFrame` | `features.rfm:82` | Stage F2 RFM Recency → `recency_df` | (ReferenceDate - LastPurchaseDate).days; signed semantics inherited. |
| `compute_frequency_variants(df_transactions, df_base, ...) -> FrequencyVariants` | `features.rfm:147` | Stage F2 RFM Frequency variants | FREQ-01 (nunique InvoiceNo) vs FREQ-02 (count transaction lines) comparison. |
| `materialize_frequency(freq_variants, df_base, ..., mode=...) -> pd.DataFrame` | `features.rfm:216` | Stage F2 RFM Frequency → `frequency_materialized` (ONE variant, per FE-05 hard constraint). | Default mode = `Frequency_ByInvoice` per FE-05. |
| `compute_monetary_variants(df_transactions, df_base, ...) -> MonetaryVariants` | `features.rfm:282` | Stage F2 RFM Monetary variants | 4 monetary variants compared. |
| `materialize_monetary(mon_variants, df_base, ..., mode=...) -> pd.DataFrame` | `features.rfm:445` | Stage F2 RFM Monetary → `monetary_materialized` (ONE variant, per FE-05 hard constraint). | Default mode = `MonetarySigned` per FE-05. |
| `compute_signed_quantity_set(df_transactions, df_base, customer_key=...) -> pd.DataFrame` | `features.transaction_behavior:155` | Stage F2 Quantity working set → `quantity_set` (after column rename, xem dưới). | ONE working set materialized (default = signed). FE-05 hard constraint: PurchaseOnly set exists for comparison only, NOT materialized in candidate. |
| **column rename:** `signed_set.rename(columns={"TotalQuantity_Signed": "TotalQuantity", "AverageQuantity_Signed": "AverageQuantity", "BasketSize_Signed": "BasketSize"})` rồi select 4 cols | mirror `run_fe05_feature_engineering.py:407-413` | Stage F2 Quantity working set construction | DEV-03 phải mirror đúng pattern rename + column select để giữ FE-05 schema. |
| `compute_tenure_days(df_base, customer_key=...) -> pd.DataFrame` | `features.transaction_behavior:269` | Stage F2 behavioral → `tenure_df` | (LastPurchaseDate - FirstPurchaseDate).days. Inherited. |
| `compute_purchase_interval(df_transactions, customer_key=...) -> pd.DataFrame` | `features.transaction_behavior:312` | Stage F2 behavioral → `purchase_interval_df` | Invoice-level; NaN for < 2 invoices (NOT filled with 0); std ddof=1. FE-05 hard constraint. |
| `compute_active_days(df_transactions, customer_key=...) -> pd.DataFrame` | `features.transaction_behavior:388` | Stage F2 behavioral → `active_days_df` | Unique calendar dates per customer. Inherited. |
| `compute_average_invoice_value(df_candidates, customer_key=...) -> pd.DataFrame` | `features.transaction_behavior:419` | Stage F2 behavioral → `average_invoice_value_df` | Monetary / Frequency (FE-05 candidate version; **khác** FE-04 AverageTransactionValue). |
| `compute_diversity_features(df_base, customer_key=...) -> pd.DataFrame` | `features.diversity:67` (wraps `compute_products_per_invoice:18`) | Stage F2 diversity → `diversity_df` (ProductsPerInvoice) | ONE feature materialized (ProductsPerInvoice = ratio proxy). CategoryCount NOT materialized (FE-05 hard constraint). |
| `compute_cancellation_features(df_candidates, customer_key=...) -> pd.DataFrame` | `features.cancellation:107` | Stage F2 cancellation → `cancellation_df` (CancellationRate, ReturnRate) | FE-05 primitives. Ratios computed only where Frequency > 0 (no division by zero). |
| `build_candidate_features(df_base, recency_df, frequency_df, monetary_df, quantity_set, tenure_df, purchase_interval_df, active_days_df, average_invoice_value_df, products_per_invoice_df, cancellation_features_df, *, customer_key="CustomerID") -> CandidateDatasetResult` | `features.candidate_dataset:35` | Stage F2 final orchestration (11 separate DataFrames, NO wrapper) | Single function combines 11 separate feature DataFrames into the candidate feature matrix. **DEV-03 gọi 11 function riêng lẻ (không qua `compute_all_transaction_behavior` wrapper)** để đảm bảo 1-1 mapping với 11 parameter của `build_candidate_features`. |
| `validate_candidate_dataset(result, *, customer_key="CustomerID") -> dict` | `features.candidate_dataset:109` | Stage F2 post-build validation | 6 checks: unique_customers, no_category_count, one_monetary, one_frequency, one_quantity_set, critical_no_nan. Inherited verbatim. |

**Lý do KHÔNG dùng `compute_all_transaction_behavior` (wrapper):**
- Function này (`features.transaction_behavior:484`) trả về `TransactionBehaviorResult` dataclass gồm `.tenure_days`, `.purchase_interval`, `.active_days`, `.average_invoice_value`, `.quantity_variants` (một `QuantityVariants` dataclass).
- `build_candidate_features` yêu cầu 11 **separate** DataFrames làm parameter, không phải dataclass.
- Nếu dùng wrapper, DEV-03 phải unpack dataclass rồi vẫn rename columns từ `signed_set` cho `quantity_set` — không thực sự compact hơn.
- Trade-off: gọi 11 function riêng lẻ cho 1-1 mapping với parameter order của `build_candidate_features`; giúp code review dễ verify, dễ debug từng feature; không có magic trong orchestration.

**Bảo toàn FE-05 semantics:** Plan §1 stage F2 orchestration phải theo đúng thứ tự sau (mirror `run_fe05_feature_engineering.py:222-430`):

1. `compute_reference_date(df_transactions)` → `reference_date`
2. `compute_recency(df_base, reference_date, ...)` → `recency_df`
3. `compute_frequency_variants(df_transactions, df_base, ...)` + `materialize_frequency(..., mode=...)` → `frequency_materialized`
4. `compute_monetary_variants(df_transactions, df_base, ...)` + `materialize_monetary(..., mode=...)` → `monetary_materialized`
5. `compute_signed_quantity_set(df_transactions, df_base, ...)` → `signed_set`; rename columns → `quantity_set`
6. `compute_tenure_days(df_base, ...)` → `tenure_df`
7. `compute_purchase_interval(df_transactions, ...)` → `purchase_interval_df`
8. `compute_active_days(df_transactions, ...)` → `active_days_df`
9. **interim candidate** (chỉ để pass vào `compute_average_invoice_value`): merge `df_base` + `recency_df` + `frequency_materialized` + `monetary_materialized` → `interim_candidate_df`
10. `compute_average_invoice_value(interim_candidate_df, ...)` → `average_invoice_value_df`
11. `compute_diversity_features(df_base, ...)` → `diversity_df`
12. `compute_cancellation_features(interim_candidate_df, ...)` → `cancellation_df`
13. `build_candidate_features(df_base, recency_df, frequency_materialized, monetary_materialized, quantity_set, tenure_df, purchase_interval_df, active_days_df, average_invoice_value_df, diversity_df, cancellation_df, ...)` → `candidate_result`
14. `validate_candidate_dataset(candidate_result)` → `validation_checks`

Các bước 1-14 này là **wrap-and-call**; không introduce semantics mới, không invent feature mới.

#### 5.4.3. Cả hai sub-packages phải ADD (new symbols, không reuse)

- `preprocessed_id` derivation = `pp_<sha256(dataset_id + config_hash + content_sha256)>` (24 hex).
- Preprocessed artefact path resolution under `<storage_root>/<dataset_id>/preprocessed/`.
- Optional `transformation` × `scaling` × `imputation` stage (sklearn direct, NOT via `transformation.pipeline`).
- `PreprocessedManifest` schema (similar shape to DEV-02 manifest, with new `dataset_scope = PREPROCESSED_PROTOTYPE`, `preprocessing_block`, `feature_generation_block`, `ml_dataset_block`).
- Lifecycle status: `NOT_VALIDATED` / `VALIDATING` / `VALID` / `FAILED` (mirror DEV-02).
- Idempotency lookup by sha256 of (dataset_id + config_hash + content_sha256).
- Logging: per-stage log entries (timestamp, stage, level, message); aggregated to `<preprocessed_id>.log`.
- Import-blocklist test (mirror `test_dev02_import_blocklist.py`).
- Research-safety test (mirror `test_dev02_research_safety.py`).
- Consistency test (NEW, no DEV-02 equivalent): runs the same input through DEV-03 AND through the canonical FE-02/04/05/06 pipeline, compares outputs within tolerance (see AC §8).

### 5.5. Per-cleaning-rule status re-marking (CRITICAL)

FE-02 cleaning rules have a status annotation in `configs/preprocessing.yaml`:
- `WORKING_ASSUMPTION` for CL-01, CL-03, CL-04, CL-05, CL-07, CL-09, CL-10
- `PENDING_MENTOR_REVIEW` for CL-06, CL-08

When DEV-03 wraps these rules, the **prototype-layer manifest records the
inherited status verbatim**. DEV-03 does **NOT** re-classify or re-promote
the status. The status is a fact about the rule, owned by the research
methodology layer; DEV-03 just records it.

The manifest's `preprocessing_block.rules[].status` field is one of:
`WORKING_ASSUMPTION` | `PENDING_MENTOR_REVIEW` | `REVIEW_REQUIRED`.
Promotion of any status to `RESEARCH_APPROVED_FINAL` is owned by mentor +
ADR (AGENTS.md §2.10); not within DEV-03 scope.

## 6. Files dự kiến tạo / sửa

### 6.1. Implementation phase — file tạo MỚI (KHÔNG tạo trong plan này)

#### 6.1.1. `prototype.preprocessing` sub-package (10 files)

| Path | Mục đích |
|---|---|
| `src/customer_segmentation/prototype/__init__.py` | Package marker for `prototype.*` namespace. |
| `src/customer_segmentation/prototype/preprocessing/__init__.py` | Public API surface (re-exports). |
| `src/customer_segmentation/prototype/preprocessing/scope.py` | `PreprocessedScope`, `PreprocessingStage`, `TransformationMethod`, `ScalingMethod`, `ImputationMethod`, `OutlierAction`, `OutlierMethod` enums + frozen sets. |
| `src/customer_segmentation/prototype/preprocessing/storage.py` | Path resolution, `preprocessed_id` derivation, container sanity, idempotency lookup. |
| `src/customer_segmentation/prototype/preprocessing/pipeline.py` | Single-pipeline driver (Stage A→E); wraps `preprocessing.*` building blocks; optional sklearn transform/scale. |
| `src/customer_segmentation/prototype/preprocessing/manifest.py` | `PreprocessedManifest` dataclass + JSON I/O + stable/runtime classification. |
| `src/customer_segmentation/prototype/preprocessing/validation.py` | Input validation (Stage B) + 3-category final validation (Stage G1). |
| `src/customer_segmentation/prototype/preprocessing/list.py` | Enumerate preprocessed artefacts for a dataset_id. |
| `src/customer_segmentation/prototype/preprocessing/config_loader.py` | YAML loader for `configs/dev03_preprocessing.yaml` (frozenset + typed-error). |
| `src/customer_segmentation/prototype/preprocessing/logging_config.py` | Per-stage log emission (configurable level + output). |
| `configs/dev03_preprocessing.yaml` | DEV-03 default config (single source of truth for prototype-layer preprocessing + feature generation). |

#### 6.1.2. `prototype.feature_generation` sub-package (4 files)

| Path | Mục đích |
|---|---|
| `src/customer_segmentation/prototype/feature_generation/__init__.py` | Public API surface (re-exports). |
| `src/customer_segmentation/prototype/feature_generation/scope.py` | `FeatureGenerationScope`, `FeatureStatus` enums + frozen sets. |
| `src/customer_segmentation/prototype/feature_generation/pipeline.py` | Single-stage driver (Stage F1 aggregation + F2 features + F3 optional transform/scale on customer-level). |
| `src/customer_segmentation/prototype/feature_generation/manifest_block.py` | `FeatureGenerationBlock` dataclass (lives under `PreprocessedManifest`). |

#### 6.1.3. CLI (1 file)

| Path | Mục đích |
|---|---|
| `scripts/dev03_preprocess_dataset.py` | CLI entry point — orchestrates Stages A→G, uses both sub-packages. |

#### 6.1.4. Test files (14 files)

| Path | Mục đích |
|---|---|
| `tests/test_dev03_scope.py` | Enum values, classification (preprocessing). |
| `tests/test_dev03_storage.py` | Path resolution, `preprocessed_id` derivation, container sanity. |
| `tests/test_dev03_pipeline.py` | Single-pipeline driver integration tests (Stage A→E). |
| `tests/test_dev03_cleaning_wrap.py` | Tests that DEV-03 wrapping of FE-02 building blocks produces identical DataFrames to direct calls (refactor-safety). |
| `tests/test_dev03_optional_transform.py` | Optional transform/scale stage (none, log1p, yeo_johnson × none, standard, minmax, robust) — parametrised, all marked `WORKING_ASSUMPTION`. |
| `tests/test_dev03_manifest.py` | Manifest schema complete, stable vs runtime fields, idempotency. |
| `tests/test_dev03_validation.py` | Input validation (Stage B) + 3-category final validation (Stage G1) + lifecycle mapping. |
| `tests/test_dev03_list.py` | Enumerate preprocessed for a dataset_id. |
| `tests/test_dev03_feature_generation.py` | Stage F1 + F2 + F3 (aggregation, RFM/behavioral/cancellation, post-aggregation transform/scale). |
| `tests/test_dev03_consistency.py` | **NEW** — Compare DEV-03 output vs canonical FE-02/04/05/06 pipeline output on the same input, within tolerance. |
| `tests/test_dev03_logging.py` | Per-stage log emission, level filtering, file output. |
| `tests/test_dev03_research_safety.py` | Research artefacts not mutated (mirror DEV-02). |
| `tests/test_dev03_import_blocklist.py` | Forbidden import / surface names absent. |
| `tests/test_dev03_runtime_dependencies.py` | No forbidden libs in process (mirror DEV-02). |
| `tests/fixtures/__init__.py` | Empty marker for `tests/fixtures` package (allows `from tests.fixtures import consistency_input` if needed). |
| `tests/fixtures/consistency_input.csv` | Small CSV fixture (subset of Online Retail, ~1000 rows, multi-customer, includes 1+ cancellation, 1+ return) used as input for both DEV-03 pipeline AND `run_fe05_feature_engineering.py` (and optionally `run_fe06_transformation.py` for AC 38b) baseline. **Same input → independent pipeline runs → outputs compared.** Fixture schema: `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country` (8 columns matching `data_dictionary/dataset_schema.csv`). |

**Total: 32 new files** (vs 30 in the previous version, +2 for the consistency
fixture: `tests/fixtures/__init__.py` and `tests/fixtures/consistency_input.csv`).

### 6.2. File KHÔNG sửa trong DEV-03 (RESEARCH CORE — READ-ONLY)

- Toàn bộ `src/customer_segmentation/preprocessing/`, `transformation/`,
  `data/`, `aggregation/`, `features/`, `outlier_analysis/`, `clustering/`,
  `evaluation/`, `profiling/`, `visualization/`, `config/`. **NOTE**: Với
  revision 2026-10-09, `aggregation/` và `features/` đã được MOVE từ
  "out of scope" sang "READ-ONLY + reused by Stage F" (xem §5.2.2).
- `src/customer_segmentation/dataset_management/**` (DEV-02 already
  shipped; DEV-03 only consumes the public API).
- `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`, `scripts/run_ml0X_*.py`,
  `scripts/run_eva0X.py`, `scripts/run_cp0X.py`, `scripts/dev02_import_dataset.py`.
- `configs/*.yaml` (other than `configs/dev03_preprocessing.yaml`).
- `tests/test_*.py` (other than the new `tests/test_dev03_*.py`).
- `data/raw/**`, `data/processed/**`, `data/interim/**`, `data/external/**`,
  `data/prototype/**` (DEV-03 only **WRITES** to
  `data/prototype/datasets/<dataset_id>/preprocessed/`).
- `reports/**`.
- `notebooks/**`.

### 6.3. Plan file (this document)

| Path | Action | Mục đích |
|---|---|---|
| `docs/system/DEV-03_preprocessing.md` | **CREATED** (this file) | Plan, contract, acceptance criteria, traceability. |

> **Filename note:** User prompt đề xuất `docs/system/DEV-03_preprocessing_plan.md`
> (với hậu tố `_plan`). Quy ước đặt tên hiện có của repo là
> `DEV-01_project_setup.md`, `DEV-02_dataset_management.md` — KHÔNG có
> hậu tố `_plan`. Plan này dùng tên **`DEV-03_preprocessing.md`** để
> khớp với quy ước hiện có. Nếu mentor muốn dùng `_plan` hậu tố, đó
> là thay đổi convention cần ADR — out of scope của plan này.

## 7. Các bước triển khai nhỏ, theo thứ tự dependency

> **Step này dành cho Phase 2 (implementation) sau khi human approve
> plan này.** Plan hiện tại KHÔNG thực hiện bất kỳ step nào dưới đây.

1. **(Zero) Plan approval gate.** Chờ human approval gate
   (`APPROVE PHASE 2`).
2. **(1) Create `prototype.preprocessing` + `prototype.feature_generation`
   package skeletons.**
   - `src/customer_segmentation/prototype/__init__.py` (empty docstring).
   - `src/customer_segmentation/prototype/preprocessing/__init__.py` (will
     re-export at the end; initially empty).
   - `src/customer_segmentation/prototype/feature_generation/__init__.py`
     (same).
3. **(2) Implement preprocessing `scope.py` + `config_loader.py`.** Enums
   + frozen sets; YAML loader with frozenset validation + typed errors.
4. **(3) Implement `storage.py`.** Path resolution, `preprocessed_id`
   derivation, container sanity. Depends on (2).
5. **(4) Implement `logging_config.py`.** Configure Python `logging`
   for per-stage emission. Depends on (2) for level enum.
6. **(5) Write `tests/test_dev03_scope.py` + `test_dev03_storage.py` +
   `test_dev03_logging.py`.** TDD-first per AGENTS.md §4 step 5.
7. **(6) Implement preprocessing `pipeline.py` (Stages A→E).** Single-pipeline
   driver wrapping `preprocessing.*` building blocks + sklearn
   transform/scale. Depends on (2)(3)(4).
8. **(7) Implement preprocessing `validation.py` (Stage B + Stage G1).**
   Input validation + 3-category final validation. Depends on (2).
9. **(8) Implement preprocessing `manifest.py` (schema only, no
   feature_generation_block yet).** `PreprocessedManifest` dataclass +
   JSON I/O + stable/runtime field classification. Depends on (2) and
   `transformation.versioning.compute_file_sha256`.
10. **(9) Implement `list.py`.** Enumerate preprocessed for a dataset_id.
    Depends on (4) and (8).
11. **(10) Write `tests/test_dev03_pipeline.py` +
    `test_dev03_cleaning_wrap.py` + `test_dev03_optional_transform.py` +
    `test_dev03_manifest.py` + `test_dev03_validation.py` +
    `test_dev03_list.py`.** TDD for the modules above.
12. **(11) Implement feature_generation `scope.py`.** Enums + frozen sets.
    Mirror preprocessing scope.py style.
13. **(12) Implement feature_generation `pipeline.py` (Stage F).** Single
    stage driver: aggregation (F1) + features (F2) + optional
    transform/scale (F3). Wraps `aggregation.*` and `features.*`.
    Depends on (2)(3)(11) for shared utilities + (10) for the preprocessing
    output DataFrame (in CLI mode).
14. **(13) Implement feature_generation `manifest_block.py`.**
    `FeatureGenerationBlock` dataclass (lives under `PreprocessedManifest`).
    Depends on (8) and (11).
15. **(14) Write `tests/test_dev03_feature_generation.py`.** TDD for the
    Stage F pipeline + manifest_block.
16. **(14.5) Create `tests/fixtures/consistency_input.csv` +
    `tests/fixtures/__init__.py`.** Small CSV fixture (subset of Online
    Retail, ~1000 rows, multi-customer, includes 1+ cancellation, 1+ return)
    used as input for BOTH DEV-03 pipeline AND `scripts/run_fe05_feature_engineering.py`
    baseline (and optionally `scripts/run_fe06_transformation.py` for AC 38b).
    Schema: `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice,
    CustomerID, Country` (8 columns matching `data_dictionary/dataset_schema.csv`).
    Source: random sample from `data/raw/primary/Online Retail.xlsx`
    (git-ignored; manually sampled for test fixture). This is the only
    place where DEV-03 reads from `data/raw/primary/`; reads do NOT mutate.
17. **(15) Write `tests/test_dev03_consistency.py` (2 tests: AC 38a + 38b).**
    AC 38a (always run): load `tests/fixtures/consistency_input.csv` →
    run DEV-03 end-to-end → run `scripts/run_fe05_feature_engineering.py`
    on same fixture (no FE-06 step) → compare `ml_dataset_*.parquet` (DEV-03)
    với `customer_candidates.parquet` (FE-05) per criteria (a)-(g) in §8.1.5
    AC 38a (column set, row count, float tolerance, object SHA-256, NaN
    preservation, row order, column order). AC 38b
    (`@pytest.mark.c7_dependent`, skipped by default): same as 38a but
    configure DEV-03 với C7-like options + run `scripts/run_fe06_transformation.py`
    on the FE-05 output → compare DEV-03 ML Dataset với FE-06
    `final_clustering_dataset.parquet` (no CustomerID) + `customer_metadata.parquet`
    (CustomerID only); pre-comparison: inner-join FE-06 outputs on row index
    (FE-06 documented `alignment: "verified_by_position_and_unique_key"`),
    then drop CustomerID từ DEV-03 output, then compare. Conclusion: 38a is
    a regression check (C7-independent); 38b is a C7-config sanity check
    (C7-dependent, opt-in).
18. **(16) Write `configs/dev03_preprocessing.yaml`.** Single source of
    truth for DEV-03 config. Includes:
    - `preprocessing.cleaning` block (mirror of FE-02 schema, with status
      annotations re-marked per §5.5).
    - `preprocessing.transformation` block (transformation, scaling, imputation,
      numeric_columns).
    - `preprocessing.outlier` block (action, method, columns, thresholds).
    - `preprocessing.logging` block (level, output path, format).
    - `preprocessing.storage` block (output_format: parquet; emit_intermediate
      bool; csv_max_rows; output_dir_relative).
    - `preprocessing.research_safety` block (readonly_paths).
    - `feature_generation.aggregation` block (mirror of `aggregation.yaml`
      schema; source.relative_path can be the preprocessed intermediate
      OR the cleaned transaction-level from preprocessing pipeline).
    - `feature_generation.features` block (mirror of `feature_engineering.yaml`
      schema; selection_gates, monetary_strategy, frequency_strategy, etc.).
    - `feature_generation.optional_transform` block (post-aggregation
      transformation + scaling for customer-level feature matrix; same
      options as preprocessing transformation, separately configurable).
    - `feature_generation.reference_date` block (computation method;
      allowed: `from_config`, `from_data_max`).
19. **(17) Implement `scripts/dev03_preprocess_dataset.py`.** Thin CLI
    mirroring `scripts/dev02_import_dataset.py`. Orchestrates: load
    config → Stage A → Stage B → Stage C → Stage D → Stage E → Stage F
    (via feature_generation.pipeline) → Stage G (write + log + manifest).
    Depends on (1)..(15) + (16) + (17).
20. **(18) Write `tests/test_dev03_research_safety.py` +
    `test_dev03_import_blocklist.py` + `test_dev03_runtime_dependencies.py`.**
    Mirror DEV-02 defence-in-depth. The import-blocklist test MUST also
    cover `customer_segmentation.aggregation.*` and
    `customer_segmentation.features.*` allowed imports (allow-list assertion)
    AND forbidden `customer_segmentation.clustering` etc. (deny-list assertion).
21. **(19) Run full test suite.** `pytest tests/test_dev03_*.py -q` + full
    `pytest` (no regression per AGENTS.md §2.8). The consistency test
    AC 38a always runs; AC 38b marked `@pytest.mark.c7_dependent` and
    skipped by default (only run when user explicitly enables C7-like
    config).
22. **(20) Run lint + format check.** `ruff check .`, `black --check .`
    (DEV-03 additions only; do NOT touch pre-existing findings per
    AGENTS.md §2.4 + DEV-01 §7.1.1).
23. **(21) Smoke test on real data.** Import a CSV via DEV-02, then
    preprocess via DEV-03. Verify preprocessed artefact + ML Dataset +
    manifest + log are written, research paths unchanged, ML Dataset
    columns match FE-05 candidate dataset schema (allow column reordering).
24. **(22) Plan-level review + completion report.** Mirror DEV-02's
    completion summary (Vietnamese; sections per AGENTS.md §7).

## 8. Acceptance criteria có thể kiểm chứng

Acceptance criteria mapped 1:1 to the **5 Jira acceptance items** (pipeline
runs / configuration / logging / output Dataset / consistency with research),
expanded per the 7 pipeline stages.

### 8.1. Acceptance criteria grouped by Jira AC

#### 8.1.1. AC-1: Pipeline chạy được end-to-end (Jira AC #1)

| # | Criterion | Verification |
|---|---|---|
| 1 | `python -c "from customer_segmentation.prototype.preprocessing import preprocess_dataset"` exits 0. | Smoke import. |
| 2 | `python -c "from customer_segmentation.prototype.feature_generation import generate_features"` exits 0. | Smoke import. |
| 3 | End-to-end CSV happy path: DEV-02 import → DEV-03 preprocess → preprocessed artefact + ML Dataset + manifest + log written. | `tests/test_dev03_pipeline.py::test_csv_happy_path`. |
| 4 | End-to-end Parquet happy path. | `tests/test_dev03_pipeline.py::test_parquet_happy_path`. |
| 5 | All 7 stages (A, B, C, D, E, F, G) execute in correct order; failure of any single stage aborts the pipeline (no partial artefact). | `tests/test_dev03_pipeline.py::test_seven_stage_execution_order` + `test_stage_failure_aborts_pipeline`. |
| 6 | Stage A: input lookup via DEV-02 public API works; refuses invalid dataset_id, wrong scope, wrong validation_status. | `tests/test_dev03_pipeline.py::test_stage_a_input_lookup`. |
| 7 | Stage B: input validation runs (basic_overview + structural checks + coerce_dtypes). | `tests/test_dev03_pipeline.py::test_stage_b_input_validation`. |
| 8 | Stage C: cleaning runs (5 sub-stages B0..B4). | `tests/test_dev03_pipeline.py::test_stage_c_cleaning_5_substages`. |
| 9 | Stage D: optional transformation runs (log1p / yeo_johnson / none). | `tests/test_dev03_pipeline.py::test_stage_d_transformation`. |
| 10 | Stage E: optional scaling runs (standard / minmax / robust / none). | `tests/test_dev03_pipeline.py::test_stage_e_scaling`. |
| 11 | Stage F: feature generation runs (aggregation + RFM/behavioral/cancellation + optional post-aggregation transform/scale). | `tests/test_dev03_feature_generation.py::test_stage_f_aggregation_plus_features`. |
| 12 | Stage G: ML Dataset write + final validation + manifest + log all written atomically. | `tests/test_dev03_pipeline.py::test_stage_g_write_atomic`. |

#### 8.1.2. AC-2: Có configuration (single source of truth via YAML) (Jira AC #2)

| # | Criterion | Verification |
|---|---|---|
| 13 | `configs/dev03_preprocessing.yaml` exists; has blocks: `preprocessing.{cleaning,transformation,outlier,logging,storage,research_safety}` + `feature_generation.{aggregation,features,optional_transform,reference_date}`. | `test_dev03_validation.py::test_config_yaml_schema_blocks_present`. |
| 14 | All 7 stages are individually configurable: each stage can be skipped, no-op, or replaced via YAML without code change. | `tests/test_dev03_pipeline.py::test_each_stage_configurable`. |
| 15 | Optional transform/scale stage: 3 transformations × 4 scalings = 12 combos, all produce numeric output with no NaN/Inf. | `tests/test_dev03_optional_transform.py::test_grid_all_combos_produce_numeric_output`. |
| 16 | Outlier off by default (matches FE-02 default). | `tests/test_dev03_pipeline.py::test_outlier_off_by_default`. |
| 17 | Cancellation / return flagging on by default (matches FE-02 default). | `tests/test_dev03_pipeline.py::test_cancellation_return_flagging_on_by_default`. |
| 18 | Validation status mapping per stage (Stage B / G1) configurable (strict / lenient). | `tests/test_dev03_validation.py::test_validation_status_mapping_configurable`. |
| 19 | Config hash is part of `preprocessed_id` (different config → different `preprocessed_id`). | `tests/test_dev03_storage.py::test_config_hash_in_preprocessed_id`. |

#### 8.1.3. AC-3: Có logging (per-stage emission) (Jira AC #3)

| # | Criterion | Verification |
|---|---|---|
| 20 | Per-stage log file `<preprocessed_id>.log` is written under `data/prototype/<dataset_id>/preprocessed/`. | `tests/test_dev03_logging.py::test_log_file_written_per_run`. |
| 21 | Each stage (A→G) emits at least one log entry: stage name, timestamp, status, key metrics (row counts, columns, durations). | `tests/test_dev03_logging.py::test_log_per_stage_emission`. |
| 22 | Log level configurable via YAML (DEBUG / INFO / WARNING / ERROR); level filter applied. | `tests/test_dev03_logging.py::test_log_level_configurable`. |
| 23 | Log format includes stage transition + per-stage summary; structured enough for post-hoc analysis. | `tests/test_dev03_logging.py::test_log_format_structured`. |
| 24 | Failures emit ERROR-level log with stack trace; log file is preserved on failure. | `tests/test_dev03_logging.py::test_failure_log_preserved`. |

#### 8.1.4. AC-4: Có output Dataset (ML Dataset + intermediate) (Jira AC #4)

| # | Criterion | Verification |
|---|---|---|
| 25 | ML Dataset (customer-level feature matrix) is written as parquet under `data/prototype/<dataset_id>/preprocessed/`. | `tests/test_dev03_pipeline.py::test_ml_dataset_written_as_parquet`. |
| 26 | ML Dataset columns = customer-level features (post FE-05 `build_candidate_features`); row count = unique customer count. | `tests/test_dev03_feature_generation.py::test_ml_dataset_shape_and_columns`. |
| 27 | Intermediate cleaned transaction-level data is written (when `config.storage.emit_intermediate = true`) as `preprocessed_<ts>_<hex>.parquet`. | `tests/test_dev03_pipeline.py::test_intermediate_written_when_configured`. |
| 28 | `PreprocessedManifest` is written as `preprocessed_manifest.json` with full schema (per §10.4 + `feature_generation_block`). | `tests/test_dev03_manifest.py::test_manifest_schema_complete`. |
| 29 | `preprocessed_id` derivation deterministic. | `tests/test_dev03_storage.py::test_preprocessed_id_deterministic`. |
| 30 | Re-preprocess idempotent: same input + same config → same `preprocessed_id`. | `tests/test_dev03_manifest.py::test_repreprocess_idempotent_same_preprocessed_id`. |
| 31 | `dataset_scope == PREPROCESSED_PROTOTYPE` always. | `tests/test_dev03_manifest.py::test_scope_always_preprocessed_prototype`. |
| 32 | `research_safety.automatically_promoted_to_research == false` always. | `tests/test_dev03_research_safety.py::test_no_automatic_research_promotion`. |
| 33 | Pre/post SHA-256 of `data/raw/primary`, `data/raw/backup`, `data/processed`, `reports/` unchanged. | `tests/test_dev03_research_safety.py::test_research_artifacts_unmodified`. |
| 34 | `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's) unchanged after DEV-03 run. | `tests/test_dev03_research_safety.py::test_dev02_manifest_unmodified`. |
| 35 | Validation 3 categories work, lifecycle status mapping correct. | `tests/test_dev03_validation.py::test_three_category_validation` + `test_lifecycle_status_mapping`. |
| 36 | FAILED validation → no artefact written (no partial artefact). | `tests/test_dev03_validation.py::test_failed_validation_no_partial_artifact`. |
| 37 | `list_preprocessed(dataset_id)` returns correct preprocessed entries. | `tests/test_dev03_list.py::test_list_after_preprocess`. |

#### 8.1.5. AC-5: Kết quả nhất quán với nghiên cứu (Jira AC #5)

> **Sửa đổi 2026-10-09 (re-audit):** Consistency test split thành **38a (C7-independent, always run)** và **38b (C7-dependent, opt-in)** để tách implementation khỏi C7 status decision. Mỗi test có contract riêng.

| # | Criterion | Verification |
|---|---|---|
| **38a** | **Consistency với FE-05 candidate (C7-INDEPENDENT, ALWAYS RUN).** Run DEV-03 end-to-end trên `tests/fixtures/consistency_input.csv` (sau khi DEV-02 import); also run `scripts/run_fe05_feature_engineering.py` trên cùng fixture input (no FE-06 step); compare DEV-03 `ml_dataset_*.parquet` output với FE-05 `customer_candidates.parquet` baseline: (a) same column set (CustomerID + 14 candidate features); (b) same row count (= unique customer count); (c) float columns within tolerance (`numpy.testing.assert_allclose(rtol=1e-5, atol=1e-7)` — `numpy.allclose` default); (d) object/categorical columns SHA-256 match per column; (e) NaN preserved (PurchaseIntervalMean/Std = NaN cho customer có < 2 invoices; `numpy.allclose` returns True cho NaN==NaN); (f) row order: same sort (CustomerID ascending; FE-05 sorts internally in `aggregate_customer_base:280` via `sort_values(["TotalMonetary", customer_key], ascending=[False, True])` — DEV-03 phải mirror sort order); (g) column order: không cần match (use set comparison for column set, then iterate shared columns). Conclusion limit: đây là **consistency check**, không phải correctness proof. Pass = DEV-03 wrap-and-call pattern không drift; fail = có regression trong wrap logic. | `tests/test_dev03_consistency.py::test_dev03_matches_fe05_candidate` (always run; no marker). |
| **38b** | **Consistency với FE-06 final (C7-DEPENDENT, OPT-IN).** Chỉ chạy khi `configs/dev03_preprocessing.yaml` configured với `feature_generation.optional_transform = {transformation: yeo_johnson, scaling: robust, imputation: median}` (C7-like). Run DEV-03 + `scripts/run_fe06_transformation.py` trên cùng fixture. Compare DEV-03 `ml_dataset_*.parquet` (CustomerID + 14 transformed features) với FE-06 `final_clustering_dataset.parquet` (NO CustomerID) + `customer_metadata.parquet` (CustomerID only). Pre-comparison: (i) inner-join FE-06 `final_clustering_dataset` với `customer_metadata` trên row index (FE-06 documented in `run_fe06_transformation.py:16-47`: `metadata row order giu nguyen source candidate order`, `alignment: "verified_by_position_and_unique_key"`); (ii) drop CustomerID từ DEV-03 output. Compare: same column set (14 features, no CustomerID), same row count, float columns within `numpy.allclose(rtol=1e-5, atol=1e-7)`. NaN handling: FE-06 imputes PurchaseIntervalMean/Std với median trước khi transform; DEV-03 phải cùng imputation step. Conclusion limit: test này chỉ pass khi C7 status resolved; hiện tại đánh dấu `@pytest.mark.c7_dependent`, default skip. | `tests/test_dev03_consistency.py::test_dev03_matches_fe06_final_c7_like` (marked `@pytest.mark.c7_dependent`, skipped by default). |
| 39 | Cleaning wrap = identical DataFrame to direct call (refactor-safety). | `tests/test_dev03_cleaning_wrap.py::test_cleaning_wrap_identical_to_direct`. |
| 40 | Feature generation wrap (aggregation + features) = identical DataFrame to direct call. | `tests/test_dev03_feature_generation.py::test_feature_gen_wrap_identical_to_direct`. |
| 41 | `preprocessing_block.rules[].status` inherits FE-02 status annotations verbatim (no reclassification). | `tests/test_dev03_manifest.py::test_rules_status_inherited_verbatim`. |
| 42 | `feature_generation_block.aggregation.status` and `feature_generation_block.features.status` inherit `WORKING_ASSUMPTION` annotations from FE-04 / FE-05 configs verbatim. | `tests/test_dev03_manifest.py::test_feature_gen_status_inherited_verbatim`. |

#### 8.1.6. Defence-in-depth (DEV-02 mirror, not Jira AC but required)

| # | Criterion | Verification |
|---|---|---|
| 43 | Forbidden imports absent (no `fastapi`, `flask`, `sqlalchemy`, etc.). | `tests/test_dev03_import_blocklist.py`. |
| 44 | No new third-party dependency added. | `tests/test_dev03_runtime_dependencies.py`. |
| 45 | Existing test suite not regressed (pre/post pass-fail map). | full `pytest`; per AGENTS.md §2.8, no regression. |
| 46 | Lint clean for DEV-03 additions only (pre-existing findings = N/A). | `ruff check src/customer_segmentation/prototype/ scripts/dev03_preprocess_dataset.py configs/dev03_preprocessing.yaml tests/test_dev03_*.py` |
| 47 | Format clean for DEV-03 additions only. | `black --check <same paths>`. |
| 48 | Documentation complete (`docs/system/DEV-03_preprocessing.md` written — this plan). | File exists. |

## 9. Test plan và lệnh kiểm thử dự kiến

### 9.1. Test files (mirror DEV-02 §12.1 naming convention)

```
tests/
    test_dev03_scope.py                       — enum values, classification (3-5 tests)
    test_dev03_storage.py                     — path resolution, container sanity,
                                                preprocessed_id derivation (8-10 tests)
    test_dev03_logging.py                     — per-stage log emission, level,
                                                file output (8-10 tests)
    test_dev03_pipeline.py                    — single-pipeline driver integration,
                                                all 7 stages (15-20 tests)
    test_dev03_cleaning_wrap.py               — wrap-vs-direct refactor safety (5-7 tests)
    test_dev03_optional_transform.py          — 3 trans × 4 scale = 12 combos
                                                (parametrised; 12-15 tests)
    test_dev03_feature_generation.py          — Stage F1 + F2 + F3 (aggregation +
                                                RFM/behavioral/cancellation + post-
                                                aggregation transform/scale)
                                                (12-15 tests)
    test_dev03_consistency.py                 — 2 tests: AC 38a (DEV-03 vs FE-05
                                                candidate, always run) + AC 38b
                                                (DEV-03 vs FE-06 final,
                                                @pytest.mark.c7_dependent,
                                                skipped by default) (3-5 tests)
    test_dev03_manifest.py                    — manifest schema, stable vs runtime,
                                                idempotency, feature_generation_block
                                                (10-12 tests)
    test_dev03_validation.py                  — Stage B + Stage G1, 3 categories,
                                                lifecycle mapping (10-12 tests)
    test_dev03_list.py                        — enumerate preprocessed (5-7 tests)
    test_dev03_research_safety.py             — research artefacts not mutated (5-6 tests)
    test_dev03_import_blocklist.py            — forbidden import / surface absent,
                                                aggregation + features allowed (3-5 tests)
    test_dev03_runtime_dependencies.py        — no forbidden libs in process (3-5 tests)
```

Estimated total: **~95-125 tests** (a significant increase vs the previous
70-90 due to the addition of feature generation, consistency, and logging
test files).

### 9.2. Edge cases per stage

```
[Pipeline Stage A — Dataset (input lookup)]
  - dataset_id not found → DatasetNotFound
  - dataset_scope != IMPORTED_PROTOTYPE → reject
  - validation_status != VALID → reject (NEEDS_CONFIRMATION — see §13.1 DEV-03-OPEN-02)
  - artefact_path missing on disk → reject
  - file too large → reject (mirror DEV-02 max_file_size_mb)
  - source file outside repo + --allow-external-source off → reject (mirror DEV-02)

[Pipeline Stage B — Validation (input validation)]
  - empty dataset (0 rows) → structural FAIL → no write
  - missing required columns (InvoiceDate, CustomerID, InvoiceNo, StockCode, Quantity, UnitPrice) → structural FAIL
  - wrong dtypes for required columns → coerce_dtypes applied; warning logged; proceed
  - all-NaN column → flagged in manifest; no crash
  - row count > 0 + col count > 0 → proceed

[Pipeline Stage C — Cleaning]
  - empty dataset (0 rows) → structural FAIL → no write
  - all-NaN column → handled by coerce_dtypes + invalid_records; no crash
  - duplicate columns → handled
  - mixed types in one column → flagged in manifest; no crash
  - missing values after invalid-record drops → apply configured strategy
  - exact-row duplicates → dropped (mirror FE-02 CL-09)

[Pipeline Stage D — Transformation (optional)]
  - transformation = none → no-op; identity check
  - transformation = log1p on negative-valued column → reject (FE-06 A2 rule
    inherited)
  - transformation = yeo_johnson on constant column → handled (sklearn
    returns same values; no crash)
  - transformation = yeo_johnson on numeric column with NaN → reject with
    clear error (NaN must be handled in Stage C first)
  - 3 transformations × 4 scalings (cross with Stage E) all produce numeric
    output

[Pipeline Stage E — Scaling (optional)]
  - scaling = none → no-op; identity check
  - scaling = standard → output mean≈0, std≈1 (within tolerance)
  - scaling = minmax → output in [0, 1]
  - scaling = robust → output median≈0, IQR≈1 (within tolerance)
  - empty numeric_columns list → skip stage
  - numeric column with all-NaN → reject with clear error (must be handled
    in Stage C first)

[Pipeline Stage F — Feature Generation]
  - F1 aggregation:
    - empty cleaned transaction-level (post-Stage-C) → FAIL → no write
    - single customer only → produces 1-row customer-level base dataset
      (allowed; V-07 distinct_invoice_count >= 1 still satisfied)
    - duplicate CustomerID after aggregation → V-02 violation → FAIL
    - cancellation rate / return rate computation works on transaction-level
      data with cancellation flags (mirror FE-02 CL-06/CL-08)
  - F2 features (RFM / behavioral / cancellation):
    - reference_date = "from_config" → use configured date (default:
      max(InvoiceDate) in input + 1 day, per FE-05 default)
    - reference_date = "from_data_max" → compute from input max(InvoiceDate)
    - RFM: ONE Monetary materialized (MonetarySigned by default)
    - RFM: ONE Frequency materialized (Frequency_ByInvoice by default)
    - PurchaseInterval: ddof=1, NaN for < 2 invoices (FE-05 hard constraint)
    - CategoryCount NOT materialized (FE-05 hard constraint; no test needed
      since not called; if accidentally called → fail loudly)
    - ProductsPerInvoice is ratio proxy (no NaN for single-invoice customers)
  - F3 optional transform/scale on customer-level:
    - default: transformation=none, scaling=none → no-op; identity check
    - same options as Stage D/E, separately configurable
    - 12-cell grid (3 trans × 4 scale) all produce numeric output

[Pipeline Stage G — ML Dataset write + final validation]
  - Valid ML Dataset → PASS, lifecycle = VALID
  - Empty ML Dataset (0 rows) → FAIL
  - Constant column → WARNING, lifecycle = VALID
  - NaN present in numeric output → FAIL (transform/scale should not
    introduce NaN; if it does, stage F3 fails before G)
  - Inf present → FAIL
  - status mapping PASS → VALID, FAIL → FAILED
  - Atomic write: temp file unlinked on exception
  - FAILED validation → no partial artefact (no preprocessed_*.parquet,
    no ml_dataset_*.parquet, no manifest, no log)
  - Storage-root path inside data/prototype/datasets/<dataset_id>/preprocessed/ only

[Idempotency / manifest]
  - Same dataset + same config → same preprocessed_id
  - Re-preprocess (same input) → no new artefact, last_seen_utc updated
  - Different config → different preprocessed_id (content-addressed)
  - manifest.dataset_scope == PREPROCESSED_PROTOTYPE always
  - manifest.preprocessing_block.rules[] inherits FE-02 status annotations
    verbatim (no reclassification)
  - manifest.feature_generation_block.aggregation.status and
    .features.status inherit FE-04 / FE-05 status annotations verbatim

[Consistency with research — AC 38a (C7-INDEPENDENT, always run)]
  - Fixture: `tests/fixtures/consistency_input.csv` (1000 rows, multi-customer,
    1+ cancellation, 1+ return).
  - Baseline: run `scripts/run_fe05_feature_engineering.py` on the same
    fixture input; output = `customer_candidates.parquet` (14 features + CustomerID).
  - DEV-03: run on same fixture (after DEV-02 import); output =
    `ml_dataset_*.parquet` (CustomerID + 14 features).
  - Comparison:
    (a) `set(dev03.columns) == set(candidate.columns)` (column set match;
        allow column reordering)
    (b) `dev03.shape[0] == candidate.shape[0]` (row count = unique
        customer count; both pipelines sort by CustomerID ascending)
    (c) For each shared numeric column: `numpy.testing.assert_allclose(
        dev03[col].values, candidate[col].values, rtol=1e-5, atol=1e-7)`.
        NaN == NaN is True (preserved by `numpy.allclose`).
    (d) For each shared object column: SHA-256 match
        (`hashlib.sha256(col.astype(str).values.tobytes()).hexdigest()`).
    (e) Conclusion: pass = wrap-and-call pattern không drift; fail = có
        regression trong wrap logic (cần debug Stage F2 orchestration).
  - Note: AC 38a KHÔNG chạy FE-06 (transformation); chỉ compare với
    FE-05 candidate (pre-FE-06).

[Consistency with research — AC 38b (C7-DEPENDENT, opt-in)]
  - Fixture: same `tests/fixtures/consistency_input.csv`.
  - Baseline: run `scripts/run_fe05_feature_engineering.py` → run
    `scripts/run_fe06_transformation.py`; outputs =
    `customer_candidates.parquet` + `final_clustering_dataset.parquet`
    (14 transformed features, NO CustomerID) + `customer_metadata.parquet`
    (CustomerID only).
  - DEV-03: configure với `feature_generation.optional_transform = {
    transformation: yeo_johnson, scaling: robust, imputation: median }`
    (C7-like) và run on same fixture; output = `ml_dataset_*.parquet`
    (CustomerID + 14 transformed features).
  - Pre-comparison (mandatory):
    (i) FE-06: `final_inner = final_matrix.merge(metadata, left_index=True,
        right_index=True, how="inner")` — FE-06 documented
        `alignment: "verified_by_position_and_unique_key"`; row order
        giữ nguyên source candidate order.
    (ii) DEV-03: `dev03_features = dev03.drop(columns=["CustomerID"])`
    (iii) `numpy.testing.assert_allclose(fe06_inner_features.shape,
         dev03_features.shape)` (row count match); reindex
         `dev03_features` by CustomerID order from `fe06_inner["CustomerID"]`.
  - Comparison:
    (a) `set(dev03_features.columns) == set(fe06_inner_features.columns)`
    (b) `dev03_features.shape[0] == fe06_inner_features.shape[0]`
    (c) For each shared column: `numpy.testing.assert_allclose(rtol=1e-5,
        atol=1e-7)`. NaN đã được imputed bởi FE-06 (median for
        PurchaseIntervalMean/Std) nên không còn NaN.
  - Note: AC 38b is `@pytest.mark.c7_dependent`, default skip. Chỉ chạy
    khi user explicitly configure DEV-03 với C7-like config. Kết quả
    test này KHÔNG quyết định implementation success; chỉ là sanity
    check nếu user opt-in vào C7-like path.

[Logging (Jira AC #3)]
  - Log file `<preprocessed_id>.log` written under
    `data/prototype/<dataset_id>/preprocessed/`
  - Per-stage log entries: stage name, timestamp, level, key metrics
  - Level filter (DEBUG / INFO / WARNING / ERROR) applied
  - Failures: ERROR log + stack trace + log file preserved on failure

[Research safety]
  - pre/post snapshot SHA-256 + mtime of data/raw/primary,
    data/raw/backup, data/processed, reports/ → unchanged
  - data/prototype/datasets/<dataset_id>/manifest.json (DEV-02's) SHA-256
    unchanged
  - No write to data/processed/, data/raw/, reports/

[Import blocklist]
  - prototype.preprocessing does NOT import fastapi, flask, django, uvicorn,
    sqlalchemy, psycopg2, redis, celery, rq, pymongo, aiosqlite, jinja2,
    gunicorn, starlette, boto3, httpx
  - prototype.preprocessing does NOT import from customer_segmentation.clustering,
    .evaluation, .profiling, .outlier_analysis, .visualization
  - prototype.preprocessing MAY import from customer_segmentation.preprocessing,
    .data, .transformation.versioning, .config.loader (pattern),
    .dataset_management
  - prototype.feature_generation does NOT import fastapi, flask, etc.
  - prototype.feature_generation does NOT import from customer_segmentation.clustering,
    .evaluation, .profiling, .outlier_analysis, .visualization,
    .transformation.{scaling,pipeline}
  - prototype.feature_generation MAY import from customer_segmentation.aggregation,
    .features, .prototype.preprocessing, .data.audit,
    .transformation.versioning, .dataset_management
```

### 9.3. Verification commands (Phase 2)

```bash
# Unit + integration
PYTHONPATH=src pytest tests/test_dev03_*.py -q --tb=line

# Full test suite (no-regression check)
PYTHONPATH=src pytest -q --tb=line

# Lint (DEV-03 additions only)
ruff check src/customer_segmentation/prototype/preprocessing/ \
           scripts/dev03_preprocess_dataset.py \
           configs/dev03_preprocessing.yaml \
           tests/test_dev03_*.py

# Format
black --check <same paths>

# Research-safety smoke
PYTHONPATH=src python scripts/dev02_import_dataset.py --file <test.csv>
PYTHONPATH=src python scripts/dev03_preprocess_dataset.py --dataset-id <id>
git diff --stat data/raw/ data/processed/ reports/  # expect empty

# Git-ignore check on new preprocessed sub-tree
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/
# expect: .gitignore:114:/data/prototype/** ...
```

### 9.4. Acceptance vs pre-existing baseline

Acceptance = no regression vs pre-DEV-03 baseline (DEV-01 §7.1.1
disposition). The pre-DEV-03 baseline is **1468 passed** (per
`docs/system/DEV-01_project_setup.md` §4.1). This is **informational**,
not a pass/fail threshold.

> **NEEDS_CONFIRMATION** (see §13.1 DEV-03-OPEN-05): confirm with
> human researcher whether they want a hard regression floor (e.g.
> "all 1468 must still pass") or the DEV-02 "no-regression map"
> pattern (per `tests/test_dev02_research_safety.py`). The plan defaults
> to the DEV-02 pattern.

## 10. Research safety, provenance, artifact isolation

### 10.1. Hard rule — never write to research artefacts

DEV-03 **must not** write, mutate, delete, or rename anything under:

- `data/raw/primary/**`
- `data/raw/backup/**`
- `data/processed/**` (FE-06 canonical `ba54033e...80f9c` lives here)
- `reports/**` (FE-01..06, EXP-01..05, EVA-01..03, CP-01..05 evidence)
- `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's manifest
  is **read-only** for DEV-03 — DEV-03 writes only to
  `data/prototype/datasets/<dataset_id>/preprocessed/`)

Enforcement:

- **Storage root constraint:** the only writable location is
  `data/prototype/datasets/<dataset_id>/preprocessed/`. Like DEV-02,
  the storage root is **fixed in config** (no CLI override).
- **Import-blocklist test** asserts that `prototype.preprocessing`
  cannot import from any research-core module that would have side
  effects on research paths.
- **Research-safety test** snapshots the four research paths (SHA-256 +
  mtime) before and after, asserts unchanged.
- **DEV-02 manifest test** snapshots `data/prototype/datasets/<dataset_id>/manifest.json`
  before and after, asserts unchanged.

### 10.2. Read-side access policy (mirror DEV-02 §11.2)

DEV-03 inherits the DEV-02 read-isolation model: the user may pass
`--file` (in DEV-02) pointing to `data/raw/primary/...` if they have
read access. DEV-03 cannot re-import a dataset — it consumes the
DEV-02 manifest, not the source file directly. The DEV-02 public API
is the only entry point.

### 10.3. Source-path portability

The DEV-03 manifest inherits the DEV-02 manifest's source-path
policy: `provenance.source_filename` is portable; `provenance.source_relative_path`
is null for external source with `--allow-external-source`. DEV-03
adds a `preprocessing_block.input_provenance` field referencing the
DEV-02 `dataset_id` (content-addressed) — this is the **only**
way DEV-03 references the input.

### 10.4. Provenance snapshot in PreprocessedManifest

| Field | Source | Purpose |
|---|---|---|
| `preprocessed_id` | `pp_<sha256(dataset_id + config_hash + content_sha256)[:24]>` | Content-addressed identity (mirror DEV-02 pattern) |
| `source_dataset_id` | from DEV-02 manifest | Pointer to DEV-02 |
| `source_dataset_sha256` | from DEV-02 manifest | Pointer to source content |
| `config_hash` | SHA-256 of `configs/dev03_preprocessing.yaml` at run time | Reproducibility contract (AGENTS.md §2.7) |
| `preprocessing_block.config_snapshot` | full preprocessing config dict at run time | Allows reproduction from manifest alone |
| `preprocessing_block.rules[].status` | inherited from `configs/preprocessing.yaml` KEY_ANNOTATIONS | Per-rule status (verbatim, no reclassification) |
| `feature_generation_block.aggregation.status` | inherited from `configs/aggregation.yaml` | Verbatim, no reclassification |
| `feature_generation_block.features.status` | inherited from `configs/feature_engineering.yaml` | Verbatim, no reclassification |
| `feature_generation_block.reference_date` | from config or computed from data | Reproducibility |
| `ml_dataset_block.row_count`, `.column_count`, `.columns[]`, `.sha256` | computed at Stage G | Customer-level feature matrix summary |
| `environment.python`, `.platform`, `.key_libraries` | sys, platform, package versions | 5-field reproducibility contract (SYS-02 §9.2) |
| `created_utc`, `last_seen_utc` | runtime | Idempotency lookup |
| `log_file` | relative path to `<preprocessed_id>.log` | Audit trail (Jira AC #3) |
| `research_safety.automatically_promoted_to_research = false` | hard-coded | Guarantee that DEV-03 output is never research evidence |
| `research_safety.readonly_paths_unmodified[]` | hard-coded list of 4 research paths | Document the safety contract |

### 10.5. Git-ignore (already covered by DEV-02 §7.3 fix)

`data/prototype/**` is already git-ignored (`.gitignore` line 114,
per DEV-02 §7.3). DEV-03 writes into the same `data/prototype/`
sub-tree, so no `.gitignore` change is needed. The preprocessed
sub-tree is automatically git-ignored.

## 11. Traceability — Research → System → Implementation → Test

| Research / methodology source | System requirement (SYS-01) | Implementation (DEV-03) | Test |
|---|---|---|---|
| FE-02 cleaning pipeline (`preprocessing/cleaning.py` 5 stages) | FR-DATA-02 (validate dataset schema) | `prototype.preprocessing.pipeline.cleaning_stage` (wraps FE-02 building blocks) | `test_dev03_cleaning_wrap` + `test_dev03_pipeline` |
| FE-02 invalid-record rules (CL-01..CL-10) | FR-DATA-02 (no NaN/Inf) | `prototype.preprocessing.pipeline.invalid_stage` (wraps `apply_invalid_rules`) | `test_dev03_pipeline::test_invalid_record_application` |
| FE-02 missing-value strategies | n/a (informational) | `prototype.preprocessing.pipeline.missing_stage` (wraps `handle_missing`) | `test_dev03_pipeline::test_missing_strategy_*` |
| FE-02 outlier policy (off by default, PENDING_MENTOR_REVIEW) | NFR-06 (methodology gate) | `prototype.preprocessing.pipeline.outlier_stage` (off by default; mirrors FE-02) | `test_dev03_pipeline::test_outlier_off_by_default` |
| FE-06 C7 (transformation options) — info only | FR-EXP-03 (preprocessing = FE-06 C7 in SYS, but DEV-03 is a SEPARATE layer) | `prototype.preprocessing.pipeline.optional_transform_stage` (NOT C7-bound; surfaces options) | `test_dev03_optional_transform::test_grid_all_combos` |
| FE-06 status annotation (C7 = WORKING_ASSUMPTION, WA-01) | NFR-06 | `preprocessing_block.rules[].status` inherits verbatim | `test_dev03_manifest::test_rules_status_inherited_verbatim` |
| EXP-04 limitation LIM-05 (log1p not full-matrix comparable) | n/a | DEV-03 surfaces `log1p` as one of 3 transformation options; user's choice; if applied to negative-valued column, the FE-06 A2 rule "log1p on negative = reject" is reused | `test_dev03_optional_transform::test_log1p_rejects_negative_column` |
| EXP-04 Family A (RFM-only) DEFERRED | n/a (out of DEV-03 pipeline default; FE-05 RFM is included with FE-05 defaults) | Stage F2 wraps `features.rfm.*` with FE-05 defaults (MonetarySigned, Frequency_ByInvoice); RFM-only reformulation is future work | n/a |
| FE-04 customer-level aggregation (V-01..V-12) | FR-DATA-03 (customer-level base dataset) | Stage F1 wraps `aggregation.base_dataset.aggregate_customer_base` + `aggregation.validation.validate_base_dataset` (V-01..V-12 verbatim) | `test_dev03_feature_generation::test_aggregation_wrap_identical_to_direct` |
| FE-05 RFM (Recency, Frequency, Monetary) | FR-DATA-04 (RFM feature set) | Stage F2 wraps `features.rfm.{compute_recency, compute_frequency_variants, materialize_frequency, compute_monetary_variants, materialize_monetary}` | `test_dev03_feature_generation::test_rfm_wrap_identical_to_direct` |
| FE-05 behavioral (Tenure, PurchaseInterval, ActiveDays, AverageInvoiceValue, Quantity working set) | FR-DATA-04 | Stage F2 wraps `features.transaction_behavior.{compute_tenure_days, compute_purchase_interval, compute_active_days, compute_average_invoice_value, compute_signed_quantity_set}` (mirror `run_fe05_feature_engineering.py:395-413`); `features.behavioral.build_behavioral_features` is a stub and NOT used | `test_dev03_feature_generation::test_behavioral_wrap_identical_to_direct` (per-function wrap identity test) |
| FE-05 cancellation (CancellationRate, ReturnRate) | FR-DATA-04 | Stage F2 wraps `features.cancellation.compute_cancellation_features` | `test_dev03_feature_generation::test_cancellation_wrap_identical_to_direct` |
| FE-05 candidate dataset (RFM + behavioral + cancellation + selection gates; ONE Monetary, ONE Frequency, no CategoryCount, PurchaseInterval NaN semantics) | FR-DATA-05 (final candidate feature matrix) | Stage F2 wraps `features.candidate_dataset.build_candidate_features` + `features.validation.validate_candidate_dataset` | `test_dev03_feature_generation::test_candidate_wrap_identical_to_direct` |
| FE-05 selection gates (evidence-based, no score/rank/weight) | NFR-06 (methodology gate) | Stage F2 reuses FE-05 selection verbatim; DEV-03 does **NOT** introduce score/rank/weight | `test_dev03_manifest::test_feature_gen_status_inherited_verbatim` |
| ML Dataset output (Jira step 7) | FR-DATA-06 (customer-level ML-ready feature matrix) | Stage G writes `ml_dataset_<ts>_<hex>.parquet` + `preprocessed_manifest.json` + log | `test_dev03_pipeline::test_ml_dataset_written_as_parquet` + `test_dev03_manifest::test_manifest_schema_complete` |
| Logging (Jira AC #3) | NFR-04, NFR-05 (audit) | Per-stage log entries via Python `logging`; log file under `data/prototype/<dataset_id>/preprocessed/<preprocessed_id>.log` | `test_dev03_logging::*` |
| Consistency with research (Jira AC #5) | FR-DATA-07 (consistency guarantee) | `test_dev03_consistency.py` 2 tests: (38a) DEV-03 vs FE-05 `customer_candidates.parquet` on same `tests/fixtures/consistency_input.csv` (C7-INDEPENDENT, always run); (38b) DEV-03 with C7-like config vs FE-06 `final_clustering_dataset.parquet` + `customer_metadata.parquet` (`@pytest.mark.c7_dependent`, skipped by default). Pre-comparison: FE-06 inner-join on row index, DEV-03 drop CustomerID; tolerance `numpy.allclose(rtol=1e-5, atol=1e-7)`. | `test_dev03_consistency::test_dev03_matches_fe05_candidate` + `test_dev03_consistency::test_dev03_matches_fe06_final_c7_like` |
| ADR-0003 (5 algorithms only) | n/a (out of DEV-03 scope) | DEV-03 does NOT touch clustering | n/a |
| ADR-0004 (RQ1/RQ2/RQ3) | n/a (out of DEV-03 scope) | DEV-03 does NOT touch RQ | n/a |
| ADR-0005 (Option A: file-based, no backend) | FR-REPORT-03, NFR-10 (config-driven) | `prototype.preprocessing` package + `scripts/dev03_preprocess_dataset.py` (CLI) + `configs/dev03_preprocessing.yaml` | `test_dev03_import_blocklist` + `test_dev03_runtime_dependencies` |
| DEV-02 contract (input for DEV-03) | FR-DATA-01, FR-DATA-05 (import dataset) | `prototype.preprocessing.pipeline.input_lookup_stage` consumes `dataset_management.{get_dataset, resolve_storage_root}` | `test_dev03_pipeline::test_input_lookup_via_dev02` |
| DEV-02 manifest schema (per §8 of DEV-02 plan) | n/a (consume-only) | `PreprocessedManifest.source_dataset_id` + `source_dataset_sha256` reference DEV-02 manifest fields | `test_dev03_manifest::test_source_pointer_to_dev02` |
| AGENTS.md §2.1 (no invented methodology) | n/a | All rules inherited from FE-02 / FE-06 / EXP-04 — no new rules invented | `test_dev03_cleaning_wrap` (refactor-safety) |
| AGENTS.md §2.3 (data integrity) | NFR-03 | SHA-256 input verified at Stage A; atomic write at Stage E; research-safety test snapshots | `test_dev03_research_safety` |
| AGENTS.md §2.4 (scope control) | n/a | DEV-03 does NOT cluster / scale / transform-as-best / evaluate / tune / visualize / deploy | import-blocklist test |
| AGENTS.md §2.5 (research decision language) | NFR-06 | No "best", "winner", "optimal", "recommended", "final" claims; statuses only | status semantics test (mirror DEV-02) |
| AGENTS.md §2.7 (reproducibility) | NFR-01 | `config_hash` + `environment` block + `created_utc` / `last_seen_utc` in manifest | `test_dev03_manifest::test_reproducibility_contract` |
| AGENTS.md §2.8 (validation) | NFR-04, NFR-05 | 3-category validation + lifecycle mapping + atomic write | `test_dev03_validation` + smoke |
| AGENTS.md §2.9 (no silent policy change) | n/a | Status annotations re-marked (inherited, not reclassified); no change to FE-02 / FE-06 configs | n/a |
| AGENTS.md §2.10 (human approval gate) | n/a | This plan is a Phase 1 read-only deliverable; Phase 2 gated on human approval | n/a |
| AGENTS.md §2.11 (Git) | FR-REPORT-03 | No commit / push / PR / merge performed | n/a |
| AGENTS.md §2.12 (data privacy) | n/a | `data/prototype/**` already git-ignored (DEV-02 §7.3); research paths read-only | `test_dev03_research_safety::test_research_artifacts_unmodified` |
| AGENTS.md §2.13 (code organization) | NFR-10 | All reusable logic under `src/customer_segmentation/prototype/preprocessing/`; no duplicate logic from notebooks | import-blocklist + lint check |
| AGENTS.md §3 (stage guardrails) | n/a | DEV-03 is a prototype capability, not a research stage; forbidden actions for "Preprocessing" stage (don't invent rules, imputation values) do NOT apply because DEV-03 WRAPS the existing research rules verbatim | n/a |
| AGENTS.md §4 (workflow) | n/a | Steps 1-9 of the workflow; this plan is step 3 (read the relevant section) | n/a |
| AGENTS.md §5 (forbidden shortcuts) | NFR-10 | No copy-paste from notebooks; no hard-coded paths; no new dependency | import-blocklist + runtime-dependency tests |
| AGENTS.md §6 (escalation) | n/a | 5 `NEEDS_CONFIRMATION` items raised in §13.1 | n/a |
| AGENTS.md §7 (communication convention) | n/a | Plan written in Vietnamese (this file); code/identifier in English; completion summary per §7 | n/a |
| AGENTS.md §8 (token efficiency) | n/a | This plan is short-form (read §8 before re-prompting) | n/a |
| AGENTS.md §9 (relationship to phase plan) | n/a | Phase-specific decisions in this plan (per §9 source of truth table) | n/a |

## 12. Rủi ro, phụ thuộc, câu hỏi chưa giải quyết

### 12.1. Rủi ro

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-01 | DEV-03 wrap of FE-02 building blocks silently diverges from research-core behaviour due to import side-effects | HIGH | `test_dev03_cleaning_wrap` asserts byte-for-byte identity to direct calls. Lint blocks re-implementation patterns. |
| R-02 | Optional transform/scale introduces silent methodology choice (e.g. user picks yeo_johnson → C7-like). | MEDIUM | Each combo marked `WORKING_ASSUMPTION`; no promotion to "best"; the optional stage can be turned off (transformation=none, scaling=none → identity). |
| R-03 | PreprocessedManifest schema diverges from DEV-02 manifest schema → downstream confusion. | MEDIUM | Manifest reuses DEV-02 manifest fields where applicable (via composition, not inheritance). Documented in §10.4. |
| R-04 | `data/prototype/datasets/<dataset_id>/preprocessed/` could become a large dataset graveyard if user re-preprocesses many times. | LOW | Atomic write + content-addressed `preprocessed_id`; old artefacts can be cleaned up by user manually; DEV-03 does NOT auto-clean (no scope). |
| R-05 | Adding `sklearn` import surface may pull in unexpected transitive dependencies. | LOW | sklearn is already in `pyproject.toml::dependencies` (used by research core). DEV-03 uses only 4 sklearn classes: `StandardScaler`, `MinMaxScaler`, `RobustScaler`, `PowerTransformer`. No new top-level dependency. |
| R-06 | Duplicate-package-name risk: `customer_segmentation.preprocessing` (research) vs `customer_segmentation.prototype.preprocessing` (prototype). | LOW | Namespaced under `prototype.*`; import paths are unambiguous. |
| R-07 | Two-layer coupling: DEV-03 depends on DEV-02 (which itself doesn't import from preprocessing). Now preprocessing is reachable from a non-research package. | MEDIUM | Justified — DEV-03 is the BRIDGE between prototype layer and research core. The bridge is one-directional (DEV-03 reads from research core, never the other way). Documented in §3.2 + §5.2. |
| R-08 | `preprocessing_block.config_snapshot` may be large (full config dict). | LOW | JSON-serialisable; ~1-2 KB typical; no privacy / no PII in the config. |

### 12.2. Phụ thuộc (Dependencies)

- **DEV-02** (completed 2026-10-08). DEV-03 cannot run without a
  `dataset_id` from DEV-02. This is documented in the DEV-02 §14.1 contract
  and re-asserted in §5.5 of this plan.
- **FE-02 / FE-06 / EXP-04 research core** (completed, immutable). DEV-03
  wraps them, never modifies them. If they were to change (which would
  require a new ADR), DEV-03 must be re-verified.
- **`pyproject.toml::dependencies`**: numpy, pandas, scipy, scikit-learn,
  pyarrow, PyYAML. All already present. **No new dependency**.
- **SYS-01..06**: status DRAFT / REVIEW_REQUIRED. No SYS doc change for
  DEV-03 (DEV-03 is a new capability, not a SYS doc change).
- **ADR-0005**: Option A (file-based, no backend). No change.
- **Future SYS-06 re-sync** (already documented in DEV-02 §15.1 C-02):
  when the HTML prototype is re-synced to the manifest layer, an ADR
  + SYS-06 revision must reconcile the "no upload" wording with the
  CLI capabilities. DEV-03 inherits this risk; does NOT resolve it.

### 12.3. Câu hỏi chưa giải quyết / Cần human / mentor phê duyệt

> **Phân loại (per user request 2026-10-09, item 7):**
> - **RESOLVED-IN-PLAN** = quyết định kỹ thuật thông thường đã được plan
>   quyết trong scope; KHÔNG cần mentor confirm vì không thay đổi scope
>   hay methodology. Mentor chỉ cần accept khi `APPROVE PHASE 2` chung.
> - **NEEDS_CONFIRMATION** = cần user/mentor xác nhận trước khi implement.
>   Lý do: có thể ảnh hưởng scope / methodology / data flow policy.
> - **METHODOLOGY BLOCKER** = cần mentor quyết định methodology trước
>   khi implement; plan không tự quyết.

| ID | Question | Recommendation | Status | Loại |
|---|---|---|---|---|
| DEV-03-OPEN-01 | **Jira task description** for DEV-03. | User đã paste nội dung Jira 2026-10-09: pipeline 7 bước + 5 AC. Plan đã cover toàn bộ scope. | **RESOLVED** | — |
| DEV-03-OPEN-02 | Should DEV-03 refuse to preprocess a dataset whose `validation_status` is `NOT_VALIDATED` / `VALIDATING` / `FAILED`, or only refuse `FAILED`? | Plan mặc định: refuse everything except `VALID` (matches DEV-02's downstream contract). `NOT_VALIDATED` is ambiguous; `VALIDATING` is in flight. | **NEEDS_CONFIRMATION** (user-side, không methodology) | NEEDS_CONFIRMATION |
| DEV-03-OPEN-03 | Should the optional transform/scale stage be exposed in CLI as `--transformation ... --scaling ...`, or only via YAML? | Plan mặc định: YAML-only (single source of truth per SYS-01 NFR-10); CLI flag sẽ là optional override nếu user yêu cầu trong tương lai. Implementation chi tiết có thể decide trong Phase 2. | **RESOLVED-IN-PLAN** (technical UX, không methodology) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-04 | Confirm `scikit-learn` is acceptable to use directly in DEV-03. | sklearn **đã có** trong `pyproject.toml::dependencies` (research core dùng rồi). DEV-03 chỉ gọi 4 class: `StandardScaler`, `MinMaxScaler`, `RobustScaler`, `PowerTransformer`. Không thêm dep mới. Plan đã xác nhận không có thay đổi scope/methodology. | **RESOLVED-IN-PLAN** (technical, không methodology) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-05 | Acceptance floor: hard regression floor (all 1468 pre-DEV-03 tests must pass) hay DEV-02 "no-regression map" pattern? | Plan mặc định: DEV-02 pattern (no-regression map). AGENTS.md §2.8 đã linh hoạt về loại này. | **RESOLVED-IN-PLAN** (validation policy, không methodology) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-06 | Should DEV-03 emit a per-run log under `reports/dev03/` (per-stage) hoặc per-`preprocessed_id` log dưới `data/prototype/<dataset_id>/preprocessed/`? | Plan mặc định: per-`preprocessed_id` log dưới `data/prototype/<dataset_id>/preprocessed/` (mirror DEV-02 pattern; tránh mutate `reports/` per AGENTS.md §2.12). Mỗi run là 1 log file gắn với 1 `preprocessed_id`. | **RESOLVED-IN-PLAN** (operational, không methodology) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-07 | Should DEV-03 also include aggregation (FE-04) or feature engineering (FE-05)? | **YES** — Jira scope (2026-10-09) xác nhận 7-step pipeline bao gồm Feature Generation. Plan revision 2026-10-09 đã add Stage F (FE-04 aggregation + FE-05 features). Đây là **scope** change (đã confirmed by Jira), không phải methodology change: DEV-03 vẫn WRAPS research core, không introduce new features. | **RESOLVED** (scope resolved by Jira) | — |
| DEV-03-OPEN-08 | Filename `docs/system/DEV-03_preprocessing.md` (no `_plan`) vs `DEV-03_preprocessing_plan.md` (with `_plan`)? | Plan mặc định: `DEV-03_preprocessing.md` (matches DEV-01/DEV-02 convention). Quy ước docs nội bộ. | **RESOLVED-IN-PLAN** (docs convention) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-09 | Reuse FE-02/04/05/06 building blocks by import-and-wrap, vs copy code? | Plan mặc định: wrap (preserves single source of truth, AGENTS.md §2.13). | **RESOLVED-IN-PLAN** (technical, không methodology) | RESOLVED-IN-PLAN |
| DEV-03-OPEN-10 | Should DEV-03 also preprocess a dataset whose source is `data/raw/primary/Online Retail.xlsx`? | Plan mặc định: YES — DEV-03 should not add a new restriction. The DEV-02 manifest already records the source provenance; the user can `--allow-external-source` trong DEV-02 và DEV-03 sẽ follow. | **NEEDS_CONFIRMATION** (data flow policy; có thể considered scope-affecting) | NEEDS_CONFIRMATION |

**Còn lại cần user/mentor trước khi implement:**
- DEV-03-OPEN-02: 1 câu hỏi về validation_status policy (user-side, có default đề xuất).
- DEV-03-OPEN-10: 1 câu hỏi về data flow policy (allow primary source hay không).

**METHODOLOGY BLOCKER (chưa resolve, plan không tự quyết):**
- DOC-CTD-01 (C7 status conflict giữa METHODOLOGY_LOCK_STATUS.md và SYS-04) — vẫn pending; DEV-03 mirror theo FE-02/FE-06 YAML configs (xem §3.5, §5.2.3); mentor quyết định canonical doc (xem §12.5).

**Plan changes so far (2026-10-09 revision):**
- Added Stage F (Feature Generation) với sub-package `prototype.feature_generation/`.
- Restructured pipeline to 7 stages A→G mapping 1:1 to Jira.
- Added 4 new files in `prototype.feature_generation/`, 3 new test files.
- Added consistency test, logging test, feature_generation test.
- Re-classified DEV-03-OPEN-01 / 07 as RESOLVED, 03 / 04 / 05 / 06 / 08 / 09 as RESOLVED-IN-PLAN; left 02 / 10 as NEEDS_CONFIRMATION.

### 12.4. Open SYS-06 conflicts inherited from DEV-02 (not resolved by DEV-03)

| ID | Conflict | Disposition (inherited from DEV-02 §15.1) |
|---|---|---|
| C-02 (DEV-02) | SYS-06 §S-02 says "**Không cho upload dataset khác trong prototype**" while DEV-02 introduces an upload capability. | HARD STOP — do not edit SYS-06 in DEV-03. Recorded as a future ADR topic. The HTML prototype is mock-data only (per ADR-0005); the DEV-03 capability is enabled via CLI, not via the UI. When the UI is re-synced, an ADR + SYS-06 revision must reconcile. |
| C-03 (DEV-02) | SYS-06 §S-02 says "chỉ hiển thị dataset primary đã freeze (Online Retail → FE06-v1.0)" — UI-side filter. | The filter is a UI concern, not a public API concern. DEV-03 inherits this. The UI layer will apply the filter when re-synced; the public API continues to operate on any `IMPORTED_PROTOTYPE` dataset. |

### 12.5. Documented contradictions between repository docs (NEEDS ADR, NOT resolved by DEV-03)

| ID | Contradiction | Disposition |
|---|---|---|
| DOC-CTD-01 | `METHODOLOGY_LOCK_STATUS.md` §2 lists **DS-03 = FE-06 C7 preprocessing** as `✅ LOCKED`. But `SYS-04` §3.1 lists **DS-03 = FE-06 C7** as `⚠️ WORKING_ASSUMPTION (WA-01)`. | This is a doc-internal contradiction. **Out of scope of DEV-03** — DEV-03 mirrors the FE-02 / FE-06 statuses as recorded in the YAML configs, not in the contradictory lock-status tables. Recommend ADR / doc PR. |
| DOC-CTD-02 | `SYS-01` §3.1 references "FE-06 final matrix" as the only acceptable research input, but DEV-02 (and now DEV-03) operate on user-imported prototype datasets — a parallel universe. | The contradiction is intentional: SYS-01 §3.1 is the **research layer**; DEV-02 + DEV-03 are the **prototype layer**. ADR-0005 + DEV-02 §3 establish the boundary. **Out of scope of DEV-03** to resolve. |

## 13. Các điểm cần user/mentor phê duyệt trước khi implement

Trước khi Phase 2 bắt đầu, **human researcher / mentor cần**:

1. **Resolve 2 NEEDS_CONFIRMATION items còn lại** (xem §12.3):
   - **DEV-03-OPEN-02**: validation_status policy (refuse everything except
     `VALID`, or only refuse `FAILED`?).
   - **DEV-03-OPEN-10**: data flow policy (allow preprocess dataset whose
     source is `data/raw/primary/Online Retail.xlsx` hay không?).
2. **Resolve DOC-CTD-01 (C7 status conflict) — methodology blocker**:
   `METHODOLOGY_LOCK_STATUS.md` §2 lists **DS-03 = FE-06 C7** as `✅ LOCKED`
   while `SYS-04` §3.1 lists **DS-03 = FE-06 C7** as `⚠️ WORKING_ASSUMPTION (WA-01)`.
   Mentor quyết định tài liệu nào canonical hoặc tạo ADR mới. Plan DEV-03
   mirror theo YAML configs (FE-02/FE-06), không tự giải quyết.
3. **General approval** of the plan (`APPROVE PHASE 2`): confirm rằng:
   - DEV-03's scope = 7-step Jira pipeline (Dataset → Validation → Cleaning →
     Transformation → Scaling → Feature Generation → ML Dataset) is correct.
   - The prototype-layer placement (under
     `customer_segmentation.prototype.{preprocessing,feature_generation}/`)
     is acceptable.
   - The reuse strategy (wrap FE-02/04/05/06 building blocks; do not fork;
     do not introduce new features) is acceptable.
   - The 30 new files in §6.1 are acceptable.
   - The 49 acceptance criteria in §8 cover all 5 Jira AC.
4. **The plan does NOT modify**: SYS-01..06, AGENTS.md, ADR-0001..0005,
   any research-core code / config, any reports, any data, any other doc.
   The only NEW file in this plan is `docs/system/DEV-03_preprocessing.md`
   (this revised version). Implementation files (proposed in §6.1) are
   not created in this plan; they will be created in Phase 2 after
   approval.

## 14. Ước lượng phạm vi thay đổi và tiêu chí hoàn thành

### 14.1. Ước lượng phạm vi thay đổi

**Files to be created (in Phase 2, NOT this plan):**

- 1 new package skeleton: `src/customer_segmentation/prototype/__init__.py`
- 9 new modules trong `prototype.preprocessing/`: `__init__.py`, `scope.py`,
  `storage.py`, `pipeline.py`, `manifest.py`, `validation.py`, `list.py`,
  `config_loader.py`, `logging_config.py`.
- 4 new modules trong `prototype.feature_generation/`: `__init__.py`,
  `scope.py`, `pipeline.py`, `manifest_block.py`.
- 1 new CLI: `scripts/dev03_preprocess_dataset.py`
- 1 new config: `configs/dev03_preprocessing.yaml`
- 14 new test files: `tests/test_dev03_*.py` (xem §6.1.4)
- 2 new test fixture files: `tests/fixtures/__init__.py` +
  `tests/fixtures/consistency_input.csv` (xem §6.1.4)

Total new: **~32 files**, ~1,800-2,400 LOC (lớn hơn plan trước do thêm
`feature_generation` sub-package, consistency test, logging test, fixture).

**Files to be modified:** **0** (this plan does NOT modify any existing
file; all new files are additive).

**Files documented but not modified:**

- `docs/decisions/README.md` (immutability convention) — not modified.
- `docs/research/EPIC09_CP05_PLAN.md` etc. — not modified.

### 14.2. Tiêu chí hoàn thành (per AGENTS.md §2.8)

DEV-03 implementation phase (Phase 2) is COMPLETE when:

1. All 49 acceptance criteria in §8 PASS.
2. `pytest tests/test_dev03_*.py` passes (~95-125 new tests).
3. `pytest` (full suite) — no regression vs pre-DEV-03 baseline
   (1468 pre-existing tests; per the DEV-02 no-regression map pattern).
4. `ruff check` for DEV-03 additions only — clean (pre-existing
   findings in research core = N/A per DEV-01 §7.1.1).
5. `black --check` for DEV-03 additions only — clean.
6. Smoke test on a real CSV: DEV-02 import → DEV-03 preprocess →
   cleaned transaction-level parquet + ML Dataset customer-level parquet +
   manifest + log written, research paths unchanged.
7. Consistency test passes (DEV-03 ML Dataset ≈ canonical FE-02/04/05/06
   ML Dataset, within tolerance). May be marked `@pytest.mark.slow` and
   excluded from fast CI; run once locally for full validation.
8. Completion summary in Vietnamese per AGENTS.md §7 (11 sections).
9. **No commit, no push, no PR, no merge** (per AGENTS.md §2.11).e** (per AGENTS.md §2.11).
9. Mentor approval gate satisfied (AGENTS.md §2.10):
   `TECHNICALLY_IMPLEMENTED` ≠ `RESEARCH_DECISION_APPROVED`.

### 14.3. Out of scope (explicit, to prevent scope creep)

- ❌ Implementing DEV-04 (feature engineering), DEV-05 (clustering),
  DEV-06..09.
- ❌ Re-running FE-02 / FE-06 / EXP-04.
- ❌ Mutating `data/processed/`, `data/raw/`, `data/interim/`,
  `data/external/`, `reports/`.
- ❌ Modifying `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's).
- ❌ Modifying any of `src/customer_segmentation/preprocessing/`,
  `transformation/`, `data/`, `config/`, `aggregation/`, `features/`,
  `outlier_analysis/`, `clustering/`, `evaluation/`, `profiling/`,
  `visualization/`.
- ❌ Modifying `src/customer_segmentation/dataset_management/**` (DEV-02).
- ❌ Modifying any of `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`,
  `scripts/run_ml0X_*.py`, `scripts/run_eva0X.py`, `scripts/run_cp0X.py`,
  `scripts/dev02_import_dataset.py`.
- ❌ Modifying `configs/*.yaml` other than `configs/dev03_preprocessing.yaml`.
- ❌ Modifying any of `tests/test_*.py` other than the new
  `tests/test_dev03_*.py`.
- ❌ Adding a new third-party dependency to `pyproject.toml` or
  `requirements.txt`.
- ❌ Editing SYS-01..06, AGENTS.md, ADR-0001..0005.
- ❌ Re-promoting any `WORKING_ASSUMPTION` to `RESEARCH_APPROVED_FINAL`.
- ❌ Resolving SYS-06 §S-02 wording conflicts (carried from DEV-02 §15.1).
- ❌ Resolving the METHODOLOGY_LOCK_STATUS ↔ SYS-04 DS-03 contradiction
  (DOC-CTD-01).
- ❌ Constructing an RFM-only dataset (RFM-only is FUTURE_WORK per
  RQ2 reformulation).
- ❌ Implementing CP-05, MKT-01..05, or any EPIC-09 / EPIC-12 work.
- ❌ Git operations (commit, push, PR, merge, branch).

## 15. Self-Review (mirror DEV-02 §17)

### 15.1. Internal consistency

| Check | Result |
|---|---|
| §1 (Objective) consistent with §4 (Data flow) | OK. §1 states DEV-03 covers 7-step Jira pipeline (Dataset → Validation → Cleaning → Transformation → Scaling → Feature Generation → ML Dataset); §4 sequence diagram maps 1:1. |
| §1 (Objective) consistent with §5.4.2 (reuse) | OK. §1 table row "Stage F: feature generation" lists `features.rfm.*`, `features.transaction_behavior.*`, `features.diversity.compute_diversity_features`, `features.cancellation.compute_cancellation_features` (the actual reused functions); `features.behavioral.build_behavioral_features` (stub) is marked as STUB in §3.1 inventory and is NOT used by Stage F2. |
| §3.2 (coupling rules) consistent with §5.5 (re-marking status) | OK. Status annotations are read from FE-02 / FE-04 / FE-05 / FE-06 YAML configs; no reclassification. |
| §5.4 (reuse) consistent with §5.2 (coupling rules) | OK. All `preprocessing.*`, `aggregation.*`, `features.*` imports are READ-ONLY; `dataset_management.*` imports consume public API only. |
| §6.1 (files to create) consistent with §5.3 (module structure) | OK. 10 modules in `prototype.preprocessing/` + 4 modules in `prototype.feature_generation/` + 1 CLI + 1 config + 14 test files = 30 files. |
| §7 (implementation steps) consistent with §8 (acceptance criteria) | OK. Each step produces a testable artefact; consistency test (step 15) closes the Jira AC #5 loop. |
| §10 (research safety) consistent with §3.2 (read-only coupling) | OK. Storage root constraint + import-blocklist + research-safety test. |
| §12.3 (NEEDS_CONFIRMATION) consistent with §13 (approval items) | OK. 2 NEEDS_CONFIRMATION items + 1 METHODOLOGY BLOCKER (C7) explicitly listed in §13. |
| No silent methodology change (§2.9) | OK. Status annotations inherited verbatim; no rule invented. |
| §11 (Traceability) covers FE-04, FE-05, ML Dataset, Logging, Consistency | OK. 5 new rows added at the end of §11 table (FE-04 / FE-05 RFM / FE-05 behavioral / FE-05 cancellation / FE-05 candidate + ML Dataset + Logging + Consistency). Consistency row updated 2026-10-09 to split AC 38a (C7-independent) vs AC 38b (C7-dependent). |

### 15.2. AGENTS.md compliance

| AGENTS.md rule | Compliance |
|---|---|
| §2.1 Research integrity | OK. DEV-03 wraps FE-02/04/05/06 rules; no new rules invented; statuses inherited verbatim. |
| §2.2 Phase isolation | OK. DEV-03 does not modify outputs of FE-02/04/05/06 / EXP-04; does not modify DEV-02 output. |
| §2.3 Data integrity | OK. SHA-256 input + output; atomic write; research-safety test. |
| §2.4 Scope control | OK. DEV-03 only adds the 7-step pipeline on DEV-02 datasets; no clustering / model training / evaluation / hyperparameter tuning / visualization / deployment. |
| §2.5 Research decision language | OK. No "best" / "winner" / "optimal" / "recommended" / "final" claims; statuses only. |
| §2.6 Feature / model selection | OK. No numerical score, no ranking, no "winner" (selection gates inherited from FE-05). |
| §2.7 Reproducibility | OK. Manifest records sha256, config_hash, environment, created_utc, last_seen_utc, log_file path. |
| §2.8 Validation | OK. §8 enumerates 49 acceptance criteria; §9 enumerates test plan; §14.2 lists validation commands. |
| §2.9 No silent policy change | OK. Status annotations re-marked (inherited, not reclassified); no SYS / ADR / methodology change; C7 contradiction preserved as pending DOC-CTD-01. |
| §2.10 Human approval gate | OK. This plan is a Phase 1 read-only deliverable; Phase 2 (implementation) is gated on human approval (§13). |
| §2.11 Git | OK. No git operations performed in this plan. |
| §2.12 Data privacy | OK. `data/prototype/**` already git-ignored (DEV-02 §7.3 fix); research paths read-only; reports/** not touched. |
| §2.13 Code organization | OK. All logic under `src/customer_segmentation/prototype/{preprocessing,feature_generation}/`; no duplicate logic from notebooks. |
| §3 (stage-by-stage guardrails) | OK. DEV-03 is a prototype capability, not a research stage; the "Forbidden actions" for "Preprocessing" (don't invent rules) and "Feature eng." (don't change RFM without ADR) do not apply because DEV-03 WRAPS existing FE-02/04/05/06 rules verbatim. |
| §4 (workflow) | OK. This plan is the workflow step "Make the change" precursor; Phase 2 will execute steps 1-9. |
| §5 (forbidden shortcuts) | OK. No copy-paste from notebooks; no hard-coded paths (all from `configs/dev03_preprocessing.yaml`); no new dependency. |
| §6 (escalation) | OK. 2 `NEEDS_CONFIRMATION` items + 1 `METHODOLOGY BLOCKER` raised in §13. |
| §7 (communication convention) | OK. Plan written in Vietnamese; code/identifier in English; completion summary per §7 (will be done in Phase 2). |
| §8 (token efficiency) | OK. This plan is concise; the AGENTS.md rules are not re-stated. |
| §9 (relationship to AGENTS.md vs phase plan) | OK. This plan is the phase-specific source of truth for DEV-03; global rules in AGENTS.md are not duplicated. |

### 15.3. Acceptance feasibility

| # | Acceptance | Has a test? |
|---|---|---|
| 1-49 | All 49 acceptance criteria in §8 | Yes — see §9.1 test file inventory (14 test files, ~95-125 new tests) and §9.2 edge cases. |
| Jira AC #1 (pipeline runs) | AC 1-12 in §8.1.1 | Yes — `test_dev03_pipeline.py` + 5 stage-specific tests. |
| Jira AC #2 (configuration) | AC 13-19 in §8.1.2 | Yes — `test_dev03_validation.py` + `test_dev03_optional_transform.py`. |
| Jira AC #3 (logging) | AC 20-24 in §8.1.3 | Yes — `test_dev03_logging.py` (NEW). |
| Jira AC #4 (output Dataset) | AC 25-37 in §8.1.4 | Yes — `test_dev03_pipeline.py` + `test_dev03_manifest.py` + `test_dev03_list.py`. |
| Jira AC #5 (consistency with research) | AC 38a, 38b, 39-42 in §8.1.5 | Yes — `test_dev03_consistency.py` (NEW; AC 38a always run, AC 38b marked `@pytest.mark.c7_dependent` skipped by default) + `test_dev03_cleaning_wrap.py` + `test_dev03_feature_generation.py`. |

## 16. References

- `AGENTS.md` §1, §2, §3, §4, §5, §6, §7, §8, §9.
- `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005).
- `docs/system/DEV-01_project_setup.md` (DEV-01 plan; verification + architecture boundary pattern).
- `docs/system/DEV-02_dataset_management.md` (DEV-02 plan; the immediate precedent for this plan).
- `docs/system/SYS-01_requirements.md` §6.1 (FR-DATA-01..06), §8 (CON-03), §13 (OQ-12..15).
- `docs/system/SYS-04_ml_processing_pipeline.md` §3.1, §3.2, §7.1, §7.2, §10, §10.1, §10.2.
- `docs/system/SYS-06_ui_ux_design.md` (documented conflict in §S-02, inherited from DEV-02 §15.1).
- `docs/data_dictionary/dataset_provenance.md`, `dataset_schema.csv`, `initial_data_profile.md`.
- `docs/methodology/methodology_overview.md` §2.3, §3.4, §4.
- `docs/methodology/research_questions.md` RQ1, RQ2, RQ3.
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` §2, §3, §5, §8 (mâu thuẫn với SYS-04 §3.1 về DS-03 status; xem §12.5 DOC-CTD-01).
- `docs/research/FE04_*.md`, `FE05_*.md`, `FE06_*.md`, `EXP04_*.md`, `ML01..06_*.md` (skim — referenced in §3.5).
- `configs/preprocessing.yaml` (FE-02 cleaning — mirror for DEV-03 defaults).
- `configs/aggregation.yaml` (FE-04 aggregation — mirror for DEV-03 Stage F1).
- `configs/feature_engineering.yaml` (FE-05 features — mirror for DEV-03 Stage F2).
- `configs/transformation.yaml` (FE-06 C0..C7 — option set for DEV-03 optional stages D, E, F3).
- `configs/exp04_preprocessing_feature_set.yaml` (EXP-04 sweep — reference, NOT a 1:1 template).
- `src/customer_segmentation/preprocessing/{cleaning,invalid_records,duplicates,missing_values,outliers}.py` (research core, READ-ONLY).
- `src/customer_segmentation/aggregation/{base_dataset,config_loader,validation,report}.py` (research core, READ-ONLY).
- `src/customer_segmentation/features/{rfm,behavioral,cancellation,candidate_dataset,config_loader,validation,selection}.py` (research core, READ-ONLY; `behavioral.py` is a STUB and NOT used by DEV-03).
- `src/customer_segmentation/features/transaction_behavior.py` (research core, READ-ONLY; reused by Stage F2 for `compute_tenure_days`, `compute_purchase_interval`, `compute_active_days`, `compute_average_invoice_value`, `compute_signed_quantity_set`).
- `src/customer_segmentation/features/diversity.py` (research core, READ-ONLY; reused by Stage F2 for `compute_diversity_features` wrapping `compute_products_per_invoice`).
- `src/customer_segmentation/data/{audit,validator,loader,schema}.py` (research core, READ-ONLY).
- `src/customer_segmentation/transformation/versioning.py` (SHA-256 utility).
- `src/customer_segmentation/config/loader.py` (YAML loader convention).
- `src/customer_segmentation/dataset_management/**` (DEV-02 — the pattern to mirror).
- `scripts/run_fe02_cleaning.py`, `run_fe04_aggregation.py`, `run_fe05_feature_engineering.py`, `run_fe06_transformation.py` (FE-02/04/05/06 orchestrators — pattern references for `scripts/dev03_preprocess_dataset.py`).
- `tests/test_dev02_*.py` (12 files — test pattern to mirror).
- `tests/test_aggregation*.py`, `test_features*.py`, `test_candidate_dataset*.py` (FE-04 / FE-05 tests — used as cross-check for Stage F wrap, NOT modified).
- `tests/fixtures/consistency_input.csv` (NEW — consistency test fixture; see §6.1.4 + §9.2).
- `conftest.py` (test PYTHONPATH setup — mirrored).
- `.gitignore` (line 114 covers `data/prototype/**`, per DEV-02 §7.3 fix).

---

*Tài liệu này là DEV-03 plan (Phase 1 — read-only), revised 2026-10-09
sau khi Jira scope confirmed. KHÔNG thực hiện implementation. KHÔNG modify
code, config, SYS, ADR, AGENTS.md. KHÔNG Git operations. Chờ human approval
gate trước Phase 2.*
