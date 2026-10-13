# DEV-07 — Final Acceptance Report

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module
> **Ngày:** 2026-10-10
> **Trạng thái:**
> - **Phase A**: **ACCEPTED** (2026-10-10) — `§1.1` bên dưới.
> - **Phase B technical infrastructure**: **TECHNICALLY IMPLEMENTED**
>   (2026-10-10) — xem `docs/system/DEV-07_phase_b_acceptance_report.md`.
> - **Phase B actual recommendation generation**: **BLOCKED** — chờ
>   MKT-01..MKT-05 framework + OQ-D07-01/-03/-04/-05 resolution.

---

## 1. Tóm tắt tổng thể

### 1.1. Kết luận Phase A

> **DEV-07 Phase A: TECHNICALLY ACCEPTED (2026-10-10)**

Tất cả 6 Phase A acceptance gate conditions đã được đạt:

| # | Acceptance condition | Status | Evidence |
|---|---|---|---|
| 1 | ADR-0008 approved (Option A: aggregate `MKT-01..05__vN`) | ✅ Resolved 2026-10-10 | ADR-0008 status = `Accepted`; `configs/dev07_marketing.yaml` updated |
| 2 | `preprocessing_warning` carry-over resolved (Option (c): no carry-forward Phase A) | ✅ Resolved 2026-10-10 | `docs/system/DEV-07_implementation_plan.md` §4.2, §4.4, AC-D07-10 updated |
| 3 | OQ-D07-02 resolved (Phase A ngay) | ✅ Resolved 2026-10-10 | `DEV-07_owner_decision_brief.md` §5.3 |
| 4 | OQ-D07-06 resolved (giữ nguyên HTML placeholder) | ✅ Resolved 2026-10-10 | `DEV-07_owner_decision_brief.md` §5.3 |
| 5 | OQ-D07-07 resolved (không tạo ADR mới) | ✅ Resolved 2026-10-10 | `DEV-07_owner_decision_brief.md` §5.3 |
| 6 | OQ-D07-08 resolved (read-only manifest) | ✅ Resolved 2026-10-10 | `DEV-07_owner_decision_brief.md` §5.3 |

### 1.2. Phase A vs Phase B vs Phase B infrastructure

| Concern | Phase A | Phase B infrastructure | Phase B actual |
|---|---|---|---|
| **Scope** | REVIEW_REQUIRED shell | Tokenization + structure + mapping scaffolding | Recommendation generation |
| **Status (2026-10-10)** | ✅ **ACCEPTED** | ✅ **TECHNICALLY IMPLEMENTED** | ❌ **BLOCKED** |
| **Blockers** | None | None (technical) | OQ-D07-01/-03/-04/-05 + MKT-01..MKT-05 absent |
| **ADR-0008 needed** | Yes (Option A accepted) | n/a | Framework content design |
| **`preprocessing_warning` carry-over** | Option (c) (no carry) | n/a | Re-evaluate when UI expands |
| **Export (CSV + JSONL)** | DISABLED (read-only per OQ-D07-08) | DISABLED (config flags=false) | ENABLE per OQ-D07-05 |
| **HTML `#/marketing` UI** | Placeholder (per OQ-D07-06) | Unchanged | Per OQ-D07-06 (giữ nguyên) |

### 1.3. Phase B infrastructure deliverables (2026-10-10)

| File | Mục đích |
|---|---|
| `src/customer_segmentation/prototype/marketing/tokenization.py` | CP-04 §4.1-§4.3 parser. |
| `src/customer_segmentation/prototype/marketing/mapping.py` | Phase B mapping scaffolding. |
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` (extended) | Thêm `MktDocRef`, `MktFrameworkStructure`, `load_mkt_framework_structure`. |
| `src/customer_segmentation/prototype/marketing/recommendation.py` (extended) | Phase B branch + `build_recommendation_entry_with_scaffolding`. |
| `src/customer_segmentation/prototype/marketing/pipeline.py` (extended) | Wire `mkt_framework_structure` param. |
| `tests/test_dev07_tokenization.py` (new) | 24 tests cho parser. |
| `tests/test_dev07_mkt_framework_structure.py` (new) | 18 tests cho structure loader. |
| `tests/test_dev07_mapping_scaffolding.py` (new) | 23 tests cho mapping + wiring. |
| `docs/system/DEV-07_phase_b_decision_memo.md` (new) | 4 OQ proposals. |
| `docs/system/DEV-07_phase_b_acceptance_report.md` (new) | Phase B acceptance report. |

**Tests:** 263 (Phase A) → 328 (Phase B infrastructure) — all pass.
**Regression DEV-02..07:** 1336 → 1401 tests pass (matches increment).
**Lint/Format:** clean.

---

## 2. Những quyết định đã chốt

### 2.1. ADR-0008 — Canonical version pattern: **Option A accepted**

**Decision:** Canonical version form là aggregate form `MKT-01..05__vN` (với `N` là số phiên bản hợp lệ).

**Bằng chứng:**

```
Pattern loaded from configs/dev07_marketing.yaml:
  '^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$'

  Match 'MKT-01..05__v1':     True   ✅
  Match 'MKT-01..05__v1.5':   True   ✅
  Match 'MKT-01..05__v2.5.3': True   ✅
  Match 'MKT-01__v1' (per-file): False ✅ (per-file shape rejected)

