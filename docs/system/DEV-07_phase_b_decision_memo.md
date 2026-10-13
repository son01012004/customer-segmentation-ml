# DEV-07 Phase B — Owner Decision Closure

> **Mã task:** DEV-07 Phase B — Owner Decision Closure (final closure attempt).
> **Tên:** Marketing Recommendation Module — Phase B decision closure.
> **Ngày:** 2026-10-10.
> **Trạng thái:** **DRAFT — chờ owner / mentor phê duyệt 4 OQ**.
> **Phạm vi:** Tổng hợp thành bảng quyết định ngắn gọn; đối chiếu từng OQ
> với contract + input; phân loại thành `READY_NOW` / `NEEDS_OWNER` /
> `NOT_REQUIRED_FOR_DEV07_ACCEPT`; đề xuất tối thiểu mỗi OQ.
> **KHÔNG thuộc memo này:** source code mới, ADR mới, MKT framework
> content, Git operations.

---

## 2. Bốn OQ — Bảng quyết định cuối cùng

### 2.1. OQ-D07-01 — MKT framework scope ↔ SYS-01 §6.7

**Câu hỏi chính xác** (theo `docs/system/DEV-07_owner_decision_matrix.md`
§4 + `docs/system/DEV-07_implementation_plan.md` §12.2):
> MKT-01..MKT-05 framework design thực tế có khớp với 6 fields của
> SYS-01 §6.7 FR-MKT-03 (Marketing Objective, Strategy, Recommended
> Action, KPI, Evidence, Limitation) không, hay schema E-MKT cần điều chỉnh?

**Contract và heading hỗ trợ:**

| Heading | Trích dẫn | Vai trò |
|---|---|---|
| `docs/system/SYS-01_requirements.md` §6.7 FR-MKT-03 | "Nếu MKT framework tồn tại: mỗi recommendation phải có Marketing Objective, Strategy, Recommended Action, KPI, Evidence / Rationale, Limitation." | Yêu cầu 6 fields. |
| `docs/system/SYS-03_data_model.md` §15.1 E-MKT schema | 12 fields: `marketing_objective`, `strategy`, `recommended_action`, `kpi`, `evidence_ref`, `limitation`, ... | Schema shell đã freeze; FR-MKT-03 map sang 6 fields này. |
| `docs/system/SYS-04_ml_processing_pipeline.md` §15.1 | Pipeline handoff interface (SegmentProfile → Recommendation input). | KHÔNG prescribe MKT framework design. |
| `docs/system/SYS-06_ui_ux_design.md` §9 S-13 | UI placeholder. | KHÔNG kết luận scope. |
| `docs/system/DEV-07_owner_decision_matrix.md` §4 row OQ-D07-01 | "MKT framework có được tạo và approve trước Phase B không?". | Block toàn bộ Phase B. |
| `configs/dev07_marketing.yaml::mkt_framework.path_relative` | `"docs/marketing"`. | Nơi MKT files sẽ đặt. |
| Module sẵn sàng: `mkt_framework_loader.py::MktDocRef.mkt_id` (constructor regex `^MKT-0[1-5](?:__|_)v\d+(?:\.\d+)*`) | Loader enforce đúng 5 MKT docs. | Đã verify cấu trúc 5 file. |

**Phương án tối thiểu phù hợp** (không tự invent nội dung):

| Field E-MKT | Mapping đề xuất | Source / Why |
|---|---|---|
| `marketing_objective` | ← MKT-02 (Marketing Objective templates) | SYS-01 §6.7 yêu cầu "Marketing Objective"; đặt ở MKT-02 hợp lý. |
| `strategy` | ← MKT-03 (Strategy section) | SYS-01 §6.7 yêu cầu "Strategy"; Strategy + Action có thể cùng MKT-03. |
| `recommended_action` | ← MKT-03 (Action section, cùng file) | SYS-01 §6.7 yêu cầu "Recommended Action". |
| `kpi` | ← MKT-04 (KPI definitions) | SYS-01 §6.7 yêu cầu "KPI"; FR-MKT-05 cấm silhouette/DBI/CH/WCSS/ARI/AMI/runtime làm KPI. |
| `evidence_ref` | ← auto-populated từ DEV-06 manifest paths | Phase A đã implement (xem `recommendation.py::build_recommendations_from_segmentation`). KHÔNG cần MKT framework. |
| `limitation` | ← MKT-05 (Limitation framework) + `MARKETING_LIMITATION_TEXT` constant | Phase A dùng constant `MARKETING_LIMITATION_TEXT` (`scope.py:231-235`); Phase B có thể nối thêm MKT-05 detail. |
| `source_framework_version` | ← `framework_version_string(ref)` | `mkt_framework_loader.py:framework_version_string` đã implement trả về `"MKT-01..05__vN"`. |

