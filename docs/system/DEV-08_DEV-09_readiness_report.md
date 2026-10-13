# DEV-08/DEV-09 — Readiness Report

> **Mã task:** DEV-07 Closure Audit → DEV-08/DEV-09 Readiness
> **Ngày:** 2026-10-10
> **Trạng thái:** **DRAFT — chờ owner / mentor review**
> **Phạm vi:** Audit DEV-07 Phase B closure; phân tích dependency matrix
> cho DEV-08 (visualization) và DEV-09 (reporting); xác định task nào
> có thể bắt đầu ngay, task nào bị block và vì sao.
> **Nguồn evidence:** `docs/system/DEV-07_phase_b_decision_memo.md`,
> `docs/system/DEV-07_final_acceptance_report.md`,
> `docs/system/DEV-07_phase_b_acceptance_report.md`,
> `docs/system/DEV-02_dataset_management.md` §14,
> `docs/system/DEV-07_implementation_plan.md`,
> `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` §9,
> `src/customer_segmentation/visualization/*.py`,
> `src/customer_segmentation/prototype/`.
> **KHÔNG thuộc báo cáo này:** implementation code, Git operations.

---

## 1. Tóm tắt

### 1.1. DEV-07 Phase B closure verdict

| Thành phần | Trạng thái | Evidence |
|---|---|---|
| Phase A | ✅ ACCEPTED (2026-10-10) | `DEV-07_final_acceptance_report.md` |
| Phase B technical infrastructure | ✅ TECHNICALLY IMPLEMENTED (2026-10-10) | `DEV-07_phase_b_acceptance_report.md`; 65 tests mới (24 + 18 + 23) |
| Phase B actual recommendation generation | ❌ BLOCKED | 4 OQ (OQ-D07-01, -03, -04, -05) `REVIEW_REQUIRED`; MKT-01..MKT-05 absent |
| DEV-07 tests | ✅ 328 passed | `pytest tests/test_dev07_*.py` |
| DEV-02..07 regression | ✅ 1401 passed, 1 skipped | `pytest tests/test_dev0[2-7]*.py` |
| Ruff / Black | ✅ Clean | `ruff check` / `black --check` |
| Marketing framework files (MKT-01..MKT-05) | ❌ ABSENT | `Glob pattern="docs/marketing/**"` → No matches |
| DEV-07 DONE (business acceptance) | ❌ BLOCKED | Phase B actual content chờ owner decisions |

### 1.2. Câu hỏi cốt lõi được trả lời

**DEV-08 và DEV-09 có bị chặn bởi DEV-07 Phase B actual recommendation
generation không?**

→ **KHÔNG.** Không tìm thấy bằng chứng trong repository cho thấy
DEV-08 hoặc DEV-09 phụ thuộc vào DEV-07 Phase B recommendation content.
Lý do chi tiết ở §2 và §3.

**DEV-08 và DEV-09 có thể bắt đầu không?**

→ **DEV-08: READY_WITH_CONSTRAINTS** (cần plan trước; có thể bắt đầu
planning).
→ **DEV-09: READY_WITH_CONSTRAINTS** (cần plan trước; có thể bắt đầu
planning).

**DEV-07 có thể partial close không?**

→ **CÓ.** Phase A + Phase B technical infrastructure đạt
`TECHNICALLY IMPLEMENTED`. Phase B actual recommendation generation vẫn
`BLOCKED` chờ 4 OQ owner decisions. Phase A đã `ACCEPTED` 2026-10-10.

---

## 2. Dependency Matrix

### 2.1. DEV-02 → DEV-09 downstream contract (verified from `DEV-02_dataset_management.md` §14)

```
DEV-02 Dataset Management
  ├── DEV-03 Preprocessing
  ├── DEV-04 Feature Engineering
  ├── DEV-05 Clustering
  ├── DEV-06 Evaluation
  ├── DEV-07 Marketing Recommendation
  ├── DEV-08 Visualization         ← consumes: dataset_id only
  └── DEV-09 Reporting             ← consumes: dataset_id, validation_status, sha256
```

**Verified from `DEV-02_dataset_management.md` §14.1 table:**

