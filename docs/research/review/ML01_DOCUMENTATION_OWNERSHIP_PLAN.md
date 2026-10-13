# ML01 Documentation Ownership & Cross-Reference Plan

> **Loại tài liệu:** Kế hoạch review ownership tài liệu (planning).
> **Phase:** 2B.2-N — ML01 Documentation Ownership & Cross-Reference Plan.
> **Ngày:** 2026-10-12.
> **Người soạn:** AI Agent (read-only review; KHÔNG sửa file nguồn).
> **Trạng thái:** AWAITING_OWNER_REVIEW.
> **Phạm vi:** Hai file `docs/research/ML01_*.md` (lowercase + PascalCase) và 6 file tham chiếu.
> **Hạn chế:** Phase 2B.1 restriction vẫn còn hiệu lực — KHÔNG merge, archive, move, rename hai file ML01.
> **Ghi chú tiên quyết:** Kế hoạch này là planning document, không phải Mentor document. Tài liệu này không thay thế nội dung hai file ML01; nó chỉ mô tả cách quản lý ownership để tránh duplicate, stale evidence, broken links trong tương lai.

---

## 0. Tóm tắt điều hành

| Mục | Giá trị |
|---|---|
| File ML01 đang tồn tại | 2 file: `ML01_clustering_experiment_framework.md` (lowercase, 829 dòng) + `ML01_Clustering_Experiment_Framework.md` (PascalCase, 1017 dòng) |
| Quyết định ownership đề xuất | (a) PascalCase = Mentor document theo contract 12 sections; (b) lowercase = Implementation Notes & kỹ thuật bổ sung |
| Số quyết định cần owner | 10 câu hỏi (xem §6) |
| Hành động cần thực hiện ngay | KHÔNG — đợi owner quyết định |
| Hành động KHÔNG ĐƯỢC tự ý làm | merge, archive, move, rename, đổi status, đổi methodology |

---

## 1. Vai trò đề xuất cho hai file ML01

### 1.1. Vai trò đề xuất

| File | Vai trò đề xuất | Bằng chứng từ contract/README | Ghi chú |
|---|---|---|---|
| `ML01_Clustering_Experiment_Framework.md` (PascalCase, 1017 dòng) | **Mentor document theo contract 12 sections** | `EPIC06_DOCUMENTATION_CONTRACT.md` §1.2 dòng 64, §11 dòng 914 — đây là đường dẫn Mentor document đích danh cho ML-01 | File đã có 12 sections đầy đủ theo template §2 (xác minh dòng 19, 57, 102, 246, 420, 613, 643, 675, 728, 797, 896, 922) |
| `ML01_clustering_experiment_framework.md` (lowercase, 829 dòng) | **Implementation Notes & chi tiết kỹ thuật bổ sung** | `EPIC06_DOCUMENTATION_CONTRACT.md` §1.2 dòng 70, §11 dòng 922 — gọi file này là "Implementation Notes" | File có 21 sections theo format cũ, không tuân 12-section template nhưng chứa 19 nhóm nội dung bổ sung (xem §3) |

### 1.2. So sánh với ghi nhận hiện tại trong README

| Nguồn | Câu ghi nhận | Phù hợp đề xuất? |
|---|---|---|
| `docs/research/README.md` §2 dòng 41–42 | "PascalCase: Tên theo template Mentor document 12-section. Đích danh của Mentor document cuối cho ML-01. Lowercase: 'Implementation Notes' — sẽ được tái cấu trúc lại theo 12-section template khi viết Mentor document cuối." | ✅ Cùng đề xuất |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` §1.2 dòng 70–73 | "File `docs/research/ML01_clustering_experiment_framework.md` hiện tại (Implementation Notes) sẽ được **tái cấu trúc lại** theo template Mentor document trong contract này khi viết Mentor document cuối." | ✅ Cùng đề xuất |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` §11 dòng 922–924 | "Lưu ý: file `docs/research/ML01_clustering_experiment_framework.md` hiện tại là **Implementation Notes** (đã có sẵn). Khi viết Mentor document cuối, file này sẽ được **tái cấu trúc** theo 12-section template trong §2." | ✅ Cùng đề xuất |
| `docs/README.md` §5.3 dòng 326–328 | "EPIC-06 contract nói rằng file lowercase sẽ được 'tái cấu trúc lại' theo template khi viết Mentor document cuối. Contract KHÔNG tuyên bố file nào hiện tại là 'superseded'. Archive/merge cần owner quyết định." | ✅ Cùng đề xuất |

**Ghi chú quan trọng:** Contract dùng từ "tái cấu trúc" (restructure), KHÔNG dùng từ "merge", "archive", "supersede", "xóa", "thay thế". Kế hoạch này tôn trọng nguyên văn contract.

### 1.3. Phân biệt ownership trong giao tiếp

| Đối tượng | Tham chiếu | Lý do |
|---|---|---|
| Mentor / human researcher | `ML01_Clustering_Experiment_Framework.md` (PascalCase) | Tuân 12-section template, đầy đủ evidence thực tế, có provenance |
| Agent / contributor (implementation chi tiết) | `ML01_clustering_experiment_framework.md` (lowercase) | Code snippet, ASCII diagram, bảng validation chi tiết |
| Cross-reference trong báo cáo khác | Ưu tiên PascalCase, có thể tham chiếu thêm lowercase nếu cần chi tiết kỹ thuật | Hai file có vai trò bổ sung, không trùng |

---

## 2. Danh sách tham chiếu hiện có

### 2.1. File tham chiếu PascalCase (8 file)