→ **6 fields bắt buộc** theo FR-MKT-03 đều có slot trong schema E-MKT
hiện tại (`SYS-03 §15.1`); **không cần** schema version bump. **MKT-01**
dự kiến là framework overview (provenance/metadata, không populate E-MKT
field nào).

**Rủi ro nếu chọn phương án này:**

- Không validate được cho đến khi MKT framework thực sự tồn tại.
- Nếu owner muốn mapping khác (vd: thêm `priority` field trong MKT-03) →
  cần ADR + schema bump.
- Nếu MKT-04 dùng đơn vị KPI khác với proposal → cần re-discuss (xem
  OQ-D07-04).

**Có thể triển khai không cần owner approval?**

- **KHÔNG** cho phần tạo MKT files. MKT-02..MKT-05 content = business
  methodology = thuộc owner / mentor (per AGENTS.md §2.1, §2.10; CP-04
  §4.4 cấm marketing terms unless data supports; CP-05 §10.4 cấm infer
  LTV/churn/retention/profitability).
- **CÓ thể** (đã xong trong Phase B infrastructure) cho phần technical:
  E-MKT schema shell, `mkt_framework_loader`, `mapping.TemplateSlots`
  field structure, `framework_version_string`. Phần technical này
  chỉ chuẩn bị "slot"; KHÔNG tự populate content.

**Phần đang block DEV-07 DONE:**

- **Actual recommendation content** (Objective / Strategy / Action /
  KPI / Limitation). Phase B hiện tại return None cho mọi slot trong
  `mapping.resolve_template_slots()`.
- **Validation ngoài MKT files thật**: technical infrastructure đã
  verified bằng synthetic framework; cần MKT files thật để integration
  test với content.

---

### 2.2. OQ-D07-03 — Canonical tokenization cho Phase B mapping

**Câu hỏi chính xác** (theo `DEV-07_owner_decision_matrix.md` §4 +
`DEV-07_implementation_plan.md` §12.2):
> CP-04 §4.1–§4.3 construction rules có phải là **canonical
> tokenization** để Phase B mapping Segment → MKT template không, hay
> cần một mapping methodology riêng?

**Contract và heading hỗ trợ (đã đọc trực tiếp `docs/evaluation/CP-04.md`):**

| Heading | Trích dẫn | Vai trò |
|---|---|---|
| `docs/evaluation/CP-04.md` §4.1 | RFM core tiers (Recency × Frequency × Monetary; mỗi trục 3 tiers: HIGHER / LOWER / COMPARABLE → Recent/Older/Mixed, Frequent/Occasional/Mixed, HighValue/LowValue/Mixed). | Định nghĩa 3 × 3 × 3 tier tokens. |
| `docs/evaluation/CP-04.md` §4.2 | Behavioural modifiers (LongTenured, IrregularCadence, Bulk, Active) với rule "direction=HIGHER + classification=HIGH_DIFFERENCE_OBSERVED". | Định nghĩa 4 modifier tokens + rule gắn. |
| `docs/evaluation/CP-04.md` §4.3 | Construction rules: ghép `[RecencyTier] [FrequencyTier]` + MonetaryTier nếu (Monetary ≠ Frequency HOẶC cả hai HIGHER) + behavioural modifier; tổng ≤ 4 từ; fallback "Comparative Segment A/B/C". | **Canonical construction rule.** |
| `docs/evaluation/CP-04.md` §4.4 | Hard NO: no marketing terms; no CancellationRate/ReturnRate; no AverageQuantity ↔ BasketSize redundancy. | Constraint tokenization. |
| `docs/evaluation/CP-04.md` §5.3 | Sample segment names (concrete examples). | **CHỈ ví dụ**, không phải template. |
| Module `src/customer_segmentation/prototype/marketing/tokenization.py` | Pure parser; closed sets RECENCY_TIERS / FREQUENCY_TIERS / MONETARY_TIERS / BEHAVIOURAL_MODIFIERS (frozen 2026-10-10). | Đã implement theo CP-04 §4.1-§4.4. |
| `src/customer_segmentation/prototype/marketing/mapping.py::resolve_template_slots` | Returns TemplateSlots; falls back to Phase A REVIEW_REQUIRED khi MKT absent. | Mapping scaffolding đã wired. |

**Kiểm tra quy tắc có đủ để xác định canonical tokenization không?**

- **Đủ cho NAMED segments**: 4 token types (Recency × Frequency ×
  Monetary + Modifier), tổng ≤ 4 từ → parser `parse_cp04_segment_name`
  trả về 4-tuple + unmatched_tokens. Đã test 24 cases trong
  `tests/test_dev07_tokenization.py`.