| Downstream DEV | Consumes from DEV-02 | Does NOT consume |
|---|---|---|
| DEV-03 | `dataset_id`, `manifest_path`, `artifact_path`, `validation_status` | — |
| DEV-04 | `dataset_id`, `manifest.columns[]` | validation block |
| DEV-05 | `dataset_id`, `validation_status` (= VALID required to run) | statistics summary |
| DEV-06 | `dataset_id`, `validation_status` | statistics summary |
| DEV-07 | `dataset_id` | full manifest; only the id |
| **DEV-08** | **`dataset_id`** | **the manifest; only the id** |
| **DEV-09** | **`dataset_id`, `validation_status`, `sha256`** | **the columns[] list** |

→ **DEV-08 và DEV-09 chỉ phụ thuộc vào DEV-02, không phải DEV-07.**
DEV-07 hiện tại chỉ bị blocked bởi 4 OQ + MKT framework absent — không ảnh
hưởng đến DEV-02 contract.

### 2.2. DEV-07 Phase B actual recommendation vs DEV-08/DEV-09

**DEV-07 Phase B actual recommendation generation** bao gồm:
- MKT-02 objective templates
- MKT-03 strategy/action templates
- MKT-04 KPI definitions
- MKT-05 limitation framework
- Actual mapping Segment → MKT template

**DEV-08 (visualization) scope (verified from `EPIC06_DOCUMENTATION_CONTRACT.md` §9):**

| EPIC | Visualization owned | Notes |
|---|---|---|
| EPIC-06 | Diagnostic / algorithm-specific | Optional; per ML-02/03/04/05 |
| **EPIC-08** | **Research comparison** | Silhouette plot, comparison dashboard, runtime, ARI/AMI distribution |
| **EPIC-09** | **Segment analysis** | Segment size, RFM profile, boxplots, radar/heatmap |

→ DEV-08 prototype visualization **KHÔNG cần** DEV-07 Phase B recommendation
content. DEV-08 lấy dữ liệu từ DEV-04 (clustering results) và DEV-06
(segmentation/profiling). DEV-07 là consumer cuối cùng của DEV-06 output,
không phải nguồn cấp cho DEV-08.

**DEV-09 (reporting) scope:**

- Report về experiment runs, evaluation results, profiling results, marketing
  recommendations.
- Marketing section của report có thể reference DEV-07 Phase A
  `availability = REVIEW_REQUIRED` → hiển thị placeholder.
- DEV-07 Phase B actual content (khi có) → DEV-09 có thể mở rộng để include.

→ **DEV-09 có thể bắt đầu mà không cần DEV-07 Phase B content thật.**
Report marketing section có thể hiển thị "REVIEW_REQUIRED" placeholder
(Phase A behavior) hoặc để trống.

### 2.3. DEV-07 owner decisions vs DEV-08/DEV-09

| OQ | Nội dung | Ảnh hưởng đến DEV-08? | Ảnh hưởng đến DEV-09? |
|---|---|---|---|
| OQ-D07-01 | MKT framework scope ↔ SYS-01 §6.7 | **KHÔNG** | **KHÔNG** |
| OQ-D07-03 | CP-04 §4.1-§4.3 tokenization canonical | **KHÔNG** | **KHÔNG** |
| OQ-D07-04 | KPI units / source | **KHÔNG** | **KHÔNG** |
| OQ-D07-05 | Export format (CSV/JSONL) | **KHÔNG** (DEV-08 không emit recommendations) | **KHÔNG** (DEV-09 report format khác) |

**Kết luận:** 4 OQ của DEV-07 hoàn toàn **KHÔNG ảnh hưởng** đến
DEV-08 và DEV-09. DEV-08/DEV-09 có thể bắt đầu độc lập với DEV-07
Phase B.

### 2.4. Visualization ownership boundary (from `EPIC06_DOCUMENTATION_CONTRACT.md` §9)

