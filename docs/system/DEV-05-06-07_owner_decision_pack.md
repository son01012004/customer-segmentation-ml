# Owner Decision Pack — Phase E (DEV-05/06/07 organization) + Phase F (Việt hóa) + Open Gates

> **Loại tài liệu:** Decision pack — chuẩn bị owner review cho Phase E/F execution.
> **Ngày:** 2026-10-13.
> **Tác giả:** AI assistant (read-only; KHÔNG tự resolve OQ, KHÔNG sửa methodology state, KHÔNG sửa file khác ngoài file này).
> **Phạm vi:**
> - §3 — trạng thái repository tại thời điểm lập pack.
> - §4 — quyết định organization (KEEP/MERGE/ARCHIVE) cho từng file DEV-05/06/07.
> - §5 — quyết định ngôn ngữ (VN/EN/bilingual) cho từng file DEV-05/06/07.
> - §6 — quyết định DEV-07 (4 OQ-D07 + 4 OQ Phase A liên quan + MKT framework).
> - §7 — quyết định K-01 (log file missing).
> - §8 — quyết định SYS-01 OQ-01/02/03/05 + SYS-02 + methodology gates.
> - §9 — tổng hợp quyết định cần owner + phân biệt owner/mentor/researcher.
> - §10 — checklist trả lời ngắn (để owner duyệt nhanh theo ID + lựa chọn).
> **Phạm vi KHÔNG thuộc pack:**
> - Không tự quyết bất kỳ OQ nào.
> - Không tạo/sửa MKT-01..MKT-05 files (researcher content).
> - Không tạo log giả, không sửa manifest, không xóa field `log_file`.
> - Không sửa code, ADR, SYS documents, configs.
> - Không commit / push / PR / branch.
> - Không tự ý promote PENDING / REVIEW_REQUIRED / WORKING_ASSUMPTION.

---

## 0. Cách đọc pack

Mỗi quyết định có:
- **ID**: mã định danh duy nhất (D-ORG-*, D-LANG-*, D-DEV07-*, D-K01-*, D-SYS01-*, D-METH-*, D-SYS02-*).
- **Câu hỏi**: câu hỏi owner cần trả lời.
- **Bằng chứng hiện có**: file path, line, evidence từ repository.
- **Lựa chọn (Options)**: từ 2 đến 4 phương án khả thi, mỗi phương án có ID option riêng (A, B, C, D).
- **Đề xuất mặc định**: chỉ đưa ra khi có bằng chứng đủ mạnh; **KHÔNG** đưa ra đề xuất khi cần owner quyết methodology.
- **Hệ quả**: hậu quả của từng lựa chọn.
- **Thẩm quyền**: owner / mentor / researcher.
- **Trạng thái tại pack**: chỉ trạng thái hiện tại, KHÔNG tự thay đổi.

**Hệ thống ID tổng quát:**
- `D-ORG-DEV05-01..05`: organization decisions cho 5 file DEV-05.
- `D-ORG-DEV06-01..03`: organization decisions cho 3 file DEV-06.
- `D-ORG-DEV07-01..09`: organization decisions cho 9 file DEV-07.
- `D-LANG-DEV05-01..05`: language decisions cho 5 file DEV-05.
- `D-LANG-DEV06-01..03`: language decisions cho 3 file DEV-06.
- `D-LANG-DEV07-01..09`: language decisions cho 9 file DEV-07.
- `D-DEV07-OQ-01..05`: 4 OQ-D07 (01, 03, 04, 05) + MKT framework.
- `D-DEV07-PHASEA-01..03`: 3 OQ-D07-06/07/08 đã RESOLVED 2026-10-10 nhưng cần owner xác nhận.
- `D-K01-01..03`: 3 phương án K-01.
- `D-SYS01-OQ-01..04`: 4 OQ SYS-01 (OQ-01, 02, 03, 05).
- `D-SYS02-01..02`: 2 quyết định về SYS-02.
- `D-METH-01..03`: 3 methodology gates WORKING (feature set, preprocessing, ranking).

---

## 1. Quy tắc bắt buộc

Áp dụng từ `AGENTS.md` (user rule) + `docs/README.md` (đã đọc end-to-end trong audit pass trước):

1. **Đọc repository first**: đã đọc `AGENTS.md` (full), `docs/README.md` (full), `docs/decisions/README.md` (full), headers + §1–§4 của tất cả 17 file DEV-05/06/07, ADR-0005/0006/0008/0009, `METHODOLOGY_LOCK_STATUS.md` §1–§3, `EXP01_EXP05_PENDING_DECISIONS.md` §A–D, `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` §0–§1, `SYS-01_requirements.md` §13 (full OQ table), `SYS-02_architecture.md` §0 (status), `DEV-07_phase_b_decision_memo.md` (full), `DEV-07_owner_decision_matrix.md` (full), `DEV-10_handoff_report.md` §6 (K-01), `reports/evaluation/eva03/eva03_run_manifest.json` (full), `reports/evaluation/eva03/eva03_report.md` §5, `data/prototype/datasets/ds_36a11ffbffc6eb46250a7c3a/preprocessed/preprocessed_manifest.json` (K-01 reference).
2. **Phân biệt TECHNICALLY_IMPLEMENTED vs RESEARCH_DECISION_APPROVED** (§2.10): không tự nâng trạng thái.
3. **Không commit/push/PR/branch/merge** (§2.11).
4. **Không tự quyết methodology** (§2.1, §2.5, §2.6, §2.10).
5. **Không move/rename/merge/archive** file nếu chưa có owner approval (`docs/README.md` §6 + Phase 2B.3 chọn Phương án B cho ML01 = tiền lệ).
6. **Bảo toàn ID, schema, path, metric, contract, technical term**.
7. **Trước khi chỉnh sửa**: đã `git status --short` snapshot (22 modified + 160 untracked). KHÔNG revert, KHÔNG checkout, KHÔNG stash, KHÔNG clean.

---

## 2. Trạng thái repository tại thời điểm pack

### 2.1. Tracked modified (22 file) — KHÔNG động vào

Đã verify trong audit pass trước; tất cả là sửa đổi có chủ đích trước phiên này, **KHÔNG touch** trong pack này.

### 2.2. Untracked (161 file sau khi thêm audit report) — KHÔNG move/rename

Toàn bộ file trong `docs/system/DEV-*.md` đều là untracked; **KHÔNG** move, rename, merge, archive bất kỳ file nào trong pack này (chỉ tạo 1 file mới = pack này).

### 2.3. ADR status (relevant)

| ADR | Status | Ngày | Vai trò |
|---|---|---|---|
| 0005-prototype-architecture-option-a | Accepted | 2026-10-08 | Prototype architecture (file-based batch) |
| 0006-dev05-prototype-noise-policy | Accepted (prototype scope only) | 2026-10-09 | DEV-05 noise policy |
| 0008-dev07-version-pattern | Accepted | 2026-10-10 | DEV-07 canonical version form |
| 0009-prototype-storage-layout | Accepted | 2026-10-12 | Storage layout (K-01 references §6.1) |

### 2.4. SYS status

| SYS | Status | Bằng chứng |
|---|---|---|
| SYS-01 | Modified tracked (OQ-09/10/11 RESOLVED per ADR-0005) | `docs/system/SYS-01_requirements.md` §13 |
| SYS-02 | DRAFT — pending mentor/researcher review (REVIEW_REQUIRED) | Header `docs/system/SYS-02_architecture.md` |
| SYS-03..06 | (canonical architecture) | `docs/README.md` §3.7 |

### 2.5. EVA-03 evidence baseline

- `pytest tests/test_eva03.py`: **54 passed, 0 failed, 0 skipped** (verified 2026-10-13).
- `n_rows_in_artifact: 327825`; `input_sha256: f80c22d4c1a5ab35...`; manifest có 4-value `decision_status` taxonomy đầy đủ.
- Source code: `_df_to_markdown` local trong `src/customer_segmentation/evaluation/eva03/report.py` (line 60), KHÔNG gọi `tabulate`; `pyproject.toml` không có `tabulate`.

### 2.6. MKT-01..MKT-05 confirmed ABSENT