- **Không đủ cho COMPARATIVE / NOISE / NOT_AVAILABLE**: CP-04 §4.3 có
  fallback "Comparative Segment A/B/C" → tokenization KHÔNG unique cho
  các segment này (CP-04 §5.3 note: "DBSCAN C1 (1,042 customers) có
  toàn bộ features COMPARABLE → naming 'Mixed Mixed' là naming đúng
  theo framework"). Parser trả về `tier_match=False` cho COMPARATIVE
  segments; `unmatched_tokens` sẽ chứa các từ không match (vd:
  "Comparative", "Segment", "A"). Khi `tier_match=False`,
  `mapping.resolve_template_slots` vẫn chạy nhưng `cp04_tokens_match`
  = False → caller nên skip Phase B path.

**Phù hợp với segment/profile thực tế không?**

- **NAMED segments** (33 clusters theo CP-04 §5.1): phù hợp. Parser
  parse đúng "Recent Frequent HighValue LongTenured" → 4 tokens.
- **NOISE** (DBSCAN noise = -1): đã được DEV-07 loại trừ từ trước
  (`recommendation.py::build_recommendations_from_segmentation` filter
  `is_noise=True` HOẶC `segment_id=-1`); không vào tokenization.
- **NOT_AVAILABLE** (5 units EXP-03 working-selected): không có segment
  name → tokenization parser return rỗng với `tier_match=False`. Không
  dùng cho MKT mapping.
- **COMPARATIVE** (vd: DBSCAN C1 "Mixed Mixed"): parser parse được nhưng
  2 tier = "Mixed" — fallback có thể cần owner quyết.

**Phương án tối thiểu phù hợp:**

- **Dùng CP-04 §4.1–§4.3 làm canonical tokenization** cho NAMED segments.
- Tokenization parser (`tokenization.py`) đã implement là **pure
  function**: input string → 4-tuple. KHÔNG suy diễn, KHÔNG generate.
- COMPARATIVE / NOT_AVAILABLE segments: giữ `tier_match=False`; không
  đi qua MKT mapping (rely on Phase A REVIEW_REQUIRED fallback).

**Rủi ro nếu chọn phương án này:**

- CP-04 §4.3 fallback "Comparative Segment A/B/C" → KHÔNG unique cho
  COMPARATIVE segments. Parser trả `tier_match=False`; nếu owner muốn
  MKT mapping vẫn áp dụng (vd: dùng default template cho COMPARATIVE)
  → cần thêm decision.
- Nếu owner muốn methodology khác (vd: K-Means cluster archetype,
  RFM tercile, ...) → cần re-discuss + re-implement parser.

**Có thể triển khai không cần owner approval?**

- **CÓ cho parser**: pure function, no synthesis, deterministic. Đã
  implement + 24 tests pass.
- **KHÔNG cho việc wire parser vào Phase B mapping path "khi nào thì
  dùng"**: đó là methodology decision (vd: NAMED → MKT mapping;
  COMPARATIVE → ??). Hiện tại wire rule = "Phase A REVIEW_REQUIRED
  fallback luôn" là conservative, an toàn.

**Phần đang block DEV-07 DONE:**

- **COMPARATIVE segment mapping rule**: parser trả `tier_match=False`;
  nếu owner muốn MKT mapping vẫn chạy với default template → cần owner
  confirm rule. Nếu owner muốn giữ fallback Phase A → đã OK.
