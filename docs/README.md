# Docs — Chỉ mục điều hướng

> **Mục đích của tài liệu này.**
> Đây là **chỉ mục điều hướng** cho toàn bộ tài liệu trong `docs/`.
> Mục tiêu là giúp người đọc lần đầu (đặc biệt là reviewer bên ngoài) tra
> cứu nhanh đúng file theo đúng vai trò.
>
> **Ngôn ngữ:** tiếng Việt cho phần diễn giải; tên file, identifier, schema,
> thuật ngữ kỹ thuật giữ nguyên tiếng Anh theo convention hiện có của
> repository.
>
> **Ngày tạo index:** 2026-10-12.
> **Cập nhật:**
> - Phase 2B.3 (2026-10-12) — ghi quyết định ML01 ownership (phương án B) vào §5.3, §7.2, §10.
> - Phase 2C (2026-10-13) — thêm §11 (handoff status sang TEST).
> **Phạm vi:** navigation tối thiểu + ML01 ownership decision + §11 handoff pointer. KHÔNG consolidation, archive, move, rename hai file ML01.

---

## 1. Quy ước đọc nhanh

- **Canonical**: tài liệu đã được review nội bộ hoặc đại diện cho implementation
  state hiện tại của một phase. Đây là điểm vào mặc định.
- **Audit / Completion / Verification / Remediation / Final review**: ghi lại
  tiến trình thực thi của một phase, có thể có nội dung chồng lấn. Cần đọc
  song song với canonical document để hiểu đầy đủ.
- **Plan / Plan report**: kế hoạch trước khi thực thi. Có thể đã được
  supersede bởi canonical implementation plan.
- **Phase A / Phase B**: ký hiệu nội bộ cho các đợt review/acceptance riêng
  biệt trong cùng một phase. Không nên suy diễn technical acceptance thành
  owner approval.
- **`PENDING_REVIEW` / `REVIEW_REQUIRED` / `WORKING_ASSUMPTION`**: trạng thái
  chưa được phê duyệt cuối. Tài liệu ở trạng thái này **không** được tự
  ý diễn giải là đã được nghiên cứu thông qua.
- **`TECHNICALLY_IMPLEMENTED`**: code chạy được, tests pass, nhưng
  **chưa** được nghiên cứu phê duyệt.
- **`RESEARCH_DECISION_APPROVED`**: mentor/human researcher đã phê duyệt
  vấn đề methodology. Chỉ dùng khi có bằng chứng trong ADR hoặc report.
- **KHÔNG dùng** các thuật ngữ `best`, `winner`, `optimal`, `recommended`,
  `final`, `superior` để mô tả feature, algorithm, model trong tài liệu
  chưa phê duyệt. Xem `AGENTS.md` §2.5.

Mọi tài liệu dưới đây đều có thể chứa trạng thái `PENDING_REVIEW` hoặc
`WORKING_ASSUMPTION`. Index này **không** tự ý nâng trạng thái lên
`RESEARCH_DECISION_APPROVED` — quyết định đó thuộc về mentor/human researcher.

---

## 2. Sơ đồ thư mục

```
docs/
├── README.md                       ← file này (top-level navigation)
│
├── decisions/                      ← ADR (Architecture Decision Records)
│   ├── README.md                   (đã tồn tại)
│   ├── 0001-…  0002-…  0003-…  0004-…  0005-…  0006-…  0008-…  0009-…
│
├── methodology/                    ← methodology docs (do project lead cố định)
│   ├── README.md                   (đã tồn tại)
│   ├── methodology_overview.md
│   └── research_questions.md
│
├── data_dictionary/                ← schema + provenance
│   ├── README.md                   (đã tồn tại)
│   ├── data_dictionary.md
│   ├── dataset_provenance.md
│   ├── dataset_schema.csv
│   └── initial_data_profile.md
│
├── experiment_logs/                ← reproducibility logs
│   ├── README.md                   (đã tồn tại — template cho run logs)
│   └── …                           (file run logs sẽ được tạo khi experiment chạy)
│
├── research/                       ← research artifacts (FE / ML / EXP / EPIC)
│   ├── README.md                   (sẽ tạo ở Phase 2B.1)
│   ├── review/
│   │   ├── README.md               (sẽ tạo ở Phase 2B.1)
│   │   └── … review files
│   ├── algorithm_theory_v3_exports/  (binary exports, không phải Markdown)
│   └── … ML01…ML06, FE04…FE06, EXP/EPIC
│
├── evaluation/                     ← evaluation criteria, checkpoints
│   ├── CP-01.md … CP-05.md
│   └── EVA-01.md … EVA-05.md
│
└── system/                         ← system + DEV-stage plans/reports
    ├── SYS-01_requirements.md
    ├── SYS-02_architecture.md
    ├── SYS-03_data_model.md
    ├── SYS-04_ml_processing_pipeline.md
    ├── SYS-05_api_design.md
    ├── SYS-06_ui_ux_design.md
    ├── ui-prototype/
    └── DEV-01 … DEV-10              (implementation plans, reports, audit)
```