| # | File tham chiếu | Dòng | Cách tham chiếu | Mức độ quan trọng |
|---|---|---|---|---|
| 1 | `README.md` | 255 | Markdown link `[docs/research/ML01_Clustering_Experiment_Framework.md](./docs/research/ML01_Clustering_Experiment_Framework.md) — framework cho clustering experiment.` | Cao — top-level navigation |
| 2 | `docs/README.md` | 78–79, 154–155, 281, 326–328, 371–372 | Liệt kê trong §3.5 (binary exports), §3.6 (ML references), §5.1 (tracked files), §5.3 (status), §7 (inventory ref) | Cao — docs navigation |
| 3 | `docs/research/README.md` | 41, 75 | Bảng hai biến thể (§2) + danh sách file (§3.3) | Cao — research index |
| 4 | `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | 64, 914, 982 | Đường dẫn Mentor document chính thức (§1.2, §11) + Source of truth (§14) | Rất cao — contract authority |
| 5 | `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` | 210 | Action item: "Update algorithm count references (if any '4 algorithms' claim)" | Trung bình — historical action |
| 6 | `docs/system/DEV-04_clustering_execution.md` | 90, 4597 | "ML-01 framework contract (research)" — reference chính | Cao — DEV-04 dependency |
| 7 | `docs/system/DEV-05_evaluation_module.md` | 115 | "skim header + §metrics" — reference cho DEV-05 | Cao — DEV-05 dependency |
| 8 | `tests/test_ml01_framework.py` | 267, 300, 949, 956, 1063 | Test framework tham chiếu `ML01` qua stage metadata (id, version, status) | Rất cao — test code dependency |

### 2.2. File tham chiếu lowercase (3 file)

| # | File tham chiếu | Dòng | Cách tham chiếu | Mức độ quan trọng |
|---|---|---|---|---|
| 1 | `docs/README.md` | 157–158, 327–328 | Liệt kê Implementation Notes (§3.6) + hạn chế Phase 2B.1 (§5.3) | Cao — docs navigation |
| 2 | `docs/research/README.md` | 42, 76, 163 | Bảng hai biến thể (§2) + danh sách file (§3.3) + hạn chế Phase 2B.1 (§7) | Cao — research index |
| 3 | `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | 70–73, 922–924, 982 | "Implementation Notes" (§1.2) + "tái cấu trúc" (§11) + Source of truth (§14) | Rất cao — contract authority |

### 2.3. File tham chiếu `ML01` không phân biệt được (4 file)

| # | File | Dòng | Lý do không phân biệt được |
|---|---|---|---|
| 1 | `docs/system/DEV-03_preprocessing.md` | 91, 1550 | Tham chiếu `ML01..06_*.md` ở dạng glob; không nêu file cụ thể |
| 2 | `src/customer_segmentation/clustering/logging_utils.py` | 34, 45, 54, 97 | Python identifier `ML01_LOG_PREFIX`; không phải link file |
| 3 | `configs/clustering.yaml` | 245–247 | Stage metadata (stage, stage_version, stage_status); không phải file path |
| 4 | `tests/test_ml01_framework.py` | 267, 300, 949, 956, 1063 | Test identifier dùng `ML01` (PascalCase); không phải file path |

### 2.4. Phân tích ảnh hưởng nếu thực hiện hành động ownership

| Hành động | File tham chiếu PascalCase bị ảnh hưởng | File tham chiếu lowercase bị ảnh hưởng | Tổng |
|---|---|---|---|
| Bổ sung nội dung vào PascalCase (chỉ thay đổi nội dung, không di chuyển) | 0 (link vẫn đúng) | 0 | 0 |
| Đổi tên PascalCase | 8 file | 0 | 8 |
| Merge nội dung lowercase vào PascalCase | 0 (lowercase vẫn tồn tại) | 0 | 0 |
| Archive lowercase | 0 | 3 file | 3 |
| Xóa lowercase | 0 | 3 file | 3 |

---

## 3. Bảy decision IDs và trạng thái từ nguồn

### 3.1. Bảy decision IDs tổng hợp

**Bằng chứng:** Báo cáo `PHASE 2B.2-M — ML01 Evidence-Based Comparison` §3.3 đã ghi rằng "7 PENDING_REVIEW items chung". Tuy nhiên khi đọc trực tiếp hai file, **ID format là KHÁC NHAU** — đây là chênh lệch quan trọng cần ghi nhận.

| Topic | lowercase §20.1/§20.2 ID | PascalCase §11 ID | Status trong cả hai file | Nguồn dòng |
|---|---|---|---|---|
| Framework interfaces shape | §20.1 #1 (numeric) | `ML-01-MET-01` | PENDING_REVIEW | lowercase dòng 775–778; PascalCase dòng 903 |
| CustomerID positional alignment | §20.1 #2 (numeric) | `ML-01-MET-02` | PENDING_REVIEW | lowercase dòng 779–783; PascalCase dòng 904 |
| Metrics placeholder shape | §20.1 #3 (numeric) | `ML-01-MET-03` | PENDING_REVIEW | lowercase dòng 785–788; PascalCase dòng 905 |
| Visualization ownership split | §20.1 #4 (numeric) | `ML-01-MET-04` | PENDING_REVIEW | lowercase dòng 790–793; PascalCase dòng 906 |
| Per-algorithm seed override | §20.2 #5 (numeric) | `ML-01-ENG-01` | DOCUMENTED | lowercase dòng 797–800; PascalCase dòng 907 |
| Artifact filename template | §20.2 #6 (numeric) | `ML-01-ENG-02` | DOCUMENTED | lowercase dòng 802–804; PascalCase dòng 908 |
| Noise label default -1 | §20.2 #7 (numeric) | `ML-01-ENG-03` | DOCUMENTED | lowercase dòng 806–807; PascalCase dòng 909 |

### 3.2. Chênh lệch so với báo cáo PHASE 2B.2-M

| Mục | Báo cáo PHASE 2B.2-M | Thực tế khi đọc file | Trạng thái |
|---|---|---|---|
| ID format | "Cùng ID, cùng status, cùng nội dung" | **ID format KHÁC NHAU**: lowercase dùng numeric (`§20.1 #1`); PascalCase dùng symbolic (`ML-01-MET-01`) | **CORRECTION** — IDs are FORMAT-EQUIVALENT nhưng KHÔNG string-equal |
| Status | 4 PENDING_REVIEW + 3 DOCUMENTED | 4 PENDING_REVIEW + 3 DOCUMENTED — **giống nhau** | EQUIVALENT |
| Nội dung | "Cùng nội dung" | "Cùng nội dung" — đã xác minh 7/7 topics giống nhau | EQUIVALENT |

**Bằng chứng hiệu chỉnh:** Grep tại `docs/research/ML01_clustering_experiment_framework.md` cho pattern `ML-01-MET|ML-01-ENG` trả về "No matches found" — xác nhận lowercase KHÔNG dùng symbolic ID. Ngược lại, PascalCase §11 dòng 903–909 liệt kê 7 symbolic IDs.

### 3.3. Bảng đối chiếu ID đầy đủ cho owner review