Bằng chứng (verified 2026-10-13):
- `find . -name "MKT-0*"` (toàn repo): **0 file**.
- `Grep "MKT-0[1-5]"` (toàn docs/): chỉ reference trong SYS-01, SYS-03, SYS-04, SYS-06, ADR-0008, planning artifacts, `index.html` placeholder; KHÔNG có file framework nào.
- `docs/marketing/` (per `configs/dev07_marketing.yaml::mkt_framework.path_relative`): **không tồn tại**.

### 2.7. K-01 confirmed BLOCKED (file missing)

Bằng chứng (verified 2026-10-13):
- `ls data/prototype/datasets/ds_36a11ffbffc6eb46250a7c3a/preprocessed/`: có 3 `ml_dataset_*.parquet`, 3 `preprocessed_*.parquet`, `preprocessed_manifest.json`; **không có** `pp_ecd1dc6aa1a9069ee85eea53.log`.
- `preprocessed_manifest.json` tham chiếu: `"log_file": "pp_ecd1dc6aa1a9069ee85eea53.log"`.
- `ADR-0009` §6.1 ghi: `q_log_resolution = q_log_report_only_block`.

---

## 3. WS-1 / Phase E — Organization decisions (per file)

Mỗi file được đánh giá evidence-based. Mặc định đề xuất **KEEP** khi và chỉ khi có bằng chứng hỗ trợ; nếu có bằng chứng cho MERGE hoặc ARCHIVE, đề xuất thay đổi.

### 3.1. DEV-05 (5 file)

#### D-ORG-DEV05-01: `DEV-05_evaluation_module.md`

| Trường | Giá trị |
|---|---|
| Vai trò | **CANONICAL** (Plan v1.2) |
| Kích thước | 145,547 bytes / 1,769 dòng / 74 H3 sections |
| Nội dung độc nhất | Toàn bộ spec: 18 § (scope/non-goals, contracts, metric semantics, design, schema, storage, display, comparison, test matrix, OQ-EVAL-NOISE) |
| Trùng lặp với | 0 file (canonical ≠ reports) |
| Canonical source | Có (Plan v1.2 + ADR-0006) |
| Citation IN | `DEV-05_completion_summary.md` §1, `ADR-0006`, `tests/test_dev05_*.py` |
| Citation OUT | (canonical — không cite các report, các report cite canonical) |
| **Đề xuất** | **KEEP** (canonical không thể archive; archive sẽ phá vỡ contract link) |
| Rủi ro nếu merge | Mất reference point cho toàn bộ hệ thống test + downstream |
| Rủi ro nếu archive | Mất spec cho Phase 1 review (gate `APPROVE PHASE 2`); ADR-0006 sẽ tham chiếu file không tồn tại |
| Thẩm quyền | N/A (đã Accepted qua ADR + Plan v1.2) |

#### D-ORG-DEV05-02: `DEV-05_completion_summary.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Completion report (Phase 2) |
| Kích thước | 13,723 bytes / 246 dòng / 7 H3 sections |
| Nội dung độc nhất | 10 source files, 214 tests, 4-value status taxonomy, ADR-0006 default, idempotency, atomic publish |
| Trùng lặp với | `DEV-05_verification_report.md` §1–2 (test counts, file counts); nhưng khác perspective (implementation vs audit) |
| Canonical source | Không (report, không phải spec) |
| Citation IN | `DEV-05_verification_report.md` (2 lần), `DEV-05_remediation_report.md` (implied) |
| Citation OUT | (1) — `DEV-05_evaluation_module.md` §1.1 |
| **Đề xuất** | **KEEP** (audit trail) |
| Rủi ro nếu merge | Mất pre-existing 1-SKIP evidence (C7-dependent) |
| Rủi ro nếu archive | Mất snapshot implementation state với timestamps |
| Thẩm quyền | Owner (low risk; merge candidate yếu) |

#### D-ORG-DEV05-03: `DEV-05_verification_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Independent verification audit (2026-10-10) |
| Kích thước | 32,873 bytes / 535 dòng / 46 H3 sections |
| Nội dung độc nhất | Static check, env table (numpy/pandas/sklearn/pyarrow version drift), test execution, `VERIFIED WITH LIMITATIONS` |
| Trùng lặp với | `DEV-05_completion_summary.md` §1–2 về số liệu; nhưng audit perspective khác |
| Canonical source | Không |
| Citation IN | `DEV-05_remediation_report.md` (3 lần), `DEV-05_final_review_report.md` (implied) |
| Citation OUT | (1) — `DEV-05_completion_summary.md` |
| **Đề xuất** | **KEEP** (audit trail) |
| Rủi ro nếu merge | Mất audit independence (audit ↔ report) |
| Rủi ro nếu archive | Mất bằng chứng `VERIFIED WITH LIMITATIONS` + 2 finding F1/F2 đã được remediation |
| Thẩm quyền | Owner |

#### D-ORG-DEV05-04: `DEV-05_remediation_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Targeted remediation F1 + F2 |
| Kích thước | 16,189 bytes / 344 dòng / 7 H3 sections |
| Nội dung độc nhất | F1 (`_make_manifest.dataset_id` propagation), F2 (`n_clusters_realized` post-noise-filter) |
| Trùng lặp với | 0 file (chỉ xử lý 2 finding cụ thể) |
| Canonical source | Không |
| Citation IN | `DEV-05_final_review_report.md` (implied) |
| Citation OUT | (1) — `DEV-05_verification_report.md` |
| **Đề xuất** | **KEEP** (audit trail; remediation cycle evidence) |
| Rủi ro nếu merge | Có thể merge vào final review, NHƯNG final review đã reference remediation riêng → merge gây trùng citation |
| Rủi ro nếu archive | Mất bằng chứng remediation F1/F2 đã close |
| Thẩm quyền | Owner |

#### D-ORG-DEV05-05: `DEV-05_final_review_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Final technical review post-remediation |
| Kích thước | 20,488 bytes / 413 dòng / 12 H3 sections |
| Nội dung độc nhất | 3 file remediation verified, F1/F2 closed, no out-of-scope modification; `READY WITH ACCEPTED LIMITATIONS` |
| Trùng lặp với | Tóm tắt verification + remediation, nhưng giá trị audit riêng |
| Canonical source | Không |
| Citation IN | 28 references đến verification + remediation |
| Citation OUT | (0) — không cite file DEV-05 nào khác; đây là endpoint |
| **Đề xuất** | **KEEP** (audit trail) |
| Rủi ro nếu merge | Merge với verification + remediation = 1 file lớn ~70 KB; mất ranh giới "audit → remediation → final review" |
| Rủi ro nếu archive | Mất final acceptance state `READY WITH ACCEPTED LIMITATIONS` |
| Thẩm quyền | Owner |

**Tổng hợp DEV-05:** 5/5 đề xuất **KEEP**. Lý do evidence-based:
- 1 canonical (Plan) không thể archive.
- 4 reports theo trình tự thời gian (completion → verification → remediation → final review) có giá trị audit riêng.
- Mỗi file có header ghi rõ vai trò; không có file nào tuyên bố supersede file khác.
- Citation graph có hướng (canonical ← reports), không có chu trình supersede.

---

### 3.2. DEV-06 (3 file)

#### D-ORG-DEV06-01: `DEV-06_customer_segment_module.md`

| Trường | Giá trị |
|---|---|
| Vai trò | **CANONICAL** (Plan v1.x) |
| Kích thước | 123,066 bytes / 2,123 dòng |
| Nội dung độc nhất | 18 § toàn bộ spec; OQ-SEG-DEPENDENCY-01 đã DECIDED; §14.2.10 (no new deps) |
| Trùng lặp với | 0 file (canonical) |
| Citation IN | `DEV-06_implementation_report.md` (nhiều lần), `DEV-06_remediation_report.md` (nhiều lần) |
| **Đề xuất** | **KEEP** (canonical) |
| Rủi ro nếu archive | Phá vỡ contract link từ implementation + remediation |
| Thẩm quyền | N/A |

#### D-ORG-DEV06-02: `DEV-06_implementation_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Implementation report (full Phase 2B→2L) |
| Kích thước | 21,046 bytes / 416 dòng |
| Nội dung độc nhất | 12 source files, 306 tests, 8 test files; OQ-SEG-DEPENDENCY-01 DECIDED |
| Trùng lặp với | `DEV-06_remediation_report.md` (1 phần test count) |
| Citation IN | `DEV-06_remediation_report.md` (implied) |
| **Đề xuất** | **KEEP** (audit trail Phase 2B→2L) |
| Lưu ý | Nội dung **EN-dominant** (count vn_chars = 0); xem §5 language decision |
| Thẩm quyển | Owner |

