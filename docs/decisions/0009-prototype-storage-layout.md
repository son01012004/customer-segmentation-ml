# 0009 — Prototype storage layout: nested `preprocessed/` is canonical

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, regex pattern, status enum, command, file
> path, ADR ID, task ID, EPIC ID theo convention hiện có.

- **Status**: Accepted
- **Date**: 2026-10-12
- **Deciders**: Owner (decision được ghi trong poll 2026-10-12
  `q_layout_clarification` = `q_b2c_formalize_nested`; không có ADR
  trước đó nào formalise on-disk tree)
- **Task ID**: DEV-03..09 (cross-cutting; ảnh hưởng prototype-layer
  storage contract)
- **Supersedes**: n/a
- **Audit source**: read-only inspection của
  `src/customer_segmentation/prototype/preprocessing/storage.py`,
  `tests/test_dev03_storage.py`, và tất cả consumer module
  (`prototype/{clustering,segmentation,evaluation,end_to_end}/{pipeline,storage}.py`,
  `prototype/segmentation/validation.py`) trên 2026-10-12.

---

## 1. Context

Prototype layer (DEV-02 → DEV-09) ghi artifact tới
`data/prototype/<storage_root>/datasets/<dataset_id>/…`. Contract cho
**nơi** DEV-03 ghi output (cleaned parquet, ML dataset parquet,
per-stage log, manifest) trước đây **chỉ** được document trong
`docs/system/DEV-03_preprocessing.md` §4.2 dưới dạng descriptive prose,
và **chỉ** được ghim trong code bởi helper
`customer_segmentation.prototype.preprocessing.storage.preprocessed_dir()`.

Hai câu hỏi nảy sinh trong pre-handoff audit (2026-10-12):

1. **Nested `<storage_root>/<dataset_id>/preprocessed/` sub-directory có
   phải canonical location, hay flat layout
   (`<storage_root>/<dataset_id>/…` không có sub-directory) là target
   dự kiến?** Owner poll `q_layout_clarification` đã giải quyết câu hỏi
   này theo hướng **formalise nested layout làm canonical** (không có
   refactor).
2. **Contract cho downstream consumer module (DEV-04..09) đọc DEV-03
   output là gì?** Inspection cho thấy cả bốn consumer module hardcode
   nested path:
   `storage_root / dataset_id / "preprocessed"` cộng với
   `preprocessed_manifest.json` lookup và `ml_dataset_*.parquet` lookup
   bên trong sub-directory đó.

Một ADR chính thức là cần thiết vì (a) contract là cross-cutting
(DEV-03 producer + 4 consumer module), (b) contract đã được implement
và test nhưng chưa từng được ghi thành architecture decision, và (c) file
log bị thiếu
`pp_ecd1dc6aa1a9069ee85eea53.log` trên prototype layer's on-disk
artifact (xem §6) là triệu chứng của contract không được enforce
end-to-end bởi một authoritative source.

## 2. Decision

**Nested layout `<storage_root>/<dataset_id>/preprocessed/` là on-disk
tree canonical cho DEV-03 output.** Flat layout
(`<storage_root>/<dataset_id>/<file>`) bị **reject** cho current
prototype phase. Không cần code refactor; contract đã được implement
và test, và ADR này formalise nó.

Canonical on-disk tree (DEV-03 producer side):

```
<storage_root>/
└── <dataset_id>/
    ├── <original_filename>                 vd. tiny_online_retail.csv
    ├── manifest.json                       {DEV-02 dataset manifest}
    └── preprocessed/                       ← CANONICAL sub-directory
        ├── preprocessed_<timestamp>_<ppid>.parquet
        ├── ml_dataset_<timestamp>_<ppid>.parquet
        ├── preprocessed_manifest.json
        └── <preprocessed_id>.log           vd. pp_ecd1dc6aa1a9069ee85eea53.log
```