| Symbolic ID (PascalCase) | Numeric ID (lowercase) | Topic | Status | Trong file nào? |
|---|---|---|---|---|
| `ML-01-MET-01` | §20.1 #1 | Framework interfaces shape | PENDING_REVIEW | Cả hai |
| `ML-01-MET-02` | §20.1 #2 | CustomerID positional alignment | PENDING_REVIEW | Cả hai |
| `ML-01-MET-03` | §20.1 #3 | Metrics placeholder shape | PENDING_REVIEW | Cả hai |
| `ML-01-MET-04` | §20.1 #4 | Visualization ownership split | PENDING_REVIEW | Cả hai |
| `ML-01-ENG-01` | §20.2 #5 | Per-algorithm seed override | DOCUMENTED | Cả hai |
| `ML-01-ENG-02` | §20.2 #6 | Artifact filename template | DOCUMENTED | Cả hai |
| `ML-01-ENG-03` | §20.2 #7 | Noise label default -1 | DOCUMENTED | Cả hai |

**Lưu ý cho owner:** Nếu owner chọn đồng bộ hai file, cần quyết định:
- Dùng symbolic ID (`ML-01-MET-01`) thống nhất — phù hợp với convention EPIC-06.
- Dùng numeric ID — phù hợp với format cũ của lowercase.
- Dùng cả hai (mention numeric trong lowercase) — không khuyến nghị vì tạo noise.

---

## 4. Danh sách nội dung độc nhất (từ báo cáo PHASE 2B.2-M)

### 4.1. Nội dung chỉ có ở PascalCase (P-01..P-09)

| ID | Nội dung | Vị trí | Lý do cần bảo toàn |
|---|---|---|---|
| P-01 | 3 câu hỏi nghiên cứu RQ-style | PascalCase §2 dòng 64–70 | Bắt buộc theo contract §2.2 — không có ở lowercase |
| P-02 | 10 khái niệm lý thuyết (clustering framework, reproducibility, pipeline, registry, config, schema, validation, metadata, logging) | PascalCase §3 dòng 110–244 | Bắt buộc theo contract §2.3 — không có ở lowercase dưới dạng gộp |
| P-03 | Bảng phân loại decision BẮT BUỘC (TECHNICALLY_IMPLEMENTED / WORKING_ASSUMPTION / PENDING_REVIEW / OUT_OF_SCOPE) | PascalCase §4.7 dòng 397–418 | Bắt buộc theo contract §2.4.7 — không có ở lowercase |
| P-04 | 4×5 bảng Experimental Design Boundary | PascalCase §6 dòng 615–641 | Bắt buộc theo contract §2.6 — không có ở lowercase |
| P-05 | Bảng evidence 12 dòng với provenance thực tế (n_samples=4371, n_features=14, 59 tests pass) | PascalCase §7 dòng 645–673 | Bắt buộc theo contract §2.7 — không có ở lowercase |
| P-06 | Notation chuẩn (§8.1) + framework-level formulas (§8.2) | PascalCase §8 dòng 675–726 | Bắt buộc theo contract §2.8 — không có ở lowercase dưới dạng bảng |
| P-07 | Bảng evidence status per task cho diagnostic viz (ML-02 elbow, ML-03 dendrogram, ...) | PascalCase §9.2 dòng 747–760 | Không có ở lowercase — ghi rõ "CHƯA ĐƯỢC TẠO" cho từng ML |
| P-08 | Verification số liệu cụ thể (pytest, ruff, black) | PascalCase §10.1–10.3 dòng 824–846 | Bắt buộc theo contract §2.10 — không có ở lowercase |
| P-09 | 6 contract notes cuối §12.4 | PascalCase §12.4 dòng 921+ | Bắt buộc theo contract §2.12 — không có ở lowercase |

### 4.2. Nội dung chỉ có ở lowercase (L-01..L-19)

| ID | Nội dung | Vị trí | Lý do cần bảo toàn |
|---|---|---|---|
| L-01 | ASCII diagram `src/customer_segmentation/clustering/` module structure | lowercase §4 dòng 95–109 | Giá trị kỹ thuật — 9 modules trong 1 sơ đồ |
| L-02 | Class diagram rút gọn (BaseClusterAlgorithm, ClusterResult, ExperimentResult, AlgorithmRegistry, ExperimentRunner) | lowercase §4 dòng 111–171 | Giá trị kỹ thuật — 5 class hierarchy trong 1 sơ đồ |
| L-03 | Code snippet `BaseClusterAlgorithm` đầy đủ | lowercase §5.1 dòng 178–186 | Có body và usage example |
| L-04 | Code snippet `AlgorithmRegistry` 5 methods | lowercase §5.2 dòng 188–199 | Có body đầy đủ |
| L-05 | YAML schema đầy đủ với sub-sections | lowercase §6.2 dòng 252–296 | Một số field PascalCase chỉ tham chiếu file mà không inline schema |
| L-06 | ASCII pipeline 7 bước chi tiết | lowercase §7 dòng 308–327 | Chi tiết hơn PascalCase §5.3 (5 bước) |
| L-07 | Status semantics table (SUCCESS/FAILED) | lowercase §7.1 dòng 333–344 | Có bảng 2 dòng rõ ràng |
| L-08 | JSON snippet `ClusterResult.to_dict()` đầy đủ | lowercase §8.1 dòng 350–378 | Có giá trị evidence tham chiếu |
| L-09 | JSON snippet `ExperimentResult.to_dict()` đầy đủ | lowercase §8.2 dòng 380–411 | Có giá trị evidence tham chiếu |
| L-10 | Bảng schema hỗ trợ 4 algorithm family (Hard/DBSCAN/GMM/Fuzzy) | lowercase §8.3 dòng 413–437 | Có 5 dòng × 5 cột rõ ràng |
| L-11 | 2 bảng validation chi tiết (9 matrix checks + 5 customer alignment checks) | lowercase §12.1, §12.2 dòng 514–542 | Chi tiết hơn PascalCase §5.7 (1 bảng gộp) |
| L-12 | `MetricsResult` class definition với 7 fields | lowercase §13 dòng 549–563 | Có type hints đầy đủ |
| L-13 | 13-dòng bảng "Vai trò của ML-01" (Implemented vs Pending) | lowercase §2 dòng 55–73 | Liệt kê 7 ✅ + 6 ❌ (13 dòng) |
| L-14 | 6 limitations chi tiết | lowercase §16 dòng 666–680 | PascalCase §12.2 chỉ có 4 bullets ngắn |
| L-15 | Adapter pattern K-Means example code | lowercase §17 dòng 686–700 | Có code thực tế cho downstream task |
| L-16 | Ownership table cho ML-02→ML-06 (5 dòng) | lowercase §17 dòng 702–715 | Có 5 dòng chi tiết |
| L-17 | 20-dòng bảng "Trạng thái implementation" | lowercase §18 dòng 719–740 | 11 ✅ + 9 ❌ (20 dòng) |
| L-18 | 5 assumptions | lowercase §19 dòng 746–758 | Chi tiết hơn PascalCase decision table |
| L-19 | 13 items out of scope | lowercase §21 dòng 817–829 | Liệt kê 13 items rõ ràng |