Config loader:
  schema_version: "1.0.0" (no bump needed)
  version_pattern: '^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$'

Default config + synthetic MKT files (production path):
  load_mkt_framework(cfg, repo_root=tmp) → ref returned ✅
  ref.version: 'v1' ✅
  framework_version_string(ref): 'MKT-01..05__v1' ✅
```

**Tác động:**

| File | Change |
|---|---|
| `configs/dev07_marketing.yaml` | `version_pattern` updated to aggregate form (escaped) |
| `docs/decisions/0008-dev07-version-pattern.md` | Status → `Accepted`, Option A approved |
| `tests/test_dev07_mkt_framework.py` | 7 `TestDefaultConfigIntegration` tests updated (6 refactored + 1 new) |
| `tests/test_dev07_validation.py` | `_make_full_config` pattern updated |
| `tests/test_dev07_recommendation.py` | `_make_full_config` pattern updated |
| `tests/test_dev07_pipeline.py` | `_make_minimal_yaml` pattern updated (single quotes) |
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | Diagnostic log message updated (ADR-0008 → `Accepted`) |

**Loader production code:** KHÔNG thay đổi semantics. `MARKETING_MANIFEST_SCHEMA_VERSION` giữ `1.0.0` (không bump).

### 2.2. `preprocessing_warning` carry-over: **Option (c) accepted**

**Decision:** Phase A không carry forward `preprocessing_warning` từ DEV-06. Đây là quyết định có chủ đích (intentional).

**Bằng chứng:**

```
Schema verification:
  'preprocessing_warning' in MarketingRecommendationManifest fields: False ✅
  'limitation' in fields: True ✅

Phase A behavior (witness tests in TestPreprocessingWarningCarryOver):
  - manifest has no preprocessing_warning field ✅
  - DEV-06 warning does NOT propagate to limitation/limitation_note ✅
  - pipeline succeeds with non-empty preprocessing_warning ✅
  - empty string warning is accepted ✅
