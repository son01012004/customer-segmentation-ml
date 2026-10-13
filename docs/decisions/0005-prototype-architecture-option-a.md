# ADR-0005 — Prototype Architecture: File-Based Batch / Offline (Option A)

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, status enum, command, file path, EPIC ID,
> OQ ID theo convention hiện có.

- **Status**: Accepted
- **Date**: 2026-10-08
- **Deciders**: Human researcher (mentor)
- **Task ID**: DEV-01 (and pre-existing SYS-01 §13 OQ-09, OQ-10, OQ-11)

## Context

SYS-01 §13 (Limitations / Open Questions) ghi lại ba open question chờ
quyết định của mentor trước khi DEV-01 có thể tiến hành:

- **OQ-09** — Prototype chạy trên Jupyter notebook (UI-less) hay standalone
  web app (Streamlit / Flask / Django)? Ảnh hưởng SYS-02 (architecture),
  SYS-06 (UI). Trạng thái: REVIEW_REQUIRED — chưa quyết định.
- **OQ-10** — Có cần API layer (REST / GraphQL) cho SYS-01, hay prototype
  chỉ là CLI + notebook? Ảnh hưởng SYS-02 architecture. Trạng thái:
  REVIEW_REQUIRED — recommend CLI + notebook trước; API là future work.
- **OQ-11** — Database có cần không (PostgreSQL, SQLite, ...)? Ảnh hưởng
  SYS-02 architecture; hiện tại repo dùng parquet files. Recommend:
  KHÔNG cần database trong prototype. Parquet + filesystem đã đủ cho
  185 runs + profiling evidence.

SYS-02, SYS-03 và SYS-04 (đều `DRAFT — pending mentor/researcher
review`) mô tả nhất quán một file-based, batch, offline prototype
không có database, không có backend service, và không có message
broker. SYS-05 (`WORKING_DRAFT v0.1`) mô tả một REST API backend đầy
đủ với job queue, ML worker, và metadata database. Ba OQ ở trên là
biểu hiện document của architecture decision giải quyết mâu thuẫn
này.

DEV-01 (project setup cho current prototype phase) không thể tiến
hành nếu không có architecture decision được ghi lại.

## Decision

Cho current prototype phase, architecture là **Option A: File-Based
Batch / Offline Prototype**:

1. **Operator interface**: Python CLI / `scripts/run_*.py` entry points.
2. **ML orchestration**: Direct call từ `scripts/` tới
   `src/customer_segmentation/*` modules (không HTTP service, không
   separate worker process, không job queue).
3. **Persistence**: Filesystem + Parquet (`data/processed/`,
   `data/interim/`) + JSON manifests (`reports/<stage>/<run_id>/`).
4. **Prototype frontend**: `docs/system/ui-prototype/index.html` hiện
   có (vanilla HTML / CSS / JS, mock data, design review only). Đây
   là SYS-06 interactive prototype, **không** phải production React /
   Vue frontend.
5. **Backend / API / database**: **KHÔNG** implement trong current
   prototype phase. SYS-05 được giữ làm API design reference only.

Quyết định này **chỉ áp dụng** cho current prototype phase. Nó KHÔNG
vĩnh viễn cấm một API / backend / database architecture trong tương lai
ở EPIC-12 hoặc các phase sau. Bất kỳ reversal hay supersession nào của
quyết định này phải được ghi thành một ADR mới (theo
`docs/decisions/README.md` immutability convention).

## Resolves

- `docs/system/SYS-01_requirements.md` §13 OQ-09 → RESOLVED
- `docs/system/SYS-01_requirements.md` §13 OQ-10 → RESOLVED
- `docs/system/SYS-01_requirements.md` §13 OQ-11 → RESOLVED

## Affected documents