```
EPIC-06 (ML-01 → ML-06): diagnostic viz (optional, per algorithm)
  ├── ML-02: Elbow / WCSS diagnostic plot
  ├── ML-03: Dendrogram, linkage matrix (optional)
  ├── ML-04: k-distance plot (optional)
  ├── ML-05: BIC/AIC curve (optional)
  └── ML-06: Membership distribution (optional)

EPIC-08 (Evaluation): research comparison viz
  ├── Silhouette comparison plot
  ├── DBI/CH comparison
  ├── Runtime comparison
  ├── ARI/AMI stability distribution
  └── Multi-metric dashboard

EPIC-09 (Profiling): segment analysis viz
  ├── Segment size bar chart
  ├── RFM profile radar/heatmap
  ├── Feature distribution boxplots
  └── Segment characteristics chart
```

→ **DEV-08 prototype visualization** nằm ở prototype layer
(`src/customer_segmentation/prototype/`), không thuộc research-core
visualization. DEV-08 có thể reuse content từ cả 3 EPIC groups
(EPIC-06/08/09) ở prototype level. DEV-08 **KHÔNG cần** DEV-07 Phase B
recommendation content để visualize clustering/segmentation results.

---

## 3. Classification

### 3.1. DEV-08 (Visualization)

**Classification: READY_WITH_CONSTRAINTS**

**Căn cứ:**

1. **DEV-02 contract**: DEV-08 chỉ tiêu thụ `dataset_id` từ DEV-02.
   DEV-02 đã hoàn thành (DEV-02 tests pass, repo đã verify).
   → Không bị chặn bởi DEV-07.

2. **Placeholder modules hiện có**: `src/customer_segmentation/visualization/`
   có 4 placeholder files (`distributions.py`, `rfm.py`, `clustering.py`,
   `profiling.py`) với `NotImplementedError`. Đây là research-core
   visualization; prototype-level visualization cần tạo trong
   `src/customer_segmentation/prototype/visualization/`.

3. **No visualization plans exist**: Không có `docs/system/DEV-08_*.md`
   plan file trong repo. Agent **PHẢI** tạo planning document trước
   khi implement (AGENTS.md §4).

4. **DEV-07 Phase B**: KHÔNG phụ thuộc. DEV-08 visualize clustering
   results từ DEV-04 và profiling results từ DEV-06. DEV-07 là consumer
   của DEV-06 output, không phải nguồn cấp.

5. **Marketing visualization**: DEV-08 prototype **có thể** include
   marketing section nhưng chỉ hiển thị `availability = REVIEW_REQUIRED`
   placeholder (matching Phase A behavior của DEV-07). Khi DEV-07 Phase B
   hoàn thành, DEV-08 mở rộng để show actual marketing content.

**Constraints:**

- Cần planning document trước (AGENTS.md §4: writing-plans skill).
- Cần xác định scope: prototype visualization so với research-core
  visualization (DEV-08 vs `src/customer_segmentation/visualization/`).
- Visualization ownership boundary phải tuân thủ EPIC-06 §9:
  diagnostic viz = EPIC-06 (optional), research comparison = EPIC-08,
  segment viz = EPIC-09.
- Marketing section DEV-08: hiển thị placeholder REVIEW_REQUIRED
  (matching DEV-07 Phase A); không tự tạo marketing content.

**Safe next action:**

1. Tạo planning document cho DEV-08 (xác định scope, deliverables,
   visualization ownership).
2. Xác định cấu trúc `prototype/visualization/` package.
3. Implement safe parts: segment size visualization (reuse CP-01 data),
   cluster distribution (reuse DEV-04 results), evaluation metrics
   table (reuse DEV-05 results).
4. Marketing section: placeholder only (matching DEV-07 Phase A).

### 3.2. DEV-09 (Reporting)

**Classification: READY_WITH_CONSTRAINTS**

**Căn cứ:**

1. **DEV-02 contract**: DEV-09 chỉ tiêu thụ `dataset_id`,
   `validation_status`, `sha256` từ DEV-02.
   → Không bị chặn bởi DEV-07.

2. **No reporting package exists**: Không có
   `src/customer_segmentation/prototype/reporting/` package.
   DEV-07 hiện có `pipeline.py` và `display.py` nhưng đó là marketing
   module, không phải general reporting.

3. **No DEV-09 plans exist**: Không có `docs/system/DEV-09_*.md`
   plan file. Agent **PHẢI** tạo planning document trước khi
   implement.

