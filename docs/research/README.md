# Research — Chỉ mục tài liệu research

> **Mục đích của tài liệu này.**
> Đây là chỉ mục cho `docs/research/`. Tài liệu trong thư mục này
> là **research artifacts** cho FE (feature engineering), ML
> (clustering algorithms), EXP (experiment plans), EPIC (cross-EPIC
> contracts). Không phải `plan/` implementation — không phải
> `report/` thực thi.
>
> **Ngôn ngữ diễn giải:** tiếng Việt.
> **Tên file, identifier, schema, thuật ngữ kỹ thuật:** giữ nguyên
> tiếng Anh theo convention hiện có.
>
> **Phạm vi:** navigation + ML01 ownership decision (Phase 2B.3). KHÔNG sửa, move,
> rename, merge, archive file ML01; KHÔNG sửa METHODOLOGY_LOCK_STATUS.md.

---

## 1. Quy ước vai trò

| Loại file | Vai trò | Trạng thái điển hình |
|---|---|---|
| **Specification / Contract** (`EPIC*_DOCUMENTATION_CONTRACT.md`, `EPIC*_PLAN.md`) | Đặc tả cấu trúc nội dung Mentor document | `TECHNICALLY_IMPLEMENTED` |
| **Plan** (`*_PLAN.md`, `FE*_*.md`, `ML*-*.md`) | Kế hoạch nghiên cứu theo task ID | `TECHNICALLY_IMPLEMENTED` (chưa chạy) hoặc `PENDING_REVIEW` |
| **Review / Audit** (`review/*`) | Review/audit độc lập — xem `docs/research/review/README.md` | `RESOLVED`, `REVIEW_REQUIRED`, `PENDING`, tuỳ file |
| **Exports (binary)** (`algorithm_theory_v3_exports/`) | File binary (`.pdf`, `.docx`) không phải Markdown. KHÔNG dùng Markdown index. | N/A |

Index này **không** tự ý nâng trạng thái file lên
`RESEARCH_DECISION_APPROVED` — quyết định methodology thuộc về
mentor/human researcher (xem `AGENTS.md` §2.10).

---

## 2. Hai biến thể tên ML01 — lưu ý quan trọng

Trong thư mục hiện có **hai file cùng nội dung dạng ML01** với
tên khác nhau:

| File | Phân biệt | Theo EPIC-06 contract |
|---|---|---|
| `docs/research/ML01_Clustering_Experiment_Framework.md` (PascalCase) | Tên theo template Mentor document 12-section. | Đích danh của Mentor document cuối cho ML-01. |
| `docs/research/ML01_clustering_experiment_framework.md` (lowercase) | "Implementation Notes" — ghi rõ trong header. | Sẽ được **tái cấu trúc lại** theo 12-section template khi viết Mentor document cuối. |

Contract nói rõ: file lowercase sẽ được "tái cấu trúc" chứ KHÔNG nói
"superseded" hay "xóa". Trên hệ điều hành Linux phân biệt hai file
(lowercase ≠ PascalCase); trên Windows/macOS (khi checkout qua một số
filesystem) hai file có thể gây collision. Archive/merge/unify cần
**owner quyết định** (xem Phase 2B.1 inventory ngoài repo).

Hai file này cùng tồn tại — index này KHÔNG tự ý merge hoặc archive.

---

## 3. Danh sách file — FE / ML / EXP / EPIC

### 3.1. EPIC contracts / plans

| File | Vai trò |
|---|---|
| `EPIC06_DOCUMENTATION_CONTRACT.md` | Spec chuẩn hóa 6 Mentor document ML-01..ML-06. Định nghĩa 12-section template, methodology boundary, formula, visualization boundary. |
| `EPIC09_CP05_PLAN.md` | Plan cho EPIC-09 / CP-05. |

### 3.2. Feature engineering (FE)

| File | Vai trò |
|---|---|
| `FE04_Customer_Level_Aggregation.md` | Customer-level aggregation spec (FE-04). |
| `FE05_Customer_Feature_Engineering.md` | RFM + extended feature engineering spec (FE-05). |
| `FE06_Transformation_Final_Dataset.md` | Final clustering dataset transformation spec (FE-06) — cung cấp input cho ML-01. |

### 3.3. Clustering experiment framework và algorithms (ML)

| File | Vai trò |
|---|---|
| `ML01_Clustering_Experiment_Framework.md` (PascalCase) | Mentor document cho ML-01 (đích danh theo EPIC-06 contract). |
| `ML01_clustering_experiment_framework.md` (lowercase) | ML-01 Implementation Notes hiện tại. Sẽ được tái cấu trúc theo 12-section template khi viết Mentor document cuối. |
| `ML02_KMeans.md` | Mentor document cho ML-02 (K-Means). |
| `ML03_Hierarchical_Clustering.md` | Mentor document cho ML-03 (Agglomerative). |
| `ML04_DBSCAN.md` | Mentor document cho ML-04 (DBSCAN — bao gồm noise label `-1`). |
| `ML05_GMM.md` | Mentor document cho ML-05 (GMM — posterior probabilities). |
| `ML06_Fuzzy_CMeans.md` | Mentor document cho ML-06 (Fuzzy C-Means + Algorithm Baseline — membership matrix). |

### 3.4. Experiments (EXP)

| File | Vai trò |
|---|---|
| `EXP01_baseline_experiment_PLAN.md` | Plan baseline experiment (EXP-01). |
| `EXP02_cluster_number_PLAN.md` | Plan cluster-number experiment (EXP-02). |
| `EXP05_stability_reproducibility_PLAN.md` | Plan stability/reproducibility experiment (EXP-05). |

