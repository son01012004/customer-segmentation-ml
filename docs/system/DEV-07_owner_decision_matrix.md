# DEV-07 — Owner Decision Matrix & Phase A Scope Finalization

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module — Owner Decision Preparation
> **Ngày:** 2026-10-10
> **Trạng thái:** **PHASE A ACCEPTANCE GATE RESOLVED 2026-10-10** —
> ADR-0008 (Option A) accepted; `preprocessing_warning` Option (c)
> accepted; OQ-D07-02/-06/-07/-08 resolved. OQ-D07-01/-03/-04/-05 vẫn
> `REVIEW_REQUIRED` (block Phase B start only).
> **Phạm vi:** Đối chiếu 2 báo cáo planning, xác minh methodology dependency,
> lập decision matrix cho từng hạng mục Phase A, xác định scope cho phép
> triển khai ngay vs scope bị block.
> **Không thuộc task này:** implementation code, modification system
> contract / ADR / prototype HTML, Git operations.

---

## Mục lục

1. [Các điểm đã xác minh](#1-c%C3%A1c-%C4%91i%E1%BB%83m-%C4%91%C3%A3-x%C3%A1c-minh)
2. [So sánh hai planning reports](#2-so-s%C3%A1nh-hai-planning-reports)
3. [Phase A decision matrix](#3-phase-a-decision-matrix)
4. [Owner questions cần quyết định](#4-owner-questions-c%E1%BA%A7n-quy%E1%BA%BFt-%C4%91%E1%BB%8Bnh)
5. [Scope đề xuất được phép triển khai ngay sau owner phê duyệt](#5-scope-%C4%91%E1%BB%81-xu%E1%BA%A5t-%C4%91%C6%B0%E1%BB%A3c-ph%C3%A9p-tri%E1%BB%83n-khai-ngay-sau-owner-ph%C3%AA-duy%E1%BB%87t)
6. [Scope phải tiếp tục bị block](#6-scope-ph%E1%BA%A3i-ti%E1%BA%BFp-t%E1%BB%A5c-b%E1%BB%8B-block)
7. [Citation correction status](#7-citation-correction-status)
8. [Exit criteria để bắt đầu implementation](#8-exit-criteria-%C4%91%E1%BB%83-b%E1%BA%AFt-%C4%91%E1%BA%A7u-implementation)

---

## 1. Các điểm đã xác minh

Tất cả các điểm dưới đây đã được verify bằng `Grep` / `Read` / `Glob` trong
reconnaissance pass trước đó (xem `docs/system/DEV-07_implementation_plan.md`
§2 cho danh sách tài liệu đầy đủ).

### 1.1. MKT-01..MKT-05 vẫn không tồn tại trong repository

- **Verification command**: `Grep pattern="MKT-0[1-5]"` (toàn repo) +
  `Glob pattern="docs/**/MKT-*"` + `Glob pattern="docs/**/MKT_*"`.
- **Kết quả**: 0 file MKT framework tồn tại. References duy nhất đến
  "MKT-01..MKT-05" nằm trong:
  - `docs/system/SYS-01_requirements.md` (§2.8, §6.7, OQ-01/02).
  - `docs/system/SYS-03_data_model.md` (§4.7, §15.1, OQ-DM-02..03, OQ-DM-14).
  - `docs/system/SYS-04_ml_processing_pipeline.md` (§2.1, §3.7, §15.1).
  - `docs/system/SYS-06_ui_ux_design.md` (§9 S-13, §19 OQ #3).
  - `docs/system/ui-prototype/index.html` (§1584–1613 `renderMarketing()`).
  - `docs/system/DEV-07_planning_report.md` và `docs/system/DEV-07_implementation_plan.md`
    (planning artifacts).
  - `docs/system/DEV-03_completion_summary.md`, `docs/system/DEV-03_preprocessing.md`
    (negation context — DEV-03 không có marketing scope).
  - `docs/system/SYS-02_architecture.md` (mentions MKT in placeholder context).
- **Kết luận**: MKT framework confirmed **ABSENT**. Giả định "MKT-01..MKT-05
  đã hoàn thành về mặt nghiệp vụ" của project owner **không có bằng chứng**
  trong repository hiện tại.

### 1.2. SYS-01 §6.7 (FR-MKT-01..06)

| FR | Nội dung | Status |
|---|---|---|
| FR-MKT-01 | REVIEW_REQUIRED gate: chỉ hiển thị khi MKT framework tồn tại. | MUST (gate). |
| FR-MKT-02 | Kế thừa từ MKT framework; KHÔNG tự phát minh. | MUST (when applicable). |
| FR-MKT-03 | Mỗi recommendation phải có Objective, Strategy, Action, KPI, Evidence, Limitation. | SHOULD (when applicable). |
| FR-MKT-04 | KHÔNG campaign automation (no send/schedule/trigger). | MUST. |
| FR-MKT-05 | KHÔNG dùng internal clustering metric (silhouette/DBI/CH/WCSS/ARI/AMI) làm business KPI. | MUST. |
| FR-MKT-06 | KHÔNG dùng DBSCAN noise (label = -1) làm segment target. | MUST. |

### 1.3. SYS-03 §15.1 (E-MKT schema shell)

E-MKT field list (verified):

| Field | Type | Required | Default khi MKT absent |
|---|---|---|---|
| `recommendation_id` | str | conditional | null |
| `segment_id` | FK(E-SEG) | yes | n/a |
| `availability` | enum{AVAILABLE, NOT_AVAILABLE, REVIEW_REQUIRED} | yes | NOT_AVAILABLE |
| `marketing_objective` | str \| null | conditional | null |
| `strategy` | str \| null | conditional | null |
| `recommended_action` | str \| null | conditional | null |
| `kpi` | list[str] \| null | conditional | null |
| `evidence_ref` | list[FK(E-SPR)] | conditional | empty list |
| `limitation` | str \| null | conditional | null |
| `source_framework_version` | str \| null | no | null |
| `computed_at_utc` | str \| null | conditional | null |
| `notes` | str | no | empty |

Constraints (verified):

- `availability` mặc định = `NOT_AVAILABLE` cho tất cả segment trong
  SYS-03 scope.
- `E-MKT.segment_id` UNIQUE → 1 segment có tối đa 1 recommendation
  (1 E-SEG → 0..1 E-MKT).
- KHÔNG tự tạo strategy / KPI / segment name trong Data Model.
- KHÔNG dùng internal clustering metric làm business effectiveness.
- KHÔNG dùng cluster ID = -1 làm input.
- Prototype UI ẩn Marketing section cho đến khi MKT framework tồn tại.

### 1.4. SYS-04 §15.1 (Marketing handoff)

- Marketing = `REVIEW_REQUIRED` (MKT-01..05 absent, SYS-03 §15.1).
- Pipeline chỉ mô tả handoff interface (SegmentProfile → Recommendation
  input), KHÔNG tự tạo recommendation methodology.
- Prototype UI ẩn Marketing section cho đến khi MKT framework tồn tại
  (SYS-01 FR-MKT-01).
- Khi MKT framework tồn tại: `E-MKT.availability = AVAILABLE`; schema
  fields populate từ MKT framework.

### 1.5. SYS-06 §9 (S-13 Marketing placeholder)

Verified tại `docs/system/ui-prototype/index.html` §506 + §1584–1613:

- Route `#/marketing` đã đăng ký (`render: renderMarketing`).
- `renderMarketing()` hiện là static placeholder với:
  - `mockBanner()` ở top.
  - Big badge `statusBadge("REVIEW_REQUIRED")`.
  - Heading "Marketing framework pending".
  - Body giải thích MKT-01..MKT-05 chưa tồn tại.
  - Bulleted list "What this module will do (when MKT framework exists)".

→ HTML prototype đã đúng theo SYS-06 §9 S-13 spec; không cần sửa ở Phase A.

### 1.6. Methodology constraints cần enforce

| Constraint | Nguồn | Áp dụng cho DEV-07 |
|---|---|---|
| **CON-07** (internal metrics only) | AGENTS.md §2.5; ADR-0004 | KPI blocklist (FR-MKT-05). |
| **CON-08** (DBSCAN noise not segment) | CP-01 §4.4; CP-05 §12 | Exclude `segment_id = -1` khỏi MKT input (FR-MKT-06). |
| **CON-09** (no cross-algorithm mapping) | CP-05 §14 | KHÔNG tạo K-Means C1 ↔ GMM C3 mapping. |
| **CON-12** (Marketing inherits MKT) | SYS-01 §6.7; AGENTS.md §2.1 | KHÔNG tự phát minh strategy/KPI/action. |
| **CON-16** (status taxonomy) | CP-01 §3.3 | NAMED/COMPARATIVE/NOISE/NOT_AVAILABLE. |
| **FR-SEG-08** (no hard-code segment name) | AGENTS.md §3; CP-05 §6.4 | KHÔNG tự đặt "Champions", "Loyal", "VIP", "at-risk". |

### 1.7. CP-04 — Construction Rules vs Sample Names

Đã verify: CP-04 **không** có "S1–S4 archetypes" canonical templates.
Phần có cấu trúc template-like thực sự:

- **CP-04 §4.1**: RFM core tiers (Recency × Frequency × Monetary; mỗi
  trục 3 tiers: HIGHER / LOWER / COMPARABLE → Recent/Older/Mixed, etc.).
- **CP-04 §4.2**: Behavioural modifiers (LongTenured, IrregularCadence,
  Bulk, Active) với điều kiện HIGHER direction + HIGH classification.
- **CP-04 §4.3**: Construction rules (ghép `[RecencyTier] [FrequencyTier]`
  + MonetaryTier nếu condition + behavioural modifier; tổng ≤ 4 từ;
  fallback "Comparative Segment A/B/C").
- **CP-04 §4.4**: Hard NO marketing terms.
- **CP-04 §5.3**: **Sample segment names** (concrete examples only).

### 1.8. KPI có thể được hỗ trợ bởi nguồn hiện tại (không suy diễn)

Các KPI có thể compute từ **research core** (KHÔNG phải prototype layer):

- Average order value → từ `data/processed/...` (FE-04 evidence).
- Repeat purchase frequency → từ RFM `Frequency` feature.
- Product category diversity → từ transaction-level aggregates.
- Customer tenure growth → từ `TenureDays`.

Lưu ý: Prototype layer **KHÔNG** compute KPI từ raw data — chỉ inherit
từ MKT-04 framework khi Phase B. Phase A `kpi = None`.

Các KPI **KHÔNG ĐƯỢC PHÉP** (FR-MKT-05, CON-07): silhouette, DBI, CH,
WCSS, ARI, AMI, runtime — bất kỳ internal clustering metric.

---

## 2. So sánh hai planning reports

| Aspect | `DEV-07_planning_report.md` (existing, đã đính chính) | `DEV-07_implementation_plan.md` (new) |
|---|---|---|
| Scope | Phase 1 reconnaissance + planning | Phase 1 reconnaissance + planning |
| MKT absence analysis | ✅ §4 | ✅ §3 |
| Input contract from DEV-06 | ✅ §5.3, §6 | ✅ §4 (verified against `manifest.py`) |
| E-MKT schema | ✅ §6.1, §6.2 | ✅ §5.7 |
| Two-phase approach | ✅ §4.3 | ✅ §5.3, §10 |
| FR-MKT-01..06 traceability | ✅ §10.1 | ✅ §5, §11 |
| **S1–S4 archetypes citation** | **CITATION SAI → ĐÃ ĐÍNH CHÍNH** (§7.1, §7.2, §7.3, §8.1.2, §9.3, §11.1, §11.2, §12.2/OQ-D07-03, §12.5/A-02) | **KHÔNG có** — sử dụng CP-04 §4.1–§4.3 ngay từ đầu (§5.3, §5.4, CF-D07-04) |
| Open questions | 5 (OQ-D07-01..05) | 8 (OQ-D07-01..08) |
| Risks | 7 (R-01..07) | 8 (R-01..08) |
| Blocker analysis | 1 (CF-D07-01) | 4 (B-01..B-04) |
| Phase A files | 18 (§11.1) | 25 (§9.1) |
| Test count | 85 (§11.2) | ~84 (§10.3) |
| Hard stop gate | ✅ §15 | ✅ §13.5 |
| Owner questions | 5 | 8 (extra OQ-D07-06..08 về HTML scope, export scope, ADR decision) |
| Recommendation mapping | S1–S4 (sai) | CP-04 §4.1–§4.3 tokenization |

### 2.1. Mâu thuẫn giữa hai báo cáo

Sau khi đính chính citation S1–S4 ở `DEV-07_planning_report.md`, **không
còn mâu thuẫn substantive** giữa hai báo cáo. Hai báo cáo:

- **Đồng thuận** về: MKT framework absent, two-phase approach, FR-MKT-01..06
  interpretation, input contract từ DEV-06, E-MKT schema shell, methodology
  gates (FR-MKT-05, FR-MKT-06, FR-SEG-08, CON-12).
- **Khác biệt** về: scope chi tiết (25 vs 18 files), open questions (8 vs 5),
  risks (8 vs 7), blocker analysis (4 vs 1), detail về mapping logic (CP-04
  §4.1–§4.3 vs S1–S4 đã đính chính).

### 2.2. Citation không chính xác đã đính chính

Xem chi tiết §7 bên dưới.

### 2.3. Owner questions đã được làm rõ bởi nguồn hiện có

| OQ | Source evidence đã có | Status |
|---|---|---|
| OQ-D07-06 (Phase A có mở rộng HTML placeholder không) | SYS-06 §9 S-13 đã đúng spec; placeholder hiện đủ cho Phase A. | Owner quyết định có mở rộng hay không. |
| OQ-D07-07 (Có tạo ADR mới cho DEV-07 không) | ADR-0005 + planning artifacts đã đủ cho Phase A; ADR mới chỉ cần nếu methodology thay đổi. | Owner quyết định. |
| OQ-D07-08 (Phase A có export hay read-only) | FR-REPORT-01..03 chỉ "view/export" cho prototype, KHÔNG có MUST cho Phase A. | Owner quyết định. |

### 2.4. Đề xuất chưa có căn cứ

Các đề xuất trong `DEV-07_planning_report.md` §7.3 (Phase B mapping
"S1–S4 → MKT template") **thiếu căn cứ** vì S1–S4 không tồn tại trong
CP-04. Đã sửa trong §7.1 đính chính (xem §7 bên dưới).

Các đề xuất trong `DEV-07_implementation_plan.md` §8.3 (`marketing_id`
9 canonical fields), §5.7 (manifest schema), §10.1 (17 bước Phase A)
**chưa được owner review** — đây là planning proposal, không phải
contract.

### 2.5. Scope Phase A có thể vượt quá contract

| Phase A scope item | Có vượt contract? | Bằng chứng |
|---|---|---|
| Tạo `prototype/marketing/` package | Không — mirror `prototype/segmentation/`, `prototype/evaluation/`, `prototype/clustering/` packages đã có. | AGENTS.md §2.13 (reusable logic ở `src/customer_segmentation/`). |
| Implement `marketing_id` derivation | Không — mirror `segmentation_id` 8-field pattern từ `segmentation/storage.py`. | DEV-06 manifest pattern. |
| Phase A render placeholder HTML (giữ nguyên) | Không — SYS-06 §9 S-13 đã đúng spec; placeholder §1584–1613 đã implement. | Đã verify `index.html`. |
| Phase A mở rộng HTML placeholder thêm per-segment table | **Có thể vượt scope FR-MKT-01..06** — chỉ FR-MKT-01 (gate), FR-MKT-02 (no invent), FR-MKT-04 (no automation), FR-MKT-05 (no internal metric), FR-MKT-06 (no noise) đang active. FR-MKT-03 chỉ SHOULD khi MKT exists. | SYS-01 §6.7 — cần owner quyết định UI scope Phase A. |
| CSV + JSONL export Phase A | **Có thể vượt scope FR-REPORT-01..03** — đó là SHOULD, không MUST. | SYS-01 §6.8 — cần owner quyết định export scope. |
| Tạo ADR mới `0007-dev07-prototype-scope.md` | **Có thể vượt scope ADR-0005** — ADR-0005 đã cover prototype layer architecture. ADR mới chỉ cần nếu methodology thay đổi. | `docs/decisions/README.md` immutability convention. |

### 2.6. Đề xuất giữ / sửa / đánh dấu superseded

| File | Đề xuất |
|---|---|
| `docs/system/DEV-07_planning_report.md` | **Đã đính chính surgical** (12 chỗ S1–S4 → CP-04 §4.1–§4.3). Có thể giữ làm "early reconnaissance draft" với §7.1 note rằng đã đính chính. KHÔNG đánh dấu superseded. |
| `docs/system/DEV-07_implementation_plan.md` | **Giữ** làm canonical implementation plan với evidence matrix đầy đủ, owner questions, decision matrix. |
| Báo cáo này (`DEV-07_owner_decision_matrix.md`) | **Tạo mới** để owner ra quyết định scope Phase A. |

---

## 3. Phase A decision matrix

Bảng dưới phân loại từng hạng mục theo 4 trạng thái:

- **[CONTRACT]** = việc đã được contract cho phép (SYS-01..06, AGENTS.md, ADR).
- **[PROPOSAL]** = chỉ là đề xuất trong planning; cần owner confirm.
- **[OWNER]** = cần owner/mentor quyết định trước khi implement.
- **[BLOCKED]** = bị block vì thiếu MKT methodology.

| Hạng mục | Nguồn contract | Đề xuất | Rủi ro | Cần owner approval? |
|---|---|---|---|---|
| **Core package** `src/customer_segmentation/prototype/marketing/` | AGENTS.md §2.13 (reusable logic ở `src/customer_segmentation/`); mirror `prototype/segmentation/` package pattern | Tạo package với 13 files: `__init__.py`, `scope.py`, `exceptions.py`, `manifest.py`, `storage.py`, `config_loader.py`, `logging_config.py`, `mkt_framework_loader.py`, `validation.py`, `recommendation.py`, `pipeline.py`, `display.py`, `__init__.py` | Low — pattern đã có. | **Không** ([CONTRACT] — mirror existing pattern). |
| **Input validation** | SYS-01 §6.7 FR-MKT-01..06; SYS-03 §15.1 E-MKT constraints; CP-01 §4.4 (noise); CP-04 §4.4 (no marketing terms); ADR-0006 (noise default). | Read-only DEV-06 manifest; regex check `^seg_[0-9a-f]{24}$`; `research_safety.scope = "PROFILED_PROTOTYPE"`; noise excluded via `is_noise`/`segment_id=-1`; duplicate `segment_id` reject; forbidden tokens (champion/loyal/VIP/at-risk/churn/LTV/CLV) check; KPI blocklist (silhouette/DBI/CH/WCSS/ARI/AMI/runtime). | Medium — false-positive noise exclusion. | **Không** ([CONTRACT] — direct enforcement). |
| **Manifest/storage integration** | `src/customer_segmentation/prototype/segmentation/{manifest,storage}.py` pattern; SYS-03 §15.1 E-MKT fields. | Mirror DEV-06 dataclass pattern với atomic write; `marketing_id = "mkt_" + SHA-256(JSON canonical(9 fields))[:24]`; storage path `<seg_dir>/marketing/<mkt_id>/`. | Low — pattern đã có. | **Không** ([CONTRACT] — mirror pattern). |
| **Recommendation schema shell** | SYS-03 §15.1 E-MKT fields; SYS-01 §6.7 FR-MKT-03 (6 fields when applicable). | Tạo `MarketingRecommendationManifest` với đầy đủ 12 fields; `availability = REVIEW_REQUIRED` cho Phase A; `marketing_objective`/`strategy`/`recommended_action`/`limitation` = `"PENDING_MKT_FRAMEWORK"`; `kpi = None`; `evidence_ref = []` (auto-populated paths); `research_safety.scope = "MARKETING_PROTOTYPE"`. | Low — chỉ là schema. | **Không** ([CONTRACT] — direct mapping). |
| **HTML `#/marketing`** | SYS-06 §9 S-13 spec; `index.html` §1584–1613 hiện đúng spec. | **Giữ nguyên** placeholder hiện tại ở Phase A; KHÔNG mở rộng trừ khi owner approve. | Medium — owner có thể muốn thêm per-segment table. | **Có** ([OWNER] — OQ-D07-06). |
| **Export** | SYS-01 §6.8 FR-REPORT-01..03 (SHOULD, không MUST); FR-MKT-04 (no campaign automation). | CSV + JSONL `recommendations.csv` + `recommendations.jsonl` ở Phase A; KHÔNG Markdown report. | Low. | **Có** ([OWNER] — OQ-D07-08). |
| **Synthetic fixtures** | AGENTS.md §2.1 (no invent data); FR-MKT-02 (no invent framework). | Phase A KHÔNG cần synthetic fixtures vì chỉ REVIEW_REQUIRED shell. Tests dùng synthetic manifest ở test fixtures (`tests/fixtures/`). | Low — không có data fake trong output thật. | **Không** ([CONTRACT] — synthetic only ở test scope). |
| **Tests** | AGENTS.md §2.13 (public behavior mới phải có ≥1 unit test); FR-MKT-05/06 methodology gate tests. | ~84 tests across 10 files: manifest schema, scope enums, storage/ID, config loader, logging, MKT framework loader (absent + present placeholder), validation (input + KPI blocklist + forbidden tokens + noise exclusion + duplicate), recommendation builder (per-segment + Phase A REVIEW_REQUIRED + Phase B AVAILABLE placeholder), pipeline Stage A–H, display, research_safety, CLI, methodology gate. | Medium — tests có thể overspecify Phase B behavior khi MKT absent. | **Không** ([CONTRACT] — Phase A tests chỉ cover Phase A paths). |
| **ADR** | `docs/decisions/README.md` immutability convention; ADR-0005 + ADR-0006 cover prototype scope. | **KHÔNG tạo ADR mới** ở Phase A. Nếu MKT framework sau này conflict với ADR-0003/0004/0005/0006 → tạo ADR mới. | Low — ADR-0005 đã cover prototype. | **Có** ([OWNER] — OQ-D07-07). |

### 3.1. Bổ sung decision matrix: Phase B scope (cho context)

| Hạng mục | Status | Bằng chứng |
|---|---|---|
| Recommendation generation thực sự (Strategy/Action/Objective populated) | [BLOCKED] | MKT-01..MKT-05 absent. |
| Mapping logic CP-04 tokenization → MKT template | [BLOCKED] | Cần MKT-02/MKT-03 templates. |
| KPI computation từ framework definitions | [BLOCKED] | Cần MKT-04 framework. |
| Limitation framework integration | [BLOCKED] | Cần MKT-05 framework. |
| Per-segment template resolution | [BLOCKED] | Phụ thuộc MKT framework. |
| HTML Phase B mockup (per-archetype filter, per-segment fields) | [BLOCKED] | Phụ thuộc MKT framework design. |

---

## 4. Owner questions cần quyết định

| OQ | Câu hỏi | Default recommendation | Impact |
|---|---|---|---|
| **OQ-D07-01** | MKT-01..MKT-05 có được tạo và approve trước Phase B không? | Cần owner confirm timeline. | Block toàn bộ Phase B. |
| **OQ-D07-02** | Phase A có implement ngay (REVIEW_REQUIRED shell) hay đợi MKT framework xong rồi implement trực tiếp Phase B? | Recommend **Phase A ngay** (low risk, contract đầy đủ). | Timeline. |
| **OQ-D07-03** | CP-04 §4.3 construction rules có phải canonical tokenization cho Phase B mapping không? | Recommend **CP-04 §4.1–§4.3** (verified từ source). | Phase B mapping logic. |
| **OQ-D07-04** | KPI definitions trong MKT-04 dùng nên ở đơn vị nào — survey-based / transaction-based / composition? | Không áp dụng Phase A (kpi=None). | Phase B only. |
| **OQ-D07-05** | DEV-07 export format? | Recommend CSV + JSONL (mirror DEV-06). | Phase A export scope. |
| **OQ-D07-06** | Phase A có mở rộng `renderMarketing()` HTML placeholder thêm per-segment table (từ DEV-06 manifest) hay giữ nguyên placeholder hiện tại? | Recommend **giữ nguyên** placeholder cho đến Phase B; Phase A không cần UI mở rộng. | UI scope Phase A. |
| **OQ-D07-07** | Có tạo ADR mới `0007-dev07-prototype-scope.md` cho DEV-07 Phase A scope không? | Recommend **KHÔNG** ở Phase A — ADR-0005 đã cover prototype layer. ADR mới chỉ cần khi MKT framework adopt. | ADR scope. |
| **OQ-D07-08** | Phase A có cho phép export (CSV + JSONL) hay read-only (chỉ `marketing_manifest.json`)? | Recommend **read-only manifest** ở Phase A. CSV/JSONL chỉ ở Phase B khi có recommendation thực. | Export scope Phase A. |

### 4.1. OQ cần resolve trước khi bắt đầu implementation

- **OQ-D07-06** (HTML scope): cần quyết trước.
- **OQ-D07-07** (ADR): cần quyết trước.
- **OQ-D07-08** (export): cần quyết trước.

### 4.2. OQ có thể resolve sau (Phase A không block)

- OQ-D07-01..05 (MKT framework) — Phase A không cần MKT; chỉ cần để
  unblock Phase B.

---

## 5. Scope đề xuất được phép triển khai ngay sau owner phê duyệt

Sau khi owner approve OQ-D07-06, OQ-D07-07, OQ-D07-08, Phase A có thể
triển khai với scope sau (verbatim từ `DEV-07_implementation_plan.md` §10.1):

### 5.1. Files đề xuất tạo (13 source + 1 config + 1 script + 10 test files)

| Path | Lý do |
|---|---|
| `src/customer_segmentation/prototype/marketing/__init__.py` | Public API surface. |
| `src/customer_segmentation/prototype/marketing/scope.py` | Scope enums. |
| `src/customer_segmentation/prototype/marketing/exceptions.py` | Exception classes. |
| `src/customer_segmentation/prototype/marketing/manifest.py` | MarketingRecommendationManifest dataclass + I/O. |
| `src/customer_segmentation/prototype/marketing/storage.py` | `derive_marketing_id()`, path resolution. |
| `src/customer_segmentation/prototype/marketing/config_loader.py` | `load_dev07_config()`. |
| `src/customer_segmentation/prototype/marketing/logging_config.py` | Per-stage logging. |
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | Returns None if absent (Phase A). |
| `src/customer_segmentation/prototype/marketing/validation.py` | Input + KPI blocklist + forbidden tokens. |
| `src/customer_segmentation/prototype/marketing/recommendation.py` | Per-segment builder. |
| `src/customer_segmentation/prototype/marketing/pipeline.py` | Stage A–H. |
| `src/customer_segmentation/prototype/marketing/display.py` | Format functions. |
| `scripts/dev07_run_marketing.py` | CLI entry point. |
| `configs/dev07_marketing.yaml` | DEV-07 config. |
| `tests/test_dev07_*.py` (10 files, ~84 tests) | Unit tests. |

### 5.2. Hard constraints Phase A

- **Read-only** DEV-06 contracts; **không modify** DEV-02..06 modules.
- **Không** thêm dependencies mới (`pyproject.toml` không sửa).
- **Không** Git operations (commit/push/PR/branch).
- **Không** modify `AGENTS.md`, `.gitignore`, `SYS-*`, `DEV-*`, `pyproject.toml`.
- **Không** thêm marketing terms ("champion", "loyal", "VIP", "at-risk",
  "churn", "LTV", "CLV") trong output.
- **Không** dùng internal clustering metric (silhouette/DBI/CH/WCSS/ARI/AMI/runtime)
  làm KPI.
- **DBSCAN noise** (`segment_id=-1`) **luôn** exclude.
- **`research_safety.scope = "MARKETING_PROTOTYPE"`**, `automatically_promoted_to_research=False`,
  `appeared_in_research_evidence=False` always.

### 5.3. Phase A output

- `marketing_manifest.json` (12 fields, `availability=REVIEW_REQUIRED`).
- `recommendations.csv` (per recommendation flat table).
- `recommendations.jsonl` (per recommendation nested JSON).

Nếu OQ-D07-08 được approve là "read-only" → chỉ `marketing_manifest.json`
+ skip CSV/JSONL.

---

## 6. Scope phải tiếp tục bị block

| Item | Blocker | Unblock condition |
|---|---|---|
| Recommendation generation thực sự | MKT-01..MKT-05 absent | Tạo MKT framework + owner approve. |
| Strategy/Action/Objective populate | MKT-02/MKT-03 absent | Tương tự. |
| KPI computation từ framework | MKT-04 absent | Tương tự. |
| Limitation framework integration | MKT-05 absent | Tương tự. |
| Cross-segmentation compare thật sự | Phase A chỉ hỗ trợ single segmentation | (a) MKT framework có compare semantics, hoặc (b) owner quyết Phase A có compare placeholder. |
| HTML Phase B mockup | MKT framework design chưa biết | (a) MKT framework design xong, (b) owner approve UI mockup. |
| Tự phát minh bất kỳ marketing framework | AGENTS.md §2.1 cấm | Không bao giờ unblock — đây là hard rule. |

### 6.1. Phase A vẫn hợp lệ dù bị block

Phase A (REVIEW_REQUIRED shell) **không** cần MKT framework. Phase A
chỉ cần:

- DEV-06 `SegmentationManifest v1.0.0` (đã có).
- SYS-03 §15.1 E-MKT schema shell (đã có).
- SYS-06 §9 S-13 placeholder (đã có).
- ADR-0005 Option A architecture (đã có).

→ Phase A có thể implement **ngay** sau khi owner approve OQ-D07-06,
OQ-D07-07, OQ-D07-08.

---

## 7. Citation correction status

### 7.1. Citation đã đính chính

Trong `docs/system/DEV-07_planning_report.md`, citation "S1–S4 archetypes
(CP-04 §5.3)" — đã được verify là **không chính xác**:

- CP-04 §5.3 chỉ chứa **sample segment names** (concrete examples), không
  có archetype template S1–S4.
- Phần có cấu trúc template-like thực sự là **CP-04 §4.1–§4.3** (RFM
  tiers + behavioural modifiers + construction rules).

**Đã thực hiện 8 StrReplace surgical** (không refactor toàn bộ file):

| StrReplace # | Section | Thay đổi |
|---|---|---|
| 1 | §7.1 | Section header + table + hard constraint → định nghĩa lại với CP-04 §4.1, §4.2, §4.3. |
| 2 | §7.2 (mapping flow) | "Map: CP-04 segment_name → MKT archetype" → "Map: CP-04 segment_name → MKT template (per CP-04 §4.3 tokenization)". |
| 3 | §7.3 (MKT content) | "MKT-02 | Marketing Objective templates per archetype (S1–S4 + COMPARATIVE)" → "MKT-02 | ... per CP-04 §4.3 tokenization ...". |
| 4 | §9.3 (ambiguous mapping) | 3 dòng về "S1–S4" → reframe theo CP-04 §4.3. |
| 5 | §11.1 (file tree) | `mapping.py | archetype_matching(), S1-S4 template resolution` → `mapping.py | cp04_tokenization(), CP-04 §4.3 mapping resolution`. |
| 6 | §11.2 (test matrix) | "Mapping | S1-S4 archetypes, COMPARATIVE ..." → "Mapping | CP-04 §4.3 tokenization, COMPARATIVE ...". |
| 7 | §12.2 (OQ-D07-03) | "S1–S4 archetypes (CP-04 §5.3) có phải là canonical ..." → "CP-04 §4.3 construction rules có phải là canonical tokenization ...". |
| 8 | §12.5 (A-02) | "S1–S4 archetypes từ CP-04 §5.3 là appropriate base" → "**INVALID** — citation sai được phát hiện sau reconnaissance ...". |
| 9 | §8.1.2 (Phase B UI mockup) | 6 dòng "S1" trong UI mockup text → reframe theo CP-04 tokenization. |

### 7.2. Verification sau đính chính

- **Còn lại 2 chỗ chứa "S1–S4"** trong file (intentional):
  - **Line 474** trong §7.1 — note giải thích citation sai đã được đính
    chính (documentation-of-correction).
  - **Line 908** trong §12.5 A-02 — note **INVALID** assumption.
- Cả 2 chỗ đều là documentation-of-correction, không phải citation
  sai còn sót lại.

### 7.3. Không có "out-of-scope changes"

- File `DEV-07_planning_report.md` là **untracked** (chưa commit).
- `git diff` cho thấy toàn bộ file là addition; không có pre-existing
  content cần bảo vệ ngoài scope.
- Tất cả 8 StrReplace chỉ chạm vào citation S1–S4 và context trực tiếp
  liên quan — không refactor bất kỳ section nào khác.

---

## 8. Exit criteria để bắt đầu implementation

### 8.1. Owner approval gate (RESOLVED 2026-10-10 cho Phase A accept)

Implementation Phase A đã được chấp thuận cho tất cả điều kiện sau:

```
✅ Owner approve scope Phase A (Section 5 của báo cáo này).
✅ Owner quyết định OQ-D07-06 (HTML scope): "giữ nguyên placeholder"
   — RESOLVED 2026-10-10.
✅ Owner quyết định OQ-D07-07 (ADR): "KHÔNG tạo ADR mới" — RESOLVED
   2026-10-10. (ADR-0008 created + accepted cho canonical version form.)
✅ Owner quyết định OQ-D07-08 (export): "read-only manifest" — RESOLVED
   2026-10-10.
✅ Owner quyết định OQ-D07-02 (timeline): "Phase A ngay" — RESOLVED
   2026-10-10.
✅ Owner quyết định ADR-0008 (canonical version form): Option A
   "aggregate MKT-01..05__vN" — RESOLVED 2026-10-10.
✅ Owner quyết định preprocessing_warning carry-over: Option (c)
   "không carry forward Phase A" — RESOLVED 2026-10-10.
⬜ OQ-D07-03 (CP-04 §4.3 mapping): chưa quyết — KHÔNG block Phase A
   accept (Phase A không thực hiện mapping); block Phase B start.
```

### 8.2. Khi nào thì có thể bắt đầu code

- **Có thể bắt đầu code Phase A** khi owner approve tất cả OQ ở §8.1.
- **KHÔNG thể** bắt đầu Phase B cho đến khi MKT-01..MKT-05 tồn tại và
  owner approve Phase B scope.

### 8.3. Validation trước khi tuyên bố Phase A READY

Theo AGENTS.md §2.8:

```
✅ pytest tests/test_dev07_*.py  (all ~84 tests pass)
✅ ruff check .                  (clean)
✅ black --check .               (clean)
✅ marketing_manifest.json SHA-256 stable across rerun (NFR-01)
✅ Methodology gate test PASS (no forbidden tokens)
✅ research_safety block always False / MARKETING_PROTOTYPE
✅ DBSCAN noise count correctly reported in n_segments_noise
✅ No new dependencies in pyproject.toml
✅ No modification of AGENTS.md, .gitignore, SYS-*, DEV-02..06,
   pyproject.toml
```

### 8.4. Phase B unblock criteria

```
✅ MKT-01..MKT-05 exists in docs/marketing/ (or equivalent path)
✅ Owner approve Phase B scope
✅ OQ-D07-01 resolved (MKT framework scope matches SYS-01 §6.7)
✅ OQ-D07-04 resolved (KPI unit definitions)
✅ Phase A all validation passed
✅ (Optional) ADR mới nếu methodology conflicts with ADR-0003..0006
```

---

## Phụ lục A — Summary table

| Decision point | Status | Owner approval needed? |
|---|---|---|
| Phase A implement ngay (REVIEW_REQUIRED shell) | [CONTRACT + PROPOSAL] | **Có** — OQ-D07-02. |
| Core package `prototype/marketing/` | [CONTRACT — mirror pattern] | Không. |
| Input validation (noise, KPI blocklist, forbidden tokens) | [CONTRACT — direct enforcement] | Không. |
| Manifest schema shell (12 fields, `availability=REVIEW_REQUIRED`) | [CONTRACT — direct mapping] | Không. |
| Storage path mirror DEV-06 | [CONTRACT — mirror pattern] | Không. |
| `marketing_id` 9-field SHA derivation | [PROPOSAL] | Không (low risk). |
| HTML placeholder giữ nguyên | [CONTRACT — SYS-06 §9 đúng spec] | **Có** — OQ-D07-06. |
| HTML mở rộng per-segment table | [PROPOSAL] | **Có** — OQ-D07-06. |
| Export read-only (chỉ manifest) | [PROPOSAL] | **Có** — OQ-D07-08. |
| Export CSV + JSONL | [PROPOSAL] | **Có** — OQ-D07-08. |
| ADR mới `0007-dev07-prototype-scope.md` | [PROPOSAL] | **Có** — OQ-D07-07. |
| Không tạo ADR mới | [CONTRACT — ADR-0005 đã cover] | **Có** — OQ-D07-07. |
| CP-04 §4.3 tokenization cho Phase B mapping | [CONTRACT — verified source] | **Có** — OQ-D07-03. |
| Synthetic fixtures chỉ ở test scope | [CONTRACT — AGENTS.md §2.1] | Không. |
| Tests ~84 với methodology gate | [CONTRACT — AGENTS.md §2.13] | Không. |
| Phase B recommendation generation | [BLOCKED — MKT absent] | **Có** — OQ-D07-01. |

---

## Phụ lục B — Glossary

| Thuật ngữ | Ý nghĩa |
|---|---|
| **[CONTRACT]** | Việc đã được contract cho phép qua SYS-01..06, AGENTS.md, hoặc ADR. |
| **[PROPOSAL]** | Chỉ là đề xuất trong planning; cần owner confirm. |
| **[OWNER]** | Cần owner/mentor quyết định trước khi implement. |
| **[BLOCKED]** | Bị block vì thiếu MKT methodology. |
| **S1–S4 archetypes** | Citation sai trong bản gốc planning_report; **KHÔNG tồn tại** trong CP-04. |
| **CP-04 §4.3 construction rules** | Quy tắc ghép `[RecencyTier] [FrequencyTier] [MonetaryTier?] [Modifier?]` từ CP-04 §4.1 + §4.2 + §4.3. |
| **Phase A** | DEV-07 implementation khi MKT-01..MKT-05 chưa tồn tại (REVIEW_REQUIRED shell). |
| **Phase B** | DEV-07 implementation khi MKT-01..MKT-05 đã tồn tại và được approve. |

---

*File này là DEV-07 Owner Decision Matrix. KHÔNG implement code. Chờ
owner review và approval trước khi bắt đầu DEV-07 Phase A.*