```

**Tác động:**

| File | Change |
|---|---|
| `docs/system/DEV-07_implementation_plan.md` | §4.2, §4.4, AC-D07-10 updated (clarified Option (c)) |
| `docs/system/DEV-07_owner_decision_brief.md` | §5.1, §5.3, §6.1 updated |
| `docs/system/DEV-07_owner_decision_matrix.md` | §4 updated |

**Witness tests giữ nguyên** (4 tests): `TestPreprocessingWarningCarryOver` trong `tests/test_dev07_pipeline.py`. Schema E-MKT và contract DEV-06 không sửa.

---

## 3. Những thay đổi đã thực hiện

### 3.1. Files đã tạo (1)

| File | Mục đích |
|---|---|
| `docs/system/DEV-07_final_acceptance_report.md` | Báo cáo nghiệm thu Phase A (file này) |

### 3.2. Files đã sửa (12)

#### Config (1)
| File | Thay đổi |
|---|---|
| `configs/dev07_marketing.yaml` | `version_pattern` → `^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$`; comment updated; owner decision comment updated |

#### ADR (1)
| File | Thay đổi |
|---|---|
| `docs/decisions/0008-dev07-version-pattern.md` | Status → `Accepted`; Option A documented; consequences updated; affected files listed |

#### Source (1)
| File | Thay đổi |
|---|---|
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | Diagnostic log message updated to reflect ADR-0008 Accepted |

#### Test files (3)
| File | Thay đổi |
|---|---|
| `tests/test_dev07_mkt_framework.py` | 7 `TestDefaultConfigIntegration` tests refactored (behavior now matches default config = aggregate form); 1 new test added `test_default_config_rejects_per_file_naming_convention` |
| `tests/test_dev07_validation.py` | `_make_full_config` pattern → aggregate form |
| `tests/test_dev07_recommendation.py` | `_make_full_config` pattern → aggregate form |
| `tests/test_dev07_pipeline.py` | `_make_minimal_yaml` pattern → aggregate form (single quotes) |

#### Docs (4)
| File | Thay đổi |
|---|---|
| `docs/system/DEV-07_owner_decision_brief.md` | §1 Executive summary; §5.1; §5.3; §5.4; §6.1; §6.4 — all updated to reflect decisions recorded |
| `docs/system/DEV-07_owner_decision_matrix.md` | Header; §4; §8.1 — all updated to reflect decisions resolved |
| `docs/system/DEV-07_implementation_plan.md` | §4.2 (note); §4.4 (note); §5.4 (note); AC-D07-10 (clarified Option (c)) |

### 3.3. Files KHÔNG thay đổi (verified)

- `pyproject.toml` — unchanged
- `.gitignore` — unchanged
- `docs/system/SYS-01_requirements.md` — unchanged
- `docs/system/SYS-05_api_design.md` — unchanged
- `src/customer_segmentation/dataset_management/**` — unchanged
- `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,preprocessing,transformation,visualization}/**` — unchanged
- `configs/dev0[2-6]_*.yaml` — unchanged
- `tests/test_dev0[2-6]_*.py` — unchanged
- `AGENTS.md` — unchanged
- `data/**` — unchanged
- `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` — **chỉ log message**; KHÔNG thay đổi logic
- `src/customer_segmentation/prototype/marketing/storage.py` — unchanged
- `src/customer_segmentation/prototype/marketing/pipeline.py` — unchanged
- `src/customer_segmentation/prototype/marketing/manifest.py` — unchanged
- `src/customer_segmentation/prototype/marketing/scope.py` — unchanged
- `src/customer_segmentation/prototype/marketing/config_loader.py` — unchanged
- `src/customer_segmentation/prototype/marketing/validation.py` — unchanged
- `src/customer_segmentation/prototype/marketing/display.py` — unchanged
- `src/customer_segmentation/prototype/marketing/recommendation.py` — unchanged

---

## 4. Kết quả kiểm tra thực tế

### 4.1. DEV-07 tests

```
python3 -m pytest tests/test_dev07_*.py
============================= 263 passed in 1.41s ==============================
```

**Delta:** 263 (was 262 in remediation report → +1 new test `test_default_config_rejects_per_file_naming_convention`).

### 4.2. DEV-02..07 regression tests

```
python3 -m pytest tests/test_dev0[2-7]*.py
================ 1336 passed, 1 skipped, 26 warnings in 34.20s =================
```

**Delta:** 1336 (was 1335 in remediation report → +1 from DEV-07 new test). Pre-existing skipped: `test_dev03_consistency.py:241` (AC 38b OPT-IN, C7-dependent).

### 4.3. Ruff lint

```
python3 -m ruff check src/customer_segmentation/prototype/marketing/ \
                         tests/test_dev07_*.py scripts/dev07_run_marketing.py
All checks passed!
```

### 4.4. Black format

```
python3 -m black --check src/customer_segmentation/prototype/marketing/ \
                       tests/test_dev07_*.py scripts/dev07_run_marketing.py
All done! ✨ 🍰 ✨
21 files would be left unchanged.
```

### 4.5. YAML config parse

```
python3 -c "import yaml; data = yaml.safe_load(open('configs/dev07_marketing.yaml'))"
Pattern: '^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$'
Parse: OK ✅
```

### 4.6. Default config + synthetic MKT framework (production path)

```
load_mkt_framework(load_dev07_config(), repo_root=tmp)
  → ref returned ✅
  → ref.version: 'v1' ✅
  → framework_version_string(ref): 'MKT-01..05__v1' ✅
```

### 4.7. Per-file filenames rejected (aggregate pattern matches per-file names)

```
load_mkt_framework with per-file naming (MKT-01__v1.md)
  → Constructed aggregate form: 'MKT-01..05__v1'
  → Matches default config pattern: True ✅
  → ref returned ✅
```

### 4.8. Invalid naming rejected

```
load_mkt_framework with MKT-01_NOTES.md (no version suffix)
  → _extract_version returns None
  → ref is None ✅
```

### 4.9. Manifest schema (preprocessing_warning absent)

```
MarketingRecommendationManifest fields:
  'preprocessing_warning': False ✅
  'limitation': True ✅
  'limitation_note': True ✅
```

---

## 5. Bằng chứng ADR-0008 Option A

### 5.1. Config pattern đúng

Pattern `^MKT-01\.\.05__v\d+(?:\.\d+)*$` (escaped trong YAML):

```
MKT-01..05__v1     → matches ✅ (canonical)
MKT-01..05__v1.5    → matches ✅
MKT-01..05__v2.5.3 → matches ✅
MKT-01__v1         → NO match ✅ (per-file shape rejected)
MKT-01..05__1      → NO match ✅ (missing v prefix)
MKT-01..05__v1.x   → NO match ✅ (x not digit)
```

### 5.2. Loader production code không đổi

```python
# mkt_framework_loader.py::framework_version_string — giữ nguyên ✅
def framework_version_string(ref: MktFrameworkRef) -> str:
    return f"MKT-01..05__{ref.version}"  # aggregate form

# _extract_version — giữ nguyên logic ✅
if not pattern.match(f"MKT-01..05__{version}"):  # aggregate check
    return None
return version
```

### 5.3. `marketing_id` derivation không đổi

```python
# storage.py:39 — giữ nguyên ✅
CANONICAL_PAYLOAD_KEYS = (
    ...,
    "mkt_framework_version",  # null (Phase A) | "MKT-01..05__vN" (Phase B)
    ...
)
```

### 5.4. `MARKETING_MANIFEST_SCHEMA_VERSION` giữ `1.0.0`

```python
# scope.py
MARKETING_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"  # không bump
```

---

## 6. Bằng chứng Option (c): không carry-over `preprocessing_warning`

### 6.1. Schema E-MKT không có field

`MarketingRecommendationManifest` (v1.0.0) **không** chứa field `preprocessing_warning`. Schema E-MKT (SYS-03 §15.1) không bị sửa. Không bump schema version.

### 6.2. Pipeline không đọc DEV-06 warning

```python
# pipeline.py — giữ nguyên ✅
limitation=MARKETING_LIMITATION_TEXT,  # constant text, NOT DEV-06 warning
```

`MARKETING_LIMITATION_TEXT` constant:
```python
# scope.py:231-235
MARKETING_LIMITATION_TEXT: Final[str] = (
    "Marketing framework (MKT-01..MKT-05) not implemented in this "
    "prototype scope. Recommendation is descriptive only; do not "
    "interpret as a business action."
)
```

### 6.3. Witness tests giữ nguyên

4 tests trong `TestPreprocessingWarningCarryOver` xác nhận behavior hiện tại (không propagate):

1. `test_marketing_manifest_has_no_preprocessing_warning_field` — witness ✅
2. `test_dev06_preprocessing_warning_does_not_propagate_to_limitation` — witness ✅
3. `test_dev07_pipeline_succeeds_with_preprocessing_warning` — defensive ✅
4. `test_dev06_preprocessing_warning_empty_string_is_accepted` — defensive ✅

### 6.4. Plan đã được đính chính

| Vị trí | Nội dung mới |
|---|---|
| §4.2 | "DEV-07 KHÔNG carry forward trong Phase A (intentional; owner-approved Option (c))" |
| §4.4 | "KHÔNG raw 'post-preprocessing' values — Phase A không carry forward; Phase B sẽ re-evaluate" |
| AC-D07-10 | "preprocessing_warning KHÔNG được carry-forward trong Phase A (Option (c) accepted)" |

---

## 7. Mục còn pending

### 7.1. Phase B blockers

| OQ | Câu hỏi | Status | Owner quyết |
|---|---|---|---|
| **OQ-D07-01** | MKT-01..MKT-05 scope có khớp SYS-01 §6.7 (6 fields)? | `REVIEW_REQUIRED` | Owner / mentor |
| **OQ-D07-03** | CP-04 §4.1–§4.3 construction rules có phải canonical tokenization cho Phase B? | `REVIEW_REQUIRED` | Owner / mentor |
| **OQ-D07-04** | KPI definitions dùng đơn vị nào — survey / transaction / composition? | `REVIEW_REQUIRED` | Owner / mentor |
| **OQ-D07-05** | DEV-07 export format (CSV + JSONL hay khác)? | `REVIEW_REQUIRED` | Owner / mentor |

### 7.1.1. Owner Decision Closure (2026-10-10)

Concise decision table cho 4 OQ đã được cập nhật trong
`docs/system/DEV-07_phase_b_decision_memo.md` §2 với:

- Câu hỏi chính xác theo `DEV-07_owner_decision_matrix.md` §4.
- Contract + heading cụ thể (cite file + section, vd `SYS-01_requirements.md` §6.7, `CP-04.md` §4.1–§4.4, `SYS-03_data_model.md` §15.1).
- Phương án tối thiểu + căn cứ.
- Rủi ro nếu chọn phương án đó.
- Có thể triển khai không cần owner approval hay không.
- Phần nào đang block DEV-07 DONE.

Phân loại việc:

- **Ready now** (đã xong Phase B technical infrastructure): tokenization
  parser (24 tests), MKT framework structure loader (18 tests), mapping
  scaffolding (23 tests), recommendation builder Phase B branch wired,
  pipeline integration, config flags, 328 DEV-07 tests, 1401 DEV-02..07
  regression, ruff/black clean, no Git ops.
- **Needs owner approval**: OQ-D07-01, OQ-D07-03, OQ-D07-04, MKT-01..05
  framework files, actual recommendation content, HTML UI expansion.
- **Not required for DEV-07 acceptance** (deferred): CSV/JSONL writers
  (OQ-D07-05 = optional; FR-REPORT-* = SHOULD), Markdown report writer,
  cross-segmentation compare (CON-09 cấm), actual populate của 5 template
  fields, UI expansion.

### 7.2. Pre-existing gaps (ngoài phạm vi Phase A)

| Gap | Audit reference | Status |
|---|---|---|
| Malformed YAML test | §7.2.3 | Out of scope Phase A |
| `research_safety` carry-through với DEV-06 manifest thật | §7.2.4 | DEV-06 manifest thật chưa có |
| Schema-version bump + old manifest reload | §7.2.5 | Chưa có manifest cũ |
| `test_recommendation_id_format_compliance` | §9.3 F-P3-04 | Phase A không required |

---

## 8. Điều được nghiệm thu và chưa được nghiệm thu

### 8.1. Đã nghiệm thu ✅

| Item | Evidence |
|---|---|
| ADR-0008 Option A accepted (canonical aggregate form) | ADR-0008 status = `Accepted`; config updated; 7 tests pass |
| `preprocessing_warning` Option (c) accepted (no carry-forward Phase A) | Plan updated; 4 witness tests pass |
| 263/263 DEV-07 tests pass | pytest output verified |
| 1336/1336 DEV-02..07 tests pass | pytest output verified |
| Ruff clean (0 errors) | ruff output verified |
| Black clean (21 files) | black output verified |
| YAML parse OK | yaml.safe_load verified |
| Config loader loads with new pattern | load_dev07_config() verified |
| Default config + per-file MKT filenames → ref returned (aggregate matches) | production path verified |
| Default config + invalid naming → None | rejection verified |
| Default config + partial docs → None | rejection verified |
| Schema E-MKT không có `preprocessing_warning` | dataclass fields verified |
| Pipeline không đọc DEV-06 `preprocessing_warning` | pipeline.py line 414 verified |
| `MARKETING_MANIFEST_SCHEMA_VERSION` giữ `1.0.0` | scope.py verified |
| Loader production logic không đổi | source code verified |
| No Git operations | no git command executed |
| No research data used | synthetic fixtures only |

### 8.2. Chưa được nghiệm thu (Phase B blocked)

| Item | Blocker |
|---|---|
| Actual marketing recommendation generation | MKT-01..MKT-05 absent |
| Framework version pattern với file thật | MKT-01..MKT-05 absent |
| `preprocessing_warning` carry-over trong Phase B | OQ pending; Phase B task |
| KPI definitions | OQ-D07-04 pending |
| Recommendation mapping logic | OQ-D07-03 pending |
| Export format (CSV + JSONL) | OQ-D07-05 pending |
| HTML per-segment expansion | OQ-D07-06 resolved (giữ nguyên) |

### 8.3. Phase B unlock path

```
1. Owner / mentor tạo MKT-01..MKT-05 trong docs/marketing/
2. Owner resolve OQ-D07-01 (framework scope)
3. Owner resolve OQ-D07-03 (CP-04 tokenization)
4. Owner resolve OQ-D07-04 (KPI units)
5. Owner resolve OQ-D07-05 (export format)
6. Phase B implementation task
```

---

## 9. Cấu trúc files thay đổi (diff scope)

```
Files tạo mới:
  docs/system/DEV-07_final_acceptance_report.md  (this file)

Files sửa (12):
  configs/dev07_marketing.yaml                           (pattern update)
  docs/decisions/0008-dev07-version-pattern.md       (status → Accepted)
  src/customer_segmentation/prototype/marketing/
    mkt_framework_loader.py                            (log message only)
  tests/test_dev07_mkt_framework.py                   (7 tests refactored + 1 new)
  tests/test_dev07_validation.py                       (helper pattern updated)
  tests/test_dev07_recommendation.py                  (helper pattern updated)
  tests/test_dev07_pipeline.py                         (helper pattern updated)
  docs/system/DEV-07_owner_decision_brief.md         (decisions recorded)
  docs/system/DEV-07_owner_decision_matrix.md         (decisions recorded)
  docs/system/DEV-07_implementation_plan.md             (Option C documented)

Files KHÔNG bị thay đổi (verified):
  pyproject.toml, .gitignore
  docs/system/SYS-01..06_*.md
  docs/system/DEV-01..06_*.md
  src/customer_segmentation/dataset_management/**
  src/customer_segmentation/prototype/{clustering,evaluation,segmentation,preprocessing,transformation,visualization}/**
  configs/dev0[2-6]_*.yaml
  tests/test_dev0[2-6]_*.py
  AGENTS.md, data/**
```

---

## 10. Appendix: Commands chạy verification

```bash
# Setup
cd /home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml

# Tests
python3 -m pytest tests/test_dev07_*.py                        # 263 passed
python3 -m pytest tests/test_dev0[2-7]*.py                    # 1336 passed, 1 skipped

# Lint
python3 -m ruff check src/customer_segmentation/prototype/marketing/ \
                     tests/test_dev07_*.py scripts/dev07_run_marketing.py
# All checks passed

# Format
python3 -m black --check src/customer_segmentation/prototype/marketing/ \
                       tests/test_dev07_*.py scripts/dev07_run_marketing.py
# 21 files would be left unchanged

# YAML
python3 -c "import yaml; d=yaml.safe_load(open('configs/dev07_marketing.yaml')); print(d['dev07_marketing']['mkt_framework']['version_pattern'])"

# Config loader + pattern
PYTHONPATH=src python3 -c "
from customer_segmentation.prototype.marketing.config_loader import load_dev07_config
cfg = load_dev07_config()
print(cfg.mkt_framework.version_pattern)
"

# Production path test
PYTHONPATH=src python3 -c "
from customer_segmentation.prototype.marketing.config_loader import load_dev07_config
from customer_segmentation.prototype.marketing.mkt_framework_loader import load_mkt_framework, framework_version_string
from pathlib import Path
import tempfile
cfg = load_dev07_config()
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / 'docs' / 'marketing').mkdir(parents=True)
    for i in range(1, 6): (td / 'docs' / 'marketing' / f'MKT-0{i}__v1.md').write_text('x')
    ref = load_mkt_framework(cfg, repo_root=td)
    print('ref:', ref)
    if ref: print('version:', ref.version, 'framework:', framework_version_string(ref))
"
```

---

## 11. Owner Decision Closure (2026-10-10)

### 11.1. Trạng thái cuối cùng

> **DEV-07 Phase A**: ACCEPTED (2026-10-10).
>
> **DEV-07 Phase B technical infrastructure**: TECHNICALLY IMPLEMENTED
> (2026-10-10). 65 tests mới (24 tokenization + 18 framework structure
> + 23 mapping scaffolding). 328 DEV-07 tests pass; 1401 DEV-02..07
> regression pass (1 skipped pre-existing); ruff/black clean.
>
> **DEV-07 Phase B actual recommendation generation**: **BLOCKED** —
> chờ owner approve 4 OQ + MKT-01..MKT-05 framework files.
>
> **Owner Decision Closure** (2026-10-10): Concise decision table đã
> được cập nhật trong `docs/system/DEV-07_phase_b_decision_memo.md` §2.
> **KHÔNG tự giải OQ** — chờ owner review.

### 11.2. OQ nào đã có căn cứ giải quyết và OQ nào thực sự cần owner

- **OQ-D07-01** (MKT framework scope ↔ SYS-01 §6.7): 6 fields mapping đã
  xác định (Objective → MKT-02, Strategy/Action → MKT-03, KPI → MKT-04,
  Evidence → auto, Limitation → MKT-05 + constant); nhưng **CẦN owner**
  confirm mapping trước khi tạo MKT files.
- **OQ-D07-03** (CP-04 §4.1–§4.3 canonical tokenization): Parser đã
  implement + 24 tests; **CẦN owner** confirm methodology adoption
  (đặc biệt rule cho COMPARATIVE segments).
- **OQ-D07-04** (KPI units / source): Inventory + đề xuất đã liệt kê
  (composition-based từ 8/14 RFM features `ELIGIBLE`; KHÔNG dùng 6
  features `ELIGIBLE_WORKING_ASSUMPTION`); **CẦN owner** confirm scope.
- **OQ-D07-05** (Export format): Đề xuất "giữ read-only" = status quo;
  **KHÔNG block** DEV-07 acceptance (FR-REPORT-* = SHOULD; OQ-D07-08 đã
  resolve = read-only cho Phase A).

### 11.3. Files thay đổi trong task này

```
Files sửa (3):
  docs/system/DEV-07_phase_b_decision_memo.md
      # Concise decision table (516 lines); ready/owner/deferred split.
  docs/system/DEV-07_phase_b_acceptance_report.md
      # Added §12 Owner Decision Closure section.
  docs/system/DEV-07_final_acceptance_report.md
      # Added §7.1.1 + §11 Owner Decision Closure sections.

Files KHÔNG thay đổi (verified):
  src/customer_segmentation/prototype/marketing/{tokenization,mapping,
    mkt_framework_loader,recommendation,pipeline}.py
  tests/test_dev07_*.py
  configs/dev07_marketing.yaml
  AGENTS.md, .gitignore, pyproject.toml
  docs/system/SYS-01..06_*.md, docs/system/DEV-01..06_*.md
  docs/system/DEV-07_owner_decision_*.md
  docs/system/DEV-07_implementation_plan.md
  docs/system/ui-prototype/index.html
  data/**
  docs/marketing/**
```

### 11.4. Test / lint thực tế (verified 2026-10-10)

| Gate | Kết quả |
|---|---|
| `pytest tests/test_dev07_*.py` | 328 passed in 1.50s |
| `pytest tests/test_dev0[2-7]*.py` | 1401 passed, 1 skipped pre-existing |
| `ruff check src/customer_segmentation/prototype/marketing/ tests/test_dev07_*.py scripts/dev07_run_marketing.py` | All checks passed |
| `black --check ...` | 26 files would be left unchanged |
| YAML parse `configs/dev07_marketing.yaml` | OK |

### 11.5. Quyết định tối thiểu để chuyển sang DEV-08/DEV-09

Để DEV-07 đạt trạng thái DONE thực sự (không chỉ TECHNICALLY
IMPLEMENTED), owner / mentor cần confirm 3 OQ sau (OQ-D07-05 không
block acceptance):

1. **OQ-D07-01**: MKT framework scope ↔ SYS-01 §6.7 6 fields mapping.
2. **OQ-D07-03**: CP-04 §4.1–§4.3 canonical tokenization cho Phase B
   mapping (đặc biệt rule cho COMPARATIVE).
3. **OQ-D07-04**: KPI units / source — composition-based từ 8/14 RFM
   features `ELIGIBLE`, hoặc survey/transaction-derived, hoặc khác.

Sau khi owner approve 3 OQ trên + tạo MKT-01..MKT-05 framework files,
`mapping.resolve_template_slots` có thể được extend trong task tiếp
theo để populate slots từ MKT content. Phase B actual recommendation
generation mới có thể nghiệm thu. Lúc đó DEV-08/DEV-09 mới có thể bắt
đầu (nếu scope cho phép).

---

*File này là DEV-07 Final Acceptance Report. Theo AGENTS.md §2.11,
**KHÔNG** thực hiện git operations. Phase A đã accepted 2026-10-10;
Phase B technical infrastructure TECHNICALLY IMPLEMENTED 2026-10-10;
Phase B actual recommendation generation vẫn BLOCKED chờ 4 OQ + MKT framework.*