#### D-ORG-DEV06-03: `DEV-06_remediation_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Targeted remediation P1 + P2 + P3 |
| Kích thước | 53,955 bytes / 1,065 dòng |
| Nội dung độc nhất | 3 P1 findings, P2 coverage gaps, P3 ruff/lint |
| Trùng lặp với | 1 phần với implementation report |
| Citation IN | (0) — endpoint |
| **Đề xuất** | **KEEP** (audit trail) |
| Thẩm quyền | Owner |

**Tổng hợp DEV-06:** 3/3 đề xuất **KEEP**. Lý do:
- 1 canonical không thể archive.
- 2 reports là 2 giai đoạn (implementation → remediation), timestamps riêng.
- Implementation report EN-dominant là 1 lý do truy vết tại sao DEV-06 có style khác DEV-05/07 (xem §5).

---

### 3.3. DEV-07 (9 file)

**Bối cảnh đã xác minh:**
- `DEV-07_owner_decision_matrix.md` header ghi rõ: **PHASE A ACCEPTANCE GATE RESOLVED 2026-10-10**; OQ-D07-02/-06/-07/-08 resolved; OQ-D07-01/-03/-04/-05 vẫn `REVIEW_REQUIRED`.
- `DEV-07_final_acceptance_report.md` §1.1: **DEV-07 Phase A: TECHNICALLY ACCEPTED (2026-10-10)** với 6 acceptance gate conditions.
- `DEV-07_phase_b_decision_memo.md` (DRAFT 2026-10-10): 4 OQ chờ owner/mentor approve.

**Citation graph từ data (verified):**

| File | Cite out | Cite in (từ file khác) |
|---|---|---|
| implementation_plan | 0 DEV-07 file | 5+3+6+6+6+1 = 27 |
| planning_report | 0 | 7+7+3 = 17 |
| phase_a_audit_report | 0 | 1 (remediation) |
| remediation_report | 1 (phase_a_audit) | 0 (endpoint) |
| owner_decision_brief | 1+2 (impl plan, owner matrix) | 7+2+1 = 10 |
| owner_decision_matrix | 6+7 (impl plan, planning) | 4+2+1+3+5 = 15 |
| phase_b_decision_memo | 6+1+5+1+2 (nhiều) | 4+8+1 = 13 |
| phase_b_acceptance_report | 1+1 (final, decision_memo) | 3+1 = 4 |
| final_acceptance_report | 5+7+4+3+4 (nhiều) | 1 (phase_b_acceptance) |

**Quan sát:** `implementation_plan` và `owner_decision_matrix` là **hub** được cite nhiều nhất; `remediation_report` là **endpoint** (không cite file nào). Citation graph có cấu trúc layer rõ ràng.

#### D-ORG-DEV07-01: `DEV-07_implementation_plan.md`

| Trường | Giá trị |
|---|---|
| Vai trò | **CANONICAL** (Plan) |
| Kích thước | 61,470 bytes / 993 dòng |
| Nội dung độc nhất | 5 § chính: MKT-01..05 evidence matrix, DEV-06 contract, DEV-07 contract, dependency analysis |
| Citation IN | 27 lần từ 7 file khác |
| **Đề xuất** | **KEEP** (canonical + hub) |
| Thẩm quyền | N/A |