### 4.3. Nội dung trùng tương đương (EQUIVALENT)

| Nội dung | Lowercase | PascalCase | Ghi chú |
|---|---|---|---|
| Dataset version `FE06-v1.0` | §3 dòng 85 | §4.1 dòng 255, §7 dòng 657 | EQUIVALENT |
| Framework version `ML01-v1.0` | §1 dòng 4, §18 dòng 728 | §0 dòng 4, §7 dòng 658 | EQUIVALENT |
| 14 features list | §3 dòng 85 (qua reference) | §1 dòng 29, §7 dòng 653 | PascalCase liệt kê đầy đủ |
| 3 kênh reproducibility | §10 dòng 472–485 | §3.2 dòng 117–123, §4.6 dòng 384–395 | EQUIVALENT |
| 3 artifact paths (cluster_labels, algorithm_output, experiment_log) | §11.2 dòng 496–504 | §4.5 dòng 380–383 | EQUIVALENT |
| Stage status `TECHNICALLY_IMPLEMENTED` | §1 dòng 5, §18 dòng 729 | §0 dòng 6, §7 dòng 659 | EQUIVALENT |
| 7 PENDING_REVIEW/DOCUMENTED topics (xem §3 ở trên) | §20.1, §20.2 dòng 765–799 | §11 dòng 903–909 | FORMAT-EQUIVALENT (numeric vs symbolic) |

### 4.4. Nội dung có SHA-256 chỉ ở PascalCase

| Nội dung | Vị trí | Ghi chú |
|---|---|---|
| `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` (final_clustering_dataset) | PascalCase §1 dòng 27, §7 dòng 655 | **Chỉ PascalCase ghi rõ SHA-256**; lowercase §3 dòng 81 chỉ ghi `(4371, 14)` không ghi SHA |
| `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` (customer_metadata) | PascalCase §1 dòng 27, §7 dòng 656 | **Chỉ PascalCase ghi rõ SHA-256**; lowercase §3 dòng 82 chỉ ghi `(4371, 1)` không ghi SHA |

**Bằng chứng SHA-256 từ nguồn:** `docs/research/review/METHODOLOGY_LOCK_STATUS.md` §2 dòng 50 ghi `DS-02` = `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` (✅ LOCKED). SHA-256 customer_metadata tương ứng chưa được ghi trong METHODOLOGY_LOCK_STATUS.md (chỉ có SHA `final_clustering_dataset`); SHA này đến từ `reports/fe06/fe06_run.json` theo PascalCase §1 dòng 29.

**Bằng chứng đối chiếu chênh lệch với PHASE 2B.2-M:**

PHASE 2B.2-M §3.3 ghi rằng "Lowercase §3 dòng 78 (không ghi rõ)"; thực tế khi đọc trực tiếp, lowercase §3 dòng 78 CHỈ ghi `(4371, 14)` cho shape, không có SHA-256 nào. Chênh lệch này khớp với báo cáo PHASE 2B.2-M (cùng kết luận), nhưng ghi nhận rõ rằng **PascalCase là nguồn authoritative cho SHA-256 input**.

---

## 5. Rủi ro về duplicate, stale evidence, methodology, broken links

### 5.1. Rủi ro duplicate

| ID | Rủi ro | Mức độ | Bằng chứng |
|---|---|---|---|
| DUP-01 | 7 PENDING_REVIEW/DOCUMENTED topics tồn tại ở 2 file với 2 ID format (numeric + symbolic) | Trung bình | Nếu mentor review dựa trên PascalCase `ML-01-MET-01`, lowercase dùng `§20.1 #1` — dễ nhầm nếu grep sai file |
| DUP-02 | 3 reproducibility channels tồn tại ở 2 file (lowercase §10 + PascalCase §3.2 + §4.6) | Thấp | Cùng nội dung, khác format — nếu ai đó update một file, file kia lỗi thời |
| DUP-03 | 3 artifact paths tồn tại ở 2 file (lowercase §11.2 + PascalCase §4.5) | Thấp | Tương tự DUP-02 |
| DUP-04 | Validation checks tồn tại ở 2 file (lowercase §12 — 14 checks; PascalCase §5.7 — 14 checks) | Trung bình | Lowercase liệt kê 9 matrix + 5 customer alignment; PascalCase liệt kê 14 tổng — khác format presentation |

### 5.2. Rủi ro stale evidence

| ID | Rủi ro | Mức độ | Bằng chứng |
|---|---|---|---|
| STALE-01 | PascalCase §7 dòng 660 ghi "Số framework tests: 59" và §7 dòng 661 ghi "59/59 passed" — có thể lỗi thời nếu pytest count thay đổi | Trung bình | Test count chỉ xác minh tại thời điểm file được viết; chưa re-run trong session hiện tại |
| STALE-02 | PascalCase §10.2 dòng 838 ghi "All checks passed!" với `ruff 0.16.8` — version có thể đã đổi | Thấp | Lint version ghi tại thời điểm file được viết |
| STALE-03 | PascalCase §10.3 dòng 845 ghi "15 files would be left unchanged" với `black 26.5.1` — version có thể đã đổi | Thấp | Tương tự STALE-02 |
| STALE-04 | Library versions ghi trong PascalCase §7 dòng 662 có thể lỗi thời | Thấp | numpy/pandas/scipy/sklearn/pyarrow versions snapshot tại thời điểm file được viết |
| STALE-05 | Không có timestamp "last verified" trong bất kỳ file ML01 nào | Trung bình | Cả hai file chỉ có status `TECHNICALLY_IMPLEMENTED` ở header, không có "verified at" date |

### 5.3. Rủi ro methodology

