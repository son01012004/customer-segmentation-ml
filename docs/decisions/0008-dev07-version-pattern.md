# 0008 — DEV-07 MKT framework version pattern (canonical form)

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, regex pattern, status enum, command, file
> path, ADR ID, task ID, EPIC ID theo convention hiện có.

- **Status**: Accepted
- **Date**: 2026-10-10
- **Deciders**: Owner (decision được ghi trong
  `docs/system/DEV-07_owner_decision_brief.md` §6.1 + §6.2 và
  `docs/system/DEV-07_owner_decision_matrix.md` §4; brief + matrix
  xác nhận Phase A acceptance gate đã giải quyết)
- **Task ID**: DEV-07 (Phase A acceptance gate)
- **Supersedes**: n/a
- **Audit source**: `docs/system/DEV-07_phase_a_audit_report.md` §4.1,
  §4.2, §5
- **Phạm vi áp dụng**: `configs/dev07_marketing.yaml`,
  `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py`,
  `tests/test_dev07_*.py`.

---

## 1. Context

`src/customer_segmentation/prototype/marketing/mkt_framework_loader.py`
chứa hai khái niệm về version string:

1. **Per-file version** — version của từng tài liệu MKT-NN đơn lẻ,
   extract từ tên file (vd: `MKT-01__v1.md` → version `v1`).
2. **Aggregate framework version** — version tổng hợp của cả framework,
   format `MKT-01..05__vN` (do `framework_version_string()` sinh ra).

Công thức trong loader (`mkt_framework_loader.py:154-156`):

```python
version = m.group(1)                              # "v1"
if not pattern.match(f"MKT-01..05__{version}"):   # "MKT-01..05__v1"
    return None
return version
```

Tức là loader **luôn** construct aggregate form `MKT-01..05__vN` rồi
match với `config.mkt_framework.version_pattern`. Vậy pattern trong
config **phải** match aggregate form `MKT-01..05__v\d+(?:\.\d+)*$` để
loader chấp nhận framework.

Trước owner quyết định, có 3 pattern forms khác nhau trong codebase:

| Nguồn | Pattern | Loại |
|---|---|---|
| `configs/dev07_marketing.yaml` (line 78) | `^MKT-0[1-5]__v[0-9]+$` | **Per-file** (match `MKT-01__v1`) |
| `mkt_framework_loader.py::framework_version_string()` | `f"MKT-01..05__{ref.version}"` | **Aggregate** |
| `tests/test_dev07_mkt_framework.py::_make_config()` | `r"^MKT-01\.\.05__v\d+(?:\.\d+)*$"` | **Aggregate** |
| `tests/test_dev07_validation.py::_make_full_config()` | `r"^MKT-0[1-5]__v[0-9]+$"` | **Per-file** |
| `tests/test_dev07_pipeline.py::_make_minimal_yaml()` (inline) | `"^MKT-01..05__v[0-9]+$"` | **Aggregate** (unescaped) |

→ Phase A hiện tại may mắn pass vì MKT-01..MKT-05 files **chưa tồn tại**
trong repo (`docs/marketing/` absent). Loader return `None` vì
directory missing, không phải vì pattern mismatch. Tuy nhiên, đây là
silent-failure tiềm ẩn cho Phase B.

## 2. Decision

**Option A được owner chấp thuận** — canonical version form là aggregate
form `MKT-01..05__vN` (với `N` là số phiên bản hợp lệ).

Cụ thể:

1. **`configs/dev07_marketing.yaml::mkt_framework.version_pattern`** được
   đổi sang aggregate pattern (escaped):
   ```yaml
   version_pattern: "^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$"
   ```
2. **Loader production code KHÔNG** thay đổi (`_extract_version`,
   `framework_version_string` giữ nguyên logic và output).
3. **`marketing_id` derivation **không đổi** — `mkt_framework_version`
   tiếp tục mang aggregate form `MKT-01..05__vN` trong canonical
   payload (đã được `storage.py:39` document cho Phase B).
4. **`MARKETING_MANIFEST_SCHEMA_VERSION` giữ `1.0.0`** — không bump
   (vì aggregate form đã là canonical từ đầu; chỉ config thay đổi).
5. **Test helpers** trong `test_dev07_validation.py`,
   `test_dev07_recommendation.py`, `test_dev07_pipeline.py`
   (`_make_minimal_yaml`) được đồng bộ sang aggregate pattern để
   khớp với default config.