---

## 3. Từng thư mục — mô tả và vai trò

### 3.1. `docs/decisions/` — Quyết định nghiên cứu và kỹ thuật

- **Vai trò**: ghi lại các quyết định nghiên cứu / kỹ thuật theo template ADR.
- **Quy tắc**: ADR đã `Accepted` là bất biến. Khi đảo ngược, viết ADR mới
  supersede; không sửa ADR cũ.
- **Đã có ADR (theo `git ls-files` ở Phase 2B.1)**:
  - `0001-primary-dataset-uci-online-retail.md` (Accepted)
  - `0002-backup-dataset-uci-online-retail-ii.md` (Accepted)
  - `0003-algorithm-scope.md` (Accepted — five-algorithm benchmark, K-Medoids
    OUT OF SCOPE)
  - `0004-research-questions.md` (Accepted — RQ1/RQ2/RQ3 definitions)
- **ADRs hiện là untracked file** (chưa được commit; xem §6):
  - `0005-prototype-architecture-option-a.md`
  - `0006-dev05-prototype-noise-policy.md`
  - `0008-dev07-version-pattern.md`
  - `0009-prototype-storage-layout.md`
- **Điểm vào**: `docs/decisions/README.md`.

### 3.2. `docs/methodology/` — Methodology nghiên cứu

- **Vai trò**: research questions, study design, benchmarking protocol,
  unit of analysis. **Cố định bởi project lead**, không sửa bởi contributor.
- **Cách phê duyệt thay đổi**: PR + review + ADR mới.
- **Đã có file tracked**:
  - `methodology_overview.md`
  - `research_questions.md`
  - `README.md`
- **Điểm vào**: `docs/methodology/README.md`.

### 3.3. `docs/data_dictionary/` — Schema và provenance

- **Vai trò**: mô tả cột dataset (raw, processed, clustering-output).
- **Quy tắc**: cập nhật `data_dictionary.md` khi thêm feature/column mới.
  Xem `AGENTS.md` §5 (skipped data dictionary update là một
  forbidden shortcut).
- **Điểm vào**: `docs/data_dictionary/README.md`.

### 3.4. `docs/experiment_logs/` — Nhật ký reproducibility

- **Vai trò**: mỗi experiment run có một file log theo template trong
  `docs/experiment_logs/README.md`.
- **Trạng thái ở Phase 2B.1**: chỉ có `README.md`. File run log sẽ được
  tạo khi experiment chạy (Phase 2B.1 KHÔNG tạo run logs).

### 3.5. `docs/research/` — Research artifacts

- **Vai trò**: tài liệu kỹ thuật cho FE (feature engineering),
  ML (clustering algorithms), EXP (experiment plans), EPIC (cross-EPIC
  contracts). Không phải plan implementation — mà là research artifacts.
- **Điểm vào**: `docs/research/README.md` (tạo mới ở Phase 2B.1).
- **Sub-folder `docs/research/review/`**: các review/audit độc lập với
  research — xem `docs/research/review/README.md` (tạo mới ở Phase 2B.1).
- **Sub-folder `docs/research/algorithm_theory_v3_exports/`**: file binary
  (`.pdf`, `.docx`) — KHÔNG phải Markdown. KHÔNG cần index.