`<preprocessed_id>` là `"pp_" + first 24 hex char` của SHA-256 trên
`(dataset_id + config_hash + cleaned-content-sha)` (xem
`prototype.preprocessing.storage.derive_preprocessed_id`).

Downstream consumer module (DEV-04..09) đọc DEV-03 output tại:

```
preprocessed_dir  = <storage_root>/<dataset_id>/preprocessed/
manifest_path     = preprocessed_dir / "preprocessed_manifest.json"
ml_dataset_path   = preprocessed_dir / f"ml_dataset_<timestamp>_<ppid>.parquet"
                   (manifest ghi chính xác `ml_dataset_block.artifact_path`)
log_path          = preprocessed_dir / f"<preprocessed_id>.log"
                   (manifest ghi chính xác field `log_file` — chỉ filename,
                   relative tới `preprocessed_dir`; consumer resolve
                   absolute path bằng cách join `preprocessed_dir` với
                   field `log_file`)
```

### 2.1. Căn cứ quyết định

| Lý do | Chi tiết |
|---|---|
| **Code đã implement + test verify contract nested** | `prototype/preprocessing/storage.py::preprocessed_dir()` trả về `<storage_root>/<dataset_id>/preprocessed/`; `tests/test_dev03_storage.py::test_preprocessed_dir_resolves_inside_storage_root` pass (verified bởi repo state 2026-10-12). |
| **Tất cả consumer đã assume nested** | `prototype/clustering/pipeline.py:251-285`, `prototype/clustering/storage.py:378-380`, `prototype/segmentation/validation.py:518-522`, `prototype/evaluation/pipeline.py:589`, `prototype/end_to_end/pipeline.py` đều đọc từ `preprocessed_dir`. Refactor sẽ break ≥10 file. |
| **"Ít thay đổi nhất"** | Owner poll q1 (`q_b2c_formalize_nested`) chọn phương án formalize contract hiện tại. Flat refactor (Option B.2.a) sẽ phá vỡ ≥10 file + test + downstream; ngược lại với mục tiêu "ít thay đổi nhất". |
| **Không có ADR nào ghi nhận flat làm canonical** | Grep trong `docs/decisions/0001..0008` và `docs/system/DEV-0*.md` không thấy ADR nào ghi nhận flat layout. Quyết định flat = silent methodology change nếu làm mà không có ADR. |
| **Consistency với Stage Tree của DEV-04..05 docs** | `docs/system/DEV-04_clustering_execution.md:4266`, `docs/system/DEV-05_evaluation_module.md:889, 901` đều mô tả layout nested: `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/` (chính là sub-tree của `preprocessed/`). |

### 2.2. Forward-looking ràng buộc

- **Không thêm sub-directory mới dưới `preprocessed/` ngoài những gì đã
  có** (`preprocessed_*.parquet`, `ml_dataset_*.parquet`,
  `preprocessed_manifest.json`, `<preprocessed_id>.log`,
  `<preprocessed_id>/clustering/…`, `<preprocessed_id>/segmentation/…`,
  `<preprocessed_id>/evaluation/…`). Việc thêm subdir mới cần ADR mới.
- **Tên file trong `preprocessed/` phải follow pattern
  `{base}_{timestamp}_{preprocessed_id}.{ext}`** cho parquet; manifest
  tên `preprocessed_manifest.json` (cố định); log tên
  `<preprocessed_id>.log` (cố định).
- **Nếu sau này cần flat layout** (vd: thay đổi yêu cầu operator,
  integrate với hệ thống file khác), cần ADR mới superseding 0009 +
  refactor toàn bộ consumer + tests. Đây không phải quick fix.

## 3. Consequences

### 3.1. Easier

- Contract được formalize trong ADR này → không còn ambiguity về layout.
- Không phải refactor code → zero production-code change trong
  implementation phase này.
- Test `test_dev03_storage.py` đã verify contract, không cần sửa.
- Missing log file issue (§6) trở thành vấn đề cụ thể của một dataset
  cụ thể (`ds_36a11ffbffc6eb46250a7c3a`), không phải vấn đề của
  contract.