6. **`TestDefaultConfigIntegration`** trong
   `test_dev07_mkt_framework.py` được điều chỉnh để:
   - Verify default config pattern đúng là aggregate form.
   - Verify default config + per-file MKT filenames
     (`MKT-01__v1.md ... MKT-05__v1.md`) → loader chấp nhận và
     return ref hợp lệ (vì aggregate pattern được tạo từ extracted
     per-file version vẫn match).
   - Verify warning diagnostic vẫn được emit khi pattern explicit
     mismatch (dùng override config để demonstrate).

### 2.1. Căn cứ quyết định

| Lý do | Chi tiết |
|---|---|
| **Loader production code không cần sửa** | `_extract_version` đã construct aggregate form. Chỉ cần config pattern khớp. Giảm surface area của code change. |
| **`marketing_id` derivation không đổi** | `storage.py:39` đã document `"null (Phase A) | "MKT-01..05__vN" (Phase B)"`. Option A canonicalize aggregate form đã có. |
| **Plan §5.7 + §8.3 đã descriptive aggregate** | `marketing_id = "mkt_" + SHA-256(..., "MKT-01..05__vN", ...)` đã được plan §8.3 viết rõ literal. |
| **Diagnostic đã đúng** | WARNING log ở `mkt_framework_loader.py` đã emit constructed aggregate form `MKT-01..05__vN` khi mismatch. |
| **Backward compatibility** | Aggregate form đã là canonical trong `framework_version_string()` + plan; chỉ config + test helpers thay đổi. |
| **Đồng bộ MKT framework version** | MKT-01..MKT-05 phải có cùng version `vN` trong cùng một framework pass (đồng bộ `version_pattern`). |

### 2.2. Định nghĩa "aggregate form" hợp lệ

Pattern canonical regex (escaped trong YAML):

```
^MKT-01\.\.05__v\d+(?:\.\d+)*$
```

- `MKT-01..05__` — prefix cố định, ký tự `..` là literal (range
  shorthand cho MKT-01..MKT-05).
- `v` — literal `v`.
- `\d+` — major version (1 hoặc nhiều chữ số).
- `(?:\.\d+)*` — optional minor.patch (zero hoặc nhiều lần lặp).
- `$` — end-of-string anchor.

Ví dụ hợp lệ: `MKT-01..05__v1`, `MKT-01..05__v1.0`, `MKT-01..05__v2.5.3`.

Ví dụ KHÔNG hợp lệ: `MKT-01__v1` (per-file shape — không match),
`MKT-01..05__v1.x` (chữ ở vị trí digit), `MKT-01..05__1` (thiếu prefix
`v`).

### 2.3. Forward-looking ràng buộc

- MKT-01..MKT-05 file filenames trong `docs/marketing/` phải theo
  convention `MKT-NN__vN.md` (per-file naming); loader sẽ construct
  aggregate form và match default pattern. Pattern này KHÔNG cấm
  per-file filenames — chỉ yêu cầu **đồng bộ version** giữa 5 file.
- Nếu owner convention thay đổi sang aggregate filename
  (`MKT-01..05__vN.md`), cần sửa `_MKT_FILE_RE` trong
  `mkt_framework_loader.py` (hiện chỉ match `MKT-<digit>` regex). ADR
  mới sẽ cần nếu thay đổi naming convention.

## 3. Consequences

### 3.1. Easier

- Loader production code không cần sửa — giảm surface area.
- `marketing_id` derivation giữ aggregate form → backward compatible
  với plan §8.3.
- Diagnostic WARNING log (`mkt_framework_loader.py:114-128`) đã đúng
  semantics; chỉ cần config thay đổi.
- Test coverage ở `TestDefaultConfigIntegration` đã sẵn sàng verify
  end-to-end behavior với default config.

### 3.2. Harder hoặc riskier

- **Forward constraint**: MKT-01..MKT-05 phải có cùng version `vN`
  trong cùng một framework pass. Nếu owner muốn per-file version
  linh hoạt (vd: `MKT-01__v1.md` + `MKT-02__v2.md`), cần Option B
  (ADR mới) và bump schema.
