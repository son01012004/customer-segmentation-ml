# SYS-06 — UI/UX Design + Interactive HTML Prototype

> **Mã tài liệu:** SYS-06
> **Tên:** **UI/UX Design + Interactive HTML Prototype**
> **Trạng thái:** `REVIEW_READY v0.2` — Phase: design + prototype, **không phải** EPIC-12 production frontend.
> **Ngày:** 2026-10-07 (v0.1 initial; v0.2 review pass)
> **Phạm vi:**
> - Information Architecture, UX flow, screen inventory.
> - Component system, visual direction, interaction / animation, accessibility, responsive.
> - API → UI mapping (SYS-05) và Research → UI traceability.
> - Interactive HTML prototype mở được trực tiếp trên trình duyệt.
> **NGOÀI phạm vi:**
> - React / production frontend (thuộc EPIC-12).
> - Backend / database / API implementation thật.
> - Methodology / RQ / algorithm scope / preprocessing policy change.
> - Tự tạo MKT framework, segment names, "best algorithm" claim.
> - Git operations (commit / push / PR / merge).

> **Quy ước:**
> - Tiếng Việt cho mô tả UX; tiếng Anh cho identifier / endpoint / schema.
> - Thuật ngữ ML giữ nguyên tên gốc (K-Means, silhouette, ARI, ...).
> - Mọi số liệu / policy đều có nguồn trỏ về `SYS-01..05` / ADR / methodology.
> - Mock data trong prototype được đánh dấu rõ `Prototype mock data`.
> - **Canonical API status enum** (per `SYS-05` §G.3):
>   `PENDING` / `RUNNING` / `SUCCEEDED` / `FAILED` / `CANCELLED` /
>   `TIMEOUT`. UI hiển thị qua **display label** mapping (xem §10.4)
>   nhưng underlying value là API enum.

---