- **Hai biến thể tên ML01**:
  - `docs/research/ML01_Clustering_Experiment_Framework.md` (PascalCase)
    — đích danh của Mentor document cuối theo EPIC-06 contract.
  - `docs/research/ML01_clustering_experiment_framework.md` (lowercase)
    — Implementation Notes hiện tại. Theo EPIC-06 contract, file này
    sẽ được **tái cấu trúc** theo 12-section template khi viết
    Mentor document cuối. Trạng thái hiện tại KHÔNG được tuyên bố là
    "superseded" — contract chỉ nói "tái cấu trúc". Archive/merge
    cần owner quyết định (xem Phase 2B.1 inventory ngoài repo).
- **Phase 2B.1 KHÔNG archive file nào và KHÔNG sửa file nào trong
  `docs/research/`.**

### 3.6. `docs/evaluation/` — Criteria và checkpoints

- **Vai trò**: evaluation criteria, checkpoints (`CP-*`) và review
  perspectives (`EVA-*`) cho từng phase.
- **Đã có file tracked**: `CP-01.md … CP-05.md`, `EVA-01.md … EVA-05.md`.
- **Vài trò cụ thể**: cần xác nhận trong file từng nếu cần tra cứu nhanh.

### 3.7. `docs/system/` — SYS + DEV documents

- **`SYS-*` (system architecture)**:
  - `SYS-01_requirements.md`, `SYS-05_api_design.md` — đang có
    modification tracked ở Phase 2B.1 thời điểm (xem §6). KHÔNG sửa
    trong Phase 2B.1.
  - `SYS-02_architecture.md`, `SYS-03_data_model.md`,
    `SYS-04_ml_processing_pipeline.md`, `SYS-06_ui_ux_design.md` —
    canonical architecture.
  - `ui-prototype/` — UI prototype assets.
- **`DEV-*` (DEV-stage plans/reports)**: toàn bộ là untracked file ở
  Phase 2B.1 thời điểm. Vai trò lẫn lộn giữa implementation plan,
  completion/verification report, audit trail, remediation, final review
  (xem §4 và §5 bên dưới cho từng cụm).

---

## 4. DEV-stage documents — phân loại vai trò

Hầu hết `DEV-*` documents hiện ở Phase 2B.1 đều là **untracked file**
(chưa được commit). Quyết định cuối cùng về việc giữ riêng, gộp, hoặc
archive từng file thuộc về owner (Phase 2B.1 KHÔNG consolidation).
Dưới đây là bản đồ vai trò **dựa trên header + cấu trúc đã đọc**,
không phải đánh giá overlap %.

### 4.1. DEV-05 — Evaluation module

| File | Vai trò |
|---|---|
| `DEV-05_evaluation_module.md` | Canonical — module specification |
| `DEV-05_completion_summary.md` | Completion report |
| `DEV-05_verification_report.md` | Verification report |
| `DEV-05_remediation_report.md` | Remediation report |
| `DEV-05_final_review_report.md` | Final review report |

Status gộp: 5 file, trong đó 1 canonical (`_evaluation_module.md`) +
4 audit/report. Cần owner quyết định việc keep/merge từng nhóm (xem
inventory ngoài repo).

### 4.2. DEV-06 — Customer segmentation module

| File | Vai trò |
|---|---|
| `DEV-06_customer_segment_module.md` | Canonical — module specification |
| `DEV-06_implementation_report.md` | Implementation report |
| `DEV-06_remediation_report.md` | Remediation report |

Status gộp: 3 file, trong đó 1 canonical + 2 reports.

### 4.3. DEV-07 — Marketing framework

| File | Vai trò (initial assessment) |
|---|---|
| `DEV-07_implementation_plan.md` | Canonical — implementation plan |
| `DEV-07_planning_report.md` | Planning report (pre-implementation) |
| `DEV-07_final_acceptance_report.md` | Phase A final acceptance report |
| `DEV-07_phase_a_audit_report.md` | Phase A audit |
| `DEV-07_phase_b_decision_memo.md` | Phase B decision memo |
| `DEV-07_phase_b_acceptance_report.md` | Phase B technical acceptance |
| `DEV-07_owner_decision_brief.md` | Owner decision brief |
| `DEV-07_owner_decision_matrix.md` | Owner decision matrix |
| `DEV-07_remediation_report.md` | Remediation report |