4. **DEV-07 Phase B**: KHÔNG phụ thuộc. Report có thể include
   marketing section với `availability = REVIEW_REQUIRED` placeholder.
   DEV-09 không cần actual recommendation content để bắt đầu.

5. **Marketing placeholder in report**: DEV-09 report cho marketing
   section có thể hiển thị:
   - Phase A: "Marketing recommendation: REVIEW_REQUIRED"
   - Phase B (khi hoàn thành): actual content từ DEV-07 Phase B.

**Constraints:**

- Cần planning document trước (AGENTS.md §4).
- Cần xác định report format: markdown, HTML, JSON, hay kết hợp.
- Marketing section trong report: placeholder hoặc empty section
  (matching DEV-07 Phase A behavior).
- Report generation có thể reuse content từ DEV-04/05/06/07 manifests.

**Safe next action:**

1. Tạo planning document cho DEV-09.
2. Xác định report sections (experiment summary, evaluation results,
   profiling results, marketing placeholder).
3. Implement report generation cho experiment + evaluation + profiling
   sections (reuse manifests from DEV-04/05/06).
4. Marketing section: placeholder text "Marketing recommendations:
   REVIEW_REQUIRED" (matching DEV-07 Phase A).

---

## 4. DEV-07 Partial Closure

### 4.1. Có thể partial close DEV-07 không?

**CÓ.** DEV-07 có thể được phân chia thành 2 phần:

| Phần | Trạng thái | Nội dung |
|---|---|---|
| **Phase A** | ✅ ACCEPTED | REVIEW_REQUIRED shell + read-only manifest |
| **Phase B technical infrastructure** | ✅ TECHNICALLY IMPLEMENTED | Tokenization parser, MKT framework structure loader, mapping scaffolding, recommendation builder Phase B branch |
| **Phase B actual recommendation content** | ❌ BLOCKED | MKT-01..MKT-05 absent; 4 OQ REVIEW_REQUIRED |

**Phân biệt:**

- `TECHNICALLY IMPLEMENTED` ≠ `RESEARCH DECISION APPROVED` (AGENTS.md §2.10).
- Phase A đã accepted vì không cần MKT framework.
- Phase B technical infrastructure đã technically implemented vì không
  cần MKT framework content (chỉ cần structural metadata).
- Phase B actual content **chưa** technically implemented vì không thể
  populate template slots mà không có MKT content.

### 4.2. Những gì không thể partial close

- **Actual marketing recommendation content**: objective, strategy,
  action, KPI, limitation text — đều đến từ MKT-02..MKT-05.
- **KPI framework**: KPI definitions cần MKT-04 + owner approval.
- **Marketing segment mapping**: cần OQ-D07-03 canonical tokenization
  confirmation + MKT framework.

### 4.3. DEV-07 closure status

```
DEV-07 DONE (business acceptance)
├── Phase A: ACCEPTED ✅
├── Phase B technical infrastructure: TECHNICALLY IMPLEMENTED ✅
└── Phase B actual recommendation content: BLOCKED ❌
    └── Chờ: OQ-D07-01/03/04 + MKT-01..MKT-05 files
```

**Recommendation:** Owner có thể partial-close DEV-07 (Phase A + Phase B
technical infrastructure) và bắt đầu DEV-08/DEV-09 planning. DEV-07
actual content có thể tiếp tục sau khi owner approve 4 OQ.

---

## 5. Smallest Sequence to Avoid Rework

### 5.1. Recommended sequence

```
1. Owner partial-close DEV-07 (Phase A + Phase B technical infra)
   → No action needed; already ACCEPTED/TECHNICALLY_IMPLEMENTED

2. Owner approve 3 OQ để unblock DEV-07 actual content:
   - OQ-D07-01: MKT framework scope ↔ SYS-01 §6.7 6 fields
   - OQ-D07-03: CP-04 §4.1-§4.3 canonical tokenization
   - OQ-D07-04: KPI units / source
   (OQ-D07-05: export format — not blocking)

3. Owner / mentor tạo MKT-01..MKT-05 framework files

4. DEV-07 task tiếp theo: extend resolve_template_slots
   → populate template slots từ MKT framework content

5. DEV-08 (visualization) planning + implementation
   → Can start immediately (does NOT wait for step 4)
   → Marketing viz placeholder = REVIEW_REQUIRED

6. DEV-09 (reporting) planning + implementation
   → Can start immediately (does NOT wait for step 4)
   → Marketing section placeholder = REVIEW_REQUIRED

7. DEV-08/DEV-09 expand when DEV-07 Phase B content available
   → No rework: placeholder → actual content (additive change)
```