## Mục lục

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Users / Roles](#3-users--roles)
4. [UX Principles](#4-ux-principles)
5. [Information Architecture](#5-information-architecture)
6. [Navigation](#6-navigation)
7. [User Flows](#7-user-flows)
8. [Screen Inventory](#8-screen-inventory)
9. [Screen Specifications](#9-screen-specifications)
10. [Component System](#10-component-system)
11. [Visual Design Direction](#11-visual-design-direction)
12. [Interaction & Animation](#12-interaction--animation)
13. [State Design](#13-state-design)
14. [Accessibility](#14-accessibility)
15. [Responsive Behavior](#15-responsive-behavior)
16. [API → UI Mapping](#16-api--ui-mapping)
17. [Research → UI Traceability](#17-research--ui-traceability)
18. [Prototype Structure](#18-prototype-structure)
19. [Open Questions / Review Findings](#19-open-questions--review-findings)
20. [Out of Scope](#20-out-of-scope)
21. [Acceptance Criteria](#21-acceptance-criteria)
22. [Implementation Handoff to EPIC-12](#22-implementation-handoff-to-epic-12)
23. [Appendix A — Glossary](#appendix-a--glossary)
24. [Appendix B — Change Log](#appendix-b--change-log)

---

## 1. Purpose

SYS-06 đặc tả **UI/UX design** và cung cấp **interactive HTML prototype**
cho hệ thống Customer Segmentation ML (research-oriented), phục vụ
hai mục tiêu:

1. Cho mentor / human researcher / collaborator review trải nghiệm sử
   dụng prototype trước khi EPIC-12 implement frontend thật.
2. Làm **UI reference chính** cho EPIC-12 (sau này): cấu trúc màn
   hình, component, behavior, mapping với API, mapping với research
   evidence.

Prototype phải:

- Phản ánh đúng `SYS-01..05` contract và research baseline đã freeze.
- Cho thấy hệ thống là **research / analytical software** (không phải
  AI chatbot hay generative dashboard).
- Giúp user **hiểu trạng thái hệ thống và evidence** — không cố làm
  cho hệ thống "trông thông minh".

---

## 2. Scope

### 2.1 In scope

| Hạng mục | Phạm vi |
| --- | --- |
| Information architecture | Site map, navigation model |
| UX flows | 1 primary flow (Dataset → Config → Experiment → Evaluation → Profile) + 1 secondary flow (Reports) + Audit/supporting audit view (right rail / in-page only, không phải screen riêng) |
| Screen inventory | 13 màn hình chính (xem §8) |
| Screen specifications | Mục đích, components, data shown, actions, API mapping, states, research constraints |
| Component system | Buttons, inputs, tables, badges, modals, tabs, charts, navigation, status indicators |
| Visual direction | Typography, color tokens, spacing, density, iconography |
| Interaction & animation | Hover, focus, transitions, micro-interaction, `prefers-reduced-motion` |
| States | Loading, empty, error, success, disabled, long-running |
| Accessibility | Semantic HTML, keyboard navigation, focus, contrast, ARIA only when needed |
| Responsive | Desktop / laptop primary, tablet cơ bản |
| API → UI mapping | Bảng UI feature → SYS-05 endpoint |
| Research → UI mapping | Bảng UI element → methodology / ADR / RQ / FE-06 / CP-0X |
| HTML prototype | Single-page app, vanilla HTML/CSS/JS, navigation thật, mock data có nhãn |

### 2.2 Out of scope (EPIC-12 sẽ làm sau)

- React / Vue / framework frontend.
- Production build, CI/CD cho frontend.
- Authentication / Authorization thật (theo `SYS-05` §13 — `IMPLEMENTATION_OPTION`).
- Real API call (prototype dùng mock data).
- Internationalization (UI chỉ tiếng Anh cho prototype; document spec
  song ngữ Việt–Anh).
- Mobile-first layout.
- High-density power-user mode (sẽ là Phase sau nếu cần).

### 2.3 Out of scope (research — KHÔNG BAO GIỜ)

- Thay đổi methodology, RQ, algorithm scope, preprocessing policy.
- Tự tạo segment names ("Champions", "Loyal", "VIP", "At Risk", ...).
- Tự tạo MKT framework, marketing strategy, KPI, recommendation.
- Tự đặt "best / winner / optimal / recommended / final" claim.
- Cross-algorithm ranking hoặc composite score.
- Tự compute stability metric (ARI/AMI/Hungarian/CI/bootstrap) khi chưa
  có methodology lock.
- Đưa DBSCAN noise (label = -1) vào segment list / marketing.

---

## 3. Users / Roles

Prototype giữ actor ở mức tối thiểu, đúng `SYS-01` §5.

| Actor | Mô tả | Quyền trong prototype |
| --- | --- | --- |
| **Researcher / System User** | Người thực hiện nghiên cứu, chạy experiment, xem kết quả. | Toàn quyền trong prototype (single-user, local). |
| **Mentor / Human Reviewer** (implicit) | Review methodology decisions, approve status changes. | KHÔNG tương tác trực tiếp trong UI; review qua PR / ADR. |

> Per `SYS-01` §5, prototype không tạo actor phức tạp (Admin /
> Auditor / Data Engineer / Business Stakeholder). UI không hiển thị
> role switcher.

---

## 4. UX Principles

Áp dụng 10 nguyên tắc usability cơ bản (Nielsen) làm design criteria,
không biến thành lý thuyết dài:

| # | Nguyên tắc | Áp dụng vào prototype |
| --- | --- | --- |
| 1 | Visibility of system status | Mọi action có feedback (loading, success, error); run status hiển thị đúng canonical API enum (`SYS-05` §G.3: `PENDING` / `RUNNING` / `SUCCEEDED` / `FAILED` / `CANCELLED` / `TIMEOUT`) với UI display label mapping (§10.4). |
| 2 | Match between system and real world | Dùng terminology nghiên cứu: "experiment", "configuration", "evaluation", "stability evidence", "profiling" — không dùng "AI insight", "smart segment" |
| 3 | User control and freedom | Cancel job, back navigation, undo destructive action (best-effort với confirm dialog) |
| 4 | Consistency and standards | Cùng pattern cho table, form, button, status; icon dùng 1 library (Lucide) |
| 5 | Error prevention | Validation rõ trước khi submit; confirm trước action phá huỷ (delete dataset, cancel running run) |
| 6 | Recognition rather than recall | Breadcrumb, current page indicator, default values hiển thị; mọi parameter đi kèm tooltip giải thích |
| 7 | Flexibility and efficiency | Power-user có thể dùng keyboard (tab, esc, enter); tránh bắt buộc wizard cho expert |
| 8 | Aesthetic and minimalist design | Whitespace, hierarchy, không dùng gradient/glow; chỉ một nguồn màu brand; status dùng tone muted |
| 9 | Help users recognize / recover from errors | Error message: chuyện gì xảy ra, có thể làm gì tiếp; có error code + link tới log |
| 10 | Help and documentation | Tooltip cho thuật ngữ ML; link tới `docs/` cho giải thích dài; nhãn `WORKING_ASSUMPTION` và `REVIEW_REQUIRED` không ẩn |

---

## 5. Information Architecture

### 5.1 Site map

```
Dashboard
├── Datasets
│   ├── List
│   └── Detail
│       ├── Overview tab
│       ├── Features tab
│       ├── Provenance tab
│       └── Usage / Lineage tab
├── Experiments
│   ├── List
│   ├── New (wizard)
│   │   ├── Step 1: Dataset
│   │   ├── Step 2: Feature Set & Preprocessing
│   │   ├── Step 3: Algorithm
│   │   ├── Step 4: Configuration
│   │   ├── Step 5: Review
│   │   └── Run
│   ├── Running (live status)
│   ├── Result Detail
│   │   ├── Overview tab
│   │   ├── Evaluation tab
│   │   ├── Cluster Distribution tab
│   │   ├── Stability tab
│   │   └── Lineage tab
├── Evaluation
│   ├── Comparison table
│   └── Per-algorithm detail
├── Profiling
│   ├── Segment overview
│   ├── Segment detail
│   └── Cross-segment compare
├── Reports
│   ├── List
│   └── Detail
└── Marketing ── REVIEW_REQUIRED
    └── Placeholder (MKT framework pending)
```

> **Marketing section** chỉ làm 1 placeholder page hiển thị trạng
> thái `REVIEW_REQUIRED` cho đến khi MKT-01..MKT-05 tồn tại. Không
> tự sinh framework.

### 5.2 Section grouping (sidebar)

Sidebar trái chia 5 nhóm (đặt tên theo vai trò nghiên cứu, không
theo vai trò "AI SaaS"):

1. **Overview** — Dashboard.
2. **Data** — Datasets.
3. **Research** — Experiments, Evaluation, Stability.
4. **Segments** — Profiling, (Marketing = `REVIEW_REQUIRED`).
5. **Reports** — Reports.

> **Audit** (per `SYS-05` §G.7) là **supporting view** xuất hiện
> dưới dạng right rail trong màn hình có liên quan (vd. S-04
> Experiments List), **không** là screen riêng và **không** xuất
> hiện trong sidebar. Status hiện tại `REVIEW_REQUIRED` (xem
> §16 API mapping).

---

## 6. Navigation

### 6.1 Primary navigation (sidebar)

- **Persistent** trên desktop, collapsible trên tablet.
- **Active state**: bar mỏng bên trái + tone text đậm hơn.
- **Section header** (chữ in hoa, kích thước nhỏ) phân tách nhóm.
- **Icon** + label cho mỗi item; icon từ Lucide (consistent stroke).

### 6.2 Top bar (contextual)

- **Left**: breadcrumb hiện tại.
- **Center**: tên dataset active (nếu có).
- **Right**:
  - Environment indicator (Python, branch) — small, subtle.
  - User menu placeholder (avatar + name) — không có action, chỉ để
    cho thấy đây là single-user prototype.

### 6.3 Secondary navigation (in-page)

- **Tabs** trong Dataset Detail, Experiment Result, Report Detail.
- **Anchor links** trong Documentation page (nếu có ở Phase sau).

### 6.4 Back / breadcrumb

- Mọi trang (trừ Dashboard) có breadcrumb.
- Browser back hoạt động bình thường (prototype dùng hash routing
  tương thích history API).

---

## 7. User Flows

### 7.1 Primary flow: "Run an experiment and inspect results"

```
Dashboard
  → click "New experiment"
Experiments / New (wizard)
  Step 1: Chọn dataset
  Step 2: Chọn Feature Set = RFM Extended (fixed), Preprocessing = FE-06 C7 (fixed)
  Step 3: Chọn algorithm (5 options, K-Medoids absent)
  Step 4: Configuration (read-only snapshot từ config — K, seed, hyperparameters; không cho user input trực tiếp theo SYS-05 config-only principle)
  Step 5: Review → Run
Experiments / Running
  → progress + current step + cancel option
Experiments / Result Detail
  → tab Evaluation, Cluster Distribution, Stability, Lineage
Evaluation (compare nhiều runs)
Profiling (segment overview, segment detail)
Reports (export)
```

### 7.2 Secondary flow: "Inspect dataset lineage"

```
Datasets / List
  → chọn dataset
Datasets / Detail
  → tab Overview → tab Features → tab Provenance → tab Usage / Lineage
```

### 7.3 Supporting view: "Audit log" (in-page, không phải screen riêng)

```
Bất kỳ màn hình nào có gắn audit panel (vd. S-04 Experiments List, S-02 Datasets List)
  → right rail / collapsible panel hiển thị recent audit entries
  → filter: actor, action, time range
  → KHÔNG có route riêng; mở từ page context
```

> Audit log endpoint (`GET /api/v1/audit`, `SYS-05` G.7) hiện ở
> trạng thái `REVIEW_REQUIRED` — chưa được expose trong Phase này
> ngoài supporting panel scope.

### 7.4 Error / empty paths

- **Dataset not validated**: hiển thị empty state với CTA
  "Run validation" (xem §S-02 Validate button logic).
- **No experiments yet**: empty state với CTA "Create experiment".
- **Run failed**: detail page hiển thị error log, link tới
  "Edit configuration" để retry.
- **Marketing unavailable**: placeholder page với explanation
  "MKT framework pending".

---

## 8. Screen Inventory

| ID | Screen | Mục đích | Status |
| --- | --- | --- | --- |
| S-01 | Dashboard | Tổng quan dataset active, experiment gần đây, system status, quick actions | `CONTRACT_REQUIRED` |
| S-02 | Datasets / List | Liệt kê dataset, version, validation status, SHA | `CONTRACT_REQUIRED` |
| S-03 | Datasets / Detail | 4 tabs: Overview, Features, Provenance, Usage / Lineage | `CONTRACT_REQUIRED` |
| S-04 | Experiments / List | Lịch sử experiments với filter | `CONTRACT_REQUIRED` |
| S-05 | Experiments / Wizard | 5-step wizard + Review + Run | `CONTRACT_REQUIRED` |
| S-06 | Experiments / Running | Live status, progress, cancel | `CONTRACT_REQUIRED` |
| S-07 | Experiments / Result Detail | 5 tabs: Overview, Evaluation, Cluster Distribution, Stability, Lineage | `CONTRACT_REQUIRED` |
| S-08 | Evaluation / Compare | Bảng side-by-side, sort/filter | `CONTRACT_REQUIRED` (so sánh) |
| S-09 | Profiling / Overview | Segment list per algorithm, size, status | `CONTRACT_REQUIRED` |
| S-10 | Profiling / Segment Detail | RFM profile, behavioural profile, distinguishing features | `CONTRACT_REQUIRED` |
| S-11 | Reports / List | Reports sinh ra từ pipeline | `WORKING_ASSUMPTION` |
| S-12 | Reports / Detail | Report content, inputs, export | `WORKING_ASSUMPTION` |
| S-13 | Marketing / Placeholder | REVIEW_REQUIRED page | `REVIEW_REQUIRED` |

---

## 9. Screen Specifications

> Mỗi screen mô tả: mục đích, primary user, entry point, main
> components, data shown, actions, API mapping, states, interactions,
> validation, research constraints, review status. Theo template
> brief yêu cầu.

### S-01 Dashboard

- **Purpose**: cung cấp research/system overview + quick actions.
- **Primary user**: Researcher.
- **Entry point**: default landing page.
- **Main components**:
  - **Hero card** (đơn giản): dataset active, feature set status,
    preprocessing status, số customer, số feature.
  - **Recent experiments** (table 5 dòng gần nhất).
  - **System status** (panel nhỏ): environment, library versions.
  - **Quick actions**: "New experiment", "View all datasets",
    "View reports".
  - **Recent reports** (list 5 reports gần nhất).
- **Data shown**: dataset name, version, SHA-256, n_customers, n_features;
  experiments gần đây; reports.
- **Actions**: click vào row / card để navigate.
- **API mapping**:
  - `GET /api/v1/datasets` (Danh sách dataset, filter status=ACTIVE)
  - `GET /api/v1/experiments?limit=5` (Danh sách experiment gần đây)
  - `GET /api/v1/reports?limit=5` (Danh sách report gần đây)
  - `GET /api/v1/system/info` (System status)
- **States**: loading (skeleton), empty (chưa có dataset / experiment),
  error.
- **Interactions**: click card / row để navigate; refresh button.
- **Validation**: N/A.
- **Research constraints**: không claim "best". Hiển thị `WORKING_ASSUMPTION`
  cho FE-06 C7 status.
- **Review status**: `CONTRACT_REQUIRED`.

### S-02 Datasets / List

- **Purpose**: list dataset, version, validation status, SHA, action.
- **Primary user**: Researcher.
- **Entry point**: sidebar Data → Datasets.
- **Main components**:
  - Filter bar: search by name, filter by kind, filter by status.
  - Table: name, kind, version, n_rows, validation status, SHA-256 (truncated), created_at.
  - Row actions: "View detail" (icon, always available), "Validate"
    (icon, **state machine** per `validation_status`):
    - `NOT_VALIDATED` (hoặc absent) → **enabled**, label "Validate".
    - `VALID` → **disabled**, label "Validated", icon `circle-check`.
    - `VALIDATING` → **disabled** + spinner inline, label "Validating…".
    - `FAILED` → **enabled**, label "Retry validation", icon `refresh-cw`.
  - Empty state.
- **Data shown**: dataset metadata per `SYS-05` B.4.
- **Actions**: row click → detail; validate action (per state machine
  ở trên).
- **API mapping**: `GET /api/v1/datasets` (`SYS-05` B.4),
  `POST /api/v1/datasets/{id}/validate` (B.3 — async job trả
  `job_id`; status poll qua `GET /jobs/{id}` G.3).
- **States**: loading, empty, error.
- **Interactions**: row hover, row click; filter input.
- **Validation**: filter input chỉ chấp nhận allowed chars.
- **Research constraints**: chỉ hiển thị dataset primary đã freeze
  (Online Retail → FE06-v1.0). Không cho upload dataset khác trong
  prototype.
- **Review status**: `CONTRACT_REQUIRED` cho list; `REVIEW_REQUIRED`
  cho upload (B.1) — không expose ở Phase này.

### S-03 Datasets / Detail

- **Purpose**: hiển thị chi tiết dataset + features + provenance + usage.
- **Primary user**: Researcher.
- **Entry point**: row click từ List.
- **Main components**:
  - **Header**: dataset name, kind, version, status badge, SHA-256.
  - **Tabs**:
    - **Overview**: n_rows, n_features, version label, created_at, file size.
    - **Features**: table 14 features; mỗi row: tên, FE-06 status
      (`ELIGIBLE` / `ELIGIBLE_WORKING_ASSUMPTION`), mô tả ngắn.
      Highlight row `ELIGIBLE_WORKING_ASSUMPTION` bằng badge màu.
    - **Provenance**: source URL, license, download date, SHA-256,
      ADR reference. Per `SYS-01` FR-DATA-03.
    - **Usage / Lineage**: list runs đã sử dụng dataset, với
      `stage`, `config_id`, `config_version`, `ran_at`.
- **Data shown**: per `SYS-05` B.5.
- **Actions**: copy SHA-256, navigate to run, navigate to config.
- **API mapping**: `GET /api/v1/datasets/{id}` (B.5).
- **States**: loading, error.
- **Interactions**: tab switching, copy button, link navigation.
- **Validation**: N/A.
- **Research constraints**: feature status phải rõ ràng theo FE-06 §13
  (6 features ở `ELIGIBLE_WORKING_ASSUMPTION`).
- **Review status**: `CONTRACT_REQUIRED`.

### S-04 Experiments / List

- **Purpose**: list tất cả experiments với filter.
- **Primary user**: Researcher.
- **Entry point**: sidebar Research → Experiments.
- **Main components**:
  - Filter bar: by algorithm, by status, by K, by date range, by dataset.
  - Table: run_id, experiment_id, algorithm, K, dataset, status, created_at.
  - Row action: "View" (always), "Re-run" (if `SUCCEEDED`),
    "Cancel" (if `PENDING` / `RUNNING`).
- **Data shown**: per `SYS-05` D.3.
- **Actions**: row click → detail; re-run (gọi `POST /clustering/runs` với
  cùng config); cancel (`POST /jobs/{id}/cancel`).
- **API mapping**: `GET /api/v1/clustering/runs` (D.3), `POST /clustering/runs` (D.1).
- **States**: loading, empty, error.
- **Interactions**: filter, row hover, row click.
- **Validation**: filter input.
- **Research constraints**: chỉ list experiments trong scope (5 algorithms).
  Không tạo "score" / "winner" column.
- **Review status**: `CONTRACT_REQUIRED`.

### S-05 Experiments / Wizard

- **Purpose**: hướng dẫn user tạo experiment mới theo config-only principle.
- **Primary user**: Researcher.
- **Entry point**: button "New experiment" từ Dashboard hoặc Experiments / List.
- **Main components**:
  - **Stepper** (top): 5 steps + Review + Run. Current step highlighted.
  - **Step 1 — Dataset**: dropdown chọn dataset active (Online Retail / FE06-v1.0).
    Hiển thị SHA-256 ngắn gọn + status.
  - **Step 2 — Feature Set & Preprocessing**:
    - **Feature Set**: hiển thị `RFM Extended (14 features)` kèm badge
      `CURRENT WORKING BASELINE` và explanation. KHÔNG có option khác.
    - **Preprocessing**: hiển thị `FE-06 C7 (median imputation +
      Yeo-Johnson + RobustScaler)` kèm badge `WORKING_ASSUMPTION`.
      KHÔNG có option khác.
  - **Step 3 — Algorithm**: radio cards cho 5 algorithms
    (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means).
    Mỗi card: tên, family (hard / density / model / fuzzy), 1-line
    description. **K-Medoids KHÔNG xuất hiện**.
  - **Step 4 — Configuration** (config-only view):
    - Hiển thị config đang được sử dụng: `clustering_kmeans_default v1`
      (hoặc tương ứng với algorithm đã chọn ở Step 3). Nút
      "View configuration" link tới config detail (read-only).
    - **Mọi** algorithm parameter — `eps`, `min_samples`, `linkage`,
      `covariance_type`, `fuzziness`, `n_init`, `max_iter`,
      `random_seed` — đều đến từ configuration. UI **không** expose
      override field cho các parameter này (per `SYS-05` §D.1
      config-only principle, `CONTRACT_REQUIRED`).
    - K và `random_seed` được hiển thị dưới dạng **read-only snapshot**
      từ configuration (vd. `K = 4`, `seed = 42`) — đây là 2
      "trace-level knob" mà research plan (EXP-02 / EXP-05) đã chốt
      default. User **không** chỉnh trực tiếp trong default flow.
    - **K-bearing vs not K-bearing**:

      | Algorithm       | K applicable? |
      | --------------- | ------------- |
      | K-Means         | yes           |
      | Agglomerative   | yes           |
      | GMM             | yes (`n_components`) |
      | Fuzzy C-Means   | yes (`c`)     |
      | DBSCAN          | **no** — DBSCAN không có K input; `n_clusters_realized` do density quyết. UI ẩn trường K khi algorithm = DBSCAN. |
    - Mọi override của K hoặc `random_seed` qua request body hiện ở
      trạng thái `REVIEW_REQUIRED` (`SYS-05` §15, item 8; `SEED_NOT_OVERRIDABLE`
      error code chỉ phát sinh nếu override được mentor approve).
      Khi chưa lock, wizard **chỉ hiển thị** giá trị từ config,
      không cho phép edit.
  - **Step 5 — Review**: tóm tắt toàn bộ lựa chọn + nút "Run".
  - **Run**: chuyển sang S-06 (Experiments / Running).
- **Data shown**: dataset info, feature set, preprocessing, algorithm,
  configuration snapshot (K, seed, hyperparameters) — tất cả
  read-only từ config.
- **Actions**: Next / Back / Cancel wizard / View configuration / Run.
- **API mapping**: `POST /api/v1/clustering/runs` (D.1) ở step Run —
  request body **không** chứa K / seed inline.
- **States**: step loading (validation), step error (validation fail),
  disabled Next khi thiếu required field.
- **Interactions**: step navigation, hover cards, selection state.
- **Validation**:
  - Step 1: dataset phải `VALID` status.
  - Step 3: chỉ chấp nhận 1 trong 5 algorithm.
  - Step 4: K và seed là **read-only snapshot từ config** — user
    không nhập trực tiếp. Validation chỉ kiểm tra:
    - Config snapshot tồn tại (`clustering_<algo>_default v1`).
    - K (nếu applicable cho K-bearing algorithms) ∈ [2, 10]
      (theo EXP-02 K-range working assumption, `WA-03`).
    - Seed = 42 (default, per `WA-04`; override là
      `REVIEW_REQUIRED`).
    - DBSCAN: validation **bỏ qua** trường K (không applicable).
- **Research constraints**:
  - KHÔNG hiển thị K-Medoids.
  - KHÔNG cho phép chọn feature set khác (chỉ RFM Extended).
  - KHÔNG cho phép chọn preprocessing khác (chỉ FE-06 C7).
  - Nhãn `WORKING_ASSUMPTION` cho C7.
  - Nhãn `CURRENT WORKING BASELINE` cho RFM Extended.
  - RFM-only = `FUTURE_WORK`, không hiển thị như option.
- **Review status**: `CONTRACT_REQUIRED` (UI shape + config-only
  principle). K / seed override từ UI hiện `REVIEW_REQUIRED`
  (`SYS-05` §15 item 8, `SYS-01` FR-EXP-05) — sẽ được bật trong
  Phase sau nếu mentor approve qua ADR.

### S-06 Experiments / Running

- **Purpose**: hiển thị live status của experiment đang chạy.
- **Primary user**: Researcher.
- **Entry point**: auto-redirect sau khi Run từ S-05.
- **Main components**:
  - **Header**: run_id, algorithm, status badge. **Canonical API
    status enum** (per `SYS-05` §G.3):
    `PENDING` / `RUNNING` / `SUCCEEDED` / `FAILED` / `CANCELLED` /
    `TIMEOUT`. UI hiển thị bằng **display label thân thiện** (vd.
    `PENDING → "Queued"`, `SUCCEEDED → "Completed"`,
    `TIMEOUT → "Timed out"`). Mapping API enum ↔ display label
    được ghi rõ trong §10.4 để EPIC-12 không lệch contract.
  - **Progress bar** (linear): step current / total. Step label.
  - **Current step** panel: mô tả step hiện tại (vd. "Fitting K-Means with K=4...").
  - **Elapsed time** (live).
  - **Logs preview** (5-10 dòng cuối, monospace font, "show more").
  - **Cancel button** (chỉ khi status `PENDING` / `RUNNING`;
    API sẽ trả `409 JOB_ALREADY_TERMINAL` nếu cancel khi
    `SUCCEEDED` / `FAILED` / `CANCELLED` / `TIMEOUT`).
- **Data shown**: per `SYS-05` G.3.
- **Actions**: cancel, view logs (full).
- **API mapping**: `GET /api/v1/jobs/{job_id}` (G.3), `POST /jobs/{id}/cancel` (G.5),
  `GET /jobs/{id}/logs` (G.4).
- **States**: QUEUED, RUNNING (animate progress), COMPLETED (auto-redirect
  to S-07), FAILED (error block), CANCELLED.
- **Interactions**: cancel confirm dialog.
- **Validation**: confirm trước cancel.
- **Research constraints**: không hiển thị nội dung algorithm internals.
  Chỉ step label mô tả bước hiện tại.
- **Review status**: `CONTRACT_REQUIRED`.

### S-07 Experiments / Result Detail

- **Purpose**: hiển thị kết quả experiment.
- **Primary user**: Researcher.
- **Entry point**: row click từ S-04 hoặc auto-redirect từ S-06.
- **Main components**:
  - **Header**: algorithm, K, dataset, configuration, status
    (canonical API enum per `SYS-05` §G.3 — `SUCCEEDED` cho
    successful run, hiển thị label "Completed"), runtime.
  - **Tabs**:
    - **Overview**: metadata (input SHA, config SHA, seed, environment
      block). Per `SYS-01` FR-EXP-07.
    - **Evaluation**: bảng internal metrics (silhouette, DBI, CH,
      WCSS = `diagnostic_only` badge, runtime). Per `SYS-01` FR-EVAL-01..05.
    - **Cluster Distribution**: bar chart size distribution; nếu DBSCAN,
      tách `Noise (-1)` riêng với hatch / pattern khác biệt. Per
      `SYS-01` FR-VIZ-01, FR-VIZ-02.
    - **Stability**: status `NOT_REQUESTED` (default) hoặc evidence
      reference nếu có. Per `SYS-05` E.2.
    - **Lineage**: dataset, configs, seed, environment, output SHA-256.
      Per `SYS-05` G.6.
- **Data shown**: per `SYS-05` D.2, E.2.
- **Actions**: navigate to dataset, navigate to config, export run
  metadata (per `SYS-01` FR-REPORT-02).
- **API mapping**: `GET /api/v1/clustering/runs/{id}` (D.2),
  `GET /evaluation/runs/{id}` (E.2), `GET /lineage/{id}` (G.6).
- **States**: loading, error, success.
- **Interactions**: tab switch, navigate.
- **Validation**: N/A.
- **Research constraints**:
  - WCSS = `diagnostic_only` badge.
  - DBSCAN noise tách riêng, không gộp vào cluster nào.
  - Stability status mặc định `NOT_REQUESTED` cho đến khi có evidence
    (per `SYS-05` E.2; stability methodology chưa lock).
  - KHÔNG có "best algorithm" / "winner" / "score" highlight.
- **Review status**: `CONTRACT_REQUIRED`.

### S-08 Evaluation / Compare

- **Purpose**: so sánh kết quả nhiều runs side-by-side.
- **Primary user**: Researcher.
- **Entry point**: sidebar Research → Evaluation.
- **Main components**:
  - **Filter**: select experiments để compare (multi-select).
  - **Table** (sortable columns):
    `Algorithm | K | Silhouette | Davies-Bouldin | Calinski-Harabasz |
     WCSS (diagnostic) | Runtime | Stability status`
  - Cột sort: ascending / descending.
  - **Empty state**: chưa chọn experiment nào.
- **Data shown**: per `SYS-05` E.5.
- **Actions**: chọn / bỏ chọn experiment, sort column, export CSV.
- **API mapping**: `POST /api/v1/evaluation/compare` (E.5),
  `GET /evaluation/runs` (E.3).
- **States**: loading, empty, error.
- **Interactions**: checkbox select, column sort, export button.
- **Validation**: tối đa 10 runs (heuristic để tránh tràn UI).
- **Research constraints**:
  - KHÔNG có "Winner" / "Best" / "Score" / "Overall ranking" column.
  - WCSS column kèm `diagnostic_only` badge.
  - Stability status mặc định `NOT_REQUESTED`; khi EPIC-08 evidence
    có sẵn → trạng thái từ API.
  - Sort có thể theo metric; KHÔNG tô đậm / highlight "best" theo metric.
- **Review status**: `CONTRACT_REQUIRED` (UI shape); column
  stability = `REVIEW_REQUIRED` (per `SYS-05` §9 E.2).

### S-09 Profiling / Overview

- **Purpose**: tổng quan segments theo algorithm.
- **Primary user**: Researcher.
- **Entry point**: sidebar Segments → Profiling.
- **Main components**:
  - **Algorithm selector** (radio: K-Means / Agglomerative / DBSCAN / GMM / FCM).
  - **Segment list table**: segment_id, size (count + %), share of total,
    status (`NAMED` / `COMPARATIVE` / `NOT_AVAILABLE` / `NOISE`).
  - **Note**: per `SYS-01` FR-SEG-04, FR-SEG-08, FR-SEG-09. **Không**
    gán tên business; **Noise** là status riêng (DBSCAN).
- **Data shown**: per `SYS-05` F.2.
- **Actions**: navigate to segment detail.
- **API mapping**: `GET /api/v1/profiling/runs/{id}` (F.2) — UI cần chọn
  profiling run trước (qua Experiment Result).
- **States**: loading, empty (chưa có profiling run), error.
- **Interactions**: algorithm switch, row click.
- **Validation**: N/A.
- **Research constraints**:
  - Status `NOISE` chỉ xuất hiện cho DBSCAN.
  - KHÔNG hard-code business name.
  - Nhãn `Business label: Not assigned` cho mọi segment khi chưa
    có CP-04 mapping được approve.
  - Status `NOT_AVAILABLE` cho EXP-03 working-selected (per
    `SYS-01` FR-SEG-01, CON-11).
- **Review status**: `CONTRACT_REQUIRED`.

### S-10 Profiling / Segment Detail

- **Purpose**: hiển thị profile numeric cho segment (CP-02, CP-03, CP-04).
- **Primary user**: Researcher.
- **Entry point**: row click từ S-09.
- **Main components**:
  - **Header**: segment_id, size, share, status, business label
    (`Not assigned` nếu chưa approve).
  - **Feature statistics table** (mỗi feature 1 row): mean, median, std,
    p25, p75, min, max. Highlight features ở
    `ELIGIBLE_WORKING_ASSUMPTION` status.
  - **Distinguishing features** (từ CP-03 evidence) — danh sách features
    phân biệt segment này với overall.
  - **Charts**: per-feature box plot hoặc distribution chart (mock).
  - **RFM tier** + behavioural profile panel.
- **Data shown**: per `SYS-05` F.2.
- **Actions**: export segment profile (CSV), navigate to experiment.
- **API mapping**: `GET /api/v1/profiling/runs/{id}` (F.2).
- **States**: loading, error.
- **Interactions**: tab (nếu có), chart hover, export.
- **Validation**: N/A.
- **Research constraints**:
  - Feature status highlight bắt buộc cho 6 features
    `ELIGIBLE_WORKING_ASSUMPTION`.
  - KHÔNG có "target this segment" / "campaign" suggestion — đó là
    phần Marketing (REVIEW_REQUIRED).
- **Review status**: `CONTRACT_REQUIRED`.

### S-11 Reports / List

- **Purpose**: list reports sinh ra từ pipeline (per `SYS-01` FR-REPORT-01).
- **Primary user**: Researcher.
- **Entry point**: sidebar Reports.
- **Main components**:
  - Filter: by stage, by date.
  - Table: report_id, title, stage, created_at, n_inputs, size_bytes.
  - Row action: View, Download.
- **Data shown**: per `SYS-05` F.7.
- **Actions**: row click → detail; download.
- **API mapping**: `GET /api/v1/reports` (F.7).
- **States**: loading, empty, error.
- **Interactions**: filter, row hover, row click.
- **Validation**: N/A.
- **Research constraints**: KHÔNG tự sinh title mang tính
  "best / winner / recommended".
- **Review status**: `WORKING_ASSUMPTION` (nếu report generation
  pipeline chưa fully wired — nguồn `SYS-01` OQ-09, OQ-10).

### S-12 Reports / Detail

- **Purpose**: hiển thị nội dung report + inputs.
- **Primary user**: Researcher.
- **Entry point**: row click từ S-11.
- **Main components**:
  - **Header**: title, format, status, generated_at, generated_by.
  - **Content**: render Markdown hoặc PDF preview.
  - **Inputs panel**: list of evaluation_run_ids, profiling_run_ids, configs.
  - **Export / Download button** (local only).
- **Data shown**: per `SYS-05` F.6.
- **Actions**: download.
- **API mapping**: `GET /api/v1/reports/{id}` (F.6),
  `GET /api/v1/reports/{id}/download` (F.8).
- **States**: loading, error.
- **Interactions**: scroll, download.
- **Validation**: N/A.
- **Research constraints**: KHÔNG có "send to email" / "share link"
  / "schedule" — đó là campaign automation (OOS-01).
- **Review status**: `WORKING_ASSUMPTION`.

### S-13 Marketing / Placeholder

- **Purpose**: hiển thị trạng thái chờ MKT framework.
- **Primary user**: Researcher.
- **Entry point**: sidebar Segments → Marketing.
- **Main components**:
  - Big badge: `REVIEW_REQUIRED`.
  - Explanation: "Marketing Recommendation module phụ thuộc MKT-01..MKT-05.
    Framework chưa tồn tại trong repo. Module sẽ được implement khi MKT
    framework được approve."
  - Link to `docs/decisions/`.
- **Data shown**: status, expected fields, blocker.
- **Actions**: không có.
- **API mapping**: không có (module chưa tồn tại).
- **States**: chỉ 1 state (placeholder).
- **Research constraints**:
  - KHÔNG tự sinh marketing strategy, KPI, recommendation.
  - KHÔNG dùng internal clustering metric như business effectiveness.
  - KHÔNG dùng DBSCAN noise (label = -1) làm segment target.
- **Review status**: `REVIEW_REQUIRED`.

---

## 10. Component System

### 10.1 Buttons

| Variant | Background | Text | Border | Use |
| --- | --- | --- | --- | --- |
| **Primary** | `#0f766e` (teal-700) | `#ffffff` | none | Main CTA (Run experiment, Save) |
| **Secondary** | `#ffffff` | `#1c1917` | `#d6d3d1` (stone-300) | Cancel, Back |
| **Ghost** | transparent | `#0f766e` | none | Inline link action |
| **Danger** | `#b91c1c` (red-700) | `#ffffff` | none | Delete, Cancel running run |
| **Disabled** | `#f5f5f4` (stone-100) | `#a3a3a3` | none | Mọi variant khi disabled |

Sizes: `sm` (28px), `md` (36px), `lg` (44px).

### 10.2 Inputs

- **Text input**: border 1px, padding 8px 12px, focus ring teal-700 2px.
- **Number input**: như text + spinner.
- **Select**: native `<select>` với custom arrow icon (Lucide chevron-down).
- **Radio card**: 1 card có border, padding 16px, hover/selected state.
- **Checkbox**: native + custom check icon.
- **Tooltip**: hover/click icon, popover với arrow.

### 10.3 Tables

- **Header row**: tone nhạt hơn (`#fafaf9`), font 600, color
  `#57534e` (stone-600).
- **Body row**: hover `#f5f5f4` (stone-100).
- **Cell padding**: 12px 16px.
- **Sticky header** khi scroll dọc.
- **Sortable header**: icon chevron bên cạnh label.

### 10.4 Badges

> **Quy ước API status ↔ UI display label**: prototype dùng
> canonical API status enum từ `SYS-05` §G.3 làm **underlying value**
> (lưu trong DOM / data-* / mock state), và map sang **UI display
> label** thân thiện để hiển thị. Mapping này là **single source
> of truth** — EPIC-12 không được tự ý thay đổi mapping mà không
> cập nhật SYS-06.

| API status enum | UI display label | Icon (Lucide) | Background | Text | Use |
| --- | --- | --- | --- | --- | --- |
| `PENDING` | "Queued" | `circle-dashed` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | Job queued, chưa bắt đầu |
| `RUNNING` | "Running" | `circle-dot` | `#dbeafe` (blue-100) | `#1e3a8a` (blue-900) | Job đang chạy |
| `SUCCEEDED` | "Completed" | `circle-check` | `#d1fae5` (emerald-100) | `#064e3b` (emerald-900) | Job thành công |
| `FAILED` | "Failed" | `circle-x` | `#fee2e2` (red-100) | `#7f1d1d` (red-900) | Job fail |
| `CANCELLED` | "Cancelled" | `ban` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | Job bị cancel |
| `TIMEOUT` | "Timed out" | `clock-alert` | `#fef3c7` (amber-100) | `#78350f` (amber-900) | Job vượt timeout |

> **Status taxonomy khác** (per `SYS-03` §3.6, methodology lock):

| Status | Background | Text | Use |
| --- | --- | --- | --- |
| `WORKING_ASSUMPTION` | `#fef3c7` (amber-100) | `#78350f` (amber-900) | FE-06 C7, 6 features |
| `FUTURE_WORK` | `#e0e7ff` (indigo-100) | `#312e81` (indigo-900) | RFM-only |
| `CONTRACT_REQUIRED` | `#d1fae5` (emerald-100) | `#064e3b` (emerald-900) | UI chốt |
| `REVIEW_REQUIRED` | `#fee2e2` (red-100) | `#7f1d1d` (red-900) | Method chưa lock |
| `CURRENT WORKING BASELINE` | `#dbeafe` (blue-100) | `#1e3a8a` (blue-900) | RFM Extended 14 features |
| `DIAGNOSTIC_ONLY` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | WCSS |
| `NOISE` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | DBSCAN -1 |
| `NOT_AVAILABLE` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | EXP-03 working-selected |
| `NAMING_PENDING` | `#fef3c7` (amber-100) | `#78350f` (amber-900) | segment có labels, chưa CP-04 |
| `NOT_REQUESTED` | `#f5f5f4` (stone-100) | `#44403c` (stone-700) | stability evidence |

### 10.5 Tabs

- **Default**: text 14px, color `#57534e` (stone-600), border-bottom 2px transparent.
- **Hover**: color `#1c1917` (stone-900).
- **Active**: text 600, color `#0f766e`, border-bottom 2px teal-700.
- **Disabled**: color `#a3a3a3` (stone-400).

### 10.6 Modal / Drawer

- **Modal**: max-width 560px, padding 24px, header + body + footer.
- **Drawer**: từ phải, width 480px, slide-in 200ms.
- **Overlay**: `rgba(28, 25, 23, 0.5)`.

### 10.7 Charts

- **Bar chart**: dùng inline SVG (simple, không thư viện ngoài).
- **Distribution**: 14 bar (mỗi feature 1) hoặc theo cluster.
- **No** 3D, no animation vô tận, no gradient bars.

### 10.8 Tooltip

- Background `#1c1917` (stone-900), text `#fafaf9` (stone-50).
- Padding 6px 8px, radius 4px.
- Hover icon help (Lucide `help-circle`).

### 10.9 Notifications / Toasts

- Bottom-right, max-width 360px.
- Variants: `success` (teal-700), `error` (red-700), `info` (blue-700).
- Auto-dismiss sau 5s (configurable; respect reduced-motion).

### 10.10 Skeleton Loading

- Rectangle với background `#f5f5f4`, animate `pulse` (1.5s).
- Respect `prefers-reduced-motion` → tắt animation.

---

## 11. Visual Design Direction

### 11.1 Typography

- **Font family**: `Inter, system-ui, -apple-system, "Segoe UI", Roboto,
  "Helvetica Neue", Arial, sans-serif`. Monospace cho SHA-256 / log:
  `ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace`.
- **Type scale**:
  - `text-xs` 12px / 16px line-height.
  - `text-sm` 13px / 18px.
  - `text-base` 14px / 20px (default body).
  - `text-md` 15px / 22px.
  - `text-lg` 16px / 24px.
  - `text-xl` 18px / 28px.
  - `text-2xl` 20px / 28px (page title).
  - `text-3xl` 24px / 32px (hero / metric big number).
- **Weight**: 400, 500 (label), 600 (heading, table header), 700 (page
  title).

### 11.2 Spacing scale

4-px base: `0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96`.

### 11.3 Color tokens

```css
--color-bg:           #fafaf9;  /* stone-50  */
--color-surface:      #ffffff;
--color-surface-2:    #f5f5f4;  /* stone-100 */
--color-border:       #e7e5e4;  /* stone-200 */
--color-border-strong:#d6d3d1;  /* stone-300 */
--color-text:         #1c1917;  /* stone-900 */
--color-text-muted:   #57534e;  /* stone-600 */
--color-text-subtle:  #78716c;  /* stone-500 */
--color-text-disabled:#a3a3a3;  /* neutral-400 */
--color-accent:       #0f766e;  /* teal-700 */
--color-accent-hover: #115e59;  /* teal-800 */
--color-accent-soft:  #ccfbf1;  /* teal-100 */
--color-success:      #15803d;  /* green-700 */
--color-warning:      #b45309;  /* amber-700 */
--color-error:        #b91c1c;  /* red-700 */
--color-info:         #1d4ed8;  /* blue-700 */
```

> Tone chủ đạo: stone (trung tính) + teal-700 (accent). Không dùng
> gradient, glow, glassmorphism.

### 11.4 Density

- **Comfortable** (mặc định): padding 12–16px, row height 44–48px.
- **Compact** (table dữ liệu lớn): padding 8–12px, row height 32–36px.

### 11.5 Borders / shadows

- Border 1px stone-200 cho card, table, input.
- Shadow chỉ dùng cho **dropdown / modal / toast**:
  `0 1px 2px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.08)`.
- Card bình thường **không** có shadow — chỉ border.

### 11.6 Iconography

- **Library**: Lucide (CDN: `https://unpkg.com/lucide@latest`).
- **Stroke width**: 1.75 (default).
- **Size**: 16px (in-text), 20px (button), 24px (sidebar), 32px (hero).
- **Style**: outline (không dùng solid variant).
- **Rule**: dùng 1 icon cho 1 concept xuyên suốt (vd. `play` cho "Run",
  `circle-check` cho "Completed", `circle-x` cho "Failed",
  `circle-dot` cho "Running", `circle-dashed` cho "Queued",
  `ban` cho "Cancelled").

### 11.7 Layout

- **Grid**: 12 column, gutter 24px, max-width 1440px.
- **Sidebar width**: 240px (desktop), collapsible 64px.
- **Top bar height**: 56px.
- **Content max-width**: 1200px (text), full (table).

---

## 12. Interaction & Animation

### 12.1 Hover

- Button: background shift + 1px shadow up.
- Table row: background `#f5f5f4`.
- Card / link: cursor pointer, subtle color shift.

### 12.2 Focus

- Visible focus ring: 2px teal-700, offset 2px.
- Keyboard: Tab đi qua theo DOM order; Esc đóng modal/drawer.

### 12.3 Transitions

- Duration: 120ms (hover, button), 200ms (modal, drawer, tab),
  300ms (page transition).
- Easing: `cubic-bezier(0.2, 0, 0, 1)` (decelerate, subtle).

### 12.4 Micro-interactions

- Skeleton loading khi fetch.
- Progress bar animate width 200ms.
- Toast slide-in 200ms từ dưới, auto-dismiss 5s.
- Form validation inline (instant sau blur).

### 12.5 Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 12.6 Forbidden animation

- Loading spinner vô tận không có progress.
- Glow / pulse liên tục.
- Parallax.
- Animation chỉ để trang trí.

---

## 13. State Design

> **Nguyên tắc**: mỗi screen có các state **phù hợp với lifecycle
> của screen đó** — không phải mọi state (loading / empty / error /
> success / disabled / long-running) đều áp dụng cho mọi screen.
> Bảng dưới liệt kê state theo screen; ô `—` nghĩa là state đó
> không applicable cho screen đó. EPIC-12 triển khai state nào có
> trong bảng; bỏ qua state `—`. Acceptance criteria (§21.3) dùng
> wording "state phù hợp / applicable" thay vì "đủ 6 state" để
> tránh bắt buộc thêm state không có ý nghĩa.

| Screen | Loading | Empty | Error | Success | Disabled | Long-running |
| --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Skeleton 3 panel | "No dataset uploaded" | Retry button | — | — | — |
| Datasets List | Skeleton table | "No datasets" + CTA | Retry | — | — | — |
| Dataset Detail | Skeleton tabs | — | Retry | — | — | Validate button khi `VALIDATING` |
| Experiments List | Skeleton | "No experiments" + CTA | Retry | — | — | — |
| Wizard | Inline validation | — | Step error | Step complete (visual confirmation) | Next khi thiếu required field | — |
| Running | Progress + log | — | Error block (`FAILED` status, `SYS-05` G.3) | Auto-redirect khi `SUCCEEDED` | Cancel button chỉ khi `PENDING` / `RUNNING` | progress + cancel (live elapsed/ETA) |
| Result Detail | Skeleton tabs | — | Retry | — | — | — |
| Evaluation Compare | Skeleton table | "Select 2+ experiments" | Retry | — | — | — |
| Profiling Overview | Skeleton | "No profiling run" | Retry | — | — | — |
| Segment Detail | Skeleton | — | Retry | — | — | — |
| Reports List | Skeleton | "No reports" | Retry | — | — | — |
| Report Detail | Skeleton | — | Retry | — | — | — |
| Marketing | — | — | — | — | — | — (placeholder, 1 state) |

**Error message convention**:

```
[Icon: triangle-alert]
[Title]: [What happened]
[Body]: [What user can do next]
[Error code]: e.g. SYS05_504_TIMEOUT (link to log / docs)
```

---

## 14. Accessibility

- **Semantic HTML**: `<header>`, `<nav>`, `<main>`, `<section>`,
  `<table>`, `<button>`, `<label for=...>`, `<th scope=...>`.
- **Keyboard navigation**: mọi interactive element reachable bằng Tab;
  Esc đóng modal/drawer; Enter submit form; arrow keys cho tab list
  (theo WAI-ARIA Authoring Practices).
- **Focus visible**: outline 2px teal-700 + offset 2px.
- **Contrast**:
  - Text / background ≥ 4.5:1 (AA).
  - Large text / icon ≥ 3:1.
  - Status badge: text tone đậm + background tone nhạt.
- **ARIA**:
  - `aria-label` cho icon button (Run, Cancel, View).
  - `aria-live="polite"` cho status update (job status, toast).
  - `aria-busy="true"` khi đang load.
  - `aria-current="page"` cho active nav item.
- **Form**: `<label for>` cho mỗi input; required field có `aria-required`.
- **Không dùng màu là tín hiệu duy nhất**: status có cả icon + label.
- **Reduced motion**: respect `prefers-reduced-motion` (xem §12.5).

---

## 15. Responsive Behavior

- **Desktop** (≥ 1280px): primary target. Sidebar expanded.
- **Laptop** (1024–1279px): sidebar expanded, table có thể scroll ngang.
- **Tablet** (768–1023px): sidebar collapsed (icon-only, expandable
  on hover), table horizontal scroll.
- **Mobile**: **không** yêu cầu (research tool dùng desktop). Nhưng
  layout không vỡ khi mở ở mobile (table scroll, sidebar drawer).

Breakpoints:

```css
--bp-sm: 640px;
--bp-md: 768px;
--bp-lg: 1024px;
--bp-xl: 1280px;
```

---

## 16. API → UI Mapping

Bảng mapping UI feature ↔ SYS-05 endpoint. Status theo
`CONTRACT_REQUIRED` / `WORKING_ASSUMPTION` / `REVIEW_REQUIRED` /
`IMPLEMENTATION_OPTION` (theo `SYS-05` §2.11).

| UI Feature | Screen | SYS-05 API | Method | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| Recent experiments list | S-01 Dashboard | `GET /api/v1/clustering/runs` | GET | `CONTRACT_REQUIRED` | D.3 |
| Recent reports list | S-01 Dashboard | `GET /api/v1/reports` | GET | `WORKING_ASSUMPTION` | F.7 |
| System info | S-01 Dashboard | `GET /api/v1/system/info` | GET | `CONTRACT_REQUIRED` | G.9 |
| Health indicator | S-01 Dashboard | `GET /healthz`, `GET /readyz` | GET | `CONTRACT_REQUIRED` | G.1, G.2 |
| Dataset list | S-02 | `GET /api/v1/datasets` | GET | `CONTRACT_REQUIRED` | B.4 |
| Dataset validate | S-02 | `POST /api/v1/datasets/{id}/validate` | POST | `CONTRACT_REQUIRED` | B.3 |
| Dataset detail | S-03 | `GET /api/v1/datasets/{id}` | GET | `CONTRACT_REQUIRED` | B.5 |
| Dataset lineage | S-03 | `GET /api/v1/lineage/{run_id}` | GET | `CONTRACT_REQUIRED` | G.6 |
| Experiment list | S-04 | `GET /api/v1/clustering/runs` | GET | `CONTRACT_REQUIRED` | D.3 |
| Experiment re-run | S-04 | `POST /api/v1/clustering/runs` | POST | `CONTRACT_REQUIRED` | D.1 (cùng config, cùng seed → EXP-05 Block R) |
| Experiment cancel | S-04 / S-06 | `POST /api/v1/jobs/{job_id}/cancel` | POST | `CONTRACT_REQUIRED` | G.5 |
| Wizard: dataset selector | S-05 | `GET /api/v1/datasets` | GET | `CONTRACT_REQUIRED` | B.4 |
| Wizard: config view | S-05 | `GET /api/v1/admin/configs/{id}` | GET | `CONTRACT_REQUIRED` | A.2 |
| Wizard: run | S-05 | `POST /api/v1/clustering/runs` | POST | `CONTRACT_REQUIRED` | D.1 |
| Running: live status | S-06 | `GET /api/v1/jobs/{job_id}` | GET | `CONTRACT_REQUIRED` | G.3 |
| Running: log stream | S-06 | `GET /api/v1/jobs/{job_id}/logs` | GET | `CONTRACT_REQUIRED` | G.4 |
| Result: clustering run detail | S-07 | `GET /api/v1/clustering/runs/{run_id}` | GET | `CONTRACT_REQUIRED` | D.2 |
| Result: evaluation run | S-07 | `GET /api/v1/evaluation/runs/{run_id}` | GET | `CONTRACT_REQUIRED` | E.2 |
| Result: model labels | S-07 | `GET /api/v1/clustering/runs/{run_id}/labels` | GET | `CONTRACT_REQUIRED` | D.5 |
| Result: lineage | S-07 | `GET /api/v1/lineage/{run_id}` | GET | `CONTRACT_REQUIRED` | G.6 |
| Compare runs | S-08 | `POST /api/v1/evaluation/compare` | POST | `CONTRACT_REQUIRED` | E.5 |
| Profiling run | S-09 / S-10 | `POST /api/v1/profiling/runs` | POST | `CONTRACT_REQUIRED` | F.1 |
| Profiling detail | S-09 / S-10 | `GET /api/v1/profiling/runs/{run_id}` | GET | `CONTRACT_REQUIRED` | F.2 |
| Report list | S-11 | `GET /api/v1/reports` | GET | `WORKING_ASSUMPTION` | F.7 |
| Report detail | S-12 | `GET /api/v1/reports/{report_id}` | GET | `WORKING_ASSUMPTION` | F.6 |
| Report download | S-12 | `GET /api/v1/reports/{report_id}/download` | GET | `WORKING_ASSUMPTION` | F.8 |
| Audit log | S-04 (right rail / supporting panel) | `GET /api/v1/audit` | GET | `REVIEW_REQUIRED` | G.7 — không phải screen riêng, chỉ in-page panel; ẩn khi chưa review |
| Model registry list | (không có trong prototype scope) | `GET /api/v1/models` | GET | `REVIEW_REQUIRED` | D.8 — chưa expose |
| Model promote | (không có trong prototype scope) | `POST /api/v1/models/{id}/promote` | POST | `REVIEW_REQUIRED` | D.11 — chưa expose |
| Predict | (không có trong prototype scope) | `POST /api/v1/clustering/predict` | POST | `REVIEW_REQUIRED` | D.6 — chưa expose |
| Explain | (không có trong prototype scope) | `POST /api/v1/clustering/explain` | POST | `REVIEW_REQUIRED` | D.7 — chưa expose |
| Dataset promote | (không có trong prototype scope) | `POST /api/v1/datasets/{id}/promote` | POST | `REVIEW_REQUIRED` | B.6 — chưa expose |
| Admin reset | (không có trong prototype scope) | `POST /api/v1/admin/policies/reset` | POST | `REVIEW_REQUIRED` | A.6 — chưa expose |
| Marketing module | S-13 placeholder | (no API) | — | `REVIEW_REQUIRED` | MKT-01..MKT-05 chưa tồn tại |

---

## 17. Research → UI Traceability

| UI Element | Methodology / Source | Status |
| --- | --- | --- |
| Algorithm list (5 options, no K-Medoids) | ADR-0003; `SYS-01` §2.4 | `LOCKED` |
| Feature set: RFM Extended 14 only | FE-06; ADR-0004 RQ2 reformulation; `SYS-01` §2.2 | `WORKING_ASSUMPTION` (C7); RFM-only `FUTURE_WORK` |
| Preprocessing: FE-06 C7 only | FE-06 C7; `SYS-01` §2.1; `SYS-04` §3 | `WORKING_ASSUMPTION` (WA-01) |
| Feature status badge (6 features) | FE-06 §13; `SYS-01` FR-DATA-04, FR-VIZ-04 | `LOCKED` per feature; 6 ở `ELIGIBLE_WORKING_ASSUMPTION` |
| WCSS = `DIAGNOSTIC_ONLY` badge | `methodology_overview.md` §3.6; `SYS-01` FR-EVAL-04 | `LOCKED` |
| Internal metrics only (silhouette, DBI, CH, WCSS) | `SYS-01` §2.5; ADR-0004 | `LOCKED` |
| No "best / winner / optimal / recommended" claim | `AGENTS.md` §2.5; `SYS-01` §1.5; FR-EVAL-09 | `LOCKED` |
| DBSCAN noise (`-1`) = `NOISE` badge, separate from segments | `SYS-01` §2.5; FR-SEG-09; CP-01 §4.4; LIM-07 | `LOCKED` |
| Stability status default `NOT_REQUESTED` | `SYS-05` §9 E.2; `SYS-04` §3.3; METHODOLOGY_LOCK_STATUS §4 | `REVIEW_REQUIRED` (stability metrics chưa lock) |
| K range + seed = **config-only** (read-only snapshot trong UI) | `SYS-05` §D.1 config-only principle; `SYS-01` FR-EXP-04, EXP-02/03 plans | `LOCKED` (config-only); K / seed override từ UI = `REVIEW_REQUIRED` (`SYS-05` §15 item 8) |
| EXP-03 working-selected = `NOT_AVAILABLE` | `SYS-01` CON-11; CP-01 §3.2; EV03-HP-01 | `LOCKED` |
| Cross-algorithm ranking absent | `AGENTS.md` §2.5, §2.6; FR-EVAL-08; `SYS-01` §1.7 | `LOCKED` |
| Reproducibility 5-field contract (manifest) | `SYS-02` §9.2; `SYS-03` §3.5 | `LOCKED` |
| RQ1 / RQ2 / RQ3 visibility | `SYS-01` §2.3; ADR-0004 | `LOCKED` |
| Marketing = `REVIEW_REQUIRED` placeholder | `SYS-01` §2.8, §6.7; FR-MKT-01..06 | `REVIEW_REQUIRED` (MKT-01..05 absent) |
| Segment names absent | `SYS-01` §1.10; FR-SEG-08; `AGENTS.md` §3 | `LOCKED` |
| K-Medoids absent | ADR-0003; OOS-11 | `LOCKED OUT` |
| 5 algorithms × EXP coverage | `SYS-02` §5.2; EXP-01..05 plans | `LOCKED` |

---

## 18. Prototype Structure

### 18.1 Files

```
docs/system/
├── SYS-06_ui_ux_design.md          # tài liệu này
└── ui-prototype/
    ├── index.html                   # single-page prototype
    └── assets/                      # (chỉ khi cần; prototype dùng inline SVG / CDN)
```

### 18.2 Tech

- **HTML5** semantic.
- **CSS**: vanilla, dùng CSS variables cho tokens, không framework.
- **JavaScript**: vanilla, hash routing, không framework.
- **Icon**: Lucide CDN (`https://unpkg.com/lucide@latest`).
- **Font**: system font stack (Inter nếu có, fallback system-ui).
- **Chart**: inline SVG (đơn giản), không thư viện ngoài.

### 18.3 Routing

Hash-based:

- `#/dashboard`
- `#/datasets`
- `#/datasets/{id}`
- `#/experiments`
- `#/experiments/new`
- `#/experiments/{id}` (Result detail)
- `#/experiments/{id}/running`
- `#/evaluation`
- `#/profiling`
- `#/profiling/{run_id}/{algorithm}/{segment_id}`
- `#/reports`
- `#/reports/{id}`
- `#/marketing`

### 18.4 Mock data — 3-tier classification

Tất cả data trong prototype là mock, **không phải** kết quả nghiên
cứu thật. Mọi screen đều có banner cam `Prototype mock data` ở
trên cùng để user biết.

Để tránh hiểu nhầm giữa "mock UI state" và "research evidence",
prototype phân biệt rõ **3 tier** mock data:

| Tier | Mô tả | Nguồn / Quy tắc | Ví dụ trong prototype |
| --- | --- | --- | --- |
| **A. Research Evidence Data** | Số liệu / metadata đã được **freeze trong research evidence** (FE-06, ADR, EXP-01..05 plans, `METHODOLOGY_LOCK_STATUS`). Được dùng để prototype hiển thị đúng identity / content của artifact đã tồn tại. | Phải trùng với evidence; KHÔNG tự invent. | `4,371 customers × 14 features`; SHA `ba54033e…`; `FE06-v1.0`; 14 features với status `ELIGIBLE` × 8 / `ELIGIBLE_WORKING_ASSUMPTION` × 6; 5 algorithms; `clustering_kmeans_default v1`. |
| **B. Prototype UI State Data** | Data phục vụ **tương tác UI** (status, progress, timestamps, segment counts trong demo, IDs, navigation state, mock alert). Có thể synthetic nhưng phải **consistency** (vd. status enum theo `SYS-05` G.3). | Được phép tạo để demo interaction; KHÔNG được diễn giải như research result. | Experiment list có 8 rows; 1 row `RUNNING` ở giữa, các row khác `SUCCEEDED`; timestamps dạng `2026-10-01 12:34`; segment counts như `1,100` / `25.2%` (placeholder). |
| **C. Placeholder Data** | Số liệu cần điền vào UI layout nhưng **chưa có giá trị thật** (vd. metric `0.000` / `n/a` / `—`, K range `[2, 10]`, seed `42` khi chưa run). | Phải hiển thị rõ là placeholder; KHÔNG được giả mạo. | `silhouette = 0.0000`; `WCSS = 0.0`; `runtime = 0.00 s`; K = 4 (chưa chạy). |

**Quy tắc chung** (per `AGENTS.md` §2.1, §2.10):

1. Tier A — dùng **đúng** số liệu từ evidence; không tự ý thay
   đổi dù chỉ 1 chữ số.
2. Tier B — được phép synthetic; phải dán nhãn `Prototype mock data`
   và gắn với UI lifecycle hợp lý (vd. `RUNNING` chỉ xuất hiện
   trong UI flow S-04 / S-06).
3. Tier C — KHÔNG được tính toán hoặc suy ra thành evidence;
   phải hiển thị rõ là placeholder.
4. KHÔNG tier nào được tự ý claim "best" / "winner" / "optimal" /
   "recommended" / "final" — bất kể tier nào.
5. Khi EPIC-12 wire với API thật: tier A sẽ đến từ
   `GET /datasets/{id}` / `GET /clustering/runs/{id}`; tier B
   sẽ đến từ job state machine; tier C sẽ được thay bằng giá
   trị thật hoặc `null` / "n/a" theo API.

### 18.5 Interaction

- Sidebar navigation thật.
- Tab switching thật.
- Wizard multi-step thật (Step 1 → 5 + Review + Run).
- Modal / drawer thật.
- Toast thật.
- Filter / sort trên table (chỉ render, không fetch).
- Loading skeleton + auto-transition sang success state.
- Cancel confirm dialog.
- Empty state có CTA.

---

## 19. Open Questions / Review Findings

Các điểm dưới đây cần mentor / human researcher review trước khi
EPIC-12 implement.

1. **AuthN/AuthZ.** Prototype không có login. EPIC-12 cần chốt cơ chế
   (Bearer + JWT hay session). `IMPLEMENTATION_OPTION` (`SYS-05` §13.1).
2. **Datasets trong prototype.** Prototype chỉ hiển thị dataset
   `Online Retail` (FE06-v1.0) đã freeze. Khi EPIC-12 cần upload
   dataset mới → `SYS-05` B.1 endpoint sẽ được wire; hiện ở trạng
   thái `REVIEW_REQUIRED` (per `SYS-01` OQ-04).
3. **MKT framework.** Marketing section chỉ là placeholder. Khi
   MKT-01..MKT-05 tồn tại → EPIC-12 sẽ build screen theo
   `SYS-01` FR-MKT-03 (per `SYS-01` OQ-01, OQ-02).
4. **Stability evidence UI.** Hiện stability tab mặc định
   `NOT_REQUESTED`. Khi EPIC-08 chốt methodology (ARI/AMI/Hungarian/CI)
   → UI sẽ hiển thị evidence reference + summary stats. `REVIEW_REQUIRED`.
5. **Custom config UI.** Hiện prototype chỉ dùng default configs.
   Khi `SYS-05` A.3 (PUT config) được implement → wizard step 4 sẽ
   thêm dropdown "Override config" với audit warning.
6. **Run re-run UI.** Có nên thêm "Re-run với cùng seed" UI action
   để verify EXP-05 Block R reproducibility trực tiếp trong UI không?
   `REVIEW_REQUIRED`. (Per `SYS-01` OQ-14.)
7. **Report generation pipeline.** Hiện `Reports` section ở
   `WORKING_ASSUMPTION` vì chưa có end-to-end report generation
   (per `SYS-01` OQ-09, OQ-10). EPIC-12 sẽ wire khi có.
8. **Custom theme.** Prototype dùng light theme. Có cần dark mode
   cho EPIC-12 không? `REVIEW_REQUIRED`.
9. **Accessibility audit.** Prototype đã áp dụng best practices, nhưng
   chưa qua WCAG audit tool. EPIC-12 nên chạy axe / Lighthouse
   trước release.

---

## 20. Out of Scope

| OOS ID | Item | Lý do |
| --- | --- | --- |
| OOS-UI-01 | Production React / Vue / Svelte frontend | Thuộc EPIC-12 |
| OOS-UI-02 | Real API call | Prototype dùng mock data |
| OOS-UI-03 | Authentication / Authorization thật | `SYS-05` §13 — `IMPLEMENTATION_OPTION` |
| OOS-UI-04 | Mobile-first design | Research tool dùng desktop |
| OOS-UI-05 | Internationalization (i18n) | Prototype chỉ tiếng Anh (document song ngữ) |
| OOS-UI-06 | Marketing Recommendation screen thật | MKT-01..05 chưa tồn tại (`SYS-01` OQ-01) |
| OOS-UI-07 | Tự tạo segment names | `AGENTS.md` §2.5, FR-SEG-08 |
| OOS-UI-08 | "Best / winner / optimal / recommended" UI | `AGENTS.md` §2.5, FR-EVAL-09 |
| OOS-UI-09 | K-Medoids algorithm option | ADR-0003 OUT OF SCOPE |
| OOS-UI-10 | RFM-only feature set option | ADR-0004 RQ2 reformulated → `FUTURE_WORK` |
| OOS-UI-11 | Cross-algorithm ranking UI | `SYS-01` §1.7, FR-EVAL-08 |
| OOS-UI-12 | Tự tạo MKT framework / strategy / KPI | `SYS-01` §6.7, CON-12 |
| OOS-UI-13 | Git commit / push / PR | `AGENTS.md` §2.11 |

---

## 21. Acceptance Criteria

SYS-06 đạt `READY` khi tất cả items dưới đây PASS.

### 21.1 Structural

- [ ] File `docs/system/SYS-06_ui_ux_design.md` tồn tại.
- [ ] File `docs/system/ui-prototype/index.html` tồn tại và mở được
      trực tiếp trên trình duyệt.
- [ ] **22 main sections** (§1 → §22) **+ 2 appendices** (Appendix A
      Glossary, Appendix B Change Log) theo template brief §24.
- [ ] Bảng API → UI mapping tồn tại.
- [ ] Bảng Research → UI traceability tồn tại.

### 21.2 Content / Methodology

- [ ] Không có "best / winner / optimal / recommended / final" claim.
- [ ] Không có K-Medoids trong UI.
- [ ] RFM-only = `FUTURE_WORK` (không phải option).
- [ ] FE-06 C7 = `WORKING_ASSUMPTION` (badge rõ).
- [ ] WCSS = `DIAGNOSTIC_ONLY` (badge rõ).
- [ ] DBSCAN noise (`-1`) hiển thị riêng, status `NOISE`.
- [ ] Stability default = `NOT_REQUESTED`.
- [ ] 5 algorithms × EXP coverage đúng evidence.
- [ ] Marketing = placeholder `REVIEW_REQUIRED`.
- [ ] Mock data banner rõ ràng ở mỗi screen.

### 21.3 Prototype interaction

- [ ] Sidebar navigation thật.
- [ ] Tabs switching thật.
- [ ] Wizard 5 step + Review + Run hoạt động.
- [ ] Modal / drawer thật.
- [ ] Toast thật.
- [ ] **State phù hợp** (loading / empty / error / success / disabled /
      long-running) cho mỗi screen theo bảng §13 — không bắt buộc
      state nếu không applicable cho screen đó.
- [ ] Hover / focus / transition có.
- [ ] `prefers-reduced-motion` tôn trọng.

### 21.4 Visual

- [ ] Không có neon gradient.
- [ ] Không có glassmorphism / glow / sparkle.
- [ ] Không có AI-themed background.
- [ ] Icon đồng nhất (Lucide).
- [ ] Color palette muted (stone + teal).
- [ ] Table dễ đọc, hierarchy rõ.

### 21.5 Boundary

- [ ] Không React / Vue / Svelte production app.
- [ ] Không backend / API implementation thật.
- [ ] Không methodology change.
- [ ] Không Git operations.

---

## 22. Implementation Handoff to EPIC-12

Khi EPIC-12 bắt đầu, sử dụng SYS-06 làm reference:

1. **Routing structure**: lấy từ §18.3.
2. **Component system**: copy tokens + components từ §10, §11.
3. **Screen specs**: implement theo §9, theo thứ tự ưu tiên:
   - Phase A: S-01, S-02, S-03, S-04, S-05, S-06, S-07.
   - Phase B: S-08, S-09, S-10.
   - Phase C: S-11, S-12, S-13.
4. **State mapping**: mỗi screen có `loading / empty / error / success`
   theo §13.
5. **API → UI mapping**: tham chiếu §16.
6. **Research → UI traceability**: tham chiếu §17.
7. **Accessibility**: §14.
8. **Responsive**: §15.
9. **Visual**: §11 (color tokens, typography, spacing).
10. **Open questions**: §19 cần review với mentor trước khi build
    các phần `REVIEW_REQUIRED`.

EPIC-12 KHÔNG được:

- Thay đổi routing structure mà không cập nhật SYS-06.
- Thêm "best / winner / optimal / recommended" UI.
- Expose K-Medoids hoặc RFM-only như option.
- Hard-code segment names.
- Tự tạo MKT framework.
- Tự thêm stability metric chưa được lock.

---

## Appendix A — Glossary

| Thuật ngữ | Ý nghĩa |
| --- | --- |
| `WORKING_ASSUMPTION` | Default chưa được mentor approve. Hiển thị badge. |
| `FUTURE_WORK` | Nghiên cứu ngoài scope hiện tại. Hiển thị badge. |
| `REVIEW_REQUIRED` | Methodology chưa lock. Hiển thị banner / placeholder. |
| `CONTRACT_REQUIRED` | Phần bắt buộc của UI contract. |
| `IMPLEMENTATION_OPTION` | Có thể chọn cơ chế khác; Phase sau quyết. |
| `DBSCAN noise` | Label `-1`, KHÔNG phải customer segment. |
| `WCSS` | Within-Cluster Sum of Squares; `DIAGNOSTIC_ONLY`. |
| `RQ1 / RQ2 / RQ3` | Algorithm comparison / preprocessing sensitivity / stability |
| `RFM Extended` | 14-feature RFM + extended behavioural features (FE-06). |
| `RFM-only` | 3-feature RFM; `FUTURE_WORK`, không trong current scope. |
| `K-Medoids` | `OUT OF SCOPE` per ADR-0003. |
| `ARI / AMI / Hungarian` | Stability metrics; methodology chưa lock. |
| `Block R / S / N` | EXP-05 reproducibility / seed / perturbation blocks. |
| `Cross-algorithm ranking` | Tổng xếp hạng nhiều thuật toán; bị cấm trong current scope. |
| `5-field reproducibility` | Input SHA + config hash + seed + environment + output SHA. |

---

## Appendix B — Change Log

| Date | Author | Change |
| --- | --- | --- |
| 2026-10-07 | SYS-06 author (AI assist) | Initial draft. Status `WORKING_DRAFT v0.1`. |
| 2026-10-07 | SYS-06 author (AI assist) | **v0.2 review pass** — applied mentor feedback:<br/>1. **P0 #1 (SYS-05 config-only)**: S-05 Step 4 refactored — K và `random_seed` hiển thị dưới dạng read-only snapshot từ configuration; user **không** nhập trực tiếp. Override từ UI = `REVIEW_REQUIRED` (`SYS-05` §15 item 8).<br/>2. **P0 #2 (API status enum)**: align với `SYS-05` G.3 — canonical enum `PENDING` / `RUNNING` / `SUCCEEDED` / `FAILED` / `CANCELLED` / `TIMEOUT`. §10.4 mở rộng với **API enum ↔ UI display label mapping** (Queued / Running / Completed / Failed / Cancelled / Timed out) làm single source of truth; EPIC-12 không được tự ý thay đổi mapping.<br/>3. **P1 #3 (screen count)**: §2.1 sửa `12 màn hình chính` → `13 màn hình chính` (khớp §8: S-01..S-13).<br/>4. **P1 #4 (K-bearing vs DBSCAN)**: S-05 Step 4 thêm bảng algorithm × K-applicability; DBSCAN ẩn trường K; validation bỏ qua trường K cho DBSCAN.<br/>5. **P1/P2 #5 (Validate button)**: S-02 thay `disabled if not validated` (ngược logic) bằng **state machine rõ ràng** — `NOT_VALIDATED` → enabled; `VALID` → disabled + icon `circle-check`; `VALIDATING` → disabled + spinner; `FAILED` → enabled + "Retry validation".<br/>6. **P1/P2 #6 (Audit flow)**: §2.1 sửa `2 secondary flows (Reports, Audit)` → `1 secondary flow (Reports) + Audit supporting view` (right rail, không phải screen, không trong sidebar). §5.2 + §7.3 phản ánh.<br/>7. **P1/P2 #7 (section count)**: §21.1 sửa `22 sections` → `22 main sections + 2 appendices`.<br/>8. **P1/P2 #8 (mock data)**: §18.4 tách thành **3-tier classification** — A. Research Evidence Data (đúng số liệu freeze); B. Prototype UI State Data (synthetic, có nhãn); C. Placeholder Data (chưa có giá trị). 5 quy tắc chung rõ ràng.<br/>9. **P1/P2 #9 (state design wording)**: §13 + §21.3 thay `Loading / empty / error / success states có` (quá tuyệt đối) bằng "**State phù hợp** (loading / empty / error / success / disabled / long-running) cho mỗi screen theo bảng §13". Bảng §13 thêm note giải thích `—` = not applicable.<br/>10. **P1/P2 #10 (research traceability)**: §17 sửa dòng `K range + seed = user input → LOCKED` (sai vì config-only) thành `K range + seed = config-only (read-only snapshot trong UI) → LOCKED; K / seed override từ UI = REVIEW_REQUIRED`.<br/>11. **Status** đổi từ `WORKING_DRAFT v0.1` → `REVIEW_READY v0.2`.<br/>12. Cập nhật prototype `index.html` tương ứng (status enum, wizard step 4 read-only, mock data tier). |

---

**Hết SYS-06.**