| ID | Rủi ro | Mức độ | Bằng chứng |
|---|---|---|---|
| METHOD-01 | Status `TECHNICALLY_IMPLEMENTED` ở 2 file có thể bị suy diễn thành `RESEARCH_APPROVED_FINAL` | Cao | AGENTS.md §2.10 cấm suy diễn này; nếu file merge hoặc bị tham chiếu sai context, có thể gây hiểu nhầm |
| METHOD-02 | `PENDING_REVIEW` status ở 2 file có thể bị đổi thành `CONFIRMED` nếu mentor review nhầm file | Cao | AGENTS.md §2.5, §2.10 cấm tự đổi status; nếu ai đó update PascalCase `PENDING_REVIEW` mà không đồng bộ lowercase, sẽ có stale status |
| METHOD-03 | `WORKING_ASSUMPTION` (nếu xuất hiện) có thể bị đổi thành `RESEARCH_APPROVED` nếu merge | Trung bình | METHODOLOGY_LOCK_STATUS.md §3 có 8 `WA-01..08` ở status `WORKING_ASSUMPTION`; nếu nhầm với ML01 content, có thể bị nâng cấp sai |
| METHOD-04 | Algorithm scope (5 algorithms, K-Medoids OUT) có thể bị mô tả sai nếu merge | Thấp | METHODOLOGY_LOCK_STATUS.md §1, ADR-0003 đã lock; cả hai file ML01 đều tôn trọng scope này |

### 5.4. Rủi ro broken links

| ID | Rủi ro | Mức độ | Bằng chứng |
|---|---|---|---|
| LINK-01 | Nếu rename `ML01_Clustering_Experiment_Framework.md` → 8 file tham chiếu (xem §2.1) có link hỏng | Cao | `README.md` dòng 255, `docs/README.md` 5 vị trí, `docs/research/README.md` 2 vị trí, contract 3 vị trí, DEV-04 2 vị trí, DEV-05 1 vị trí |
| LINK-02 | Nếu archive/xóa `ML01_clustering_experiment_framework.md` → 3 file tham chiếu (xem §2.2) có link hỏng | Trung bình | `docs/README.md` 2 vị trí, `docs/research/README.md` 3 vị trí, contract 3 vị trí |
| LINK-03 | Nếu move file mà không update cross-reference trong `EPIC06_DOCUMENTATION_CONTRACT.md` §14 dòng 982 | Cao | Contract §14 ghi "Framework details (current) | `docs/research/ML01_clustering_experiment_framework.md`" — nếu file move, contract trỏ sai |

---

## 6. Câu hỏi cần owner quyết định

| # | Câu hỏi | Bằng chứng liên quan | Phương án ảnh hưởng |
|---|---|---|---|
| Q-01 | Từ "tái cấu trúc lại" trong contract §1.2 (dòng 71–73) và §11 (dòng 923–924) có được phép hiểu là "merge nội dung" không, hay chỉ là "reformat theo template"? | Contract dòng 71–73, 923–924 dùng từ "tái cấu trúc lại" và "tái cấu trúc" | A, C (xem §7) |
| Q-02 | Contract EPIC06 có cho phép archive Implementation Notes sau khi Mentor document được viết xong không, hay cần giữ vĩnh viễn? | Contract §1.2 dòng 70 gọi lowercase là "Implementation Notes hiện tại"; `docs/research/README.md` §7 dòng 163 nói "Cần owner quyết định" | C |
| Q-03 | Việc bổ sung 19 items độc nhất từ lowercase (L-01..L-19) vào PascalCase có thay đổi methodology đã lock không (theo AGENTS.md §2.9)? | Lowercase §20.1 (4 MET) và §19 (5 assumptions) là PENDING_REVIEW/WORKING_ASSUMPTION; PascalCase §4.7 và §11 cũng có cùng items | A |
| Q-04 | Có cần đồng bộ hai file thường xuyên nếu chọn B (giữ nguyên)? Nếu có, ai chịu trách trách nhiệm? | Cả hai file có 7 PENDING_REVIEW/DOCUMENTED items chung; 3 reproducibility channels chung; 3 artifact paths chung | B |
| Q-05 | Nếu chọn A (bổ sung vào PascalCase), 19 items lowercase có nên inline vào PascalCase, hay append vào cuối file, hay thay thế các placeholder hiện có? | PascalCase hiện đã có 12 section đầy đủ; inline có thể phá vỡ flow; append có thể tạo duplicate | A |
| Q-06 | Nếu chọn C (merge + archive), archive path nào được chấp nhận? `docs/research/archived/ML01_*.md` hay giữ folder gốc và dùng file `.archive` suffix? | Contract không quy định archive path; `docs/research/README.md` không có folder `archived/` | C |
| Q-07 | Phase 2B.1 restriction "KHÔNG merge, archive, move, rename" có còn hiệu lực sau khi EPIC-06 hoàn thành không, hay chỉ áp dụng trong giai đoạn này? | `docs/research/README.md` §1 ghi "Phạm vi Phase 2B.1" ghi rõ hạn chế chỉ trong Phase 2B.1 | C |
| Q-08 | Có cần tạo ADR mới (ví dụ `0010-ml01-document-consolidation.md`) cho quyết định merge/archive, hay đây là engineering decision không cần ADR? | AGENTS.md §1 yêu cầu mọi thay đổi `AGENTS.md` cần ADR; METHODOLOGY_LOCK_STATUS §10 có 4 ADRs (0001..0004) | A, C |
| Q-09 | 7 PENDING_REVIEW items chung tồn tại ở 2 file với 2 ID format (numeric vs symbolic) — ID nào được dùng làm canonical nếu đồng bộ? | Cả 2 file đều ghi cùng topics, khác ID format (xem §3.2 ở trên) | A, B, C |
| Q-10 | Phương án nào (A, B, hay C) được chọn cho hai file ML01? | Tất cả 3 phương án đều có ưu/nhược điểm (xem §7) | A, B, C |

---

## 7. So sánh ba phương án (tổng hợp từ PHASE 2B.2-M + điều chỉnh)

### 7.1. Phương án A — Giữ cả hai, bổ sung nội dung cần thiết vào PascalCase

**Mô tả:** Thêm 19 items độc nhất từ lowercase (L-01..L-19) vào PascalCase bằng cách inline, append, hoặc thay thế placeholder. KHÔNG xóa, archive, hoặc đổi tên bất kỳ file nào.

**Lợi ích:**
- PascalCase đạt đầy đủ 12 section template theo contract §2, ĐỒNG THỜI có thêm 19 items bổ sung chi tiết kỹ thuật.
- 9 nội dung độc nhất của PascalCase (P-01..P-09) được giữ nguyên.
- 0 file tham chiếu bị ảnh hưởng.
- Mentor đọc PascalCase là đủ — không cần đọc lowercase.

**Rủi ro:**
- 4 items duplicate nội dung (DUP-01..DUP-04) tăng — nếu một thay đổi, file kia có thể lỗi thời.
- Effort merge cần owner review trước (theo Q-01, Q-03, Q-05, Q-09).
- 5 risks stale evidence (STALE-01..STALE-05) không tự resolve.