### 3.5. Algorithm theory exports (binary)

```
docs/research/algorithm_theory_v3_exports/
├── ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON_v3.docx
└── ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON_v3.pdf
```

- File binary được export từ nguồn khác (Word/PDF).
- **KHÔNG** dùng Markdown index cho folder này (không phải `.md`).
- **KHÔNG** tham chiếu nội dung file binary trong tài liệu Markdown
  nếu không có citation chuẩn.

---

## 4. Sub-folder `docs/research/review/`

Xem `docs/research/review/README.md` (tạo mới ở Phase 2B.1). Bao gồm:

- `EXP01_EXP02_RESULTS_REVIEW.md`
- `EXP01_EXP05_PENDING_DECISIONS.md`
- `EXP01_EXP05_REVIEW_OVERVIEW.md`
- `EXP03_HYPERPARAMETER_REVIEW.md`
- `EXP04_PREPROCESSING_FEATURE_REVIEW.md`
- `EXP05_REPRODUCIBILITY_STABILITY_REVIEW.md`
- `FULL_RESEARCH_READINESS_AUDIT_FE01_EXP05.md`
- `MENTOR_REVIEW_FORM_EXP01_EXP05.md`
- `METHODOLOGY_LOCK_STATUS.md` — authoritative record của locked
  methodology decisions (xem §5).
- `METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis phase, STATUS:
  RESOLVED. KHÔNG phải authoritative spec.
- `RFM_ONLY_FUTURE_WORK_PLAN.md`

---

## 5. Trạng thái methodology (chỉ tham chiếu)

Các quyết định methodology **được** lock bởi ADR (xem
`docs/decisions/0003-algorithm-scope.md`, `docs/decisions/0004-research-questions.md`):

- **Algorithm scope**: ✅ LOCKED qua ADR-0003. 5 algorithms:
  K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means.
  **K-Medoids OUT OF SCOPE** (theo investigation trong ADR-0003:
  hiện chỉ có `NotImplementedError` placeholder).
- **RQ1, RQ2, RQ3**: ✅ LOCKED qua ADR-0004.
- **Feature set & preprocessing config**: ⚠️ WORKING trong
  `docs/research/review/METHODOLOGY_LOCK_STATUS.md` (C7
  yeo_johnson + robust + median = WORKING_ASSUMPTION).
- **RFM-only baseline**: ⏳ FUTURE WORK theo
  `RFM_ONLY_FUTURE_WORK_PLAN.md`. KHÔNG trong scope hiện tại.
- **Cross-algorithm ranking**: ⚠️ PENDING. KHÔNG được phép cho đến
  khi EPIC-08 Phase B + mentor approval.

File `ML01_*` KHÔNG được tự ý gán trạng thái nào quá header đã ghi.
Trạng thái trong header là `TECHNICALLY_IMPLEMENTED` (chưa phải
`RESEARCH_APPROVED_FINAL`).

---

## 6. Cross-reference vào `docs/decisions/`

| Research artifact | Liên quan ADR |
|---|---|
| `ML02_KMeans.md` … `ML06_Fuzzy_CMeans.md` | `0003-algorithm-scope.md` |
| `FE05_Customer_Feature_Engineering.md` | chưa có ADR riêng (working assumption) |
| `EXP01_baseline_experiment_PLAN.md`, `EXP02_cluster_number_PLAN.md`, `EXP05_stability_reproducibility_PLAN.md` | `0004-research-questions.md` |
| `EPIC06_DOCUMENTATION_CONTRACT.md` | thiết kế EPIC contract, không có ADR riêng |

---

## 7. Rủi ro trạng thái — KHÔNG tự ý hành động

- KHÔNG merge, archive, move, rename hai file ML01. Owner đã chọn phương án B (giữ nguyên).
- KHÔNG sửa `METHODOLOGY_RESOLUTION_PROPOSAL.md` (STATUS: RESOLVED,
  analysis phase). Nếu cần archive → owner quyết định.
- KHÔNG sửa `METHODOLOGY_LOCK_STATUS.md`. Đây là authoritative record
  cho locked decisions.
- KHÔNG suy diễn `TECHNICALLY_IMPLEMENTED` thành
  `RESEARCH_DECISION_APPROVED`. Phân biệt rõ theo `AGENTS.md` §2.10.
- KHÔNG thêm dependency mới vào bất kỳ file nào trong `docs/research/`.

Inventory chi tiết cho Phase 2B.1 ở `/tmp/phase2b1_documentation_inventory.md`
(ngoài repo).

---

## 8. Trạng thái ML01 (PHASE 2B.3)

**Quyết định ownership ML01 (PHASE 2B.3):**

Hai file ML01 được giữ nguyên tại `docs/research/`:
- `ML01_Clustering_Experiment_Framework.md` (PascalCase) — Mentor document theo contract 12 sections.
- `ML01_clustering_experiment_framework.md` (lowercase) — Implementation Notes.

**Phương án B** đã được chọn:
- Giữ cả hai file, không merge, không archive, không move, không rename.
- PascalCase tiếp tục là tài liệu hướng tới Mentor.
- Lowercase tiếp tục là Implementation Notes.

Chi tiết: xem `review/ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` §1.1, §6 (Q-10).

---

**Hết Phase 2B.1 research index. Phase 2B.3 đã ghi quyết định ML01 ownership (phương án B). KHÔNG tự bắt đầu consolidation, merge hoặc archive — chờ owner review.**
