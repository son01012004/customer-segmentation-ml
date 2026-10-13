# Research / Review — Chỉ mục review và audit

> **Mục đích của tài liệu này.**
> Đây là chỉ mục cho `docs/research/review/`. Tài liệu trong thư mục
> này là **review/audit độc lập** với research — ghi lại kết quả
> review, khóa methodology, hoặc tổng hợp pending decisions.
>
> **Ngôn ngữ diễn giải:** tiếng Việt.
> **Tên file, identifier, schema, thuật ngữ kỹ thuật:** giữ nguyên
> tiếng Anh theo convention hiện có.
>
> **Phạm vi:** navigation + ML01 ownership decision (Phase 2B.3). KHÔNG sửa, move,
> rename, merge, archive file ML01; KHÔNG sửa METHODOLOGY_LOCK_STATUS.md.

---

## 1. Phân biệt STATUS trong review files

Một số file trong thư mục này có STATUS rõ ràng ở header. Index này
**chỉ tham chiếu** các trạng thái đã ghi — KHÔNG tự ý nâng hoặc hạ.

| Trạng thái header điển hình | Ý nghĩa (theo chính file đó) |
|---|---|
| `RESOLVED` | Analysis/proposal đã xong. Quyết định đã được record ở nơi authoritative (ADR hoặc METHODOLOGY_LOCK_STATUS). |
| `METHODOLOGY_LOCKED` | Quyết định methodology đã được khóa. Có thể có working assumption còn treo. |
| `PENDING_DECISIONS` | Có quyết định methodology chưa được đưa ra. |
| `REVIEW_REQUIRED` | Review cần hoàn tất trước khi dùng làm evidence. |
| `PENDING` | Có mục chưa đầy đủ; không có nghĩa "bị bỏ". |

---

## 2. Danh sách file

| File | Vai trò | Status (theo header) |
|---|---|---|
| `FULL_RESEARCH_READINESS_AUDIT_FE01_EXP05.md` | Audit tổng thể từ FE-01 đến EXP-05. | (xem header để xác nhận) |
| `MENTOR_REVIEW_FORM_EXP01_EXP05.md` | Template/Form review cho mentor ở EXP-01..EXP-05. | (xem header để xác nhận) |
| `EXP01_EXP05_REVIEW_OVERVIEW.md` | Tổng quan review EXP-01..EXP-05. | (xem header để xác nhận) |
| `EXP01_EXP02_RESULTS_REVIEW.md` | Review kết quả EXP-01 (baseline) và EXP-02 (cluster number). | (xem header để xác nhận) |
| `EXP01_EXP05_PENDING_DECISIONS.md` | Danh sách pending decisions cho EXP-01..EXP-05. | `PENDING_DECISIONS` (xem header để xác nhận) |
| `EXP03_HYPERPARAMETER_REVIEW.md` | Review hyperparameter experiments (EXP-03). | (xem header để xác nhận) |
| `EXP04_PREPROCESSING_FEATURE_REVIEW.md` | Review preprocessing/feature experiments (EXP-04). | (xem header để xác nhận) |
| `EXP05_REPRODUCIBILITY_STABILITY_REVIEW.md` | Review reproducibility/stability experiments (EXP-05). | (xem header để xác nhận) |
| `METHODOLOGY_RESOLUTION_PROPOSAL.md` | Analysis/proposal phase để giải quyết methodology gaps. **KHÔNG phải authoritative spec.** Locked decisions đã được chuyển sang `METHODOLOGY_LOCK_STATUS.md` và ADRs. | `STATUS: RESOLVED` (theo header) |
| `METHODOLOGY_LOCK_STATUS.md` | **Authoritative record** cho locked methodology decisions (FE-01→FE-06→EPIC-06→EXP-01→EXP-05). Có bảng locked decisions và rerun impact. | `METHODOLOGY_LOCKED` (theo header) |
| `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` | Kế hoạch review ownership cho hai file ML01 (PascalCase + lowercase). Chứa vai trò đề xuất, cross-reference, decision IDs, 10 câu hỏi Q-01..Q-10 cho owner, và 3 phương án (A: bổ sung, B: giữ nguyên, C: merge + archive). Owner đã chọn **phương án B** (giữ cả hai file, không merge/archive). | `AWAITING_OWNER_REVIEW` (theo header; PHASE 2B.3 đã ghi quyết định B) |
| `RFM_ONLY_FUTURE_WORK_PLAN.md` | Plan dành cho future work RFM-only (baseline 3-feature). Hiện KHÔNG trong scope — xem ADR-0004. | `FUTURE WORK` (theo header) |

Lưu ý: với các file có ghi "(xem header để xác nhận)", trạng thái
chính xác cần đọc lại header file vì Phase 2B.1 chỉ skim section đầu.
PHASE 2B.3 đã thêm `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` vào danh sách.

---

## 3. Trọng tâm: hai file METHODOLOGY

### 3.1. `METHODOLOGY_LOCK_STATUS.md` — authoritative