**Nội dung cần bảo toàn:** 9 P + 19 L.

**Tham chiếu bị ảnh hưởng:** 0.

**Điều kiện cần owner approval:**
- Q-01: "tái cấu trúc" có nghĩa là "bổ sung nội dung" không.
- Q-03: bổ sung có thay đổi methodology không.
- Q-05: cách bổ sung (inline/append/thay thế).
- Q-09: ID format nào canonical (numeric vs symbolic).

### 7.2. Phương án B — Giữ nguyên hai file với vai trò riêng

**Mô tả:** Không thay đổi hai file. PascalCase = Mentor document (theo §1.1); lowercase = Implementation Notes (theo §1.1). Hai vai trò được ghi nhận rõ ràng trong giao tiếp.

**Lợi ích:**
- Không có thay đổi — không vi phạm Phase 2B.1 restriction.
- Giữ nguyên ý nghĩa Implementation Notes vs Mentor document.
- 100% nội dung bảo toàn.
- Phù hợp với ghi nhận của `docs/research/README.md` §2 ("Hai file này cùng tồn tại").
- Không cần tạo ADR mới (Q-08: không có thay đổi methodology).

**Rủi ro:**
- Người đọc mới (mentor, reviewer mới) phải đọc 2 file để hiểu ML-01.
- 4 duplicate items (DUP-01..DUP-04) tồn tại vĩnh viễn.
- 5 stale evidence risks (STALE-01..STALE-05) tồn tại vĩnh viễn.
- 2 file có thể drift nếu một bị update mà file kia không (Q-04).

**Nội dung cần bảo toàn:** Tất cả (không thay đổi).

**Tham chiếu bị ảnh hưởng:** 0.

**Điều kiện cần owner approval:**
- Q-04: ai chịu trách nhiệm đồng bộ khi có update.

### 7.3. Phương án C — Hợp nhất + archive lowercase (sau owner approval)

**Mô tả:** Sau khi owner approve:
1. Bổ sung 19 items từ lowercase vào PascalCase (giống A).
2. Archive `ML01_clustering_experiment_framework.md` đến `docs/research/archived/ML01_*.md` (hoặc path khác do owner chỉ định).
3. Update 3 file tham chiếu lowercase (xem §2.2) để không có link hỏng.

**Lợi ích:**
- Một file Mentor document duy nhất, đầy đủ 12 section + 19 items bổ sung.
- Không còn duplicate, không còn confusion cho người đọc mới.

**Rủi ro:**
- **Phá vỡ 3+ tham chiếu** đến lowercase (`docs/README.md` 2 vị trí, `docs/research/README.md` 3 vị trí, contract 3 vị trí) — theo LINK-02.
- **Risk LINK-03 cao:** contract §14 dòng 982 vẫn trỏ đến lowercase path.
- Contract EPIC06 §1.2 dùng từ "tái cấu trúc" — KHÔNG dùng "merge + archive". Diễn giải có thể vượt phạm vi contract (Q-01).
- Phase 2B.1 restriction (`docs/research/README.md` §7) ghi rõ "KHÔNG merge, archive, move, rename" — cần owner quyết định (Q-07).
- 3 risks methodology (METHOD-01..METHOD-04) cao hơn do động tác archive có thể gây hiểu nhầm "superseded".

**Nội dung cần bảo toàn:**
- Toàn bộ 19 items từ lowercase.
- 9 items từ PascalCase.
- 7 PENDING_REVIEW/DOCUMENTED items với ID format nhất quán (Q-09).
- Cross-reference cũ (nếu archive đến folder mới, cần redirect hoặc note).

**Tham chiếu bị ảnh hưởng:** 3+ file (xem LINK-02, LINK-03).

**Điều kiện cần owner approval:**
- Q-01: "tái cấu trúc" có nghĩa là "merge + archive" không.
- Q-02: có cho phép archive Implementation Notes không.
- Q-06: archive path nào.
- Q-07: Phase 2B.1 restriction còn hiệu lực không.
- Q-08: có cần ADR mới không.
- Q-09: ID format canonical.

### 7.4. So sánh tổng hợp

| Tiêu chí | A (bổ sung) | B (giữ nguyên) | C (merge + archive) |
|---|---|---|---|
| Tuân contract 12-section template | ✅ (PascalCase đầy đủ) | ⚠️ (chỉ PascalCase) | ✅ (một file đầy đủ) |
| Bảo toàn 9 P + 19 L | ✅ | ✅ | ✅ |
| Số file thay đổi | 1 (PascalCase) | 0 | 2 (PascalCase + archive) + 3+ ref updates |
| Số tham chiếu bị ảnh hưởng | 0 | 0 | 3+ (LINK-02, LINK-03) |
| Rủi ro phá vỡ link | Thấp | Không | Cao |
| Effort merge | Trung bình | Không có | Cao |
| Cần owner approval | 4 câu hỏi (Q-01, Q-03, Q-05, Q-09) | 1 câu hỏi (Q-04) | 6 câu hỏi (Q-01, Q-02, Q-06, Q-07, Q-08, Q-09) |
| Phù hợp Phase 2B.1 | Có (không merge/archive) | Có (không thay đổi) | Không (cần vượt Phase 2B.1) |
| ADR cần tạo? | Không (nếu Q-03 = "không đổi methodology") | Không | Có thể (Q-08) |
| Rủi ro duplicate (4 items) | Tăng | Vĩnh viễn | Giảm |
| Rủi ro stale (5 items) | Tăng | Vĩnh viễn | Giảm |
| Rủi ro methodology (4 items) | Trung bình | Trung bình | Cao (archive dễ gây hiểu nhầm superseded) |
| Đề xuất tạm thời (KHÔNG phải quyết định) | **Có thể chấp nhận** | **An toàn nhất** | **Cần owner quyết định trước** |

---

## 8. Checklist kiểm tra lại sau khi owner phê duyệt

> **Mục đích:** Nếu owner chọn phương án A, B, hoặc C, dùng checklist này để kiểm tra tính toàn vẹn sau khi áp dụng.
> **Quy tắc:** Mỗi mục phải có bằng chứng (file path, dòng, hoặc commit hash).

### 8.1. Chung cho cả 3 phương án