9 file. Có **phase A vs phase B** riêng biệt; Phase B vẫn có
`REVIEW_REQUIRED` cho các owner-level open questions (OQ-D07-*).
Phase 2B.1 KHÔNG suy diễn technical acceptance thành owner approval.
Cần owner review từng file để quyết định keep/merge/archive (xem
inventory ngoài repo).

### 4.4. DEV-08 / DEV-09 / DEV-10

| File | Vai trò (initial assessment) |
|---|---|
| `DEV-08_implementation_plan.md` | Canonical — implementation plan |
| `DEV-08_completion_report.md` | Completion report |
| `DEV-08_DEV-09_readiness_report.md` | Cross-phase readiness report |
| `DEV-09_completion_report.md` | Completion report |
| `DEV-10_handoff_report.md` | Handoff report |

DEV-08/09/10 không thuộc phạm vi inventory Phase 2B.1 (task chỉ yêu cầu
DEV-05/06/07 chi tiết) — chỉ liệt kê để điều hướng.

### 4.5. DEV-01 đến DEV-04

| File | Vai trò |
|---|---|
| `DEV-01_project_setup.md` | Phase 1 — project setup |
| `DEV-02_dataset_management.md` | Phase 2 — dataset management |
| `DEV-03_preprocessing.md` / `DEV-03_completion_summary.md` | Phase 3 — preprocessing (spec + summary) |
| `DEV-04_clustering_execution.md` / `DEV-04_completion_summary.md` | Phase 4 — clustering execution (spec + summary) |

DEV-01..04 nằm ngoài phạm vi inventory chi tiết Phase 2B.1 — chỉ liệt kê
để điều hướng.

---

## 5. Trạng thái tài liệu ở Phase 2B.1

### 5.1. Tracked vs untracked (docs/)

**Tracked (đã được git track trước Phase 2B.1):**

- Tất cả file trong `docs/decisions/` (ngoại trừ 4 ADR 0005/0006/0008/0009
  hiện đang untracked).
- Tất cả file trong `docs/methodology/`.
- Tất cả file trong `docs/data_dictionary/`.
- `docs/experiment_logs/README.md`.
- Tất cả file trong `docs/evaluation/`.
- Tất cả file trong `docs/research/` (kể cả hai biến thể ML01).
- `docs/system/SYS-02_architecture.md`, `SYS-03_data_model.md`,
  `SYS-04_ml_processing_pipeline.md`, `SYS-06_ui_ux_design.md`.

**Modified tracked (đã có thay đổi chưa commit ở Phase 2B.1 — KHÔNG sửa
trong phase này, xem §6):**

- `.gitignore`
- `docs/system/SYS-01_requirements.md`
- `docs/system/SYS-05_api_design.md`
- `pyproject.toml`

**Untracked (chưa được commit):**

- `docs/decisions/0005…0006…0008…0009-prototype-*.md`
- Toàn bộ `docs/system/DEV-01…DEV-10-*.md`
- Toàn bộ `scripts/dev0*.py`
- Toàn bộ `src/customer_segmentation/dataset_management/`
- `src/customer_segmentation/prototype/`
- Toàn bộ `tests/test_dev0*.py` + `tests/conftest.py` + `tests/fixtures/`
- Toàn bộ `configs/dev0*.yaml`
- `docs/research/algorithm_theory_v3_exports/` (binary exports — đã
  tồn tại trên working tree trước Phase 2B.1 nhưng chưa được commit;
  KHÔNG phải Markdown, xem §3.5)

Phase 2B.1 **KHÔNG** sửa, move, rename, merge, xóa bất kỳ file nào
trong các nhóm trên. Phase 2B.1 chỉ tạo 3 file README mới. Phase 2B.3
đã tạo thêm `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` và cập nhật phase
markers (xem §7.2).

### 5.2. `reports/` (generated, không thuộc docs/)

`reports/**` sinh ra từ pipeline (không committed). Xem `AGENTS.md` §2.12.
Phase 2B.1 KHÔNG đọc hoặc kiểm tra `reports/` vì:
- Theo convention không commit, có thể chưa được tạo trên working tree.
- Không liên quan đến navigation tối thiểu.