- Onboarding cho tester: 1 file này + 1 file source (`storage.py`) + 1
  file test (`test_dev03_storage.py`) là đủ để hiểu contract.

### 3.2. Harder hoặc riskier

- **Forward constraint**: nếu sau này muốn đổi sang flat, phải viết
  ADR mới superseding 0009 + refactor ≥10 file + re-run full test
  suite + re-validate on-disk artefact. Estimated effort: 1-2 hours.
- **Test pollution**: 24 pre-existing test failure (theo ghi nhận
  2026-10-12) có thể che giấu regression thực sự của contract này
  trong tương lai. Cần maintain test suite clean trước khi thay đổi
  contract.
- **Missing log issue (§6) KHÔNG được giải quyết bởi ADR này** — nó
  là on-disk data issue, cần owner decision riêng (xem
  `docs/system/DEV-XX_handoff_report.md` nếu đã tạo).

## 4. Alternatives considered

### 4.1. Option A — Refactor sang flat layout (bỏ subdir `preprocessed/`)

**Description**: Bỏ subdir `preprocessed/`, files ở
`<storage_root>/<dataset_id>/` directly. Tất cả consumer module
(DEV-04..09) phải update hardcoded path.

**Bị reject** vì:

- Số file phải sửa: ≥10 (storage.py, pipeline.py, test file, 4 consumer
  module, ≥3 test file). Estimated effort 1-2 hours.
- "Ít thay đổi nhất" (mục tiêu owner) bị vi phạm.
- Không có use case rõ ràng đòi hỏi flat (operator vẫn dùng CLI,
  prototype dùng Option A file-based theo ADR-0005).
- 24 pre-existing test failure → refactor có nguy cơ che giấu regression.

### 4.2. Option B — Hybrid layout (flat cho raw + nested cho preprocessed)

**Description**: Raw dataset file (CSV/Parquet) ở flat
`<storage_root>/<dataset_id>/` (giữ nguyên hiện tại), preprocessed output
ở nested `<storage_root>/<dataset_id>/preprocessed/` (giữ nguyên hiện tại).

**Bị reject** vì:

- Đây thực ra CHÍNH LÀ contract hiện tại — Option này = Option 2 (đã
  được chọn). Đưa vào alternatives chỉ để làm rõ contract.

### 4.3. Option C — Defer ADR đến sau khi tester review

**Description**: Tạm thời không có ADR, đợi tester phát hiện issue mới
quyết định.

**Bị reject** vì:

- `AGENTS.md` §2.9 cấm "no silent policy changes". Contract đã được
  implement + test + consumer dùng mà không có ADR là silent policy
  change tiềm ẩn.
- Owner đã yêu cầu ADR trong poll `q_layout_clarification`.

## 5. Affected files

| File | Change |
|---|---|
| `docs/decisions/0009-prototype-storage-layout.md` | **CREATED** (file này). |
| `docs/system/DEV-XX_handoff_report.md` (nếu tạo) | Reference ADR-0009 cho storage contract section. |

**Files KHÔNG bị thay đổi** (verified unchanged):

- `src/customer_segmentation/prototype/preprocessing/{storage,pipeline,manifest,validation,list,config_loader,logging_config,scope}.py`
- `src/customer_segmentation/prototype/{clustering,segmentation,evaluation,end_to_end,visualization,marketing}/**`
- `tests/test_dev0[2-9]_*.py`
- `configs/dev0[2-9]_*.yaml`
- `docs/system/DEV-0[1-9]_*.md`
- `AGENTS.md`
- `data/**` (read-only investigation only)
- `pyproject.toml`, `.gitignore`

## 6. Known issues (KHÔNG được giải quyết bởi ADR này)

### 6.1. Missing `pp_ecd1dc6aa1a9069ee85eea53.log`

