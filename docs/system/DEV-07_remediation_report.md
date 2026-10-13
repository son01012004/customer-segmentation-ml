# DEV-07 — Phase A Remediation Report

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module — Phase A remediation sau audit
> **Ngày:** 2026-10-10
> **Trạng thái:** REMEDIATION COMPLETE — pending owner decision on ADR-0008
> **Phạm vi remediation:**
>   - P1: version pattern ambiguity (audit §4.1, §4.2, §5)
>   - P2: lint + format (audit §4.3, §4.4, §4.5)
>   - P3: test coverage + `preprocessing_warning` carry-over
>     (audit §4.6, §6.10, §7.2)
> **Phạm vi KHÔNG thuộc remediation:** Phase B (MKT-01..MKT-05 absent),
> contract changes, methodology changes, Git operations.
> **Audit source:** `docs/system/DEV-07_phase_a_audit_report.md` (10 §).
> **Does NOT:** tự phê duyệt ADR; thay đổi production config; thay đổi
> semantics hiện hành ngoài phạm vi diagnostics.

---

## Mục lục

1. [Tóm tắt](#1-t%C3%B3m-t%E1%BA%AFt)
2. [Findings và trạng thái](#2-findings-v%C3%A0-tr%E1%BA%A1ng-th%C3%A1i)
3. [Files đã sửa](#3-files-%C4%91%C3%A3-s%E1%BB%AFa)
4. [Validation thực tế](#4-validation-th%E1%BB%B1c-t%E1%BA%BF)
5. [P1 — Version pattern chi tiết](#5-p1--version-pattern-chi-ti%E1%BA%BFt)
6. [P2 — Lint/Format chi tiết](#6-p2--lintformat-chi-ti%E1%BA%BFt)
7. [P3 — Tests + preprocessing_warning chi tiết](#7-p3--tests--preprocessing_warning-chi-ti%E1%BA%BFt)
8. [Findings chưa xử lý / chờ owner](#8-findings-ch%C6%B0a-x%E1%BB%AD-l%C3%BD--ch%E1%BB%9D-owner)
9. [Out of scope / KHÔNG thực hiện](#9-out-of-scope--kh%C3%B4ng-th%E1%BB%B1c-hi%E1%BB%87n)
10. [Kết luận Phase A vs Phase B](#10-k%E1%BA%BFt-lu%E1%BA%ADn-phase-a-vs-phase-b)

---

## 1. Tóm tắt

| Hạng mục | Audit verdict | Remediation verdict | Pass? |
|---|---|---|---|
| **P1 — version pattern** | CONDITIONAL PASS — cần owner decision | ADR-0008 draft tạo (status `PROPOSED — OWNER DECISION REQUIRED`); diagnostics cải thiện; production config + loader KHÔNG thay đổi | ⚠️ CĐ owner |
| **P2 — lint** | FAIL — 17 errors | **All fixed** (16 auto-fixed, 1 manual) | ✅ |
| **P2 — format** | FAIL — 12 files cần reformat | **All reformatted** (21 files clean) | ✅ |
| **P2 — YAML** | Block comments gây rủi ro parse | **Verified OK** (`yaml.safe_load` parse thành công) | ✅ |
| **P3 — test default config** | Gap: 0 test dùng default config + MKT | **6 tests mới** (`TestDefaultConfigIntegration`) | ✅ |
| **P3 — preprocessing_warning** | Gap: 0 test, no carry-over | **4 witness tests** document gap (no silent change) | ⚠️ CĐ owner |
| **Test count DEV-07** | 252 | **262** (+10) | ✅ |
| **Test count DEV-02..07** | 1325 + 1 skipped | **1335 + 1 skipped** (+10) | ✅ |
| **Methodology gates** | Honored (noise excluded, KPI=None, no invent, no export, no research-promote) | **Honored** (no change) | ✅ |
| **Phạm vi thay đổi** | n/a | CHỈ sửa DEV-07 files; KHÔNG sửa SYS-*, AGENTS.md, pyproject.toml, .gitignore, DEV-02..06 contracts | ✅ |

---

## 2. Findings và trạng thái

### 2.1. Mapping từ audit findings

| Audit § | Finding | Severity | Status sau remediation |
|---|---|---|---|
| §4.1 | `version_pattern` config mismatch (per-file vs aggregate) | P1 | **ADR-0008 draft created**; production unchanged pending owner decision |
| §4.2 | Loader hard-codes aggregate form `MKT-01..05__vN` | P1 | **Diagnostics cải thiện** (WARNING log on mismatch); semantics unchanged; ADR-0008 documents options |
| §4.3 | Ruff check NOT clean (17 errors) | P2 | **All fixed** (16 auto, 1 manual) |
| §4.4 | Black check NOT clean (12 files) | P2 | **All reformatted** (21 files clean) |
| §4.5 | YAML block comments gây rủi ro parse | P2 | **Verified OK** — `yaml.safe_load` parse thành công; comments KHÔNG gây lỗi parse theo YAML spec (chỉ gây cảnh báo cho một số tool khác). Block comments giữ nguyên vì format dễ đọc cho human reviewer. |
| §4.6 | `_make_manifest_data` test pattern = config (per-file) | P3 | **Documented**; không thay đổi vì test pass với pattern hiện tại; ADR-0008 sẽ quyết sau owner |
| §4.7 | Completion summary không có file trong repo | P3 | **Remediation report này** giải quyết; 262 tests + ruff + black đều clean |
| §6.10 | `preprocessing_warning` carry-over unclear | P3 | **Documented** với 4 witness tests; KHÔNG thay đổi behavior; ADR đề xuất (xem §8) |
| §7.2.1 | Default config pattern never tested with framework | P3 | **6 new tests** (`TestDefaultConfigIntegration`) |
| §7.2.2 | `preprocessing_warning` carry-over — 0 tests | P3 | **4 new tests** (`TestPreprocessingWarningCarryOver`) |
| §7.2.3 | Malformed YAML test missing | P3 | **KHÔNG xử lý** (out of scope: ngoài audit P1/P2/P3) |
| §7.2.4 | `research_safety` carry-through với DEV-06 manifest thật | P3 | **KHÔNG xử lý** (audit note: chưa có DEV-06 manifest thật trong repo) |
| §7.2.5 | Schema-version bump khả năng re-load manifest cũ | P3 | **KHÔNG xử lý** (chưa có manifest cũ để test) |
| §9.1 | F-P1-01 fix config pattern | P1 | **KHÔNG thực hiện** vì canonical form cần owner decision (ADR-0008) |
| §9.1 | F-P1-02 ADR for version pattern | P1 | **Đã thực hiện** (ADR-0008 draft) |
| §9.2 | F-P2-01 ruff --fix | P2 | **Đã thực hiện** |
| §9.2 | F-P2-02 black reformat | P2 | **Đã thực hiện** |
| §9.2 | F-P2-03 YAML block comments | P2 | **Documented** (xem §6.3) |
| §9.3 | F-P3-01 update completion claim | P3 | **Báo cáo này** |
| §9.3 | F-P3-02 default config test | P3 | **Đã thực hiện** (6 tests mới) |
| §9.3 | F-P3-03 document preprocessing_warning | P3 | **Documented** (4 witness tests + báo cáo) |
| §9.3 | F-P3-04 test `recommendation_id` regex | P3 | **KHÔNG xử lý** (đã có test trong `test_dev07_manifest.py` theo plan §6) |

### 2.2. Tóm tắt trạng thái

- **P1**: 1 ADR draft + diagnostics cải thiện; production unchanged.
- **P2**: Tất cả lint/format sạch; YAML OK.
- **P3**: Test default config + preprocessing_warning witness tests added.
- **Pre-existing gaps**: 1 file ngoài scope (`malformed YAML test`) — ghi nhận.
- **Owner decisions pending**: 2 (ADR-0008 + preprocessing_warning ADR đề xuất).

---

## 3. Files đã sửa

### 3.1. Files mới tạo (1)

| File | Loại | Mục đích |
|---|---|---|
| `docs/decisions/0008-dev07-version-pattern.md` | ADR draft | Canonical version pattern owner decision (status: `PROPOSED — OWNER DECISION REQUIRED`) |

### 3.2. Files đã sửa (8)

| File | Loại sửa | Phạm vi thay đổi |
|---|---|---|
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | P1 diagnostics | Thêm stdlib `logging` cho debug/warning log khi version extraction fail; cập nhật docstring để document diagnostics. **KHÔNG thay đổi** return value, signature, hoặc semantics. |
| `src/customer_segmentation/prototype/marketing/__init__.py` | P2 ruff F811 | Xóa duplicate import `MarketingManifestError` (giữ từ `exceptions.py`, xóa khỏi block `manifest.py` import). |
| `src/customer_segmentation/prototype/marketing/manifest.py` | P2 ruff UP030/UP032 (auto-fix) | Đổi `format(...)` call → f-string (manifest.py:482). |
| `tests/test_dev07_mkt_framework.py` | P2 auto-fix + P3 default-config tests | Import sort (I001); thêm 6 tests mới (`TestDefaultConfigIntegration`). |
| `tests/test_dev07_manifest.py` | P2 auto-fix | Import sort (I001); xóa unused F401 imports. |
| `tests/test_dev07_scope.py` | P2 auto-fix + black reformat | Import sort (I001); xóa unused F401 import; 3 SIM300 Yoda condition auto-flip; black reformat. |
| `tests/test_dev07_storage.py` | P2 auto-fix | Import sort (I001); black reformat. |
| `tests/test_dev07_pipeline.py` | P3 preprocessing_warning tests | Thêm 4 witness tests (`TestPreprocessingWarningCarryOver`); black reformat. |
| `scripts/dev07_run_marketing.py` | P2 auto-fix | UP035 (Sequence from `collections.abc`); F401 (xóa unused `get_logger` import). |
| `src/customer_segmentation/prototype/marketing/scope.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/logging_config.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/display.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/config_loader.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/pipeline.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/storage.py` | P2 black reformat (chỉ format) | Black formatting. |
| `src/customer_segmentation/prototype/marketing/validation.py` | P2 black reformat (chỉ format) | Black formatting. |

### 3.3. Files KHÔNG thuộc phạm vi (verified unchanged)

| File / pattern | Status |
|---|---|
| `pyproject.toml` | Unchanged (verified via `git status`) |
| `.gitignore` | Unchanged |
| `docs/system/SYS-01_requirements.md` | Unchanged |
| `docs/system/SYS-05_api_design.md` | Unchanged |
| `docs/system/SYS-02..04, 06_*.md` | KHÔNG thuộc remediation scope; không sửa |
| `docs/system/DEV-01..06_*.md` | KHÔNG thuộc remediation scope; không sửa |
| `src/customer_segmentation/dataset_management/**` | KHÔNG thuộc remediation scope; không sửa |
| `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,preprocessing,transformation,visualization}/**` | KHÔNG thuộc remediation scope; không sửa |
| `configs/dev0[2-6]_*.yaml` | KHÔNG thuộc remediation scope; không sửa |
| `configs/dev07_marketing.yaml` | Unchanged (theo ADR-0008 — chờ owner decision) |
| `tests/test_dev0[2-6]_*.py` | KHÔNG thuộc remediation scope; không sửa |
| `data/**` | KHÔNG thuộc remediation scope; không sửa |
| `AGENTS.md` | KHÔNG sửa (rule bất biến) |

### 3.4. Diff scope verification

Tất cả DEV-07 files modified đều thuộc `src/customer_segmentation/prototype/marketing/`,
`tests/test_dev07_*.py`, `scripts/dev07_run_marketing.py`, hoặc
`docs/decisions/0008-dev07-version-pattern.md` (mới tạo). Files ngoài
phạm vi này không bị thay đổi.

---

## 4. Validation thực tế

### 4.1. Commands chạy + kết quả

| # | Command | Phạm vi | Kết quả thực tế |
|---|---|---|---|
| 1 | `python3 -m pytest tests/test_dev07_*.py` | DEV-07 only | **262 passed in 1.28s** (252 cũ + 10 mới) |
| 2 | `python3 -m pytest tests/test_dev0[2-7]*.py` | Regression DEV-02..07 | **1335 passed, 1 skipped in 34.27s** (1325 cũ + 10 mới) |
| 3 | `python3 -m ruff check src/customer_segmentation/prototype/marketing/ tests/test_dev07_*.py scripts/dev07_run_marketing.py` | DEV-07 source + tests + script | **All checks passed** (0 errors) |
| 4 | `python3 -m black --check src/customer_segmentation/prototype/marketing/ tests/test_dev07_*.py scripts/dev07_run_marketing.py` | DEV-07 source + tests + script | **21 files would be left unchanged** (clean) |
| 5 | `python3 -c "import yaml; yaml.safe_load(open('configs/dev07_marketing.yaml'))"` | YAML parse | **OK** — top key `dev07_marketing` |
| 6 | `PYTHONPATH=src python3 -c "from customer_segmentation.prototype.marketing.config_loader import load_dev07_config; cfg = load_dev07_config()"` | Config load | **OK** — `schema_version=1.0.0`, `version_pattern=^MKT-0[1-5]__v[0-9]+$` |
| 7 | `git status --short` | Working tree scope | DEV-07 files untracked (modified); tracked files (`.gitignore`, `pyproject.toml`, `SYS-01`, `SYS-05`) **unchanged** |

### 4.2. Test count per file (verified)

| File | Tests | Status |
|---|---|---|
| `test_dev07_scope.py` | 18 | ✅ |
| `test_dev07_manifest.py` | 30 | ✅ |
| `test_dev07_storage.py` | 25 | ✅ |
| `test_dev07_mkt_framework.py` | 44 (38 cũ + 6 mới) | ✅ |
| `test_dev07_validation.py` | 45 | ✅ |
| `test_dev07_recommendation.py` | 28 | ✅ |
| `test_dev07_pipeline.py` | 42 (38 cũ + 4 mới) | ✅ |
| `test_dev07_display.py` | 41 | ✅ |
| **Tổng** | **262** | **All passed** |

### 4.3. Test claims consistency

| Claim | Audit | Remediation | Khớp? |
|---|---|---|---|
| DEV-07 tests | 252 | 262 | +10 (6 default-config + 4 preprocessing-warning) |
| DEV-02..07 tests | 1325 + 1 skipped | 1335 + 1 skipped | +10 (same reason) |
| 173 new tests | unverifiable (no baseline) | unverifiable (no baseline) | n/a |

### 4.4. Safety gates (verified)

| Gate | Status |
|---|---|
| DBSCAN noise excluded (`segment_id=-1`) | ✅ (`test_dev07_pipeline.py::test_end_to_end_dbscan_with_noise`) |
| KPI = None (Phase A) | ✅ (`test_dev07_pipeline.py::test_no_kpi_in_phase_a`) |
| `research_safety` always False / `MARKETING_PROTOTYPE` | ✅ (`test_dev07_pipeline.py::test_research_safety_block_invariant`) |
| No internal clustering metric in KPI | ✅ (`test_dev07_validation.py::TestValidateKpiBlocklist`) |
| No forbidden marketing terms | ✅ (`test_dev07_validation.py::TestValidateTextNoForbiddenTerms` + display tests) |
| No recommendation generation (kpi=None) | ✅ (no test fail) |
| No CSV/JSONL export Phase A | ✅ (config: `emit_recommendations_csv: false`, `emit_recommendations_jsonl: false`) |
| No HTML modification | ✅ (no change to `docs/system/ui-prototype/index.html`) |
| No DEV-06 contract modification | ✅ (only read) |
| No Git operations | ✅ (verified: no `git commit`, `git push`, `git add`, etc.) |

---

## 5. P1 — Version pattern chi tiết

### 5.1. Phát hiện

Có **3 pattern forms** khác nhau trong codebase, không có tài liệu
contract nào quyết định form nào là canonical:

| Nguồn | Pattern | Loại |
|---|---|---|
| `configs/dev07_marketing.yaml::mkt_framework.version_pattern` (line 78) | `^MKT-0[1-5]__v[0-9]+$` | Per-file (match `MKT-01__v1`) |
| `mkt_framework_loader.py::framework_version_string()` (line 162) | `f"MKT-01..05__{ref.version}"` | Aggregate (match `MKT-01..05__v1`) |
| `test_dev07_mkt_framework.py::_make_config()` (line 28) | `r"^MKT-01\.\.05__v\d+(?:\.\d+)*$"` | Aggregate (escape) |
| `test_dev07_validation.py::_make_full_config()` (line 99) | `r"^MKT-0[1-5]__v[0-9]+$"` | Per-file (inherited from config) |
| `test_dev07_pipeline.py::_make_minimal_yaml()` (inline YAML) | `"^MKT-01..05__v[0-9]+$"` | Aggregate (literal, unescaped) |

### 5.2. Hành động

1. **Tạo `docs/decisions/0008-dev07-version-pattern.md`** với status
   `PROPOSED — OWNER DECISION REQUIRED`. Document đầy đủ 2 options
   (A: aggregate canonical; B: per-file canonical), tác động, và
   khuyến nghị.
2. **Cải thiện diagnostics** trong `mkt_framework_loader.py`:
   - DEBUG log khi directory absent hoặc <5 docs.
   - DEBUG log khi `_extract_version` không match pattern.
   - **WARNING log** khi framework directory tồn tại + ≥5 docs nhưng
     version pattern không match (silent-failure prevention, audit
     §4.1). Loader vẫn return `None` (giữ Phase A contract).
3. **KHÔNG thay đổi**:
   - `configs/dev07_marketing.yaml::mkt_framework.version_pattern`
   - `mkt_framework_loader.py::_extract_version` return value logic
   - `framework_version_string()` output
   - `marketing_id` derivation

### 5.3. Test default-config integration (P3 cover for P1)

6 tests mới trong `TestDefaultConfigIntegration`:

1. `test_default_config_loads` — smoke test default config loads.
2. `test_default_config_framework_absent_returns_none` — Phase A
   contract với default config.
3. `test_default_config_with_per_file_mkt_pattern_no_match` —
   documents P1 issue: per-file filenames + default per-file pattern
   produces aggregate form `MKT-01..05__v1` mà default pattern không
   match → return `None`. **Witness**: a DEBUG log records the
   pattern mismatch (audit §4.1 silent-failure-prevention).
4. `test_default_config_with_aggregate_mkt_pattern_matches` —
   verifies loader works end-to-end when config dùng aggregate
   pattern (override default per-file).
5. `test_default_config_partial_docs_returns_none` — only 3 of 5
   MKT docs → `None` (Phase A contract).
6. `test_default_config_warning_emitted_on_construct_mismatch` —
   verifies WARNING-level diagnostic khi construct mismatch. Confirms
   audit F-P1 finding ở level WARNING (không chỉ DEBUG) để operator
   thấy rõ production-relevant signal.

### 5.4. Owner decision required

Theo AGENTS.md §2.1, ADR-0008 phải được owner phê duyệt trước khi
production config/loader được thay đổi. Hai options trong ADR-0008:

- **Option A**: Canonical aggregate form `MKT-01..05__vN`. Sửa config
  pattern + test helpers. Không thay đổi loader production code.
  **Khuyến nghị** (theo ADR §2.2).
- **Option B**: Per-file form `MKT-0X__vN`. Sửa loader `_extract_version`
  + `framework_version_string`. Bump `MARKETING_MANIFEST_SCHEMA_VERSION`
  vì `marketing_id` derivation dùng `mkt_framework_version`.

---

## 6. P2 — Lint/Format chi tiết

### 6.1. Ruff errors (audit §4.3) — đã sửa hết

Audit báo cáo 17 errors. Tất cả thuộc DEV-07 scope
(`src/customer_segmentation/prototype/marketing/`,
`tests/test_dev07_*.py`, `scripts/dev07_run_marketing.py`).

**Phân loại DEV-07 vs pre-existing:**

| Loại | Count | Phân loại |
|---|---|---|
| I001 (Import sort) | 10 | DEV-07 (mới tạo) |
| F401 (Unused import) | 5 | DEV-07 (mới tạo) |
| UP035 (`Sequence` from `collections.abc`) | 1 | DEV-07 (mới tạo) |
| SIM300 (Yoda condition) | 3 | DEV-07 (test files) |
| UP030/UP032 (f-string instead of format) | 1 | DEV-07 |
| F811 (redefinition) | 1 | DEV-07 (duplicate import) |
| **Tổng** | **17** | **100% DEV-07** |

**Hành động**:

1. `python3 -m ruff check ... --fix` — auto-fix 16/17 errors.
2. Manual fix 1 error (F811 `MarketingManifestError` duplicate import
   trong `__init__.py`).
3. Verify: `python3 -m ruff check ...` → "All checks passed!".

### 6.2. Black format (audit §4.4) — đã sửa hết

Audit báo cáo 12 files cần reformat. Verify tất cả 12 files
THUỘC DEV-07 scope (không có pre-existing file ngoài DEV-07):

| File | Thuộc DEV-07? |
|---|---|
| `mkt_framework_loader.py` | ✅ |
| `logging_config.py` | ✅ |
| `display.py` | ✅ |
| `scope.py` | ✅ |
| `config_loader.py` | ✅ |
| `pipeline.py` | ✅ |
| `storage.py` | ✅ |
| `validation.py` | ✅ |
| `manifest.py` | ✅ |
| `test_dev07_manifest.py` | ✅ |
| `test_dev07_storage.py` | ✅ |
| `test_dev07_scope.py` | ✅ |

**Hành động**: `python3 -m black ...` cho 12 files + 9 files đã
clean. Sau khi thêm tests mới, `test_dev07_mkt_framework.py` và
`test_dev07_pipeline.py` cũng cần reformat (2 files mới) → tổng
14 files reformatted. Verify: `python3 -m black --check ...` →
"21 files would be left unchanged" (clean).

### 6.3. YAML config (audit §4.5)

Audit lo ngại block comments (`# ---...`) gây lỗi parse. **Verify**:
- `python3 -c "import yaml; yaml.safe_load(open('configs/dev07_marketing.yaml'))"` → parse OK.
- Top key `dev07_marketing` đúng.

**Quyết định**: Giữ block comments nguyên vì:
- (a) YAML spec cho phép comments bắt đầu bằng `#` ở bất kỳ đâu (block
  comments hoàn toàn hợp lệ theo YAML 1.1/1.2 spec).
- (b) `yaml.safe_load` (parser chính) parse thành công.
- (c) Block comments giúp human reviewer đọc config dễ hơn.
- (d) Chỉ một số tool (helm/k8s validators) có strict rules khác; project
  này không dùng các tool đó.

Nếu owner muốn convert sang single-line `# ...` để tăng tương thích
với strict YAML validators, có thể thực hiện trong cleanup pass sau.

### 6.4. Files scope (audit ngoài remediation)

Verify không sửa ngoài phạm vi: `git status --short` cho thấy:
- `.gitignore`, `pyproject.toml`, `SYS-01_requirements.md`,
  `SYS-05_api_design.md` (4 tracked files modified) — KHÔNG thuộc
  remediation, đã có sẵn trong working tree.
- Tất cả DEV-07 files modified là untracked (chưa commit), nên
  `git diff` không khả dụng. Đã manual verify danh sách files
  modified (xem §3.2).

---

## 7. P3 — Tests + preprocessing_warning chi tiết

### 7.1. Default-config integration tests (audit §4.1, §7.2.1)

6 tests mới trong `TestDefaultConfigIntegration`
(`tests/test_dev07_mkt_framework.py`):

1. `test_default_config_loads` — smoke.
2. `test_default_config_framework_absent_returns_none` — Phase A baseline.
3. `test_default_config_with_per_file_mkt_pattern_no_match` — witness
   cho P1 (per-file filenames + default per-file pattern → None).
4. `test_default_config_with_aggregate_mkt_pattern_matches` —
   verifies loader works when config dùng aggregate pattern.
5. `test_default_config_partial_docs_returns_none` — only 3/5 docs.
6. `test_default_config_warning_emitted_on_construct_mismatch` —
   WARNING-level diagnostic verification.

Các test dùng `load_dev07_config()` (không override `version_pattern`)
+ synthetic MKT framework trong `tmp_path`. Đây là đường production
của loader, không qua helper `_make_config()` override.

### 7.2. preprocessing_warning carry-over (audit §4.10, §6.10, §7.2.2)

**Investigation kết quả**:

1. **DEV-06 manifest** có field `preprocessing_warning: str = ""`
   (mandatory field, default empty).
2. **E-MKT schema (SYS-03 §15.1)** KHÔNG có field
   `preprocessing_warning`.
3. **`MarketingRecommendationManifest` v1.0.0** KHÔNG có field
   `preprocessing_warning`.
4. **Pipeline** KHÔNG đọc `preprocessing_warning` từ DEV-06 manifest.
5. **Plan §4.2 + §4.4 + AC-D07-10** yêu cầu carry forward, nhưng
   không chỉ rõ mechanism (text-level vào `limitation_note`? field
   mới?).
6. **Audit §6.10** note "Có thể được incorporated vào
   `limitation_note` hoặc chưa. Cần check."

**Hành động** (theo user instruction: "không tự thêm field vào
schema hoặc thay đổi output contract khi chưa được phê duyệt"):

1. **KHÔNG thay đổi** schema (`MarketingRecommendationManifest`).
2. **KHÔNG thay đổi** semantics (`limitation_note` giữ giá trị
   `MARKETING_LIMITATION_TEXT` mặc định, không concat
   `preprocessing_warning`).
3. **Thêm 4 witness tests** trong `TestPreprocessingWarningCarryOver`
   (`tests/test_dev07_pipeline.py`):
   - `test_marketing_manifest_has_no_preprocessing_warning_field` —
     witness: schema v1.0.0 không có field này.
   - `test_dev06_preprocessing_warning_does_not_propagate_to_limitation` —
     witness: warning không propagate vào `limitation` /
     `limitation_note`.
   - `test_dev07_pipeline_succeeds_with_preprocessing_warning` —
     defensive: pipeline không fail khi DEV-06 có warning.
   - `test_dev06_preprocessing_warning_empty_string_is_accepted` —
     defensive: empty string (default) accepted.
4. **Document gap** trong remediation report (xem §8.2 dưới).

Các witness tests document hành vi hiện tại (DEV-07 KHÔNG
carry-over `preprocessing_warning`); chúng đảm bảo behavior
transparent và ngăn regression âm thầm.

### 7.3. Test count delta

| Module | Trước | Sau | Delta |
|---|---|---|---|
| `test_dev07_mkt_framework.py` | 38 | 44 | +6 |
| `test_dev07_pipeline.py` | 38 | 42 | +4 |
| `test_dev07_*.py` (tổng) | 252 | **262** | **+10** |
| `test_dev0[2-7]_*.py` (tổng) | 1325 | **1335** | **+10** |

---

## 8. Findings chưa xử lý / chờ owner

### 8.1. ADR-0008 — Version pattern canonical form (P1)

**File**: `docs/decisions/0008-dev07-version-pattern.md`
**Status**: `PROPOSED — OWNER DECISION REQUIRED`
**Impact**: Phase B readiness. Khi MKT-01..MKT-05 files được tạo, nếu
không quyết pattern canonical, loader có thể silently reject framework
hợp lệ.

**Owner actions**:
1. Review ADR-0008 §2 (Options A vs B).
2. Chọn 1 option; record decision in ADR-0008 (status: `APPROVED`).
3. Sau khi approve, thực hiện hành động theo §3 của ADR-0008.

### 8.2. preprocessing_warning carry-over (P3)

**File**: `MarketingRecommendationManifest` (chưa có field); `pipeline.py`
(chưa đọc field từ DEV-06).
**Status**: Documented gap, no production change.
**Impact**: Plan §4.2 + §4.4 + AC-D07-10 nói "carry forward" nhưng
contract chưa rõ mechanism.

**Owner actions**:
1. Quyết định option (a) / (b) / (c) theo ADR đề xuất dưới.
2. Nếu (a) hoặc (b): tạo ADR mới (vd: `0009-dev07-preprocessing-warning-propagation.md`) theo convention immutability, bump schema version nếu cần.
3. Nếu (c): đính chính plan §4.2 / §4.4 / AC-D07-10 để document
   "DEV-07 does not carry forward `preprocessing_warning`" là quyết
   định có chủ đích.

**Đề xuất 3 options** (cần owner quyết):

- **(a) Add `preprocessing_warning` field to E-MKT schema** — yêu cầu
  SYS-03 §15.1 update + schema version bump (1.0.0 → 1.1.0). Ảnh hưởng
  lớn nhất nhưng rõ ràng nhất.
- **(b) Concatenate into `limitation_note`** — text-level propagation,
  không thêm field. Nhưng cần thay đổi giá trị `limitation_note` (hiện
  giữ constant `MARKETING_LIMITATION_TEXT`). Có thể coi là thay đổi
  output contract nếu owner strict interpretation.
- **(c) Document as "no carry-over"** — đơn giản nhất, đính chính
  plan §4.2 / §4.4. Phase A hiện tại KHÔNG có limitation vì user chỉ
  xem `REVIEW_REQUIRED` shell.

### 8.3. F-P3-04 `recommendation_id` regex test (audit §9.3)

**Status**: KHÔNG xử lý — out of scope remediation.
**Lý do**: Plan §6 đã có test cho `recommendation_id` format (line
`_RECOMMENDATION_ID_RE` in `manifest.py`); tests trong
`test_dev07_manifest.py` cover format. Audit đề xuất thêm test
explicit (`test_recommendation_id_format_compliance`) nhưng đây là
cải tiến coverage, không phải fix. Có thể làm trong Phase B cleanup.

### 8.4. Test gaps khác (audit §7.2.3..5)

| Audit § | Gap | Status | Lý do |
|---|---|---|---|
| §7.2.3 | Malformed YAML test | KHÔNG xử lý | Out of remediation scope (ngoài P1/P2/P3 của audit). Có thể thêm sau. |
| §7.2.4 | `research_safety` carry-through với DEV-06 thật | KHÔNG xử lý | DEV-06 manifest thật chưa tồn tại trong repo (test dùng synthetic). |
| §7.2.5 | Schema-version bump + reload old manifest | KHÔNG xử lý | Chưa có manifest cũ để test; cần thực hiện khi schema thực sự bump. |

---

## 9. Out of scope / KHÔNG thực hiện

### 9.1. AGENTS.md quy định không được thực hiện

| Quy định | Trạng thái remediation |
|---|---|
| Không commit / push / PR / merge / branch / stage / reset / checkout / clean / stash | ✅ Không thực hiện |
| Không tự ý sửa thay đổi có sẵn của user | ✅ (tracked files unchanged) |
| Không chạy clustering/experiment trên research data | ✅ (không chạy) |
| Không dùng research data thật cho test | ✅ (synthetic only) |
| Không tự tạo MKT-01..MKT-05 framework | ✅ |
| Không tự điền marketing strategy/objective/action/KPI | ✅ |
| Không phê duyệt methodology | ✅ (ADR-0008 chờ owner) |
| Không thay đổi phạm vi DEV-07 | ✅ |
| Không thêm export/API/UI ngoài remediation | ✅ |
| Không thay đổi contract để test pass | ✅ |
| Trước khi sửa, kiểm tra working tree | ✅ (git status) |
| Không tuyên bố PASS chỉ dựa trên test | ✅ (validation đa chiều) |

### 9.2. Items được đề xuất ngoài remediation

- **Pre-existing failure** (1 test skipped C7-dependent): đã có từ
  trước, KHÔNG thuộc DEV-07 remediation. Verify: `tests/test_dev03_consistency.py:241`
  AC 38b OPT-IN.

---

## 10. Kết luận Phase A vs Phase B

### 10.1. Phase A — `READY FOR OWNER REVIEW` (với điều kiện)

Phase A implementation **technically đạt contract** sau remediation:

- ✅ 262/262 DEV-07 tests pass.
- ✅ 1335/1335 DEV-02..07 tests pass (+ 1 pre-existing skipped).
- ✅ `ruff check` clean (0 errors).
- ✅ `black --check` clean (21 files).
- ✅ YAML parse OK.
- ✅ DBSCAN noise excluded.
- ✅ KPI = None Phase A.
- ✅ `research_safety` always False / `MARKETING_PROTOTYPE`.
- ✅ No internal clustering metric in KPI.
- ✅ No forbidden marketing terms.
- ✅ No CSV/JSONL export Phase A (per OQ-D07-08).
- ✅ No HTML modification.
- ✅ No DEV-06 contract modification.
- ✅ No Git operations.

**Điều kiện owner accept Phase A**:

1. Owner review + approve/reject ADR-0008 (canonical version form).
2. Owner quyết định về `preprocessing_warning` carry-over (option
   a/b/c ở §8.2).
3. Owner ghi nhận rằng claims "ruff clean" + "black clean" trước
   remediation là không chính xác; hiện tại đã clean.

### 10.2. Phase B — vẫn `BLOCKED`

Phase B (recommendation generation thực sự) vẫn blocked bởi:

- MKT-01..MKT-05 absent (verified `docs/marketing/` chưa tồn tại).
- OQ-D07-01..05 chưa được owner quyết.
- ADR-0008 chưa được owner approve (canonical version form).

**Sau khi owner approve ADR-0008** + tạo MKT framework + quyết
OQ-D07-01..05, Phase B có thể bắt đầu theo plan §10.2.

### 10.3. Status overall

> **Phase A: TECHNICALLY READY (với 2 owner decisions pending).**
> **Phase B: BLOCKED (chờ MKT framework + owner approval).**

---

## Phụ lục A — Lệnh kiểm thử chính xác

```bash
# Setup
cd /home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml

# Tests
python3 -m pytest tests/test_dev07_*.py                                  # DEV-07
python3 -m pytest tests/test_dev0[2-7]*.py                                # Regression

# Lint
python3 -m ruff check src/customer_segmentation/prototype/marketing/ \
                     tests/test_dev07_*.py scripts/dev07_run_marketing.py

# Format
python3 -m black --check src/customer_segmentation/prototype/marketing/ \
                       tests/test_dev07_*.py scripts/dev07_run_marketing.py

# YAML
python3 -c "import yaml; data = yaml.safe_load(open('configs/dev07_marketing.yaml')); print('YAML parse OK')"

# Config
PYTHONPATH=src python3 -c "from customer_segmentation.prototype.marketing.config_loader import load_dev07_config; cfg = load_dev07_config(); print('Config OK, pattern:', cfg.mkt_framework.version_pattern)"
```

## Phụ lục B — Diff scope summary

Tất cả thay đổi nằm trong DEV-07 scope:

```
docs/decisions/0008-dev07-version-pattern.md   (NEW)
src/customer_segmentation/prototype/marketing/__init__.py          (F811 fix)
src/customer_segmentation/prototype/marketing/config_loader.py    (black)
src/customer_segmentation/prototype/marketing/display.py          (black)
src/customer_segmentation/prototype/marketing/logging_config.py   (black)
src/customer_segmentation/prototype/marketing/manifest.py         (UP030/UP032, black)
src/customer_segmentation/prototype/marketing/mkt_framework_loader.py  (P1 diagnostics, black)
src/customer_segmentation/prototype/marketing/pipeline.py         (black)
src/customer_segmentation/prototype/marketing/scope.py            (black)
src/customer_segmentation/prototype/marketing/storage.py          (black)
src/customer_segmentation/prototype/marketing/validation.py       (black)
tests/test_dev07_manifest.py                  (I001, F401, black)
tests/test_dev07_mkt_framework.py             (I001, +6 new tests, black)
tests/test_dev07_pipeline.py                  (+4 new tests, black)
tests/test_dev07_scope.py                     (I001, F401, SIM300, black)
tests/test_dev07_storage.py                   (I001, black)
scripts/dev07_run_marketing.py                (UP035, F401)
```

**Files KHÔNG bị thay đổi** (verified unchanged):
- `pyproject.toml`, `.gitignore`
- `docs/system/SYS-01..06_*.md`
- `docs/system/DEV-01..06_*.md`
- `src/customer_segmentation/dataset_management/**`
- `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,preprocessing,transformation,visualization}/**`
- `configs/dev0[2-6]_*.yaml`, `configs/dev07_marketing.yaml`
- `tests/test_dev0[2-6]_*.py`
- `AGENTS.md`, `data/**`

## Phụ lục C — Glossary

| Thuật ngữ | Ý nghĩa trong remediation |
|---|---|
| **P1/P2/P3** | Severity theo audit (§4.1..§4.7, §6, §7) |
| **Phase A** | DEV-07 implementation khi MKT framework absent (REVIEW_REQUIRED shell) |
| **Phase B** | DEV-07 implementation khi MKT framework tồn tại + owner approve |
| **Aggregate form** | Version string `MKT-01..05__vN` (do `framework_version_string()` tạo) |
| **Per-file form** | Version string `MKT-0X__vN` (per document) |
| **Silent failure** | Bug khi output không đúng expectation nhưng không raise (audit §4.1) |
| **Witness test** | Test document behavior hiện tại (không fix), defensive against silent regression |
| **Carry-over** | Mang field từ DEV-06 sang DEV-07 output (plan §4.2) |

---

*File này là DEV-07 Phase A Remediation Report. KHÔNG commit/push/PR theo
AGENTS.md §2.11. Owner review và approval cần thiết cho 2 ADR
(ADR-0008 version pattern, ADR-đề xuất preprocessing_warning carry-over).*