### 5.3. Trạng thái phê duyệt methodology (chỉ tham chiếu)

- **Algorithm scope**: LOCKED via ADR-0003 (5 algorithms, K-Medoids OUT OF SCOPE).
- **RQ1/RQ2/RQ3**: LOCKED via ADR-0004.
- **`docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md`** —
  STATUS: RESOLVED (theo header). Đây là **analysis phase**, không phải
  authoritative spec.
- **`docs/research/review/METHODOLOGY_LOCK_STATUS.md`** —
  STATUS: METHODOLOGY_LOCKED. Đây là authoritative record cho locked
  decisions.
- **`docs/research/ML01_Clustering_Experiment_Framework.md`** vs
  **`docs/research/ML01_clustering_experiment_framework.md`**:
  Owner đã chọn **phương án B** (giữ cả hai file, không merge/archive)
  trong PHASE 2B.3. Chi tiết: xem `docs/research/review/ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` §1.1, §6 (Q-10).

Phase 2B.1 / Phase 2B.3 KHÔNG tự ý nâng trạng thái methodology quá mức các file đã
ghi rõ.

---

## 6. Rủi ro trạng thái — KHÔNG tự ý hành động

Các thay đổi tracked sau đây **KHÔNG được revert, sửa hoặc ghi đè**:

1. `.gitignore` (modified)
2. `docs/system/SYS-01_requirements.md` (modified)
3. `docs/system/SYS-05_api_design.md` (modified)
4. `pyproject.toml` (modified)

Các file untracked sau đây **KHÔNG được move, rename, merge, xóa**
trong Phase 2B.1 và Phase 2B.3 (trừ khi owner phê duyệt):

- Tất cả `docs/system/DEV-*.md`
- Tất cả `docs/decisions/0005…0009-*.md`
- Tất cả `scripts/dev0*.py`
- Tất cả file dưới `src/customer_segmentation/{dataset_management,prototype}/`
- Tất cả `tests/test_dev0*.py`, `tests/conftest.py`, `tests/fixtures/`
- Tất cả `configs/dev0*.yaml`

Inventory ngoài repo (xem §7) đã ghi rõ từng file và rủi ro.

---

## 7. Phase deliverables (Phase 2B.1 + Phase 2B.3)

### 7.1. Phase 2B.1 deliverables

Phase 2B.1 tạo **3 file mới**, không touch file hiện có:

| File | Mục đích |
|---|---|
| `docs/README.md` | Top-level navigation (file này) |
| `docs/research/README.md` | Index cho research/ |
| `docs/research/review/README.md` | Index cho research/review/ |

### 7.2. Phase 2B.3 deliverables

Phase 2B.3 tạo thêm **1 file mới** và cập nhật phase markers trong 3 file README:

| File | Mục đích |
|---|---|
| `docs/research/review/ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` | Kế hoạch review ownership cho hai file ML01. Owner đã chọn phương án B (giữ cả hai file). |
| `docs/README.md` | Cập nhật §10 (ML01 ownership decision) |
| `docs/research/README.md` | Cập nhật §8 (ML01 ownership decision) |
| `docs/research/review/README.md` | Thêm `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` vào §2; thêm §7 (ML01 ownership decision) |

Inventory chi tiết cho DEV-05/06/07, ML01, METHODOLOGY_RESOLUTION,
METHODOLOGY_LOCK_STATUS được lưu **ngoài repo** tại
`/tmp/phase2b1_documentation_inventory.md` (xem §8).
File này KHÔNG được commit vào Git; dùng để owner review trước khi
chọn phương án consolidation/archive.

Phase 2B.1 **KHÔNG** tạo:

- `docs/QUY_CHUAN_TAI_LIEU.md` — chờ owner yêu cầu cụ thể + nội dung
  giới hạn ở hướng dẫn ngôn ngữ/trình bày không mâu thuẫn `AGENTS.md`.
- `docs/archive/README.md` — chờ owner phê duyệt chính sách archive.

---

## 8. Liên kết đến inventory ngoài repo

- **Inventory Phase 2B.1** (ngoài repo, không commit):
  `/tmp/phase2b1_documentation_inventory.md`