| File | Affected scope |
|---|---|
| `docs/system/SYS-01_requirements.md` | §13 table — OQ-09 / OQ-10 / OQ-11 rows |
| `docs/system/SYS-05_api_design.md` | Header (thêm phase status); §1, §1.3, §15 — chỉ additive clarifications. **API endpoint schemas, error codes, request/response schemas, OpenAPI design patterns được GIỮ LÀM design reference cho EPIC-12.** |
| `docs/system/DEV-01_project_setup.md` | New file — acceptance criteria + Architecture Boundary section |

Các tài liệu sau **không** bị sửa bởi ADR này (đã nhất quán với
Option A):

- `docs/system/SYS-02_architecture.md`
- `docs/system/SYS-03_data_model.md`
- `docs/system/SYS-04_ml_processing_pipeline.md`
- `docs/system/SYS-06_ui_ux_design.md`
- `AGENTS.md`
- `src/customer_segmentation/**`, `scripts/**`, `configs/**`,
  `tests/**`, `docs/research/**`, `docs/decisions/0001-0004`,
  `data/**`, `reports/**`.

## Alternatives Considered

### Option B — Full Backend + Database (FastAPI + PostgreSQL + ML Worker)

**Description**: Production-style backend REST API với FastAPI + uvicorn,
PostgreSQL metadata store, RQ / Celery job queue, separate ML worker
process, React / Vue SPA frontend. Repository trở thành multi-service
application deployable qua Docker Compose.

**Decision**: Bị reject cho current prototype phase.

**Reason**:

- Trực tiếp mâu thuẫn với SYS-02 §1, §1.12, §1.14, §2.1, §2.2;
  SYS-03 §1, §2.2; SYS-04 §4.1 — tất cả đều explicitly state
  "no request/response service, no database, no message broker,
  scripts → research core directly".
- Thêm 5+ dependency mới (FastAPI, uvicorn, SQLAlchemy, psycopg,
  RQ / Celery) cộng với containerization, mất cân đối infrastructure
  cho batch 185 run của offline research workflow.
- Repository hiện đã implement 5 thuật toán, evaluation framework,
  profiling framework, 185 experimental run, và tests — tất cả
  tương thích với Option A và không nhất quán với Option B service
  topology.

### Option C — Lightweight API Service + SQLite (Hybrid)

**Description**: FastAPI service giới hạn ở dataset operations và
job submission; SQLite cho metadata; ML execution vẫn chạy trực tiếp
qua `scripts/` (synchronous, không job queue); HTML prototype không
đổi.

**Decision**: Bị reject cho current prototype phase.

**Reason**:

- Vẫn mâu thuẫn với SYS-02/03/04 statement tường minh "no service,
  no DB", dù với blast radius nhỏ hơn Option B.
- Thêm architectural ambiguity ("hybrid" boundary) mà không có
  research benefit — SQLite là single-user, nên filesystem + JSON
  manifests đạt được cùng metadata persistence với zero new
  infrastructure.
- Nếu production API cần sau này, chỗ đúng để giới thiệu nó là
  EPIC-12 (với ADR, schema, auth, deployment đầy đủ). Làm bây giờ
  tạo ra intermediate state sẽ cần migrate.

## Consequences

### Dễ hơn

- Trạng thái repository hiện tại đã Option A compliant — không có
  code mới, không dependency mới, không infrastructure mới.
- 5 clustering algorithm (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy
  C-Means theo ADR-0003), 185 experimental run qua EXP-01 đến EXP-05,
  evaluation framework, profiling framework, và tất cả test trong
  `tests/` tiếp tục hoạt động không đổi.
- Research core (`src/customer_segmentation/*`) vẫn là single source
  of truth cho ML processing. Không re-implementation dưới service
  wrappers.
- SYS-05 được giữ làm API design reference cho EPIC-12 — endpoint
  schemas, error codes, request/response structures, và OpenAPI
  patterns của nó vẫn là useful future artifacts.
- `docs/system/ui-prototype/index.html` hiện có phục vụ như design /
  mentor / UX review artifact cho prototype UX.
- Operator workflow là reproducible: clone repo → install → run
  `python scripts/run_*.py` → inspect `reports/<stage>/<run_id>/`.