### 5.2. Why this avoids rework

- DEV-08/DEV-09 **placeholder strategy** (REVIEW_REQUIRED for marketing)
  → quando DEV-07 Phase B content arrives, DEV-08/DEV-09 chỉ cần
  mở rộng, không phải viết lại.
- DEV-08/DEV-09 không phụ thuộc DEV-07 Phase B content →
  không rework khi OQ được approve.
- DEV-07 Phase B technical infrastructure đã sẵn sàng cho Phase B
  actual content → không rework khi MKT files được tạo.

---

## 6. Evidence Summary

### 6.1. Files đọc để phân tích

| File | Phần sử dụng |
|---|---|
| `docs/system/DEV-07_phase_b_decision_memo.md` | OQ status, §3 classification, §4 owner questions |
| `docs/system/DEV-07_final_acceptance_report.md` | Phase A/B status, §7 pending OQ, §11 owner closure |
| `docs/system/DEV-07_phase_b_acceptance_report.md` | §1.1 kết luận, §3 OQ detail, §12 owner closure |
| `docs/system/DEV-02_dataset_management.md` | §14 DEV-02 → DEV-09 contract mapping |
| `docs/system/DEV-07_implementation_plan.md` | AC-D07-12, export scope |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | §9 visualization ownership boundary |
| `src/customer_segmentation/visualization/*.py` | 4 placeholder modules with `NotImplementedError` |
| `src/customer_segmentation/prototype/` | 7 prototype packages; NO `prototype/visualization/` or `prototype/reporting/` |

### 6.2. Verified facts

| Fact | Evidence |
|---|---|
| DEV-02 → DEV-08 contract: `dataset_id` only | `DEV-02_dataset_management.md` §14.1 table row DEV-08 |
| DEV-02 → DEV-09 contract: `dataset_id`, `validation_status`, `sha256` | `DEV-02_dataset_management.md` §14.1 table row DEV-09 |
| DEV-07 KHÔNG là input của DEV-08 | `EPIC06_DOCUMENTATION_CONTRACT.md` §9: EPIC-08/09 owns viz; DEV-08 uses DEV-04/06 output |
| DEV-07 KHÔNG là input của DEV-09 | DEV-09 consumes manifests from DEV-04/05/06/07; DEV-07 Phase A placeholder sufficient |
| 4 OQ KHÔNG block DEV-08 | §2.3 matrix |
| 4 OQ KHÔNG block DEV-09 | §2.3 matrix |
| No DEV-08 plan exists | `Glob pattern="docs/**/DEV-08*" → No matches |
| No DEV-09 plan exists | `Glob pattern="docs/**/DEV-09*" → No matches |
| Visualization placeholders exist (NotImplementedError) | `src/customer_segmentation/visualization/*.py` — verified |
| No prototype/visualization/ or prototype/reporting/ package | `ls src/customer_segmentation/prototype/` — only 7 packages |

---

## 7. Remaining Owner Decisions

### 7.1. DEV-07 remaining (unchanged from Phase B decision memo)

| OQ | Câu hỏi | Owner cần làm gì |
|---|---|---|
| OQ-D07-01 | MKT framework scope ↔ SYS-01 §6.7 | Confirm 6 fields mapping |
| OQ-D07-03 | CP-04 §4.1-§4.3 canonical tokenization | Confirm for Phase B mapping |
| OQ-D07-04 | KPI units / source | Confirm KPI framework scope |
| OQ-D07-05 | Export format | Confirm (optional; not blocking acceptance) |

### 7.2. DEV-08/DEV-09 new owner decisions (when starting those tasks)