- **Filename convention**: docs/marketing/ filenames vẫn per-file
  (`MKT-NN__vN.md`). Loader regex `_MKT_FILE_RE` chỉ match
  `MKT-<digit>` prefix. Nếu đổi sang aggregate filename, cần sửa
  loader.
- **No silent change**: Phase A hiện tại đã pass tests vì MKT absent.
  Option A chính thức hóa form đã có; không có silent change.

## 4. Alternatives considered

### 4.1. Option B — Canonical per-file form `MKT-0X__vN`

- **Sửa loader `_extract_version`** (bỏ aggregate form check).
- **`framework_version_string`** chọn 1 trong 2:
  - **B.1**: Trả về canonical aggregate `MKT-01..05__vN` (giữ format
    hiện tại; pattern chỉ validate per-file version string).
  - **B.2**: Trả về per-file version ngắn gọn `vN` (đơn giản hóa).
- **Bump schema** 1.0.0 → 1.1.0 nếu B.2 (vì `marketing_id` derivation
  dùng field này; cache lookup sẽ miss với manifest cũ).

**Bị reject** vì (a) sửa loader production code tăng surface area, (b)
`marketing_id` backward compat risk với B.2, (c) plan §5.7 + §8.3 đã
descriptive aggregate.

### 4.2. Option C — Defer đến Phase B

- Đợi MKT-01..MKT-05 tồn tại rồi mới quyết pattern.

**Bị reject** vì (a) silent-failure tiềm ẩn khi MKT files được tạo
với per-file naming, (b) Phase A implementation có thể lock in pattern
sai trong test fixtures.

## 5. Affected files

| File | Change |
|---|---|
| `configs/dev07_marketing.yaml` | Update `mkt_framework.version_pattern` sang aggregate form (escaped). |
| `tests/test_dev07_mkt_framework.py` | Update `TestDefaultConfigIntegration` tests cho default mới. |
| `tests/test_dev07_validation.py` | Update `_make_full_config` để dùng aggregate pattern. |
| `tests/test_dev07_recommendation.py` | Update `_make_full_config` để dùng aggregate pattern. |
| `tests/test_dev07_pipeline.py` | Update `_make_minimal_yaml` để dùng aggregate pattern. |
| `docs/system/DEV-07_owner_decision_brief.md` | Record decision trong §5, §6. |
| `docs/system/DEV-07_owner_decision_matrix.md` | Record decision trong §4. |
| `docs/system/DEV-07_final_acceptance_report.md` | Document Phase A acceptance với Option A. |

**Files KHÔNG bị thay đổi** (verified unchanged):

- `pyproject.toml`, `.gitignore`
- `docs/system/SYS-01..06_*.md`, `docs/system/DEV-01..06_*.md`
- `src/customer_segmentation/dataset_management/**`
- `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,preprocessing,transformation,visualization}/**`
- `configs/dev0[2-6]_*.yaml`
- `tests/test_dev0[2-6]_*.py`
- `AGENTS.md`, `data/**`
- `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py`
  (giữ nguyên logic; chỉ aggregate form output đã đúng canonical).

## 6. References

- `docs/system/DEV-07_phase_a_audit_report.md` §4.1, §4.2, §5 — P1
  finding & analysis.
- `docs/system/DEV-07_remediation_report.md` §5 — P1 diagnostics
  improvements.
- `docs/system/DEV-07_owner_decision_brief.md` §2, §4.1, §6.1 — A/B
  comparison + recommended default.
- `docs/system/DEV-07_owner_decision_matrix.md` §3, §4 — Phase A
  decision matrix.
- `docs/system/DEV-07_implementation_plan.md` §5.7, §8.3 — descriptive
  aggregate form usage.
- `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py`
  lines 144-162 — `_extract_version` + `framework_version_string`.
- `src/customer_segmentation/prototype/marketing/storage.py:39` —
  canonical payload key `mkt_framework_version` definition.
- `AGENTS.md` §2.1, §2.5, §2.9, §2.10 — research integrity, decision
  language, no silent policy changes, human approval gate.
- `docs/decisions/README.md` — ADR template + immutability convention.

---

*File này là ADR đã được owner chấp thuận (Status: Accepted). Theo
`docs/decisions/README.md` immutability convention, ADR này không bị edit
sau khi accepted. Nếu cần thay đổi canonical form, tạo ADR mới
superseding ADR-0008.*