- HTML prototype verification là tầm thường: mở file trong browser;
  không cần server.

### Khó hơn hoặc rủi ro hơn

- Operator phải dùng CLI để chạy thí nghiệm. Không có web-based
  experiment management UI trong phase này.
- Run history được quản lý qua filesystem + JSON manifest file dưới
  `reports/<stage>/<run_id>/`, không qua centralised database. Cho
  185 run điều này đủ; nếu dự án scale lên hàng nghìn run, EPIC-12
  có thể cần một metadata store đúng nghĩa.
- HTML prototype dùng mock data only. Real API integration thuộc
  EPIC-12.
- Nếu một phase tương lai (EPIC-12) quyết định giới thiệu API /
  backend / database, một ADR mới phải supersede ADR-0005. Option A
  decision là immutable khi đã accepted theo
  `docs/decisions/README.md`.

## Scope of This Decision

ADR này bao trùm:

- Current prototype phase architecture.
- DEV-01 acceptance criteria và project setup.
- SYS-01 §13 OQ-09, OQ-10, OQ-11 resolution.
- SYS-05 phase status (FUTURE_WORK cho current prototype phase).

ADR này KHÔNG:

- Thay đổi research methodology (thuật toán, dataset, feature,
  preprocessing, evaluation metric, research question).
- Ảnh hưởng bất kỳ ADR-0001, ADR-0002, ADR-0003, ADR-0004 nào.
- Ngăn EPIC-12 thêm một production API / backend / database architecture
  trong một phase tương lai (phải được ghi thành ADR mới supersede
  ADR-0005).
- Đưa ra bất kỳ claim "best", "optimal", "recommended", "final",
  hoặc "winning" nào theo nghĩa research. ADR-0005 là engineering /
  architecture decision, không phải methodology decision. `AGENTS.md`
  §2.5, §2.6, §2.10 không bị ảnh hưởng.

## References

- `docs/system/SYS-01_requirements.md` §13 OQ-09, OQ-10, OQ-11 —
  open question được giải quyết bởi ADR này.
- `docs/system/SYS-02_architecture.md` §1, §1.12, §1.14, §2.1, §2.2,
  §5, §7, §8 — Option A nhất quán đầy đủ với mọi SYS-02 statement.
- `docs/system/SYS-03_data_model.md` §1, §2.2, §13 — Option A nhất
  quán đầy đủ với mọi SYS-03 statement.
- `docs/system/SYS-04_ml_processing_pipeline.md` §4.1 — Option A nhất
  quán đầy đủ với mọi SYS-04 statement.
- `docs/system/SYS-05_api_design.md` — Header (thêm phase status),
  §1, §1.3, §15 (additive phase-status clarifications). Tất cả API
  design content được giữ làm reference cho EPIC-12.
- `docs/system/SYS-06_ui_ux_design.md` — HTML prototype scope.
- `docs/system/ui-prototype/index.html` — interactive HTML prototype
  hiện có.
- `AGENTS.md` §4 step 7 (ADR-before-PR), §9 (phase-specific decisions
  → ADR), §2.10 (human approval gate), §2.11 (Git ops owned by human
  researcher), §6 (escalation).
- `docs/decisions/README.md` — ADR immutability convention.
- `docs/decisions/0001-primary-dataset-uci-online-retail.md`
- `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md`
- `docs/decisions/0003-algorithm-scope.md`
- `docs/decisions/0004-research-questions.md`
- `src/customer_segmentation/clustering/registry.py` — năm thuật
  toán đã registered theo ADR-0003.
- `scripts/run_*.py` — CLI entry points hiện có (Option A compliant).
- `configs/*.yaml` — file configuration hiện có.
- `tests/test_ml01_framework.py`, `tests/test_ml02_kmeans.py` …
  `tests/test_ml06_fuzzy.py` — test hiện có (Option A compliant).
- Architecture Review Report (2026-10-08) — so sánh Option A / B / C
  và conflict matrix.
- Change Plan — Revised (2026-10-08) — đã được human researcher phê
  duyệt.