- **Vai trò**: ghi lại các locked decisions từ `METHODOLOGY_RESOLUTION_PROPOSAL.md`.
  Authority: **chính file này**, kết hợp các ADR-0003/ADR-0004.
- **Khóa trong file (theo bảng ở §1 của file)**:
  - Algorithm scope: ✅ LOCKED (5 algorithms, K-Medoids OUT OF SCOPE).
  - RQ1, RQ2, RQ3: ✅ LOCKED.
  - Dataset version: ✅ LOCKED (`FE06-v1.0 = RESEARCH_WORKING_BASELINE`).
  - Feature set: ⚠️ WORKING (14 features, 6 ELIGIBLE_WORKING_ASSUMPTION).
  - Preprocessing config: ⚠️ WORKING (C7 yeo_johnson + robust + median).
  - RFM-only: ⏳ FUTURE WORK.
  - Cross-algorithm ranking: ⚠️ PENDING (chờ EPIC-08 Phase B + mentor approval).
- **Vai trò với Phase 2B.1 / Phase 2B.3**: đây là **nguồn duy nhất** mà Phase 2B.1
  tham chiếu cho locked decisions. KHÔNG sửa file này.

### 3.2. `METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis phase

- **Vai trò**: analysis/proposal phase đã dẫn đến lock. STATUS: RESOLVED.
- **Mối quan hệ với `METHODOLOGY_LOCK_STATUS.md`**:
  - `METHODOLOGY_RESOLUTION_PROPOSAL.md` = **proposal** (analysis).
  - `METHODOLOGY_LOCK_STATUS.md` = **locked decisions** (authoritative).
- **Phase 2B.1 archive?** Contract không nói "superseded" — proposal
  là analysis có giá trị tham khảo cho audit trail. Archive cần owner
  quyết định.
- **KHÔNG** tham chiếu file này làm authoritative spec — luôn dùng
  `METHODOLOGY_LOCK_STATUS.md` + ADRs.

### 3.3. Phân biệt trong giao tiếp

Khi viết documentation mới hoặc trả lời câu hỏi methodology:

- Câu hỏi về locked decisions → cite `METHODOLOGY_LOCK_STATUS.md`
  + ADR-0003 / ADR-0004.
- Câu hỏi về quá trình phân tích / background → cite
  `METHODOLOGY_RESOLUTION_PROPOSAL.md`.
- KHÔNG cite proposal làm "currently active rule".

---

## 4. Cross-reference vào thư mục khác

| Review file | Liên quan |
|---|---|
| `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` | `docs/research/ML01_Clustering_Experiment_Framework.md`, `docs/research/ML01_clustering_experiment_framework.md`, `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md`, `docs/README.md`, `docs/research/README.md`, `AGENTS.md` |
| `METHODOLOGY_RESOLUTION_PROPOSAL.md` | `decisions/0003-algorithm-scope.md`, `decisions/0004-research-questions.md`, `methodology/research_questions.md`, `methodology/methodology_overview.md`, `METHODOLOGY_LOCK_STATUS.md` (file cùng thư mục) |
| `METHODOLOGY_LOCK_STATUS.md` | 11 file đã tạo/sửa (xem §9 của file); `decisions/0003-*.md`, `decisions/0004-*.md` |
| `EXP01_EXP02_RESULTS_REVIEW.md`, `EXP03_HYPERPARAMETER_REVIEW.md`, `EXP04_PREPROCESSING_FEATURE_REVIEW.md`, `EXP05_REPRODUCIBILITY_STABILITY_REVIEW.md` | `research/EXP0X_*_PLAN.md` (xem `docs/research/README.md`) |
| `FULL_RESEARCH_READINESS_AUDIT_FE01_EXP05.md` | Research artifacts ở `docs/research/` + `docs/evaluation/CP-*` + `docs/evaluation/EVA-*` |
| `RFM_ONLY_FUTURE_WORK_PLAN.md` | ADR-0004 (RQ2 framing) + `methodology/research_questions.md` |

---

## 5. Rủi ro trạng thái — KHÔNG tự ý hành động

- KHÔNG archive `METHODOLOGY_RESOLUTION_PROPOSAL.md` cho dù STATUS là
  RESOLVED. Archive cần owner quyết định.
- KHÔNG sửa `METHODOLOGY_LOCK_STATUS.md` (authoritative record).
- KHÔNG tự ý nâng `PENDING_DECISIONS` thành `RESOLVED`.
- KHÔNG suy diễn `WORKING` / `WORKING_ASSUMPTION` thành `LOCKED`.
- KHÔNG thay đổi bất kỳ pending/pending-decision item nào.

Inventory chi tiết cho Phase 2B.1 ở `/tmp/phase2b1_documentation_inventory.md`
(ngoài repo).

---

## 7. Trạng thái ML01 (PHASE 2B.3)

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

Chi tiết: xem `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` §1.1, §6 (Q-10).

---

**Hết Phase 2B.1 review index. Phase 2B.3 đã ghi quyết định ML01 ownership (phương án B). KHÔNG tự bắt đầu consolidation, merge hoặc archive — chờ owner review.**