| # | Mục kiểm tra | Bằng chứng cần | Áp dụng cho |
|---|---|---|---|
| C-01 | Hai file ML01 vẫn tồn tại ở đúng path gốc (trừ khi C được chọn và archive đã xảy ra) | `ls docs/research/ML01_*.md` | A, B |
| C-02 | Status `TECHNICALLY_IMPLEMENTED` ở cả hai file không bị đổi | `head -n 10 docs/research/ML01_*.md` | A, B, C |
| C-03 | Framework version `ML01-v1.0` ở cả hai file không bị đổi | `grep "ML01-v1.0" docs/research/ML01_*.md` | A, B, C |
| C-04 | SHA-256 input `ba54033e...` và `c2a42b3c...` ở PascalCase không bị đổi | `grep -E "ba54033e\|c2a42b3c" docs/research/ML01_Clustering_Experiment_Framework.md` | A, B, C |
| C-05 | 7 PENDING_REVIEW/DOCUMENTED topics không bị đổi status (không tự ý nâng từ PENDING lên CONFIRMED) | `grep -A 1 "ML-01-MET\|ML-01-ENG" docs/research/ML01_Clustering_Experiment_Framework.md` | A, B, C |
| C-06 | Algorithm scope (5 algorithms, K-Medoids OUT OF SCOPE) không bị thay đổi | `grep -E "K-Medoids\|5 algorithms" docs/research/ML01_*.md` | A, B, C |

### 8.2. Riêng cho phương án A (bổ sung vào PascalCase)

| # | Mục kiểm tra | Bằng chứng cần |
|---|---|---|
| A-01 | 19 items L-01..L-19 đã được inline/append/thay thế placeholder trong PascalCase | Tìm từng keyword trong PascalCase (ví dụ: "ASCII diagram" cho L-01, "BaseClusterAlgorithm" cho L-03, "JSON snippet" cho L-08) |
| A-02 | 9 items P-01..P-09 vẫn còn trong PascalCase (không bị ghi đè) | Tìm từng keyword trong PascalCase (ví dụ: "3 câu hỏi nghiên cứu" cho P-01, "4×5 bảng" cho P-04) |
| A-03 | 12 section structure của PascalCase vẫn đúng thứ tự | `grep "^## [0-9]" docs/research/ML01_Clustering_Experiment_Framework.md` — phải trả về đúng 12 sections theo thứ tự §1..§12 |
| A-04 | Không có ID mới nào được thêm ngoài 7 PENDING_REVIEW/DOCUMENTED hiện có | `grep -c "ML-01-MET\|ML-01-ENG" docs/research/ML01_Clustering_Experiment_Framework.md` phải = 7 |
| A-05 | 7 ID format giữ nguyên symbolic (`ML-01-MET-01..04`, `ML-01-ENG-01..03`) — không tự ý đổi thành numeric | Manual review ID list |

### 8.3. Riêng cho phương án B (giữ nguyên)

| # | Mục kiểm tra | Bằng chứng cần |
|---|---|---|
| B-01 | Hai file không bị modify bởi AI Agent (so với working tree trước Phase 2B.2-N) | `git status docs/research/ML01_*.md` (chỉ đọc, không thực hiện Git operations) |
| B-02 | `docs/research/README.md` §2 vẫn ghi "Hai file này cùng tồn tại" | `grep "cùng tồn tại" docs/research/README.md` |
| B-03 | `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` §1.2 dòng 70–73 vẫn ghi "Implementation Notes" + "tái cấu trúc" | `grep "Implementation Notes\|tái cấu trúc" docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` |

### 8.4. Riêng cho phương án C (merge + archive)

| # | Mục kiểm tra | Bằng chứng cần |
|---|---|---|
| C2-01 | `ML01_clustering_experiment_framework.md` đã được archive đến path owner chỉ định | `ls <archive_path>/ML01_*.md` |
| C2-02 | `ML01_Clustering_Experiment_Framework.md` chứa 19 items L-01..L-19 từ lowercase | (giống A-01) |
| C2-03 | 3 file tham chiếu lowercase (xem §2.2) đã được update — không còn link hỏng | `grep "ML01_clustering_experiment_framework" docs/README.md docs/research/README.md docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` |
| C2-04 | Contract §14 dòng 982 đã được update — không còn trỏ đến lowercase path (nếu archive) | `grep "ML01_clustering_experiment_framework" docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` |
| C2-05 | ADR mới (nếu Q-08 = "có cần ADR") đã được tạo | `ls docs/decisions/0010-*.md` (hoặc path owner chỉ định) |
| C2-06 | 8 file tham chiếu PascalCase (xem §2.1) vẫn trỏ đúng đến PascalCase | `grep "ML01_Clustering_Experiment_Framework" README.md docs/README.md docs/research/README.md docs/research/EPIC06_DOCUMENTATION_CONTRACT.md docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md docs/system/DEV-04_clustering_execution.md docs/system/DEV-05_evaluation_module.md` |
| C2-07 | Git working tree có thay đổi tracked (nếu có) — KHÔNG tự ý commit | `git status` (chỉ đọc) — để owner commit |

### 8.5. Kiểm tra chéo cho cả 3 phương án (post-action)

| # | Mục kiểm tra | Bằng chứng cần |
|---|---|---|
| X-01 | `tests/test_ml01_framework.py` vẫn chạy (không phải để verify, chỉ để confirm không có file bị xóa nhầm) | `python -m pytest tests/test_ml01_framework.py --collect-only` (chỉ collect, không run) — nếu file test vẫn parse được, file vẫn tồn tại |
| X-02 | `configs/clustering.yaml` line 245–247 vẫn ghi `stage: ML-01`, `stage_version: ML01-v1.0`, `stage_status: TECHNICALLY_IMPLEMENTED` | `sed -n '245,247p' configs/clustering.yaml` |
| X-03 | `docs/research/review/METHODOLOGY_LOCK_STATUS.md` §1 vẫn ghi `Algorithm scope: ✅ LOCKED` | `grep "LOCKED" docs/research/review/METHODOLOGY_LOCK_STATUS.md` |
| X-04 | Status `RESEARCH_APPROVED_FINAL` KHÔNG xuất hiện trong bất kỳ file ML01 nào | `grep "RESEARCH_APPROVED_FINAL" docs/research/ML01_*.md` phải trả về 0 (theo AGENTS.md §2.10) |
| X-05 | Từ "best", "winner", "optimal" KHÔNG xuất hiện trong bất kỳ file ML01 nào ở context mô tả algorithm/feature (theo AGENTS.md §2.5) | Manual review |
| X-06 | Không có "TODO", "FIXME" xuất hiện trong status section (ngoài các comment chính đáng trong code) | Manual review |

---

## 9. Các việc chưa thực hiện