- **Confirmation rằng CP-04 §4.1-§4.3 đủ canonical**: pure technical
  fact, nhưng methodology adoption cần owner / mentor quyết (per
  AGENTS.md §2.10; SYS-03 §3.3 OQ-DM-03 đã note "có thể phải điều
  chỉnh E-MKT fields khi MKT framework đến").

---

### 2.3. OQ-D07-04 — KPI units / data source

**Câu hỏi chính xác** (theo `DEV-07_owner_decision_matrix.md` §4 +
`DEV-07_implementation_plan.md` §12.2):
> KPI definitions trong MKT-04 nên dùng đơn vị nguồn nào — survey-based,
> transaction-based, hay composition-based?

**Kiểm kê nguồn dữ liệu thực sự có trong contract + input:**

| Nguồn | Status | Contract |
|---|---|---|
| `data/raw/primary/Online Retail.xlsx` | Có trong `.gitignore` (KHÔNG commit) | FE-01 evidence; AGENTS.md §2.12. |
| `data/processed/final_clustering_dataset.parquet` (4,371 × 14 RFM Extended) | Có (git-ignored) | FE-06 evidence; SHA `ba54033e...80f9c`. |
| `data/processed/customer_metadata.parquet` (4,371 × 1, CustomerID) | Có (git-ignored) | FE-06 evidence. |
| `reports/profiling/cp04/cp04_*.csv` | Có (research artifact) | CP-04 §9 traceability. |
| Survey / external customer retention data | **KHÔNG CÓ** | Verified: KHÔNG có file ngoài primary dataset. |
| CancellationRate / ReturnRate (FE-06 features 13, 14) | CÓ raw nhưng `NOT_ASSESSABLE` | FE-06 §13 (`ELIGIBLE_WORKING_ASSUMPTION`); CP-04 §4.4 hard NO. |
| Frequency, AverageQuantity, BasketSize, ActiveDays (FE-06 features 2, 5, 6, 10) | CÓ raw, `ELIGIBLE_WORKING_ASSUMPTION` | FE-06 §13; chưa final-approved. |

**Đề xuất KPI chỉ khi có định nghĩa + đơn vị + công thức + nguồn dữ liệu được hỗ trợ:**

| KPI đề xuất | Định nghĩa | Đơn vị | Công thức / computation | Nguồn dữ liệu | Có hỗ trợ trong input không? |
|---|---|---|---|---|---|
| Average order value | Trung bình GBP / invoice | GBP | `Monetary / Frequency` (từ FE-06 RFM) | `final_clustering_dataset.parquet` | ✅ Có (RFM). |
| Repeat purchase frequency | Số invoice / tenure (active period) | invoice / day | `Frequency / ActiveDays` (nếu ≠ 0) | FE-06 RFM | ⚠️ ActiveDays = `ELIGIBLE_WORKING_ASSUMPTION`. |
| Product category diversity | Số categories unique / customer | count | Tính từ `transactions_clean.parquet` (FE-02 output) | FE-02 evidence | ⚠️ Yêu cầu re-aggregate từ FE-02; chưa có sẵn. |
| Customer tenure growth | TenureDays distribution | days | `max(InvoiceDate) - min(InvoiceDate)` per customer | FE-06 `TenureDays` | ✅ Có (RFM). |
| Internal clustering metric (silhouette, DBI, CH, WCSS, ARI, AMI, runtime) | KHÔNG ĐƯỢC | n/a | n/a | n/a | ❌ **BỊ CẤM** bởi FR-MKT-05, CON-07. |
| LTV / CLV / churn / retention / VIP / at-risk / profitability | KHÔNG ĐƯỢC | n/a | n/a | n/a | ❌ **BỊ CẤM** bởi AGENTS.md §3, CP-05 §10.4. |

**Nếu chỉ có composition data, giới hạn rõ ràng:**

- `composition-based` KPI chỉ có thể dùng 8/14 features đã `ELIGIBLE`
  (Recency, Monetary, TotalQuantity, TenureDays, PurchaseIntervalMean,
  PurchaseIntervalStd, AverageInvoiceValue, ProductsPerInvoice).
- 6 features còn lại (Frequency, AverageQuantity, BasketSize, ActiveDays,
  CancellationRate, ReturnRate) `ELIGIBLE_WORKING_ASSUMPTION` → KHÔNG
  dùng làm primary KPI evidence.
- **KHÔNG có transaction-level survey data** (churn, retention, NPS) →
  không thể compute KPI này ở Phase B.
- **KHÔNG fake** transaction hoặc survey data. AGENTS.md §2.1 cấm
  invent data.

**Phương án tối thiểu phù hợp:**

- **KHÔNG auto-compute KPI từ dữ liệu** ở Phase B prototype.
- KPI definitions **đến từ MKT-04** (do owner tạo) — agent chỉ render
  đúng những gì MKT-04 file chứa.
- Nếu MKT-04 chỉ có descriptor (không có formula/data source), AI Agent
  KHÔNG compute; chỉ pass-through string.
- **KHÔNG ĐƯỢC**:
  - Auto-compute LTV, CLV, churn, retention từ transaction data
    (AGENTS.md §3, CP-05 §10.4).
  - Auto-compute từ CancellationRate / ReturnRate (CP-04 §4.4).
  - Treatment của CancellationRate / ReturnRate là `NOT_ASSESSABLE`
    cho business interpretation (per CP-03 §4.5, CP-04 §4.4).

**Rủi ro nếu chọn phương án này:**

- Nếu owner muốn KPI framework ngay từ Phase A (vd: pass-through
  MKT-04 → E-MKT.kpi), cần owner cung cấp MKT-04 file. Hiện tại không
  có KPI nào trong `marketing_manifest.json` (`kpi: None`).
- Nếu owner muốn Phase A render composition-based KPI từ RFM features
  → vẫn cần owner approval vì đó là methodology decision.

**Có thể triển khai không cần owner approval?**

- **KHÔNG**: KPI framework là methodology decision. Agent không có
  authority để define KPI units / sources / formulas.
- **CÓ thể** (đã làm) cho phần `KPI_BLOCKLIST` enforcement
  (`scope.py::KPI_BLOCKLIST = {"silhouette", "davies_bouldin", ...}`)
  và `forbid_internal_metrics_as_kpi` config flag. Đây là defensive
  check, không phải methodology.

**Phần đang block DEV-07 DONE:**

- **MKT-04 framework file** (chưa tồn tại) → không có KPI definitions
  để pass-through.
- **Owner confirmation về KPI scope** (a) survey only, (b) transaction-
  derived, (c) composition từ features, (d) tổ hợp.

---

### 2.4. OQ-D07-05 — Export format (CSV / JSONL / Markdown)

**Câu hỏi chính xác** (theo `DEV-07_owner_decision_matrix.md` §4 +
`DEV-07_implementation_plan.md` §12.2):
> DEV-07 export format nên là gì — (a) CSV + JSONL (mirror DEV-06
> pattern), (b) chỉ manifest JSON (read-only), (c) Markdown report,
> (d) khác?

**Đối chiếu SYS-03, DEV-06, acceptance criteria:**

| Nguồn | Trích dẫn | Vai trò |
|---|---|---|
| `docs/system/SYS-01_requirements.md` §6.8 FR-REPORT-01..03 | "Hiển thị danh sách report đã sinh... SHOULD" (FR-REPORT-01), "Export report tổng hợp experiment result (CSV / Markdown)... SHOULD" (FR-REPORT-02). | **SHOULD**, KHÔNG phải MUST. |
| `docs/system/SYS-01_requirements.md` §6.7 FR-MKT-04 | "Recommendation KHÔNG biến thành campaign automation. UI chỉ 'view' / 'export', KHÔNG có 'send campaign', 'schedule', 'trigger'." | MUST (no automation). |
| `docs/system/SYS-03_data_model.md` §15.1 | E-MKT schema shell; KHÔNG có contract về export format cụ thể. | KHÔNG ép format. |
| `docs/system/DEV-06_*.md` (verify: `grep "recommendations" \| /reports/`) | DEV-06 export `recommendations.csv` + `recommendations.jsonl`. | Mirror pattern (nếu owner chọn). |
| `configs/dev07_marketing.yaml::storage.emit_*` | `emit_manifest_json: true`, `emit_recommendations_csv: false`, `emit_recommendations_jsonl: false`. | **Hiện tại**: read-only manifest. |
| `docs/system/DEV-07_owner_decision_brief.md` §5.3 row OQ-D07-08 | "Phase A export scope — read-only manifest hay CSV + JSONL? Status: RESOLVED 2026-10-10 — Read-only manifest". | Phase A đã resolve = read-only. |
| `docs/system/DEV-07_owner_decision_brief.md` §6.2 #6 | "Phase A export scope? Phương án A: Read-only manifest (Phase A không có recommendation thật), Phương án B: CSV + JSONL export. Khuyến nghị: Read-only". | Phase A = read-only. |
| `docs/system/DEV-07_implementation_plan.md` AC-D07-12 / AC list | AC list defines required deliverables; **KHÔNG ép** CSV/JSONL writers là MUST cho DEV-07 acceptance. | Acceptance = read-only manifest đủ. |

**Export có bắt buộc để nghiệm thu DEV-07 hay là tính năng có thể trì hoãn?**

- **KHÔNG bắt buộc** cho DEV-07 acceptance. Lý do:
  - FR-REPORT-01..03 = SHOULD, không MUST.
  - FR-MKT-04 chỉ cấm automation; export local là OK nhưng không bắt buộc.
  - DEV-07 hiện tại đã pass Phase A acceptance gate (2026-10-10) với
    `emit_report_csv: false` + `emit_recommendations_jsonl: false`.
  - Acceptance criteria của DEV-07 (xem `DEV-07_implementation_plan.md`
    §10.1) liệt kê deliverables gồm "marketing_manifest.json" + (optional)
    "recommendations.csv" + "recommendations.jsonl" — optional.
- **Có thể trì hoãn** cho đến khi Phase B có MKT content thật. Lý do:
  - Export giá trị `REVIEW_REQUIRED` shell (Phase A) không hữu ích cho
    researcher (per OQ-D07-08 rationale).
  - Export MKT-populated content (Phase B) chỉ hữu ích sau khi MKT
    framework tồn tại.

**Phương án tối thiểu phù hợp:**

- **Giữ export flags = false** trong Phase A và Phase B hiện tại
  (read-only manifest).
- Khi owner approve OQ-D07-05 và MKT content tồn tại → enable flags
  + implement CSV/JSONL writers (mirror DEV-06 pattern).

**Rủi ro nếu chọn phương án này:**

- Nếu owner muốn Phase B có export ngay khi MKT-02..MKT-05 files tồn tại
  → cần triển khai CSV + JSONL writers; surface area tăng nhẹ (~50 LOC).
- Nếu owner muốn Markdown report thay vì CSV/JSONL → cần thêm Markdown
  formatter.

**Có thể triển khai không cần owner approval?**

- **CÓ cho việc giữ read-only** (status quo). Config flags đã ở `false`
  trong `configs/dev07_marketing.yaml`.
- **KHÔNG cho việc enable export**: đó là methodology / scope decision.
  Agent KHÔNG tự đổi config flag từ `false` → `true` mà không có owner
  approval.

**Phần đang block DEV-07 DONE:**

- **KHÔNG block** DEV-07 acceptance (export là optional).
- Có thể trì hoãn sang Phase B thực sự (sau khi MKT framework tồn tại).

---

## 3. Phân loại phần việc

### 3.1. Ready now (đã có căn cứ — có thể triển khai / đã xong)

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| CP-04 §4.1–§4.3 tokenization parser (`tokenization.py`) | ✅ Implemented + 24 tests pass | `tests/test_dev07_tokenization.py` (24 tests); pure parsing, no synthesis. |
| MKT framework structure loader (`mkt_framework_loader.py` extension) | ✅ Implemented + 18 tests pass | `tests/test_dev07_mkt_framework_structure.py` (18 tests); per-doc metadata (sha256, byte_count, token_count); no business content parsing. |
| Mapping scaffolding (`mapping.py`) | ✅ Implemented + 23 tests pass | `tests/test_dev07_mapping_scaffolding.py` (23 tests); content-free slots, all `None` until MKT content. |
| Recommendation builder Phase B branch wired | ✅ Implemented | `recommendation.py::build_recommendation_entry` accepts `mkt_framework_structure` + `cp04_segment_name`; falls back to Phase A REVIEW_REQUIRED. |
| Pipeline integration | ✅ Wired | `pipeline.py` passes `mkt_framework_structure` through. |
| Config flags cho export | ✅ Present (`=false`) | `configs/dev07_marketing.yaml::storage.emit_recommendations_csv/jsonl`. |
| Test suite / DEV-07 | ✅ 328 pass | `pytest tests/test_dev07_*.py` (verified 2026-10-10). |
| Regression DEV-02..07 | ✅ 1401 pass, 1 skipped pre-existing | `pytest tests/test_dev0[2-7]*.py` (verified 2026-10-10). |
| Ruff clean | ✅ | `ruff check src/customer_segmentation/prototype/marketing/ tests/test_dev07_*.py scripts/dev07_run_marketing.py` — All checks passed. |
| Black clean | ✅ | `black --check ...` — 26 files unchanged. |
| HTML prototype unchanged | ✅ | `index.html` không bị sửa (per OQ-D07-06 resolution). |
| AGENTS.md, .gitignore, pyproject.toml, SYS-* | ✅ Unchanged | Verified không có diff. |

### 3.2. Needs owner approval (không tự quyết)

| Hạng mục | Lý do block | Cần owner / mentor quyết |
|---|---|---|
| **OQ-D07-01**: MKT framework scope ↔ SYS-01 §6.7 6 fields | Business methodology (khi nào thì mapping nào → template nào). | Owner confirm mapping 6 fields → MKT-01..05. |
| **OQ-D07-03**: CP-04 §4.1–§4.3 canonical tokenization | Methodology adoption (CP-04 §4.3 fallback COMPARATIVE không unique). | Owner confirm CP-04 §4.1–§4.3 là canonical cho Phase B mapping. |
| **OQ-D07-04**: KPI units / data source | Methodology (KPI framework = business definition). | Owner confirm scope (a) survey only, (b) transaction-derived, (c) composition từ features, (d) tổ hợp. |
| **MKT-01..MKT-05 framework files** | Business methodology content. | Owner / mentor tạo + approve. |
| **Actual recommendation content** (Objective / Strategy / Action / KPI / Limitation) | Phụ thuộc MKT framework + 4 OQ. | Owner approve OQ-D07-01 + MKT files. |
| **HTML `#/marketing` UI expansion** | Per OQ-D07-06 = giữ nguyên placeholder Phase A. | Owner quyết Phase B UI scope. |

### 3.3. Not required for DEV-07 acceptance (có thể để sau)

| Hạng mục | Lý do | Trì hoãn khi nào |
|---|---|---|
| CSV + JSONL export writers | OQ-D07-05 deferred; FR-REPORT-* = SHOULD; DEV-07 accept đã pass với read-only manifest. | Khi owner enable OQ-D07-05 + MKT content tồn tại. |
| Markdown report writer | Không có trong AC; SYS-01 §6.8 chỉ "CSV / Markdown" — KHÔNG MUST. | Khi owner enable. |
| Cross-segmentation compare | Phase B only; CP-04 cross-algorithm mapping bị cấm (CON-09). | Sau khi MKT framework có compare semantics (nếu có). |
| Actual `marketing_objective / strategy / recommended_action / kpi / limitation` populate | Phụ thuộc MKT framework. | Sau khi owner approve OQ-D07-01, OQ-D07-04 + MKT files tồn tại. |
| UI expansion `#/marketing` (per-segment table) | Per OQ-D07-06 = giữ nguyên placeholder. | Phase B + owner approve UI scope. |

---

## 4. Câu hỏi owner tối thiểu để unblock DEV-07 DONE

Dưới đây là 4 câu hỏi owner, mỗi câu có đề xuất mặc định và căn cứ.
**KHÔNG tự giải quyết** — đây là methodology decision thuộc thẩm quyền
owner / mentor (AGENTS.md §2.10).

### 4.1. OQ-D07-01 (MKT framework scope ↔ SYS-01 §6.7)

**Câu hỏi:** MKT framework design có khớp với 6 fields FR-MKT-03 không?
- `marketing_objective` ← MKT-02
- `strategy` ← MKT-03
- `recommended_action` ← MKT-03
- `kpi` ← MKT-04
- `evidence_ref` ← auto-populated (đã có Phase A)
- `limitation` ← MKT-05 + `MARKETING_LIMITATION_TEXT` constant

**Đề xuất mặc định:** Giữ mapping như trên; `source_framework_version`
← `framework_version_string(ref) = "MKT-01..05__vN"`. **KHÔNG bump**
`MARKETING_MANIFEST_SCHEMA_VERSION` (1.0.0).

**Căn cứ:** SYS-03 §15.1 E-MKT schema shell đã có sẵn 6 fields này;
SYS-01 §6.7 FR-MKT-03 đã định nghĩa; MKT-01 đóng vai trò framework
overview/provenance (không populate E-MKT field nào).

### 4.2. OQ-D07-03 (CP-04 §4.1–§4.3 canonical tokenization)

**Câu hỏi:** CP-04 §4.1–§4.3 có phải canonical tokenization cho Phase B
mapping Segment → MKT template không? Đặc biệt cho COMPARATIVE segments
(vd: DBSCAN C1 "Mixed Mixed")?

**Đề xuất mặc định:** Dùng CP-04 §4.1–§4.3 cho NAMED segments;
COMPARATIVE / NOT_AVAILABLE → skip (rely on Phase A REVIEW_REQUIRED
fallback).

**Căn cứ:** CP-04 §4.3 đã verify có closed sets (3 × 3 × 3 tiers + 4
modifiers); parser pure function đã implement + 24 tests pass;
COMPARATIVE fallback không unique → an toàn nhất là skip.

### 4.3. OQ-D07-04 (KPI units / data source)

**Câu hỏi:** KPI definitions trong MKT-04 dùng nguồn nào?

**Đề xuất mặc định:** KHÔNG auto-compute; KPI từ MKT-04 file do owner
tạo. Nếu MKT-04 có KPI = composition từ 8/14 RFM features `ELIGIBLE` →
cho phép (AnovaInvoiceValue, TenureDays, etc.). KHÔNG dùng 6 features
`ELIGIBLE_WORKING_ASSUMPTION` (Frequency, AverageQuantity, BasketSize,
ActiveDays, CancellationRate, ReturnRate) làm primary KPI evidence.

**Căn cứ:** AGENTS.md §2.1, §2.5; CP-04 §4.4; CP-05 §10.4; FR-MKT-05
cấm internal clustering metric. Hiện tại chỉ có composition data (FE-06
RFM) + research artifacts (CP-04 evidence) + raw transactions (FE-02).
KHÔNG có survey data.

### 4.4. OQ-D07-05 (Export format)

**Câu hỏi:** DEV-07 export format nào cho Phase B? (a) CSV + JSONL
(mirror DEV-06), (b) read-only, (c) Markdown, (d) khác.

**Đề xuất mặc định:** Giữ read-only cho Phase B hiện tại (MKT absent).
Enable CSV + JSONL ở task Phase B riêng khi MKT content tồn tại.

**Căn cứ:** FR-REPORT-01..03 = SHOULD; DEV-07 acceptance đã pass với
read-only; OQ-D07-08 đã resolve = read-only cho Phase A. Export chỉ
hữu ích khi MKT content populated.

---

## 5. Validation gates đã chạy (verified 2026-10-10)

| Gate | Status | Bằng chứng |
|---|---|---|
| DEV-07 tests | ✅ | `pytest tests/test_dev07_*.py` → `328 passed`. |
| DEV-02..07 regression | ✅ | `pytest tests/test_dev0[2-7]*.py` → `1401 passed, 1 skipped` (pre-existing AC 38b OPT-IN). |
| Ruff check | ✅ | `ruff check src/customer_segmentation/prototype/marketing/ tests/test_dev07_*.py scripts/dev07_run_marketing.py` → All checks passed. |
| Black format | ✅ | `black --check ...` → 26 files would be left unchanged. |
| YAML parse | ✅ | `yaml.safe_load(configs/dev07_marketing.yaml)` OK. |
| Default config + absent MKT → None | ✅ | Phase A contract preserved. |
| Default config + synthetic MKT framework | ✅ | `load_mkt_framework_structure(...)` returns structure; `framework_version_string(ref) = "MKT-01..05__v1"`. |
| E-MKT schema unchanged | ✅ | `MARKETING_MANIFEST_SCHEMA_VERSION = "1.0.0"`; không bump. |
| HTML prototype unchanged | ✅ | `index.html` không bị sửa (per OQ-D07-06). |
| AGENTS.md, .gitignore, pyproject.toml, SYS-* | ✅ | Unchanged. |
| No Git operations | ✅ | No commit / push / PR / branch. |
| No research data used | ✅ | Synthetic fixtures only. |

---

## 6. Conclusion

### 6.1. Trạng thái DEV-07 hiện tại

- **Phase A**: ACCEPTED 2026-10-10.
- **Phase B technical infrastructure**: TECHNICALLY IMPLEMENTED 2026-10-10.
- **Phase B actual recommendation generation**: **BLOCKED** — chờ owner
  approve OQ-D07-01 + OQ-D07-03 + OQ-D07-04 (+ MKT-01..MKT-05 files).
- **DEV-07 acceptance**: CÓ THỂ nghiệm thu Phase A + Phase B technical
  infrastructure ngay. **KHÔNG thể** nghiệm thu actual recommendation
  generation vì đó là methodology decision.

### 6.2. OQ nào đã có căn cứ giải quyết và OQ nào thực sự cần owner

- **OQ-D07-01** (MKT scope): CẦN owner confirm mapping 6 fields ↔
  MKT-01..05. **KHÔNG thể tự giải.**
- **OQ-D07-03** (CP-04 tokenization canonical): Parser đã implement +
  tested; **CẦN owner confirm** methodology adoption (đặc biệt rule
  cho COMPARATIVE segments).
- **OQ-D07-04** (KPI source): CẦN owner confirm scope. **KHÔNG thể tự
  giải** vì đó là KPI framework definition.
- **OQ-D07-05** (export): CẦN owner confirm nếu muốn enable. Hiện tại
  read-only = status quo, **KHÔNG block** DEV-07 acceptance.

### 6.3. Câu hỏi owner tối thiểu để chuyển sang DEV-08/DEV-09

4 câu hỏi ở §4 — đề xuất mặc định mỗi câu + căn cứ contract.

### 6.4. Phần kỹ thuật độc lập đã hoàn thành

- Tokenization parser + 24 tests.
- MKT framework structure loader + 18 tests.
- Mapping scaffolding + 23 tests.
- Recommendation builder Phase B branch wired (fall back to Phase A).
- Config flags cho export (read-only).
- DEV-07 tests pass (328/328).
- DEV-02..07 regression pass (1401/1401 + 1 pre-existing skipped).
- Ruff/Black clean.
- 4 acceptance reports (Phase B decision memo, Phase B acceptance,
  Final acceptance) — Phase B technical infrastructure accepted.

---

## Phụ lục A — Files thay đổi trong task này

```
Files sửa (1):
  docs/system/DEV-07_phase_b_decision_memo.md    # file này (concise decision table)

Files KHÔNG thay đổi (verified):
  src/customer_segmentation/prototype/marketing/{tokenization,mapping,
    mkt_framework_loader,recommendation,pipeline}.py
  tests/test_dev07_*.py
  configs/dev07_marketing.yaml
  AGENTS.md, .gitignore, pyproject.toml
  docs/system/SYS-01..06_*.md, docs/system/DEV-01..06_*.md
  docs/system/DEV-07_phase_b_acceptance_report.md
  docs/system/DEV-07_final_acceptance_report.md
  docs/marketing/**                          # KHÔNG tồn tại (MKT framework absent)
  docs/system/ui-prototype/index.html         # Placeholder giữ nguyên
  data/**                                     # git-ignored
```

---

*File này là DEV-07 Phase B Decision Closure Memo. KHÔNG implement code
mới trong memo này. KHÔNG thay đổi OQ status trong owner matrix. Chờ
owner review và approval 4 OQ để unblock Phase B actual recommendation
generation trong task tiếp theo.*