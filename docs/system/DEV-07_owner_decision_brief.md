# DEV-07 — Owner Decision Brief (Phase A → Phase B)

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module
> **Ngày:** 2026-10-10
> **Trạng thái:** **DECISIONS RECORDED (2026-10-10) — chờ Phase A acceptance gate sign-off**.
>
> **Quyết định đã được ghi nhận**:
> - ADR-0008: **Accepted — Option A (canonical aggregate form `MKT-01..05__vN`)**.
>   Config `mkt_framework.version_pattern` đã được cập nhật
>   trong `configs/dev07_marketing.yaml`. Loader production code
>   giữ nguyên.
> - `preprocessing_warning` carry-over: **Option (c) — KHÔNG carry forward
>   trong Phase A**. Đây là quyết định có chủ đích (intentional).
>   Schema E-MKT giữ nguyên; contract DEV-06 không sửa.
>
> **Phạm vi brief:**
>   1. Tổng hợp 2 quyết định **ADR-0008 (canonical version form)**.
>   2. Đối chiếu "carry forward" của `preprocessing_warning` với E-MKT
>      schema + implementation.
>   3. Đề xuất các phương án cho `preprocessing_warning` carry-over
>      (không tự chọn).
>   4. Khuyến nghị kỹ thuật riêng cho từng quyết định + căn cứ.
>   5. Liệt kê owner decisions còn chờ (OQ-D07-01..08 + ADR-0008).
>
> **Không thuộc brief này:** implementation code, config edit, contract
> edit, ADR edit, Git operations, source modification.

---

## Mục lục