- **Báo cáo Phase 2A** (history; agent transcripts): đã có sẵn từ
  Phase 2A.1.

---

## 9. Các quy tắc bắt buộc của `AGENTS.md` (liên kết nhanh)

Mọi contributor và AI agent làm việc trên repo này phải đọc và tuân
thủ `AGENTS.md` ở root. Các điểm hay bị vi phạm nhất ở phase tài liệu:

- §2.1 Research integrity — KHÔNG invent data/kết quả/tham khảo.
- §2.5 Research decision language — dùng `CANDIDATE`,
  `PENDING_REVIEW`, `WORKING_ASSUMPTION`, `RETAIN_CANDIDATE` thay vì
  `best`/`winner`/`optimal`.
- §2.9 No silent policy changes.
- §2.10 Human approval gate — `TECHNICALLY_IMPLEMENTED` KHÔNG
  đồng nghĩa `RESEARCH_DECISION_APPROVED`.
- §2.11 Git — agent KHÔNG commit/push/PR/merge/branch/stage/reset/
  checkout/clean/stash.
- §2.12 Data privacy — KHÔNG commit raw/interim/processed/external
  dataset; KHÔNG commit `reports/**`.
- §5 Forbidden shortcuts — KHÔNG hard-code, KHÔNG copy-paste logic
  notebook ↔ src/, KHÔNG thêm dependency thiếu ADR.
- §6 Escalation — dừng và hỏi khi có methodology ambiguity.

---

## 10. Trạng thái ML01 (PHASE 2B.3)

**Quyết định ownership ML01 (PHASE 2B.3):**

Hai file ML01 được giữ nguyên tại `docs/research/`:
- `ML01_Clustering_Experiment_Framework.md` (PascalCase) — Mentor document theo contract 12 sections.
- `ML01_clustering_experiment_framework.md` (lowercase) — Implementation Notes.

**Phương án B** đã được chọn:
- Giữ cả hai file, không merge, không archive, không move, không rename.
- PascalCase tiếp tục là tài liệu hướng tới Mentor.
- Lowercase tiếp tục là Implementation Notes.
- Không chuẩn hóa bảy decision IDs (`ML-01-MET-01..04`, `ML-01-ENG-01..03`).
- Không thay đổi trạng thái `PENDING_REVIEW` / `DOCUMENTED`.

Chi tiết: xem `docs/research/review/ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` §1.1, §6 (Q-10).

---

## 11. Trạng thái bàn giao (PHASE 2C — sang TEST)

> Pointer ngắn; nội dung chi tiết nằm ở
> `docs/system/DEV-10_handoff_report.md`. Phần này mô tả
> **technical implementation status**, KHÔNG đồng nghĩa với
> **research approval** (xem `AGENTS.md` §2.10).

- **Báo cáo handoff**:
  [`DEV-10_handoff_report.md`](./system/DEV-10_handoff_report.md).
- **Verdict (DEV-10):** `TECHNICALLY_IMPLEMENTED`. Pipeline
  `DEV-02 → DEV-05` chạy được trên dữ liệu thật UCI Online Retail
  (541,909 giao dịch → 4,371 customers × 14 features) và trên
  synthetic fixture; 5 thuật toán (`ADR-0003`) đều wrap + evaluate.
- **Test suite gần nhất:** 2,094 passed, 1 skipped (xem DEV-10 §4).
- **Open gates** (KHÔNG tự ý giải): DBSCAN methodology (D-DEV04-ML04-01);
  MKT-01..MKT-05 (`ABSENT`); OQ-D05 / OQ-D07; SYS-01 OQ; SYS-02 `DRAFT`;
  EPIC-08/09/10; K-01 (missing preprocessed log).
- **Pointer trong README gốc:** xem `README.md` §12 — tựa đề
  "Bàn giao giai đoạn TEST" (cùng verdict, cùng open gates, cùng
  ngày cập nhật).

**Phase 2B.1 + Phase 2B.3 navigation bảo toàn:** §1–§10 vẫn giữ nguyên;
phase marker này chỉ bổ sung pointer sang TEST phase, không sửa nội
dung của bất kỳ ADR hoặc `docs/system/DEV-*` nào.

---