| Decision | Câu hỏi | Impact |
|---|---|---|
| DEV-08 scope | Prototype-level visualization hay research-core visualization? | Determines package location (`prototype/` vs `visualization/`) |
| DEV-08 visualization ownership | EPIC-06/08/09 content reused ở prototype level? | Avoid scope creep giữa EPIC groups |
| DEV-09 report format | Markdown / HTML / JSON / combined? | Affects implementation approach |
| DEV-09 report sections | Experiment / evaluation / profiling / marketing sections? | Marketing section = placeholder |

---

## 8. Conclusion

### 8.1. Câu trả lời cho câu hỏi audit

| Câu hỏi | Câu trả lời |
|---|---|
| DEV-08/DEV-09 có bị chặn bởi DEV-07 Phase B không? | **KHÔNG.** Không có dependency contract giữa DEV-08/DEV-09 và DEV-07 Phase B actual content. |
| DEV-08/DEV-09 có thể bắt đầu không? | **CÓ** — READY_WITH_CONSTRAINTS. Cần planning document trước; có thể bắt đầu ngay sau khi owner partial-close DEV-07. |
| DEV-07 partial close có được không? | **CÓ.** Phase A (ACCEPTED) + Phase B technical infrastructure (TECHNICALLY IMPLEMENTED) có thể partial close. Phase B actual content BLOCKED chờ 4 OQ. |
| Điều gì đang block? | (a) Owner approval cho 4 OQ DEV-07; (b) MKT-01..MKT-05 framework files; (c) Planning documents cho DEV-08/DEV-09 (not created yet). |
| Sequence nào tránh rework? | DEV-08/DEV-09 bắt đầu ngay với marketing placeholder (REVIEW_REQUIRED); DEV-07 Phase B content tiếp tục song song; DEV-08/DEV-09 mở rộng khi DEV-07 hoàn thành. |

### 8.2. Safe tasks that can start immediately

1. **DEV-07 partial closure**: Phase A + Phase B technical infrastructure
   đã sẵn sàng để owner formalize partial acceptance.
2. **DEV-08 planning**: Tạo `docs/system/DEV-08_*.md` planning document;
   xác định scope, deliverables, visualization ownership.
3. **DEV-09 planning**: Tạo `docs/system/DEV-09_*.md` planning document;
   xác định report format, sections.
4. **DEV-08 implementation** (sau planning): Segment size, cluster
   distribution, evaluation metrics visualization (reuse DEV-04/05/06 data);
   marketing section = placeholder.
5. **DEV-09 implementation** (sau planning): Report generation cho
   experiment/evaluation/profiling sections; marketing section = placeholder.

### 8.3. Tasks that must wait

| Task | Must wait for | Căn cứ |
|---|---|---|
| DEV-07 Phase B actual content | Owner approve 4 OQ + MKT-01..MKT-05 files | `DEV-07_phase_b_decision_memo.md` §4 |
| DEV-08 marketing viz (actual) | DEV-07 Phase B content available | Placeholder → actual (additive) |
| DEV-09 marketing section (actual) | DEV-07 Phase B content available | Placeholder → actual (additive) |

---

## Phụ lục A — Glob verification

```bash
# DEV-08 plans
Glob pattern="docs/**/DEV-08*"    # → No matches

# DEV-09 plans
Glob pattern="docs/**/DEV-09*"  # → No matches

# Visualization placeholders
Glob pattern="src/customer_segmentation/visualization/*.py"
# → distributions.py, rfm.py, clustering.py, profiling.py (all NotImplementedError)

# Prototype packages
ls src/customer_segmentation/prototype/
# → clustering, evaluation, feature_generation, marketing, preprocessing,
#    segmentation, __init__.py
# → NO prototype/visualization/ or prototype/reporting/

# Marketing framework files
Glob pattern="docs/marketing/**"
# → No matches (MKT-01..MKT-05 absent)
```

---

## Phụ lục B — DEV-02 downstream contract table (verbatim)

From `docs/system/DEV-02_dataset_management.md` §14.1:

```
DEV-08 (visualization) | dataset_id | the manifest; only the id (UI layer).
DEV-09 (reporting)    | dataset_id, validation_status, sha256 | the columns[] list.
```

---

*File này là DEV-08/DEV-09 Readiness Report. KHÔNG implement code.
KHÔNG thực hiện Git operations. Owner partial-close DEV-07 và bắt đầu
DEV-08/DEV-09 planning là safe next steps.*