On-disk dataset
`data/prototype/datasets/ds_36a11ffbffc6eb46250a7c3a/preprocessed/preprocessed_manifest.json`
tham chiếu `log_file: "pp_ecd1dc6aa1a9069ee85eea53.log"` (relative
filename, theo ADR-0009 §2 spec) nhưng file KHÔNG tồn tại tại
`preprocessed_dir / "pp_ecd1dc6aa1a9069ee85eea53.log"`.

**Decision**: Owner poll `q_log_resolution` = `q_log_report_only_block`.
Issue được document trong handoff report và flag là **BLOCKED** cho
tester pending owner-supplied original log file. **Không code change**,
**không manifest edit**, **không tạo file**.

### 6.2. Orphan log file trong double-nested path

Ba log file tồn tại tại
`data/prototype/datasets/datasets/ds_36a11ffbffc6eb46250a7c3a/preprocessed/pp_ecd1dc6aa1a9069ee85eea53/clustering/_preparing_*.log`.

Các file này KHÔNG phải DEV-03 log (DEV-03 log là `pp_<id>.log`, không
phải `_preparing_*.log`). Chúng là DEV-04/05 staging artifact được ghi
tới double-nested path (`datasets/datasets/<ds_id>/…`) — double-nesting
là bất thường và on-disk location không khớp với ADR-0009 canonical tree
(không có layer `datasets/datasets/`).

**Decision**: Flag trong handoff report là pre-existing data anomaly.
**Không code change**, **không di chuyển file**, **không xóa file**
(`AGENTS.md` §2.12 data integrity; "no overwrite/delete existing
artifact"). Owner có thể quyết định cleanup approach trong một change
riêng nếu muốn.

### 6.3. Test pollution (24 pre-existing failure)

Full pytest suite cho DEV-02..09 có 24 pre-existing failure (ghi nhận
trước ADR này). Handoff report sẽ capture baseline và document các cái
này là **NOT IN SCOPE** cho handoff — theo `AGENTS.md` §2.8
"pre-existing failure" handling.

## 7. References

- `src/customer_segmentation/prototype/preprocessing/storage.py` —
  `preprocessed_dir`, `preprocessed_log_path`, `derive_preprocessed_id`,
  `PREPROCESSED_DIR_SUFFIX = "preprocessed"`,
  `PREPROCESSED_ID_PREFIX = "pp_"`,
  `PREPROCESSED_ID_HEX_LEN = 24`.
- `tests/test_dev03_storage.py` —
  `test_preprocessed_dir_resolves_inside_storage_root`,
  `test_preprocessed_log_path_returns_canonical`.
- `src/customer_segmentation/prototype/clustering/pipeline.py:251-285` —
  consumer read paths.
- `src/customer_segmentation/prototype/clustering/storage.py:378-380` —
  doc comment mô tả on-disk tree.
- `src/customer_segmentation/prototype/segmentation/validation.py:518-522` —
  `preprocessed_manifest_ml_dataset_artifact_path_present` check.
- `src/customer_segmentation/prototype/evaluation/pipeline.py:589` —
  consumer `pd.read_parquet(ml_dataset_path)`.
- `docs/system/DEV-03_preprocessing.md` §4.2 — descriptive on-disk tree.
- `docs/system/DEV-04_clustering_execution.md:4194, 4266` — sub-tree
  description.
- `docs/system/DEV-05_evaluation_module.md:8, 889, 901` — sub-tree
  description.
- `AGENTS.md` §2.9 (no silent policy changes), §2.10 (human approval
  gate), §2.12 (data integrity), §2.8 (pre-existing failure).
- `docs/decisions/0005-prototype-architecture-option-a.md` — Option A
  file-based, supports nested layout.
- `docs/decisions/0008-dev07-version-pattern.md` — example ADR với
  full template structure.
- `docs/decisions/README.md` — ADR immutability convention.

---

*File này là ADR đã được owner chấp thuận (Status: Accepted). Theo
`docs/decisions/README.md` immutability convention, ADR này không bị
edit sau khi accepted. Nếu cần thay đổi layout, tạo ADR mới
superseding 0009.*