#### D-ORG-DEV07-02: `DEV-07_planning_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Pre-implementation planning (reconnaissance) |
| Kích thước | 55,198 bytes / 1,056 dòng |
| Nội dung độc nhất | 6 § chi tiết về MKT framework, FR-MKT-01..06, 5-algorithm constraint, no-promote-research invariant; **đã đính chính 8 chỗ S1–S4 → CP-04 §4.1–§4.3** (per `owner_decision_matrix.md` §7) |
| Citation IN | 17 lần từ 3 file |
| **Đề xuất** | **KEEP** (early reconnaissance với citation correction) |
| Lưu ý đặc biệt | File chứa documentation-of-correction (2 chỗ "S1–S4" còn lại là note giải thích đính chính, KHÔNG phải citation sai còn sót) — xác minh bởi `owner_decision_matrix.md` §7.2 |
| Rủi ro nếu archive | Mất lịch sử reconnaissance + evidence đính chính citation |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-03: `DEV-07_final_acceptance_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Final acceptance summary (Phase A + B infra) |
| Kích thước | 26,659 bytes / 641 dòng |
| Nội dung độc nhất | 6 acceptance gates Phase A, 4 OQ-D07 vẫn REVIEW_REQUIRED, §1.1/§1.2 |
| Citation IN | 1 lần |
| **Đề xuất** | **KEEP** (audit endpoint cho Phase A acceptance) |
| Rủi ro nếu archive | Mất bằng chứng Phase A đã accept 2026-10-10 |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-04: `DEV-07_phase_a_audit_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Independent Phase A audit |
| Kích thước | 37,608 bytes / 741 dòng |
| Nội dung độc nhất | 10 §; findings P0/P1/P2/P3 = 0/2/3/2; test claims 173/252/1325; **Phase B readiness = KHÔNG** (version pattern mismatch) |
| Citation IN | 1 lần (từ remediation) |
| **Đề xuất** | **KEEP** (independent audit) |
| Lưu ý | 252 + 1325 test claims có thể verify bằng `pytest --co`; 173 new chưa thể verify independent — ghi trong audit |
| Rủi ro nếu archive | Mất bằng chứng audit "KHÔNG ready Phase B" — quan trọng cho context của 4 OQ-D07 |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-05: `DEV-07_phase_b_decision_memo.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Phase B owner decision closure (DRAFT) |
| Kích thước | 31,148 bytes / 515 dòng |
| Nội dung độc nhất | 4 OQ (OQ-D07-01/-03/-04/-05) với contract citation, identifier, default proposal, risks, readiness classification |
| Citation IN | 13 lần |
| **Đề xuất** | **KEEP** (DRAFT — primary decision closure document) |
| Trạng thái | DRAFT chờ owner/mentor approve 4 OQ |
| Rủi ro nếu archive | Mất 4 OQ decision context; OQ-D07 vẫn còn `REVIEW_REQUIRED` sẽ không có nơi để ghi lại quyết định |
| Thẩm quyền | Owner (decision) + mentor (methodology) |

#### D-ORG-DEV07-06: `DEV-07_phase_b_acceptance_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Phase B technical acceptance |
| Kích thước | 25,729 bytes / 614 dòng |
| Nội dung độc nhất | Phase B technical infrastructure verdict; 4 OQ-D07 status; MKT framework ABSENT |
| Citation IN | 4 lần |
| **Đề xuất** | **KEEP** (audit endpoint cho Phase B technical) |
| Rủi ro nếu archive | Mất bằng chứng Phase B technical infrastructure = TECHNICALLY_IMPLEMENTED (2026-10-10) |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-07: `DEV-07_owner_decision_brief.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Owner decision brief (Phase A → B) |
| Kích thước | 38,801 bytes / 604 dòng |
| Nội dung độc nhất | 2 quyết định ADR-0008 (canonical version form) + `preprocessing_warning` carry-over; §5.3 OQ-D07-08 RESOLVED |
| Citation IN | 10 lần |
| **Đề xuất** | **KEEP** (brief format cho owner quick read) |
| Rủi ro nếu merge với owner_decision_matrix | Matrix format ≠ brief format; 2 audience khác nhau (quick read vs structured decision) |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-08: `DEV-07_owner_decision_matrix.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Owner decision matrix (Phase A finalized) |
| Kích thước | 32,512 bytes / 521 dòng |
| Nội dung độc nhất | 8 §: verified, compare 2 planning, Phase A matrix, owner questions, scope allow/block, citation correction status, exit criteria |
| Citation IN | 15 lần (hub #2) |
| **Đề xuất** | **KEEP** (matrix format; structured decision) |
| Lưu ý | Chứa citation correction status (§7) — bằng chứng cho planning_report đã đính chính |
| Thẩm quyền | Owner |

#### D-ORG-DEV07-09: `DEV-07_remediation_report.md`

| Trường | Giá trị |
|---|---|
| Vai trò | Phase A remediation |
| Kích thước | 33,259 bytes / 636 dòng |
| Nội dung độc nhất | P1 (version pattern), P2 (lint+format), P3 (test coverage + `preprocessing_warning`) |
| Citation IN | 0 (endpoint; chỉ cite audit) |
| **Đề xuất** | **KEEP** (audit endpoint cho remediation cycle) |
| Rủi ro nếu archive | Mất remediation evidence (P1 đã close, P2/P3 closed) |
| Thẩm quyền | Owner |

**Tổng hợp DEV-07:** 9/9 đề xuất **KEEP**. Lý do:
- 1 canonical (implementation_plan) + 1 hub #2 (owner_decision_matrix) + 1 DRAFT (phase_b_decision_memo) + 6 reports theo trình tự thời gian/audience.
- Phase A vs Phase B ranh giới rõ ràng; merge sẽ pha trộn technical acceptance với owner decision.
- Citation graph có cấu trúc layer (implementation_plan + owner_decision_matrix là hub; remediation + final_acceptance là endpoint).
- 4 OQ-D07 vẫn `REVIEW_REQUIRED` cần giữ nguyên trong file riêng (DRAFT memo); archive sẽ mất nơi ghi quyết định.

**Quyết định tổng hợp Phase E:**
- 17/17 file DEV-05/06/07 đều đề xuất **KEEP**.
- **0 MERGE**, **0 ARCHIVE** đề xuất.
- Lý do: mỗi file có vai trò audit/canonical/decision riêng biệt; rủi ro mất lịch sử/evidence khi merge/archive cao hơn giá trị tiết kiệm.
- **Nếu owner muốn merge/archive cụ thể**, cần ID quyết định riêng (D-ORG-DEV05-06..09, D-ORG-DEV06-04..N, D-ORG-DEV07-10..N) trong §9 shortlist.

---

## 4. WS-2 / Phase F — Language decisions (per file)

### 4.1. Chính sách hiện hành (verified)

- `docs/README.md` §0: "**Ngôn ngữ:** tiếng Việt cho phần diễn giải; tên file, identifier, schema, thuật ngữ kỹ thuật giữ nguyên tiếng Anh theo convention hiện có của repository."
- `docs/decisions/README.md` §0: cùng quy ước.

**Áp dụng:** tất cả quyết định ngôn ngữ dưới đây đều dựa trên policy này. "Đề xuất mặc định" chỉ là hướng dẫn cách áp dụng policy; **không thay đổi policy**.

### 4.2. Phân loại 3 option

- **VN** = phần diễn giải chính bằng tiếng Việt (≥60% từ ngữ narrative VN); giữ Anh cho identifier, schema, paths, command, metric, technical term.
- **EN** = chủ yếu tiếng Anh; có thể giữ nguyên không dịch.
- **BILINGUAL** = mixed tự nhiên, narrative VN + technical EN; đã đúng policy không cần thay đổi.

### 4.3. DEV-05 language

| File | Evidence | Đề xuất | Lý do |
|---|---|---|---|
| `DEV-05_evaluation_module.md` | 16,414 từ / 598 VN chars; mixed | **BILINGUAL** (giữ nguyên) | Canonical spec; narrative VN + technical EN = đúng policy |
| `DEV-05_completion_summary.md` | 1,706 từ / 27 VN chars; mostly EN | **EN** (giữ nguyên) | Implementation report style; narrative EN; chỉ 27 VN chars = header label |
| `DEV-05_verification_report.md` | 3,999 từ / 662 VN chars; VN-dominant | **VN** (giữ nguyên) | Audit report; narrative VN |
| `DEV-05_remediation_report.md` | 1,911 từ / 376 VN chars; VN-dominant | **VN** (giữ nguyên) | Audit report; narrative VN |
| `DEV-05_final_review_report.md` | 2,546 từ / 526 VN chars; VN-dominant | **VN** (giữ nguyên) | Audit report; narrative VN |

**Tổng hợp DEV-05:** 1 BILINGUAL + 1 EN + 3 VN; **0 thay đổi** đề xuất. Lý do: file hiện hành đã tuân policy; chỉ có 1 file EN (`completion_summary`) mà đó là implementation report style — vẫn nhất quán với convention.

### 4.4. DEV-06 language

| File | Evidence | Đề xuất | Lý do |
|---|---|---|---|
| `DEV-06_customer_segment_module.md` | 14,249 từ / 1,094 VN chars; mixed | **BILINGUAL** (giữ nguyên) | Canonical spec; đúng policy |
| `DEV-06_implementation_report.md` | 2,669 từ / **0 VN chars**; **EN-only** | **EN** (giữ nguyên) | Implementation report style EN; tương đồng với `DEV-05_completion_summary.md` |
| `DEV-06_remediation_report.md` | 6,560 từ / 129 VN chars; mostly EN body, VN header | **BILINGUAL** (giữ nguyên) | Header VN, body EN = mixed có chủ đích |

**Tổng hợp DEV-06:** 1 BILINGUAL (canonical) + 1 EN (impl report) + 1 BILINGUAL (remediation). 0 thay đổi đề xuất.

### 4.5. DEV-07 language

| File | Evidence | Đề xuất | Lý do |
|---|---|---|---|
| `DEV-07_implementation_plan.md` | 7,723 từ / 1,249 VN chars; mixed | **BILINGUAL** (giữ nguyên) | Canonical plan; đúng policy |
| `DEV-07_planning_report.md` | 6,876 từ / 434 VN chars; mixed | **BILINGUAL** (giữ nguyên) | Planning; đúng policy |
| `DEV-07_final_acceptance_report.md` | 3,123 từ / 324 VN chars; VN-dominant | **VN** (giữ nguyên) | Acceptance; narrative VN |
| `DEV-07_phase_a_audit_report.md` | 4,873 từ / 842 VN chars; VN-dominant | **VN** (giữ nguyên) | Audit; narrative VN |
| `DEV-07_phase_b_decision_memo.md` | 4,242 từ / 839 VN chars; VN-dominant | **VN** (giữ nguyên) | Decision memo; narrative VN |
| `DEV-07_phase_b_acceptance_report.md` | 3,403 từ / 294 VN chars; VN-dominant | **VN** (giữ nguyên) | Acceptance; narrative VN |
| `DEV-07_owner_decision_brief.md` | 5,268 từ / 1,083 VN chars; VN-dominant | **VN** (giữ nguyên) | Owner brief; narrative VN |
| `DEV-07_owner_decision_matrix.md` | 4,525 từ / 819 VN chars; VN-dominant | **VN** (giữ nguyên) | Owner matrix; narrative VN |
| `DEV-07_remediation_report.md` | 4,334 từ / 701 VN chars; VN-dominant | **VN** (giữ nguyên) | Audit; narrative VN |

**Tổng hợp DEV-07:** 2 BILINGUAL (canonical + planning) + 7 VN (audit/decision/acceptance/remediation/owner-facing). 0 thay đổi đề xuất.

### 4.6. Quyết định Phase F (tổng hợp)

| File | Status đề xuất | Cần owner quyết? |
|---|---|---|
| 17/17 file DEV-05/06/07 | **KEEP current language** | **Không** (đã đúng policy) |

**Không có quyết định cần owner** về Việt hóa hàng loạt; tất cả file đã tuân `docs/README.md` §0. Lý do evidence-based:
- Canonical spec (3 file) = BILINGUAL mixed (đúng policy).
- Audit/decision/owner-facing reports (12 file) = VN-dominant (đúng policy cho narrative + EN cho technical term).
- Implementation reports (2 file: `DEV-05_completion_summary.md`, `DEV-06_implementation_report.md`) = EN-dominant (consistent với implementation report style).
- **Không có file nào "EN-only vi phạm policy"**: 2 file EN đều là implementation report (theo convention); technical terms Anh + narrative Anh = không vi phạm.

**Nếu owner muốn chuẩn hóa implementation report style = VN narrative**, cần quyết định riêng (D-LANG-IMPL-01) trong §9. Đây là policy override; cần owner approval.

---

## 5. WS-3 / DEV-07 OQ + MKT framework

### 5.1. OQ-D07-01 — MKT framework scope ↔ SYS-01 §6.7

**D-DEV07-OQ-01: Mapping 6 E-MKT fields ↔ MKT-01..05**

| Trường | Giá trị |
|---|---|
| Câu hỏi | MKT-01..MKT-05 framework design có khớp với 6 fields của SYS-01 §6.7 FR-MKT-03 (Marketing Objective, Strategy, Recommended Action, KPI, Evidence, Limitation) không, hay schema E-MKT cần điều chỉnh? |
| Bằng chứng | SYS-01 §6.7 FR-MKT-03; SYS-03 §15.1 E-MKT 12 fields; `configs/dev07_marketing.yaml::mkt_framework.path_relative="docs/marketing"`; loader regex `^MKT-0[1-5](?:__|_)v\d+` trong `mkt_framework_loader.py` |
| Option A | **Mapping 6 fields** (per `phase_b_decision_memo.md` §2.1): `marketing_objective` ← MKT-02; `strategy` + `recommended_action` ← MKT-03; `kpi` ← MKT-04; `evidence_ref` ← auto-populated (đã có Phase A); `limitation` ← MKT-05 + `MARKETING_LIMITATION_TEXT`; `source_framework_version` ← `framework_version_string(ref)`. **KHÔNG bump** `MARKETING_MANIFEST_SCHEMA_VERSION`. |
| Option B | Owner đề xuất mapping khác (vd: thêm field mới, đổi assignment). Cần ADR + schema bump. |
| Đề xuất mặc định | **Option A** — có căn cứ contract rõ ràng (SYS-03 §15.1 đã có slot sẵn); chỉ là owner xác nhận mapping. |
| Hệ quả nếu A | Unblock OQ-D07-01; schema vẫn 1.0.0; cần owner tạo MKT-01..MKT-05 files |
| Hệ quả nếu B | Cần ADR mới + schema bump + re-test 328 DEV-07 tests; chậm trễ Phase B |
| Thẩm quyền | **Owner** (mapping) + **Mentor** (FR-MKT-03 interpretation) |

### 5.2. OQ-D07-03 — CP-04 §4.1–§4.3 canonical tokenization

**D-DEV07-OQ-02: Tokenization canonical cho Phase B mapping**

| Trường | Giá trị |
|---|---|
| Câu hỏi | CP-04 §4.1–§4.3 construction rules có phải canonical tokenization cho Phase B mapping Segment → MKT template không, đặc biệt cho COMPARATIVE segments? |
| Bằng chứng | CP-04 §4.1 (RFM core tiers 3×3×3), §4.2 (4 behavioural modifiers + rule gắn), §4.3 (construction rules + fallback "Comparative Segment A/B/C"), §4.4 (hard NO); `tokenization.py` đã implement (24 tests pass); COMPARATIVE parser trả `tier_match=False` |
| Option A | **CP-04 §4.1–§4.3 là canonical cho NAMED segments**; COMPARATIVE / NOT_AVAILABLE → skip (rely on Phase A REVIEW_REQUIRED fallback). |
| Option B | Owner dùng methodology khác cho Phase B (vd: K-Means archetype, RFM tercile). |
| Option C | Owner muốn COMPARATIVE segments vẫn đi qua MKT mapping với default template. |
| Đề xuất mặc định | **Option A** — verified từ source (CP-04 + parser tested 24 cases); conservative. |
| Hệ quả nếu A | Unblock OQ-D07-03; parser pure function, no synthesis |
| Hệ quả nếu B | Cần re-implement parser; re-test 24 cases; chậm trễ Phase B |
| Hệ quả nếu C | Cần thêm default template cho COMPARATIVE; surface area tăng nhẹ |
| Thẩm quyền | **Owner** (methodology adoption) + **Mentor** (CP-04 interpretation) |

### 5.3. OQ-D07-04 — KPI units / data source

**D-DEV07-OQ-03: KPI framework scope**

| Trường | Giá trị |
|---|---|
| Câu hỏi | KPI definitions trong MKT-04 dùng nguồn nào? (a) survey, (b) transaction-derived, (c) composition từ features, (d) tổ hợp |
| Bằng chứng | Survey data **KHÔNG CÓ**; transactions có (FE-02); composition có (FE-06 RFM: 8/14 ELIGIBLE, 6/14 ELIGIBLE_WORKING_ASSUMPTION); FR-MKT-05 cấm internal clustering metric; AGENTS.md §3 + CP-05 §10.4 cấm LTV/CLV/churn/retention/VIP/at-risk/profitability |
| Option A | **KHÔNG auto-compute KPI ở Phase B prototype**; KPI từ MKT-04 file do owner tạo. Nếu MKT-04 dùng 8/14 ELIGIBLE features → cho phép. KHÔNG dùng 6/14 `ELIGIBLE_WORKING_ASSUMPTION` làm primary KPI. |
| Option B | Auto-compute composition-based KPI từ 8/14 ELIGIBLE (AnovaInvoiceValue, TenureDays). |
| Option C | Owner chỉ định KPI nguồn khác (vd: survey external, transactional derived). |
| Đề xuất mặc định | **Option A** — an toàn nhất, không invent KPI; pass-through MKT-04 content. |
| Hệ quả nếu A | KPI chỉ = những gì MKT-04 file chứa; không có auto-compute; cần owner tạo MKT-04 file |
| Hệ quả nếu B | Cần owner approval vì auto-compute = methodology decision |
| Hệ quả nếu C | Cần external data source + ADR |
| Thẩm quyền | **Owner** (KPI framework = business methodology) |

### 5.4. OQ-D07-05 — Export format

**D-DEV07-OQ-04: Export format cho Phase B**

| Trường | Giá trị |
|---|---|
| Câu hỏi | DEV-07 export format nào? (a) CSV + JSONL (mirror DEV-06), (b) read-only, (c) Markdown, (d) khác |
| Bằng chứng | FR-REPORT-01..03 = SHOULD (không MUST); FR-MKT-04 cấm campaign automation; DEV-07 Phase A đã pass với `emit_recommendations_csv=false`, `emit_recommendations_jsonl=false`; OQ-D07-08 RESOLVED 2026-10-10 = read-only |
| Option A | **Giữ read-only** cho Phase B hiện tại (MKT absent). Enable CSV + JSONL sau khi MKT content tồn tại (mirror DEV-06 pattern). |
| Option B | Enable CSV + JSONL ngay khi MKT-01..MKT-05 files tồn tại (~50 LOC tăng). |
| Option C | Markdown report (không có trong AC; SYS-01 §6.8 chỉ "CSV / Markdown" SHOULD). |
| Đề xuất mặc định | **Option A** — đã là status quo; Phase A đã accept với read-only. |
| Lưu ý | **KHÔNG block DEV-07 acceptance** (export optional); có thể trì hoãn sang Phase B thực sự. |
| Thẩm quyền | **Owner** (export scope decision) |

### 5.5. OQ-D07-02 / 06 / 07 / 08 (Phase A — đã RESOLVED 2026-10-10)

**D-DEV07-PHASEA-01: OQ-D07-02 (Phase A implement ngay)**

| Trường | Giá trị |
|---|---|
| Trạng thái hiện tại | **RESOLVED 2026-10-10** — Phase A implement ngay (REVIEW_REQUIRED shell) |
| Option duy nhất | A. Đã resolve (status quo) |
| Thẩm quyền | N/A (đã accept) |

**D-DEV07-PHASEA-02: OQ-D07-06 (HTML `#/marketing` Phase A scope)**

| Trường | Giá trị |
|---|---|
| Trạng thái hiện tại | **RESOLVED 2026-10-10** — giữ nguyên placeholder |
| Option duy nhất | A. Đã resolve |
| Thẩm quyền | N/A |

**D-DEV07-PHASEA-03: OQ-D07-07 (ADR mới cho DEV-07 scope)**

| Trường | Giá trị |
|---|---|
| Trạng thái hiện tại | **RESOLVED 2026-10-10** — KHÔNG tạo ADR mới; ADR-0005 đã cover |
| Lưu ý | ADR-0008 đã được tạo riêng cho canonical version form (khác scope) |
| Thẩm quyền | N/A |

**D-DEV07-PHASEA-04: OQ-D07-08 (Phase A export scope)**

| Trường | Giá trị |
|---|---|
| Trạng thái hiện tại | **RESOLVED 2026-10-10** — read-only manifest |
| Option duy nhất | A. Đã resolve |
| Thẩm quyền | N/A |

### 5.6. MKT-01..MKT-05 framework files

**D-DEV07-MKT-01: MKT-01..MKT-05 framework content**

| Trường | Giá trị |
|---|---|
| Câu hỏi | MKT-01..MKT-05 có được tạo không? Nếu có: bởi ai, khi nào, theo scope nào? |
| Bằng chứng | `find . -name "MKT-0*"` → 0 file; `docs/marketing/` không tồn tại; `framework_version_string` đã implement sẵn aggregate form `MKT-01..05__vN` |
| Option A | **Owner / mentor tạo MKT-01..MKT-05 files** theo scope đã chốt (5 file markdown, mỗi file có version `__v1` ban đầu; aggregate framework_version_string = "MKT-01..05__v1"). |
| Option B | Owner đợi EPIC-09/10 xong rồi tạo. |
| Option C | Agent KHÔNG tạo; vẫn giữ Phase A REVIEW_REQUIRED indefinitely. |
| Đề xuất mặc định | **KHÔNG đề xuất** — đây là **researcher/mentor content**, không thuộc thẩm quyền agent. Owner/mentor tự quyết timeline. |
| Hệ quả nếu A | Unblock OQ-D07-01 (nếu cùng owner approve mapping 6 fields); Phase B có thể bắt đầu |
| Hệ quả nếu B | Phase B tiếp tục BLOCKED; chờ EPIC-09/10 |
| Hệ quả nếu C | DEV-07 giữ Phase A indefinitely; chuyển sang EPIC-12 (FUTURE_WORK) |
| Thẩm quyền | **Mentor / researcher** (MKT framework = research methodology) |

---

## 6. K-01 — DEV-10 log file missing

**D-K01-01: K-01 log file resolution**

| Trường | Giá trị |
|---|---|
| Câu hỏi | `pp_ecd1dc6aa1a9069ee85eea53.log` missing. Owner chọn phương án nào? |
| Bằng chứng | `preprocessed_manifest.json::log_file` reference; `ls` directory không có file `.log`; `ADR-0009` §6.1 ghi `q_log_resolution = q_log_report_only_block` |
| Option A | **Owner cung cấp log gốc** → ghi vào đúng vị trí `data/prototype/datasets/ds_36a11ffbffc6eb46250a7c3a/preprocessed/pp_ecd1dc6aa1a9069ee85eea53.log`. Manifest vẫn reference; full audit trail. |
| Option B | **Owner xóa field `log_file`** trong `preprocessed_manifest.json` → cần ADR note per `ADR-0009` §6.1 (đã có sẵn cơ chế `q_log_report_only_block`). Cần ghi rõ trong ADR-0009 history hoặc tạo ADR-0010 mới. |
| Option C | **Owner accept orphan log** → giữ nguyên manifest reference, bổ sung ADR note "log file intentionally not preserved, manifest vẫn reference cho evidence continuity". Cần ADR note. |
| Đề xuất mặc định | **KHÔNG đề xuất** — đây là owner decision về evidence handling; 3 option đều có cost/benefit riêng. |
| Hệ quả nếu A | Full audit trail; tốn effort owner phải cung cấp file |
| Hệ quả nếu B | Manifest sạch hơn; mất reference đến log (có thể OK vì log đã mất); cần ADR |
| Hệ quả nếu C | Ít thay đổi nhất; cần ADR note; downstream verification vẫn thấy reference đến file không tồn tại |
| Thẩm quyền | **Owner** (evidence integrity) + **Mentor** (nếu liên quan research methodology) |
| Tác động downstream | DEV-10 handoff; cluster_id audit; reproducibility check |
| Bước đang bị chặn | (1) Full audit trail verification; (2) Owner quyết evidence policy cho future preprocessing runs |
| Hard constraint | KHÔNG tạo log giả; KHÔNG tự xóa field `log_file`; KHÔNG tự tạo ADR mới |

---

## 7. SYS-01 OQ + SYS-02 + methodology gates

### 7.1. SYS-01 OQ-01 (MKT framework tạo trước SYS-06 hay đợi EPIC-09/10)

**D-SYS01-OQ-01: Timeline MKT framework ↔ SYS-06 ↔ EPIC-09/10**

| Trường | Giá trị |
|---|---|
| Câu hỏi | MKT framework nên tạo trước SYS-06 hay đợi EPIC-09/10 xong? |
| Bằng chứng | SYS-01 §13 OQ-01 ghi rõ 2 lựa chọn (a)/(b); FR-MKT-01..06 đang ở `REVIEW_REQUIRED`; SYS-06 hiện `REVIEW_READY v0.2` (header); EPIC-09/10 status verified từ methodology scope |
| Option A | **Tạo MKT framework trước SYS-06** (để SYS-06 có thể reference khi design UI Marketing section). |
| Option B | **Đợi EPIC-09/10 xong rồi tạo MKT** (tránh rework khi EPIC-09/10 thay đổi customer profile structure). |
| Option C | Tạo MKT song song với EPIC-09/10, integrate sau. |
| Đề xuất mặc định | **KHÔNG đề xuất** — đây là timeline decision thuộc thẩm quyền mentor/researcher. |
| Hệ quả nếu A | SYS-06 block; Phase B DEV-07 có thể bắt đầu sớm hơn |
| Hệ quả nếu B | EPIC-09/10 hoàn thành trước; MKT có customer profile thật để work với |
| Hệ quả nếu C | Cần đồng bộ giữa 3 workstream; phức tạp |
| Thẩm quyền | **Mentor** (research timeline) |

### 7.2. SYS-01 OQ-02 (MKT framework scope ↔ SYS-01 §6.7)

**D-SYS01-OQ-02: MKT framework scope vs FR-MKT-03**

| Trường | Giá trị |
|---|---|
| Câu hỏi | MKT framework scope (MKT-01..05) có khớp với 6 fields FR-MKT-03 không? |
| Bằng chứng | Tương tự `D-DEV07-OQ-01` (OQ-D07-01); SYS-01 §6.7; SYS-03 §15.1 E-MKT schema shell |
| Option A | **Giữ mapping 6 fields** (per `D-DEV07-OQ-01` Option A). |
| Option B | Điều chỉnh FR-MKT-03 hoặc E-MKT schema để khớp. |
| Đề xuất mặc định | **Option A** — schema shell đã freeze; mapping đã verified. |
| Thẩm quyền | **Owner** (mapping) + **Mentor** (FR-MKT-03) |
| Ghi chú | Cùng quyết định với `D-DEV07-OQ-01`; nếu owner approve `D-DEV07-OQ-01` Option A → OQ-02 tự đóng. |

### 7.3. SYS-01 OQ-03 (SYS layer re-implement vs re-use ML-01)

**D-SYS01-OQ-03: SYS layer re-implement vs re-use**

| Trường | Giá trị |
|---|---|
| Câu hỏi | SYS layer nên re-implement cluster code hay chỉ wrap (re-use) ML-01 framework? |
| Bằng chứng | SYS-01 §13 OQ-03; SYS-02 §1.5: "research core = SOLE ML ground truth, no re-implementation under `src/`" (constraint, không phải decision đã approve) |
| Option A | **Wrap/re-use** (recommended trong SYS-01 §13). DRY, single source of truth. |
| Option B | Re-implement SYS layer cluster code (nếu cần control chi tiết hơn). |
| Đề xuất mặc định | **Option A** — recommendation đã có trong SYS-01, có lý do kỹ thuật (DRY + ground truth); KHÔNG tự promote lên approved. |
| Hệ quả nếu A | DRY; ít code trùng; phụ thuộc ML-01 API |
| Hệ quả nếu B | Tăng code; có thể gây drift với ML-01 |
| Thẩm quyền | **Mentor** (architecture decision) |

### 7.4. SYS-01 OQ-05 (PCA/UMAP/t-SNE projection)

**D-SYS01-OQ-05: Visualization trên data projection**

| Trường | Giá trị |
|---|---|
| Câu hỏi | Prototype có cần hỗ trợ visualization trên data projection (PCA / UMAP / t-SNE) không? |
| Bằng chứng | SYS-01 §13 OQ-05; CP-05 §2.2 OOS ghi PCA/UMAP là OUT OF SCOPE cho CP-05; SYS-02 status vẫn DRAFT; EPIC-08 owned stability/visualization theo SYS-04 §13 |
| Option A | **Giữ OUT OF SCOPE** cho CP-05 (per CP-05 §2.2 OOS). Không visualization trên projection. |
| Option B | Thêm visualization trên PCA (giảm chiều) trong SYS layer; UMAP/t-SNE vẫn OUT. |
| Option C | Thêm cả PCA/UMAP/t-SNE trong SYS layer. |
| Đề xuất mặc định | **Option A** — CP-05 đã OOS rõ ràng; không có bằng chứng owner/mentor muốn thay đổi. |
| Hệ quả nếu A | SYS-06 không cần visualization mới; giữ scope hiện tại |
| Hệ quả nếu B | SYS layer thêm 1 capability; cần ADR + ownership decision |
| Hệ quả nếu C | Phạm vi tăng nhiều; cần nhiều ADR |
| Thẩm quyền | **Mentor** (visualization scope) |

### 7.5. SYS-02 status

**D-SYS02-01: SYS-02 promote từ DRAFT → approved**

| Trường | Giá trị |
|---|---|
| Câu hỏi | SYS-02 architecture có được mentor/researcher review và promote từ DRAFT sang approved không? |
| Bằng chứng | `SYS-02_architecture.md` header: "Status: DRAFT — pending mentor/researcher review (REVIEW_REQUIRED)" |
| Option A | **Mentor/researcher review và promote** sang "approved" (ghi rõ bằng chứng trong SYS-02 header). |
| Option B | Giữ DRAFT; ghi rõ rằng SYS-02 là architecture reference, không cần approve vì SYS-05 (FUTURE_WORK) đã cover production architecture. |
| Đề xuất mặc định | **KHÔNG đề xuất** — đây là mentor decision. |
| Hệ quả nếu A | SYS-02 có authoritativeness cho Phase B + EPIC-12 |
| Hệ quả nếu B | SYS-02 chỉ là reference; giữ nguyên status DRAFT |
| Thẩm quyền | **Mentor / researcher** |

**D-SYS02-02: OQ-13 (WCSS diagnostic label UI style) — SYS-06 scope**

| Trường | Giá trị |
|---|---|
| Câu hỏi | WCSS diagnostic label nên style như thế nào trong UI? |
| Bằng chứng | SYS-01 §13 OQ-13 ghi "Decision thuộc UI design (SYS-06)"; SYS-06 status: `REVIEW_READY v0.2` (chưa final) |
| Option A | **Sẽ quyết khi SYS-06 final** (current position). |
| Option B | Owner pre-empt SYS-06 với style quyết định. |
| Đề xuất mặc định | **Option A** — chờ SYS-06. |
| Thẩm quyền | **SYS-06 owner** |

### 7.6. Methodology gates (3 WORKING items)

**D-METH-01: Feature set WORKING_ASSUMPTION (6 features) có promote không?**

| Trường | Giá trị |
|---|---|
| Câu hỏi | 6 features `ELIGIBLE_WORKING_ASSUMPTION` có được promote lên `ELIGIBLE` không? |
| Bằng chứng | `METHODOLOGY_LOCK_STATUS.md` §1: feature set ⚠️ WORKING; FE-05 §13, FE-06 §13 ghi rõ 6/14 features ở trạng thái này |
| Option A | **Giữ WORKING_ASSUMPTION** cho đến khi có bằng chứng mới. |
| Option B | Promote lên ELIGIBLE (nếu có evidence mới). |
| Đề xuất mặc định | **Option A** — không có bằng chứng mới; giữ nguyên. |
| Thẩm quyền | **Mentor / researcher** |

**D-METH-02: Preprocessing config C7 có promote không?**

| Trường | Giá trị |
|---|---|
| Câu hỏi | FE-06 C7 (yeo_johnson + robust + median) có được promote từ WORKING_ASSUMPTION lên approved không? |
| Bằng chứng | `METHODOLOGY_LOCK_STATUS.md` §1: preprocessing config ⚠️ WORKING; `EXP01_EXP05_PENDING_DECISIONS.md` §A (FE-06-DATASET-01, EXP04-IMP-01, EXP04-TR-01) đều PENDING |
| Option A | **Giữ WORKING_ASSUMPTION**. |
| Option B | Promote (nếu có evidence mới). |
| Đề xuất mặc định | **Option A** — chưa có evidence mới; giữ nguyên. |
| Thẩm quyền | **Mentor / researcher** |

**D-METH-03: Cross-algorithm ranking có cho phép không?**

| Trường | Giá trị |
|---|---|
| Câu hỏi | Cross-algorithm ranking (vd: "K-Means ổn định nhất") có được phép không? |
| Bằng chứng | `METHODOLOGY_LOCK_STATUS.md` §1: cross-algorithm ranking ⚠️ PENDING, "Not allowed until EPIC-08 Phase B + mentor approval"; AGENTS.md §2.5 cấm best/winner/optimal/recommended; FR-MKT-05 cấm internal metric làm KPI |
| Option A | **Giữ PENDING / NOT ALLOWED** cho đến khi EPIC-08 Phase B + mentor approval. |
| Option B | Cho phép ranking dựa trên tiêu chí đã approve. |
| Đề xuất mặc định | **Option A** — current methodology hard rule. |
| Thẩm quyền | **Mentor / researcher** |

---

## 8. Quyết định cần owner + phân biệt thẩm quyền

### 8.1. Quyết định thuộc owner (technical/business scope)

| ID | Chủ đề | Cần cho |
|---|---|---|
| D-DEV07-OQ-01 | MKT framework mapping 6 E-MKT fields | Unblock Phase B |
| D-DEV07-OQ-02 | CP-04 tokenization canonical | Unblock Phase B |
| D-DEV07-OQ-03 | KPI framework scope | Unblock Phase B |
| D-DEV07-OQ-04 | Export format | (Optional) Phase B enhancement |
| D-SYS01-OQ-02 | MKT framework scope ↔ FR-MKT-03 | Tied to D-DEV07-OQ-01 |

### 8.2. Quyết định thuộc mentor / researcher (methodology)

| ID | Chủ đề |
|---|---|
| D-DEV07-MKT-01 | MKT-01..MKT-05 framework content |
| D-SYS01-OQ-01 | MKT framework timeline |
| D-SYS01-OQ-03 | SYS layer re-implement vs re-use |
| D-SYS01-OQ-05 | PCA/UMAP/t-SNE visualization |
| D-SYS02-01 | SYS-02 promote từ DRAFT |
| D-METH-01 | Feature set promote |
| D-METH-02 | Preprocessing C7 promote |
| D-METH-03 | Cross-algorithm ranking |

### 8.3. Quyết định thuộc SYS-06 owner (UI scope)

| ID | Chủ đề |
|---|---|
| D-SYS02-02 | OQ-13 (WCSS UI style) |

### 8.4. Quyết định thuộc evidence integrity owner

| ID | Chủ đề |
|---|---|
| D-K01-01 | K-01 log file resolution (3 options) |

### 8.5. Quyết định thuộc documentation organization (chỉ khi owner muốn override default)

| ID | Chủ đề |
|---|---|
| D-ORG-DEV05-01..05 | 5 file DEV-05 (đề xuất KEEP all) |
| D-ORG-DEV06-01..03 | 3 file DEV-06 (đề xuất KEEP all) |
| D-ORG-DEV07-01..09 | 9 file DEV-07 (đề xuất KEEP all) |
| D-LANG-DEV05-01..05 | 5 file DEV-05 (đề xuất KEEP current) |
| D-LANG-DEV06-01..03 | 3 file DEV-06 (đề xuất KEEP current) |
| D-LANG-DEV07-01..09 | 9 file DEV-07 (đề xuất KEEP current) |
| D-LANG-IMPL-01 | Policy override: implementation report style = VN narrative? (chỉ nếu owner muốn đổi) |

**Ghi chú:** cho organization + language, mặc định đề xuất KEEP current state. Owner không cần trả lời nếu đồng ý. Nếu owner muốn merge/archive/language change cụ thể, cần ID quyết định mới (chưa liệt kê ở đây vì không có evidence owner muốn thay đổi).

---

## 9. Bảng quyết định tổng hợp — bắt buộc owner review

| ID | Câu hỏi (rút gọn) | Options | Đề xuất mặc định | Thẩm quyền | Priority |
|---|---|---|---|---|---|
| **D-DEV07-OQ-01** | Mapping 6 E-MKT fields ↔ MKT-01..05? | A: mapping như memo §2.1; B: mapping khác | A (nếu OK) | Owner + Mentor | **HIGH** |
| **D-DEV07-OQ-02** | CP-04 §4.1–§4.3 là canonical tokenization? | A: CP-04; B: methodology khác; C: COMPARATIVE default template | A (nếu OK) | Owner + Mentor | **HIGH** |
| **D-DEV07-OQ-03** | KPI framework scope? | A: pass-through MKT-04; B: auto-compute composition; C: external source | A (nếu OK) | Owner | **HIGH** |
| **D-DEV07-OQ-04** | DEV-07 export format Phase B? | A: read-only; B: CSV+JSONL; C: Markdown | A (nếu OK) | Owner | LOW |
| **D-DEV07-MKT-01** | MKT-01..MKT-05 có được tạo không? Khi nào? | A: tạo sớm; B: đợi EPIC-09/10; C: không tạo | — (KHÔNG đề xuất) | Mentor / Researcher | **HIGH** |
| **D-K01-01** | K-01 log file resolution? | A: cung cấp log; B: xóa field + ADR; C: accept orphan + ADR | — (KHÔNG đề xuất) | Owner | **HIGH** |
| **D-SYS01-OQ-01** | MKT timeline (trước SYS-06 hay đợi EPIC-09/10)? | A: trước SYS-06; B: đợi EPIC-09/10; C: song song | — (KHÔNG đề xuất) | Mentor | MEDIUM |
| **D-SYS01-OQ-02** | MKT scope ↔ FR-MKT-03? | A: mapping 6 fields; B: điều chỉnh | A (nếu OK) | Owner + Mentor | MEDIUM (tied to OQ-01) |
| **D-SYS01-OQ-03** | SYS layer re-implement vs re-use? | A: re-use; B: re-implement | A (recommend) | Mentor | MEDIUM |
| **D-SYS01-OQ-05** | PCA/UMAP/t-SNE visualization? | A: OOS (giữ CP-05); B: PCA; C: cả 3 | A (nếu OK) | Mentor | LOW |
| **D-SYS02-01** | SYS-02 promote từ DRAFT? | A: review + promote; B: giữ DRAFT | — (KHÔNG đề xuất) | Mentor | MEDIUM |
| **D-SYS02-02** | OQ-13 WCSS UI style? | A: chờ SYS-06; B: pre-empt | A (nếu OK) | SYS-06 owner | LOW |
| **D-METH-01** | 6 features promote? | A: giữ WORKING; B: promote | A (nếu OK) | Mentor | MEDIUM |
| **D-METH-02** | C7 preprocessing promote? | A: giữ WORKING; B: promote | A (nếu OK) | Mentor | MEDIUM |
| **D-METH-03** | Cross-algorithm ranking? | A: NOT ALLOWED; B: cho phép | A (nếu OK) | Mentor | MEDIUM |

**Phase A (đã RESOLVED 2026-10-10, không cần owner action):**
- D-DEV07-PHASEA-01 (OQ-D07-02): Phase A implement ngay
- D-DEV07-PHASEA-02 (OQ-D07-06): HTML giữ nguyên placeholder
- D-DEV07-PHASEA-03 (OQ-D07-07): KHÔNG tạo ADR mới
- D-DEV07-PHASEA-04 (OQ-D07-08): read-only manifest

**Documentation organization (chỉ cần owner nếu muốn override KEEP):**
- D-ORG-DEV05-01..05, D-ORG-DEV06-01..03, D-ORG-DEV07-01..09: 17/17 đề xuất KEEP.
- D-LANG-DEV05-01..05, D-LANG-DEV06-01..03, D-LANG-DEV07-01..09: 17/17 đề xuất KEEP current language.

---

## 10. Checklist trả lời ngắn (owner duyệt nhanh theo ID + Option)

**Cách trả lời:** mỗi dòng 1 ID + 1 option (A/B/C). Có thể ghi "DEFAULT" nếu đồng ý đề xuất mặc định. Có thể ghi "DEFER" nếu muốn trì hoãn.

```
[ ] D-DEV07-OQ-01  [DEFAULT=A | A | B]
[ ] D-DEV07-OQ-02  [DEFAULT=A | A | B | C]
[ ] D-DEV07-OQ-03  [DEFAULT=A | A | B | C]
[ ] D-DEV07-OQ-04  [DEFAULT=A | A | B | C]
[ ] D-DEV07-MKT-01 [DEFER | A | B | C]    # mentor/researcher
[ ] D-K01-01       [DEFER | A | B | C]
[ ] D-SYS01-OQ-01  [DEFER | A | B | C]    # mentor
[ ] D-SYS01-OQ-02  [DEFAULT=A | A | B]    # tied to OQ-01
[ ] D-SYS01-OQ-03  [DEFAULT=A | A | B]    # mentor
[ ] D-SYS01-OQ-05  [DEFAULT=A | A | B | C] # mentor
[ ] D-SYS02-01     [DEFER | A | B]        # mentor
[ ] D-SYS02-02     [DEFAULT=A | A | B]    # SYS-06 owner
[ ] D-METH-01      [DEFAULT=A | A | B]    # mentor
[ ] D-METH-02      [DEFAULT=A | A | B]    # mentor
[ ] D-METH-03      [DEFAULT=A | A | B]    # mentor

# Phase A (đã RESOLVED — không cần trả lời)
# D-DEV07-PHASEA-01..04 = N/A (status quo)

# Organization (chỉ trả lời nếu muốn merge/archive override)
[ ] D-ORG-DEV05-01..05  [DEFAULT=KEEP all | specify which]
[ ] D-ORG-DEV06-01..03  [DEFAULT=KEEP all | specify which]
[ ] D-ORG-DEV07-01..09  [DEFAULT=KEEP all | specify which]

# Language (chỉ trả lời nếu muốn override)
[ ] D-LANG-DEV05-01..05  [DEFAULT=KEEP all | specify which]
[ ] D-LANG-DEV06-01..03  [DEFAULT=KEEP all | specify which]
[ ] D-LANG-DEV07-01..09  [DEFAULT=KEEP all | specify which]
[ ] D-LANG-IMPL-01       [DEFAULT=NO (giữ EN) | YES (đổi VN narrative)]
```

---

## 11. Điều kiện để Phase E/F được thực thi

| Phase | Điều kiện |
|---|---|
| **Phase E (organization)** | Owner duyệt `D-ORG-DEV05/06/07-*` (mặc định KEEP all) HOẶC chỉ định file cụ thể cần merge/archive + ADR note. **KHÔNG** thực thi nếu owner không trả lời (giữ nguyên theo `docs/README.md` §6 ràng buộc Phase 2B.1). |
| **Phase F (Việt hóa)** | Owner duyệt `D-LANG-DEV05/06/07-*` (mặc định KEEP current) HOẶC chỉ định file cụ thể cần đổi + style guide cụ thể. Nếu `D-LANG-IMPL-01 = YES` (đổi implementation report style = VN narrative) → thực hiện 2 file EN-dominant. |
| **Phase B DEV-07** | Owner duyệt `D-DEV07-OQ-01/-02/-03` (HIGH) + Mentor tạo MKT-01..MKT-05 + Mentor approve `D-SYS01-OQ-01/-02`. |
| **K-01 resolution** | Owner chọn 1 trong 3 phương án `D-K01-01` (HIGH). |
| **SYS-02 finalization** | Mentor decide `D-SYS02-01`. |
| **Methodology gates** | Mentor decide `D-METH-01/-02/-03` + tương ứng PENDING items trong `EXP01_EXP05_PENDING_DECISIONS.md`. |

---

## 12. Hết pack

> **Trạng thái pack tại 2026-10-13:**
> - **Owner decision pack đã sẵn sàng** cho owner review.
> - **0 file DEV-05/06/07 nào bị move/rename/merge/archive/sửa** trong pack này.
> - **0 status methodology nào bị nâng cấp** trong pack này.
> - **0 commit / push / PR / branch** thực hiện.
> - **1 file mới** được tạo: pack này (`docs/system/DEV-05-06-07_owner_decision_pack.md`).
>
> **Next action:** owner review §10 checklist và trả lời theo ID + Option. Sau khi owner duyệt, các quyết định HIGH có thể được thực thi trong phiên kế tiếp (vẫn giữ constraint `AGENTS.md` §2.11: KHÔNG commit/push/PR từ agent).