> **Tường thuật:** Mục này ghi rõ những gì Phase 2B.2-N chưa làm, để owner biết phạm vi thực sự của planning document này.

| # | Việc chưa thực hiện | Lý do | Khi nào có thể làm |
|---|---|---|---|
| W-01 | Re-run pytest cho `tests/test_ml01_framework.py` | Kế hoạch này là planning document; không cần bằng chứng runtime mới (AGENTS.md §2.1, §2.8) | Sau khi owner chọn phương án |
| W-02 | Re-run `ruff check` cho `src/customer_segmentation/clustering/` | Tương tự W-01 | Sau khi owner chọn phương án |
| W-03 | Re-run `black --check` cho `src/customer_segmentation/clustering/` | Tương tự W-01 | Sau khi owner chọn phương án |
| W-04 | Re-compute SHA-256 cho `data/processed/final_clustering_dataset.parquet` và `customer_metadata.parquet` | PascalCase §1 dòng 28–29 ghi SHA-256 từ session cũ; chưa verify trong session hiện tại | Sau khi owner yêu cầu |
| W-05 | Xác minh 59 tests count trong `tests/test_ml01_framework.py` | PascalCase §7 dòng 665 ghi "59 / 59 tests passed"; chưa re-run trong session hiện tại | Sau khi owner yêu cầu |
| W-06 | Tạo ADR mới (nếu Q-08 = "có cần ADR") | Không thuộc phạm vi Phase 2B.2-N; cần owner quyết định trước (Q-08) | Sau khi owner trả lời Q-08 |
| W-07 | Bổ sung nội dung vào PascalCase (nếu A được chọn) | Không thuộc phạm vi Phase 2B.2-N; cần owner quyết định trước (Q-01, Q-03, Q-05, Q-09) | Sau khi owner chọn A |
| W-08 | Archive lowercase (nếu C được chọn) | Không thuộc phạm vi Phase 2B.2-N; cần owner quyết định trước (Q-01, Q-02, Q-06, Q-07, Q-08, Q-09) | Sau khi owner chọn C |
| W-09 | Update 3+ file tham chiếu lowercase (nếu C được chọn) | Tương tự W-08 | Sau khi owner chọn C |
| W-10 | Git operations (commit/push/PR) | AGENTS.md §2.11 cấm AI Agent; Human researcher chịu trách nhiệm | Khi Human researcher quyết định |

---

## 10. Xác nhận hành vi Phase 2B.2-N

| Hành vi | Trạng thái | Bằng chứng |
|---|---|---|
| KHÔNG sửa hai file ML01 | ✅ Tuân thủ | Không có file modification tool call cho `docs/research/ML01_*.md` |
| KHÔNG sửa contract, ADR, methodology lock, README/index, code/config/test | ✅ Tuân thủ | Không có file modification tool call cho các file đó |
| KHÔNG merge, archive, move, rename, xóa file | ✅ Tuân thủ | Không có file move/delete tool call |
| KHÔNG chạy clustering/experiment trên research data | ✅ Tuân thủ | Không có shell command chạy clustering |
| KHÔNG chạy test/lint để tạo bằng chứng mới | ✅ Tuân thủ | Không có shell command chạy pytest/ruff/black |
| KHÔNG thực hiện Git operations (commit, push, branch, PR, merge, stage, reset, checkout, clean, stash, revert) | ✅ Tuân thủ | Không có git command tool call |
| KHÔNG ghi đè file có sẵn | ✅ Tuân thủ | File mới `ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` chưa tồn tại (đã xác minh bằng `ls docs/research/review/`) |
| KHÔNG diễn giải `TECHNICALLY_IMPLEMENTED` thành `RESEARCH_APPROVED_FINAL` | ✅ Tuân thủ | Toàn bộ tài liệu ghi rõ `TECHNICALLY_IMPLEMENTED`; §8.5 X-04 yêu cầu grep để đảm bảo `RESEARCH_APPROVED_FINAL` không xuất hiện |
| KHÔNG tự đổi `PENDING_REVIEW`, `WORKING_ASSUMPTION`, hoặc trạng thái methodology | ✅ Tuân thủ | Toàn bộ tài liệu ghi rõ status theo file gốc; §8.1 C-05 yêu cầu grep để đảm bảo status không bị đổi |

---

## 11. Metadata

| Trường | Giá trị |
|---|---|
| File | `docs/research/review/ML01_DOCUMENTATION_OWNERSHIP_PLAN.md` |
| Ngày tạo | 2026-10-12 |
| Phase | 2B.2-N |
| Người soạn | AI Agent (read-only review) |
| Trạng thái | AWAITING_OWNER_REVIEW |
| File nguồn đã đọc | `AGENTS.md` (1002 dòng); `EPIC06_DOCUMENTATION_CONTRACT.md` (1002 dòng, focus §1.2, §11, §14); `docs/research/README.md` (180 dòng, focus §2, §7); `docs/README.md` (418 dòng, focus §5.3, §6, §7); `ML01_clustering_experiment_framework.md` (829 dòng, full read); `ML01_Clustering_Experiment_Framework.md` (1017 dòng, full read); `METHODOLOGY_LOCK_STATUS.md` (focus §1, §2) |
| File tham chiếu đã grep | `README.md`, `docs/README.md`, `docs/research/README.md`, `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md`, `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md`, `docs/system/DEV-04_clustering_execution.md`, `docs/system/DEV-05_evaluation_module.md`, `docs/system/DEV-03_preprocessing.md`, `tests/test_ml01_framework.py`, `src/customer_segmentation/clustering/logging_utils.py`, `configs/clustering.yaml` |
| Khác biệt so với PHASE 2B.2-M | 1 chênh lệch quan trọng: ID format của 7 PENDING_REVIEW items (lowercase dùng numeric `§20.1 #1`; PascalCase dùng symbolic `ML-01-MET-01`) — báo cáo trước ghi "Cùng ID" là không chính xác. Tài liệu này đính chính thành "FORMAT-EQUIVALENT" (xem §3.2) |
| Phương án chưa được chọn | A, B, hay C (xem §6 Q-10) |
| QA correction (PHASE 2B.2-O) | Phase 2B.2-O QA review đã sửa một số line numbers và đếm items khách quan trong §3.1, §4.2 (L-13, L-17, L-19), §4.3, §4.4, §5.2 (STALE-01..04) — xem PHASE 2B.2-O report để biết chi tiết |

---

**PHASE 2B.2-N COMPLETE — WAITING FOR OWNER REVIEW**