1. [Tóm tắt executive](#1-tóm-tắt-executive)
2. [ADR-0008 — Canonical version pattern](#2-adr-0008--canonical-version-pattern)
3. [`preprocessing_warning` carry-over](#3-preprocessing_warning-carry-over)
4. [Khuyến nghị kỹ thuật](#4-khuyến-nghị-kỹ-thuật)
5. [Owner decisions còn chờ](#5-owner-decisions-còn-chờ)
6. [Bảng chọn nhanh cho owner](#6-bảng-chọn-nhanh-cho-owner)

---

## 1. Tóm tắt executive

**Trạng thái hiện tại của DEV-07 Phase A:**

- 262/262 DEV-07 tests pass; 1335/1335 DEV-02..07 pass (+ 1 pre-existing skipped).
- Ruff clean, Black clean (21 files).
- YAML parse OK.
- Diagnostics cải thiện trong `mkt_framework_loader.py` (WARNING log khi
  pattern mismatch, audit §4.1 silent-failure prevention); production
  semantics giữ nguyên.
- 10 tests mới (6 default-config integration + 4 `preprocessing_warning`
  witness).
- Methodology gates honored (DBSCAN noise excluded, KPI=None, no
  internal clustering metric, no forbidden marketing terms, no commit / push).
- `MarketingRecommendationManifest` KHÔNG chứa field `preprocessing_warning`
  (verified); schema version `1.0.0` đã freeze.

**2 owner decisions pending** (block Phase A accept + Phase B start):

| # | Quyết định | Status | Tài liệu nguồn |
|---|---|---|---|
| 1 | **ADR-0008** — canonical version pattern (Option A vs B) | `PROPOSED — OWNER DECISION REQUIRED` | `docs/decisions/0008-dev07-version-pattern.md` |
| 2 | **`preprocessing_warning` carry-over** mechanism | Documented gap, no production change | `docs/system/DEV-07_remediation_report.md` §8.2 + brief này §3 |

**OQ-D07-01..08** vẫn `REVIEW_REQUIRED` (xem `DEV-07_owner_decision_matrix.md`).
Brief này **không** thay thế decision matrix đó; nó bổ sung phân tích
sâu cho 2 quyết định ở trên.

---

## 2. ADR-0008 — Canonical version pattern

### 2.1. Context (verified từ source code)

**Trạng thái 3 pattern forms** (đã verify bằng `Grep` toàn repo):

| # | Nguồn | Pattern | Loại |
|---|---|---|---|
| 1 | `configs/dev07_marketing.yaml:78` | `^MKT-0[1-5]__v[0-9]+$` | **Per-file** (match `MKT-01__v1`) |
| 2 | `mkt_framework_loader.py::framework_version_string()` (line 162) | `f"MKT-01..05__{ref.version}"` | **Aggregate** (match `MKT-01..05__v1`) |
| 3 | `test_dev07_mkt_framework.py::_make_config()` (line 28) | `r"^MKT-01\.\.05__v\d+(?:\.\d+)*$"` | **Aggregate** (escape) |
| 4 | `test_dev07_validation.py::_make_full_config()` (line 99) | `r"^MKT-0[1-5]__v[0-9]+$"` | **Per-file** (inherited từ config) |
| 5 | `test_dev07_pipeline.py::_make_minimal_yaml()` (inline YAML) | `"^MKT-01..05__v[0-9]+$"` | **Aggregate** (literal, unescaped) |

**Loader runtime logic** (verified tại `mkt_framework_loader.py:144-158`):

```python
def _extract_version(path: Path, pattern: re.Pattern[str]) -> str | None:
    stem = path.stem  # e.g. "MKT-01__v1"
    m = re.search(r"__?(v\d+(?:\.\d+)*)$", stem)
    if m is None:
        return None
    version = m.group(1)  # "v1"
    # Reject if the entire constructed version string would not match
    # the configured pattern.
    if not pattern.match(f"MKT-01..05__{version}"):  # "MKT-01..05__v1"
        return None
    return version
```

→ Loader **luôn construct aggregate form** `MKT-01..05__vN` rồi match
với config pattern. Vậy config pattern **phải** match aggregate form
`MKT-01..05__v\d+(?:\.\d+)*$` để loader chấp nhận framework.

**`marketing_id` derivation** (verified tại `storage.py:39`):

```python
CANONICAL_PAYLOAD_KEYS = (
    ...,
    "mkt_framework_version",   # null (Phase A) | "MKT-01..05__vN" (Phase B)
    "mkt_framework_found",       # bool
    ...,
)
```

→ `marketing_id` đã được derive với aggregate form `MKT-01..05__vN` (khi
Phase B populate field); Nếu pattern đổi từ aggregate → per-file,
`marketing_id` cũ (nếu có) sẽ khác → cache lookup miss.

### 2.2. Bảng so sánh Option A vs Option B

| Tiêu chí | **Option A — Canonical aggregate form `MKT-01..05__vN`** | **Option B — Canonical per-file form `MKT-0X__vN`** |
|---|---|---|
| **Ý nghĩa version** | Version của toàn bộ framework (aggregate từ 5 docs). | Version của từng file MKT-NN độc lập. |
| **Ví dụ hợp lệ** | `MKT-01..05__v1`, `MKT-01..05__v1.2` | `MKT-01__v1`, `MKT-02__v1`, ... |
| **Files yêu cầu** | Tất cả 5 MKT-NN files phải có cùng version `vN` trong cùng framework pass (đồng bộ). | Mỗi file MKT-NN có thể có version độc lập (vd: `MKT-01__v1.md` + `MKT-02__v2.md`). |
| **Config sửa** | `configs/dev07_marketing.yaml::mkt_framework.version_pattern` → `^MKT-01\.\.05__v\d+(?:\.\d+)*$`. | KHÔNG sửa (giữ per-file `^MKT-0[1-5]__v[0-9]+$`). |
| **Loader production code** | **Giữ nguyên** `_extract_version` + `framework_version_string()`. KHÔNG sửa semantics. | **Sửa** `_extract_version` (bỏ aggregate check) + `framework_version_string` (B.1: giữ aggregate; B.2: đổi sang `vN` ngắn). |
| **Test helpers** | Sửa `test_dev07_validation.py::_make_full_config` (line 99) → aggregate. Sửa `test_dev07_pipeline.py::_make_minimal_yaml` (inline) → aggregate. Sửa `test_dev07_mkt_framework.py::_make_config` (line 28) → đọc từ `load_dev07_config()` thay vì override literal. | Sửa `test_dev07_pipeline.py::_make_minimal_yaml` → per-file. `test_dev07_mkt_framework.py::_make_config` (line 28) đã match aggregate → đổi sang per-file. `test_dev07_validation.py::_make_full_config` (line 99) đã match per-file → OK. |
| **`marketing_id` derivation** | `mkt_framework_version` giữ aggregate `MKT-01..05__vN` → `marketing_id` cũ (nếu có) ổn định. | **B.1**: aggregate giữ → `marketing_id` cũ ổn định. **B.2**: đổi sang `vN` → `marketing_id` cũ (nếu có) khác → cache miss. |
| **Plan §5.7 + §8.3 compatibility** | Khớp (plan đã dùng aggregate `MKT-01..05__vN` descriptive). | **B.1**: khớp. **B.2**: mâu thuẫn (plan §5.7 reference aggregate). |
| **Diagnostics hiện tại** | WARNING log đã đúng cho aggregate mismatch. | Cần re-think diagnostics nếu đổi. |
| **Rủi ro tương thích (backward)** | **Không**: aggregate form đã là canonical trong `framework_version_string()` + plan; chỉ config + test helpers thay đổi. | **B.1**: thấp (giữ aggregate cho `marketing_id`). **B.2**: cao (`marketing_id` derivation thay đổi; cache lookup miss; cần bump `MARKETING_MANIFEST_SCHEMA_VERSION` 1.0.0 → 1.1.0). |
| **Rủi ro tương thích (forward)** | Cấm per-file filename (vd: `MKT-01__v1.md` không khớp aggregate); phải dùng aggregate filename. | Cho phép per-file filename linh hoạt; rủi ro thấp về naming. |
| **Rủi ro silent failure** | N/A — Phase A may mắn pass vì framework absent. Khi MKT files tồn tại với per-file naming + Option A config → silent failure. | N/A — silent failure nếu aggregate form bị reject. |
| **Số files cần sửa** | 1 config + 3 test files (helpers). | 1 loader file + 1 test file (helpers); nếu B.2 thêm 1 schema bump. |

### 2.3. Quan hệ với marketing_id (tác động cụ thể)

**Verified**: `marketing_id = "mkt_" + SHA-256(JSON canonical(9 fields))[:24]`,
trong đó field thứ 6 là `mkt_framework_version` (per
`storage.py:39`, `storage.py:92`, `storage.py:201`, `storage.py:236`).

- **Phase A hiện tại**: `mkt_framework_version = None` (vì `framework_version_string()`
  không được gọi; `load_mkt_framework` returns `None`). → `marketing_id`
  ổn định qua Phase A bất kể Option A hay B.

- **Phase B (MKT-01..05 tồn tại)**:
  - Option A: `mkt_framework_version = "MKT-01..05__vN"` (aggregate) →
    nếu config pattern là aggregate, loader accept → `marketing_id`
    consistent với plan §8.3.
  - Option B.1: `mkt_framework_version` giữ aggregate `"MKT-01..05__vN"`
    nhưng config pattern là per-file → loader phải đổi `_extract_version`
    để skip aggregate check (per-file check vẫn work nếu filenames per-file).
  - Option B.2: `mkt_framework_version = "vN"` (per-file ngắn) →
    `marketing_id` derivation khác → cache miss nếu đã có manifest
    Phase B với aggregate form.

### 2.4. Rủi ro tương thích tổng hợp

| Risk ID | Mô tả | Probability | Impact | Mitigation |
|---|---|---|---|---|
| **CR-A-1** | Option A: Nếu owner tạo MKT files với per-file naming (`MKT-01__v1.md`), loader sẽ trả `None` silent (chỉ WARNING). | Medium (owner convention dễ theo config pattern hiện tại). | Medium | Diagnostics đã log WARNING rõ. Owner biết phải dùng aggregate filename. |
| **CR-A-2** | Option A: Plan §5.7 + §8.3 reference aggregate → đồng bộ. | Low. | Low | Plan đã đúng. |
| **CR-B-1** | Option B: Sửa loader production code → risk regression Phase A contract (`load_mkt_framework returns None`). | Low (có tests cover). | Medium | Tests cover Phase A contract; regression suite fail-fast. |
| **CR-B-2** | Option B.2: `marketing_id` derivation đổi → cache lookup miss nếu có manifest Phase B cũ. | Low (chưa có manifest Phase B trong repo). | Medium | Bump `MARKETING_MANIFEST_SCHEMA_VERSION` (1.0.0 → 1.1.0); schema invalidation đã design cho việc này (per `storage.py:27` comment "Bumping the schema version invalidates all previous marketing_ids"). |
| **CR-B-3** | Option B: Mâu thuẫn với plan §5.7 + §8.3 nếu B.2. | Medium. | Low | Plan đính chính nếu owner chọn B.2. |

---

## 3. `preprocessing_warning` carry-over

### 3.1. "Carry forward" references trong plan

| Vị trí | Trích nguyên văn | Cơ chế carry-over |
|---|---|---|
| **Plan §4.2** (line 204) | `preprocessing_warning \| Post-preprocessing disclaimer (mandatory field) — DEV-07 phải carry forward.` | KHÔNG chỉ rõ mechanism; chỉ ghi DEV-07 "phải" carry forward. |
| **Plan §4.4** (line 224) | `preprocessing_warning được mang theo output của DEV-07 (carry forward).` | KHÔNG chỉ rõ mechanism. |
| **Plan §4.4** (line 320-321) | `KHÔNG raw "post-preprocessing" values khi present cho user — carry forward preprocessing_warning từ DEV-06.` | Text-level reference, không carry forward field. |
| **Plan §5.4** (line 319-321) | (cùng nội dung §4.4) | Text-level reference. |
| **AC-D07-10** (line 788) | `preprocessing_warning được carry-forward từ DEV-06 manifest vào DEV-07 display.` | KHÔNG chỉ rõ mechanism; chỉ nói "DEV-07 display". |
| **CP-05 §10.4** carry-over | n/a (CP-05 plan reference) | CP-05 §10.4 cấm "business recommendation claim". |

**Nhận xét**: Plan nói "carry forward" ở 5 chỗ nhưng KHÔNG có chỗ nào
chỉ rõ:

- (a) Carry forward là gì — text-level (string) vào field nào?
- (b) Hay field-level (thêm field mới `preprocessing_warning` vào E-MKT)?
- (c) Hay chỉ là "nguyên tắc" để tránh raw values; implementation không
  carry forward gì cả?

### 3.2. Đối chiếu với E-MKT schema và implementation hiện tại

**E-MKT schema** (verified tại `SYS-03 §15.1` + `MarketingRecommendationEntry`
dataclass trong `manifest.py`):

| Field trong SYS-03 §15.1 | Có trong DEV-07 v1.0.0? |
|---|---|
| `recommendation_id`, `segment_id`, `availability` | ✅ |
| `marketing_objective`, `strategy`, `recommended_action` | ✅ |
| `kpi`, `evidence_ref`, `limitation` | ✅ |
| `source_framework_version`, `computed_at_utc`, `notes` | ✅ |
| **`preprocessing_warning`** | ❌ **KHÔNG CÓ** |

**DEV-06 `SegmentationManifest`** (verified tại
`src/customer_segmentation/prototype/segmentation/manifest.py:460`):

```python
preprocessing_warning: str = ""
```

→ Mandatory field, default empty string.

**Implementation hiện tại của DEV-07** (verified tại
`src/customer_segmentation/prototype/marketing/pipeline.py:414`):

```python
limitation=MARKETING_LIMITATION_TEXT,
```

→ Pipeline **KHÔNG đọc** `preprocessing_warning` từ DEV-06 manifest. `limitation`
và `limitation_note` lấy giá trị từ constant `MARKETING_LIMITATION_TEXT`
(verified tại `scope.py:231-235`):

```python
MARKETING_LIMITATION_TEXT: Final[str] = (
    "Marketing framework (MKT-01..MKT-05) not implemented in this "
    "prototype scope. Recommendation is descriptive only; do not "
    "interpret as a business action."
)
```

→ Đây là **constant text**, không phải `preprocessing_warning` từ DEV-06.

**`build_recommendation_entry_review_required`** trong `manifest.py:399-420` cũng dùng `MARKETING_LIMITATION_TEXT` cho `limitation` và `limitation_note` default.

**Kết luận đối chiếu**:

- DEV-07 v1.0.0 schema **không** có field `preprocessing_warning`.
- DEV-07 pipeline **không** đọc `preprocessing_warning` từ DEV-06 manifest.
- Plan §4.2 + §4.4 + AC-D07-10 nói "carry forward" nhưng cơ chế **không
  được define** trong plan.
- Plan đã liệt kê field này trong §4.2 table "các trường DEV-06 cần
  cho DEV-07" — verify rằng plan đã nhận diện field này, nhưng
  implementation chưa carry.

### 3.3. Các lựa chọn cho `preprocessing_warning` (không tự chọn)

#### Option (a) — Thêm field `preprocessing_warning` vào E-MKT schema

- **Cơ chế**: Mở rộng `MarketingRecommendationEntry` (và
  `MarketingRecommendationManifest` top-level) để có field
  `preprocessing_warning: str | None`. Pipeline đọc từ DEV-06
  `SegmentationManifest.preprocessing_warning` rồi propagate.
- **Schema impact**: Bump `MARKETING_MANIFEST_SCHEMA_VERSION` 1.0.0 →
  1.1.0 (theo `storage.py:27` design "Bumping the schema version
  invalidates all previous marketing_ids"). `marketing_id` cũ
  invalid (cache miss OK vì Phase A chưa có manifest nào).
- **Tests impact**:
  - Sửa 4 witness tests trong `TestPreprocessingWarningCarryOver` để
    test carry-over thực (hiện đang witness "no propagation" — phải
    đổi thành "assert carry-over").
  - Thêm field mới → `manifest_to_dict` + `_dict_to_manifest` + JSON
    roundtrip cần update.
- **Ảnh hưởng schema**: **Lớn**. SYS-03 §15.1 cần update để list field
  mới; ADR mới (`0009-dev07-preprocessing-warning-propagation.md`) cần
  tạo theo convention immutability.
- **Ảnh hưởng runtime**: Thêm field vào `build_marketing_manifest`
  signature + `build_recommendation_entry_review_required` signature
  (hoặc default rỗng).
- **Ảnh hưởng provenance**: `marketing_id` thay đổi (schema bump) →
  mọi manifest cũ invalid. Provenance chain giữ nguyên (DEV-06
  `segmentation_manifest_sha256` vẫn là anchor).
- **Ảnh hưởng UI**: Phase A chỉ làm placeholder nên UI impact = 0
  trong Phase A (SYS-06 §9 S-13 đã đúng spec). Phase B nếu mở rộng
  UI có thể hiển thị warning riêng.
- **Backward compat**: KHÔNG có (vì bump schema); nhưng Phase A chưa
  có manifest nào nên không ảnh hưởng thực tế.
- **Rủi ro**: Cần SYS-03 update (vi phạm principle "FROZEN STATUS"
  của SYS-03 §3.2); cần ADR mới.

#### Option (b) — Concatenate `preprocessing_warning` vào `limitation_note`

- **Cơ chế**: `limitation_note` hiện giữ giá trị `MARKETING_LIMITATION_TEXT`
  constant (verified). Option này đổi logic: `limitation_note =
  MARKETING_LIMITATION_TEXT + "\n\nPreprocessing: " + dev06_preprocessing_warning`
  (chỉ khi `dev06_preprocessing_warning` không empty).
- **Schema impact**: KHÔNG (giữ schema v1.0.0). `limitation_note` vẫn
  là `str` mandatory.
- **Tests impact**:
  - Sửa 4 witness tests để assert concatenation logic.
  - Thêm test mới: empty DEV-06 warning → giữ constant default;
  non-empty DEV-06 warning → concat.
- **Ảnh hưởng runtime**: Sửa `build_recommendation_entry_review_required`
  signature (thêm param `preprocessing_warning: str = ""`) + pipeline
  đọc DEV-06 và pass vào.
- **Ảnh hưởng schema**: Không.
- **Ảnh hưởng provenance**: KHÔNG — `marketing_id` derivation không
  thay đổi vì `mkt_framework_version` và `noise_policy_used` giữ
  nguyên.
- **Ảnh hưởng UI**: Phase A không có UI thật → impact = 0.
- **Backward compat**: Có (cùng schema). Có thể coi là thay đổi output
  contract nếu owner strict interpretation (giá trị `limitation_note`
  cũ chỉ là constant `MARKETING_LIMITATION_TEXT`; giá trị mới có thêm
  DEV-06 warning).
- **Rủi ro**: Có thể bị coi là "silent policy change" về output
  contract; cần ADR mới.

#### Option (c) — Đính chính plan, không carry forward gì cả

- **Cơ chế**: Plan §4.2, §4.4, AC-D07-7 đã nói "carry forward" nhưng
  implementation thực tế không carry. Owner quyết định đây là **quyết
  định có chủ đích** (intentional): DEV-07 Phase A hiện tại chỉ làm
  REVIEW_REQUIRED shell, không có UI nào show `preprocessing_warning`,
  nên không cần carry. Khi Phase B mở rộng UI, carry-over sẽ được
  re-evaluate.
- **Schema impact**: KHÔNG.
- **Tests impact**: KHÔNG (4 witness tests đã đúng — documents "no
  propagation" hiện tại).
- **Ảnh hưởng runtime**: KHÔNG.
- **Ảnh hưởng schema**: Không.
- **Ảnh hưởng provenance**: Không.
- **Ảnh hưởng UI**: Phase A = 0 (placeholder).
- **Backward compat**: 100% (status quo).
- **Rủi ro**: Plan và implementation không khớp → cần đính chính plan.
  Phase B khi mở rộng UI sẽ cần giải quyết lại.

### 3.4. So sánh 3 options

| Tiêu chí | **(a) Field mới** | **(b) Concat vào `limitation_note`** | **(c) Đính chính plan** |
|---|---|---|---|
| Schema impact | Lớn (bump 1.0.0 → 1.1.0; SYS-03 update) | Nhỏ (giữ schema) | 0 |
| SYS-03 update | Có (vi phạm FROZEN STATUS) | Không | Không |
| ADR mới cần | Có (0009-dev07-preprocessing-warning-propagation) | Có (interpretation của guidance output contract change) | Không (chỉ đính chính plan) |
| Tests impact | Lớn (đổi 4 witness → assert carry; + field roundtrip) | Trung bình (đổi 4 witness → assert concat) | 0 (giữ witness) |
| `marketing_id` impact | Có (schema bump invalid cũ) | Không | Không |
| Runtime impact | Trung bình (pipeline đọc + propagate) | Trung bình (concat logic) | 0 |
| Phase A `marketing_manifest.json` output | Thêm field mới | Giá trị `limitation_note` khác | Không đổi |
| Phase B readiness | Tốt (carry đã sẵn) | Trung bình (Phase B có thể cần field riêng) | Kém (cần giải quyết lại) |
| Backward compat | Không (schema bump) | Có (cùng schema; có thể strict interpretation) | 100% (status quo) |
| Rủi ro | Lớn nhất (vi phạm SYS-03 FROZEN + ADR + schema) | Trung bình (output contract change có thể strict) | Thấp nhất (chỉ đính chính plan) |
| Effort | Cao | Trung bình | Thấp |

### 3.5. Vị trí hiện tại (Phase A đã shipped)

> **Verified**: Phase A hiện tại KHÔNG carry forward `preprocessing_warning`.
> Plan nói "carry forward" nhưng implementation không thực hiện. 4
> witness tests trong `TestPreprocessingWarningCarryOver` document gap
> này (xem `tests/test_dev07_pipeline.py`). Nếu owner chọn Option (a)
> hoặc (b), sẽ phải sửa witness tests và có thể tạo ADR mới.

---

## 4. Khuyến nghị kỹ thuật

### 4.1. ADR-0008 — Khuyến nghị: **Option A** (canonical aggregate)

**Căn cứ**:

1. **Loader production code không cần sửa** — `_extract_version` đã
   construct aggregate form; chỉ cần config pattern khớp. Giảm surface
   area của code change (Phase A remediation report §5.2 đã ghi
   "KHÔNG thay đổi production config/loader").
2. **`marketing_id` derivation không đổi** — `storage.py:39` đã ghi
   `"null (Phase A) | "MKT-01..05__vN" (Phase B)"`; Option A canonical
   hóa aggregate form đã có.
3. **Plan §5.7 + §8.3 đã descriptive aggregate** — `marketing_id =
   "mkt_" + SHA-256(..., "MKT-01..05__vN", ...)` đã được plan §8.3 viết
   rõ literal.
4. **Diagnostic đã đúng** — WARNING log ở `mkt_framework_loader.py:140-150`
   đã emit constructed aggregate form `MKT-01..05__vN` khi mismatch →
   khi config chuyển sang aggregate pattern, diagnostic vẫn meaningful.
5. **Test coverage đã có witness cho Option A** — 4 test mới trong
   `TestDefaultConfigIntegration` (audit §7.2.1 + remediation §5.3):
   - `test_default_config_with_per_file_mkt_pattern_no_match` — witness
     per-file mismatch (audit §4.1 silent failure prevention).
   - `test_default_config_with_aggregate_mkt_pattern_matches` — verify
     Option A end-to-end.
   - `test_default_config_warning_emitted_on_construct_mismatch` —
     WARNING diagnostic verification.

**Trade-off acknowledged**:

- Option A **cấm** per-file filename (`MKT-01__v1.md` không khớp
  aggregate pattern). Nếu owner convention là "mỗi MKT-NN là 1 document
  có version riêng" → Option B.1 hợp lý hơn.
- Đồng bộ: MKT-01..MKT-05 phải có cùng version `vN` trong cùng một
  framework pass.

### 4.2. `preprocessing_warning` — Khuyến nghị: **Option (c) đính chính plan** (status quo)

**Căn cứ**:

1. **Plan và implementation không khớp** — Plan nói "carry forward" ở 5
   chỗ (§4.2 line 205, §4.4 line 224, §4.4 line 320-321, §5.4 line 320,
   AC-D07-10 line 788) nhưng implementation không thực hiện (verified
   `pipeline.py:414` chỉ dùng `MARKETING_LIMITATION_TEXT` constant).
2. **Phase A hiện tại không có UI** — SYS-06 §9 S-13 chỉ là placeholder
   với badge REVIEW_REQUIRED; `preprocessing_warning` không có chỗ nào
   để hiển thị. Carry forward là moot ở Phase A.
3. **SYS-03 §15.1 E-MKT schema shell đã freeze** — verified trong
   `manifest.py`. Thêm field mới vi phạm "FROZEN STATUS" của SYS-03
   §3.2. Owner strict interpretation sẽ reject Option (a).
4. **`marketing_id` đã ổn định** — Phase A chưa có manifest nào;
   schema bump (Option a) sẽ invalid `marketing_id` derivation (low
   impact thực tế nhưng semantic cost cao).
6. **4 witness tests đã đúng** — `TestPreprocessingWarningCarryOver`
   trong `tests/test_dev07_pipeline.py` documents "no propagation" hiện
   tại (remediation §7.2). Witness tests pass + document gap = tốt cho
   Phase A; Phase B có thể re-evaluate carry với mục tiêu rõ hơn.
7. **Effort thấp nhất** — chỉ cần đính chính plan §4.2, §4.4, AC-D07-10
   để clarify "DEV-07 Phase A does not carry forward `preprocessing_warning`
   (intentional; Phase B re-evaluate khi UI mở rộng)".
8. **AGENTS.md §2.1 / §2.9** — "không tự ý thay đổi methodology" +
   "không silent policy changes". Option (c) đính chính plan = chính
   xác methodology trong plan, không thay đổi implementation, không
   silent. Đây là con đường tuân thủ AGENTS.md nhất.

**Trade-off acknowledged**:

- Phase B khi mở rộng UI sẽ cần quyết carry-over lại (vd: hiển thị
  warning ở S-13 expanded view). Carry có thể là Option (a) hoặc (b)
  tại thời điểm đó.
- Owner có thể chọn Option (a) hoặc (b) nếu muốn carry ngay từ Phase A
  (xem §3.4 để so sánh chi tiết).

### 4.3. Khuyến nghị chung cho 2 quyết định

| Quyết định | Khuyến nghị | Căn cứ chính |
|---|---|---|
| **ADR-0008 version pattern** | **Option A** (aggregate) | Khớp `framework_version_string()` + plan §8.3 + `marketing_id` derivation; không sửa loader production; diagnostics đã đúng. |
| **`preprocessing_warning`** | **Option (c)** (đính chính plan, status quo) | Phase A không có UI hiển thị warning; SYS-03 E-MKT đã freeze; AGENTS.md §2.1 cấm silent policy change; effort thấp nhất; witness tests đã đúng. |

---

## 5. Owner decisions còn chờ

### 5.1. Phase A accept gate (resolved 2026-10-10)

| OQ | Câu hỏi | Status | Decision recorded |
|---|---|---|---|
| **ADR-0008** | Canonical version pattern — Option A (aggregate) hay Option B (per-file)? | **RESOLVED — Option A accepted** (ADR-0008 status = `Accepted`) | Config `mkt_framework.version_pattern` updated to aggregate form `^MKT-01\.\.05__v\d+(?:\.\d+)*$`. Loader production code giữ nguyên. |
| **`preprocessing_warning`** | Carry-over mechanism — Option (a) field mới, Option (b) concat, hay Option (c) đính chính plan? | **RESOLVED — Option (c) accepted** (intentional no carry-forward Phase A) | Plan §4.2, §4.4, AC-D07-10 đính chính để document behavior. Witness tests `TestPreprocessingWarningCarryOver` (4 tests) giữ nguyên để xác nhận behavior hiện tại. |

### 5.2. Phase B inherit gate (block Phase B start)

| OQ | Câu hỏi | Source | Status |
|---|---|---|---|
| **OQ-D07-01** | MKT-01..MKT-05 scope có khớp SYS-01 §6.7 (6 fields: Objective, Strategy, Action, KPI, Evidence, Limitation)? | SYS-01 §6.7 FR-MKT-03; SYS-03 §15.1 OQ-DM-03 | `REVIEW_REQUIRED` (block Phase B start; Phase A không block) |
| **OQ-D07-02** | Phase A implement ngay (REVIEW_REQUIRED shell) hay đợi Phase B? | SYS-01 §2.8; SYS-04 §15.1 | `REVIEW_REQUIRED` (mentor / human researcher) |
| **OQ-D07-03** | CP-04 §4.1–§4.3 construction rules có phải canonical tokenization cho Phase B mapping? | CP-04 §4.1–§4.4; CF-D07-04 đính chính | `REVIEW_REQUIRED` |
| **OQ-D07-04** | KPI definitions MKT-04 dùng đơn vị nào — survey / transaction / composition? | SYS-01 §6.7 FR-MKT-05; CON-07 | `REVIEW_REQUIRED` (Phase B only; Phase A `kpi=None`) |
| **OQ-D07-05** | DEV-07 export format (CSV + JSONL hay khác)? | SYS-01 §6.8 FR-REPORT-01..03 | `REVIEW_REQUIRED` (Phase A đã chọn read-only theo OQ-D07-08; Phase B cần quyết lại) |

### 5.3. Phase A scope finalize gate (resolved 2026-10-10)

| OQ | Câu hỏi | Source | Status | Decision |
|---|---|---|---|---|
| **OQ-D07-02** | Phase A implement ngay hay đợi Phase B? | SYS-01 §2.8; SYS-04 §15.1 | **RESOLVED — Phase A implement ngay** (REVIEW_REQUIRED shell; MKT absent → low risk) | Phase A implementation tiếp tục. |
| **OQ-D07-06** | Phase A có mở rộng HTML `#/marketing` placeholder thêm per-segment table từ DEV-06 manifest? | SYS-06 §9 S-13 (đã đúng spec); index.html §1584–1613 | **RESOLVED — Giữ nguyên placeholder** (Phase A không cần UI mở rộng) | `index.html` giữ nguyên. |
| **OQ-D07-07** | Có tạo ADR mới `0007-dev07-prototype-scope.md` cho DEV-07 Phase A scope? | `docs/decisions/README.md` immutability convention | **RESOLVED — KHÔNG tạo ADR mới** (ADR-0005 đã cover prototype layer; ADR mới chỉ cần khi methodology conflicts) | ADR-0005 cover Phase A scope. |
| **OQ-D07-08** | Phase A export scope — read-only manifest hay CSV + JSONL? | SYS-01 §6.8 FR-REPORT-01..03; FR-MKT-04 | **RESOLVED — Read-only manifest** (Phase A không có recommendation thật; export giá trị `REVIEW_REQUIRED` shell không hữu ích) | Config `emit_recommendations_csv: false`, `emit_recommendations_jsonl: false` giữ nguyên. |

### 5.4. Owner chính (từ decision matrix Phase A §8.1)

Để **bắt đầu Phase A implementation** hoặc **accept Phase A hiện tại**,
owner cần:

1. ✅ **Approve / reject ADR-0008 (Option A vs B)** — **RESOLVED 2026-10-10: Option A accepted**.
2. ✅ **Approve / reject đề xuất cho `preprocessing_warning` carry-over (Option a / b / c)** — **RESOLVED 2026-10-10: Option (c) accepted (intentional no carry-forward)**.
3. ✅ **Confirm OQ-D07-02 (Phase A ngay hay đợi Phase B)** — **RESOLVED 2026-10-10: Phase A ngay**.
4. ✅ **Confirm OQ-D07-06 (HTML placeholder scope)** — **RESOLVED 2026-10-10: Giữ nguyên placeholder**.
5. ✅ **Confirm OQ-D07-07 (ADR mới hay không)** — **RESOLVED 2026-10-10: KHÔNG tạo ADR mới**.
6. ✅ **Confirm OQ-D07-08 (export scope)** — **RESOLVED 2026-10-10: Read-only manifest**.

**Lưu ý**: OQ-D07-01, OQ-D07-03, OQ-D07-04, OQ-D07-05 chỉ block **Phase B
implementation**, không block **Phase A accept** hiện tại. Chúng vẫn
`REVIEW_REQUIRED` và sẽ được giải quyết trong task Phase B riêng.

---

## 6. Bảng chọn nhanh cho owner

### 6.1. Bảng chọn cho 2 quyết định Phase A (đã chốt 2026-10-10)

| # | Quyết định | Phương án đã chọn | Mô tả ngắn |
|---|---|---|---|
| **1** | **ADR-0008** version pattern | ✅ **A** | Canonical `MKT-01..05__vN` (aggregate). Sửa config + test helpers. KHÔNG sửa loader. Config updated 2026-10-10; ADR-0008 status = `Accepted`. |
| **2** | `preprocessing_warning` carry-over | ✅ **(c)** | Đính chính plan; KHÔNG carry forward (status quo). Phase A không có UI để hiển thị warning. Plan §4.2, §4.4, AC-D07-10 updated 2026-10-10. |

### 6.2. Bảng chọn cho 6 owner decisions (Phase A accept gate)

| # | OQ | Câu hỏi ngắn | Phương án A | Phương án B | Khuyến nghị |
|---|---|---|---|---|---|
| **3** | OQ-D07-02 | Phase A implement ngay hay đợi Phase B? | **Phase A ngay** (REVIEW_REQUIRED shell; MKT absent → low risk) | Đợi MKT framework xong | ⭐ **Phase A ngay** |
| **4** | OQ-D07-06 | HTML `#/marketing` placeholder giữ nguyên hay mở rộng? | **Giữ nguyên** (SYS-06 §9 S-13 đã đúng spec) | Mở rộng thêm per-segment table | ⭐ **Giữ nguyên** |
| **5** | OQ-D07-07 | Tạo ADR mới `0007-dev07-prototype-scope.md`? | **KHÔNG tạo** (ADR-0005 đã cover prototype layer) | Tạo ADR mới | ⭐ **KHÔNG tạo** |
| **6** | OQ-D07-08 | Phase A export scope? | **Read-only manifest** (Phase A không có recommendation thật) | CSV + JSONL export | ⭐ **Read-only** |
| **7** | ADR-0008 | (per above §6.1 row 1) | A: aggregate | B: per-file | ⭐ **A** |
| **8** | `preprocessing_warning` | (per above §6.1 row 2) | (a) field mới | (b) concat | (c) đính chính plan | ⭐ **(c)** |

### 6.3. Bảng chọn cho OQ-D07-01/03/04/05 (Phase B gate, không block Phase A accept)

| # | OQ | Câu hỏi ngắn | Phương án | Status |
|---|---|---|---|---|
| **9** | OQ-D07-01 | MKT-01..MKT-05 scope có khớp SYS-01 §6.7 6 fields? | Owner quyết sau khi MKT framework được tạo | Phase B only |
| **10** | OQ-D07-03 | CP-04 §4.1–§4.3 construction rules canonical tokenization? | **CP-04 §4.1–§4.3** (verified) hoặc architecture khác | Phase B only |
| **11** | OQ-D07-04 | KPI unit — survey / transaction / composition? | Owner quyết (Phase A `kpi=None`) | Phase B only |
| **12** | OQ-D07-05 | DEV-07 export format? | CSV + JSONL (mirror DEV-06) hoặc khác | Phase B only |

### 6.4. Validation gates hiện hành (giữ nguyên)

Brief này **KHÔNG** đề xuất thay đổi bất kỳ methodology gate nào:

- ✅ AGENTS.md §2.1 (research integrity) — honored.
- ✅ AGENTS.md §2.2 (phase isolation) — honored.
- ✅ AGENTS.md §2.5 (research decision language) — honored.
- ✅ AGENTS.md §2.7 (changelog — version pin) — honored.
- ✅ AGENTS.md §2.8 (validation) — 263 + 1336 tests pass (post-Phase-A-acceptance).
- ✅ AGENTS.md §2.9 (no silent policy changes) — Option (c) giữ status
  quo, không silent change. ADR-0008 Option A canonicalize form đã có;
  config chỉ đồng bộ với loader production code.
- ✅ AGENTS.md §2.10 (human approval gate) — owner review required.
- ✅ AGENTS.md §2.11 (Git ops owner) — không có git operation trong brief.
- ✅ AGENTS.md §2.12 (data privacy) — `data/**` không commit.
- ✅ AGENTS.md §2.13 (code organization) — Phase A code ở
  `src/customer_segmentation/prototype/marketing/`.
- ✅ FR-MKT-01..06 (SYS-01 §6.7) — Phase A giữ `availability = REVIEW_REQUIRED`.
- ✅ CON-07 (internal metrics only) — KPI blocklist enforced.
- ✅ CON-08 (DBSCAN noise not segment) — excluded.
- ✅ CON-12 (Marketing inherits MKT) — Phase A không tự tạo framework.
- ✅ SYS-03 §15.1 (E-MKT schema shell) — frozen; brief không đề xuất
  sửa (Option (c) giữ nguyên).
- ✅ SYS-04 §15.1 (Marketing handoff = REVIEW_REQUIRED) — Phase A giữ.
- ✅ SYS-06 §9 S-13 (placeholder) — Phase A giữ placeholder hiện tại
  (OQ-D07-06 RESOLVED).

---

## Phụ lục A — Căn cứ tài liệu đã đọc

| Tài liệu | Phần sử dụng |
|---|---|
| `docs/decisions/0008-dev07-version-pattern.md` | Toàn bộ (ADR-0008 draft). |
| `docs/system/DEV-07_remediation_report.md` | §4, §5, §7, §8 (validation + remediation chi tiết). |
| `docs/system/DEV-07_implementation_plan.md` | §4.2 (line 205), §4.4 (line 224, 320-321), §5.4, §5.7, §8.3, §11.1 AC-D07-10. |
| `docs/system/DEV-07_owner_decision_matrix.md` | Toàn bộ (decision matrix Phase A). |
| `AGENTS.md` | §2.1, §2.5, §2.7, §2.8, §2.9, §2.10, §2.11, §2.13. |
| `docs/system/SYS-01_requirements.md` | §2.8, §6.7 FR-MKT-01..06, §6.8 FR-REPORT-01..03, §13 OQ-01/02, CON-07/08/12. |
| `docs/system/SYS-03_data_model.md` | §15.1 E-MKT schema shell, §18.1 (1:0..1 E-SEG → E-MKT), §27 OQ-DM-02/03/14. |
| `docs/system/SYS-04_ml_processing_pipeline.md` | §15.1 Marketing handoff, §15.2, OQ-PIPE-05. |
| `docs/system/SYS-06_ui_ux_design.md` | §9 S-13 Marketing placeholder, §19 OQ #3. |
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | `_extract_version` line 144-158; `framework_version_string` line 162; diagnostics line 88-151. |
| `src/customer_segmentation/prototype/marketing/config_loader.py` | Default `version_pattern` truyền từ YAML (verified). |
| `src/customer_segmentation/prototype/marketing/storage.py` | `CANONICAL_PAYLOAD_KEYS` line 86-95, `mkt_framework_version` field line 39. |
| `src/customer_segmentation/prototype/marketing/manifest.py` | `MarketingRecommendationManifest` schema (verified: NO `preprocessing_warning`); `build_recommendation_entry_review_required` line 399-420. |
| `src/customer_segmentation/prototype/marketing/pipeline.py` | line 414 (`limitation=MARKETING_LIMITATION_TEXT` constant, NOT DEV-06 warning). |
| `src/customer_segmentation/prototype/marketing/scope.py` | `MARKETING_LIMITATION_TEXT` line 231-235. |
| `src/customer_segmentation/prototype/segmentation/manifest.py` | `preprocessing_warning: str = ""` line 460 (mandatory field). |

---

## Phụ lục B — Glossary

| Thuật ngữ | Ý nghĩa |
|---|---|
| **Aggregate form** | Version string `MKT-01..05__vN` (do `framework_version_string()` tạo; cũng là descriptive trong plan §5.7, §8.3). |
| **Per-file form** | Version string `MKT-0X__vN` (per document). |
| **`marketing_id`** | Content-addressed ID `mkt_<24 hex chars>` derive từ 9 fields (xem `storage.py:33-43`). |
| **`preprocessing_warning`** | Field mandatory trong DEV-06 `SegmentationManifest` (`str = ""` default); KHÔNG có trong DEV-07 v1.0.0. |
| **`limitation_note`** | Field mandatory trong DEV-07 `MarketingRecommendationEntry` (`str`); default `MARKETING_LIMITATION_TEXT` constant. |
| **`MARKETING_LIMITATION_TEXT`** | Hard-coded constant trong `scope.py:231-235`; Phase A limitation note mặc định. |
| **`MARKETING_PENDING_PLACEHOLDER`** | `"PENDING_MKT_FRAMEWORK"` string; dùng cho 5 fields khi MKT absent. |
| **Witness test** | Test document behavior hiện tại (không fix), defensive against silent regression. |
| **Carry-over** | Mang field từ DEV-06 sang DEV-07 output (plan §4.2, §4.4). |
| **FROZEN STATUS** | SYS-03 §3.2: schema đã freeze; thay đổi cần mentor approval + ADR. |
| **REVIEW_REQUIRED** | Methodology chưa lock, cần mentor / human researcher quyết. |
| **TECHNICALLY_IMPLEMENTED** | Code chạy, tests pass, artifacts đầy đủ (AGENTS.md §2.10). KHÔNG đồng nghĩa RESEARCH_APPROVED. |

---

## Phụ lục C — Tóm tắt methodology gates hiện hành (giữ nguyên)

| Gate | Status |
|---|---|
| DBSCAN noise (`segment_id = -1`) excluded | ✅ Enforced (FR-MKT-06, CON-08). |
| KPI = None Phase A | ✅ Enforced (`test_dev07_pipeline.py::test_no_kpi_in_phase_a`). |
| KPI blocklist (silhouette, DBI, CH, WCSS, ARI, AMI) | ✅ Enforced (`KPI_BLOCKLIST` in `scope.py:155-184`). |
| `research_safety.scope = "MARKETING_PROTOTYPE"` always | ✅ Enforced (`ResearchSafetyBlock.__post_init__`). |
| `automatically_promoted_to_research = False` always | ✅ Enforced (same). |
| No forbidden marketing terms (champion, loyal, VIP, at-risk, churn, LTV, CLV) | ✅ Enforced (`FORBIDDEN_MARKETING_TERMS` + `check_forbidden_marketing_terms`). |
| No CSV/JSONL export Phase A | ✅ Enforced (OQ-D07-08 = read-only). |
| No HTML modification Phase A | ✅ (`index.html` §1584–1613 unchanged). |
| No DEV-06 contract modification | ✅ (read-only). |
| No Git operations | ✅ (verified). |
| No raw data commit | ✅ (`.gitignore` cover). |
| 5 algorithms only (K-Means, Agglomerative, DBSCAN, GMM, FCM) | ✅ (ADR-0003; K-Medoids out). |
| No silent policy changes | ✅ (Phase A không silent change; Option (c) khuyến nghị giữ status quo). |

---

*File này là DEV-07 Owner Decision Brief. KHÔNG implement code. Chờ
owner review và approval 2 quyết định (ADR-0008 + preprocessing_warning)
trước khi accept Phase A / bắt đầu Phase B.*