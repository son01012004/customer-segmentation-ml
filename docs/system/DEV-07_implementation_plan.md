# DEV-07 — Marketing Recommendation Module: Implementation Plan

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module
> **Trạng thái:** **PLAN ONLY — RECONNAISSANCE + PLANNING**
> (no code, no config edit, no ADR edit, no SYS contract edit, no Git op).
> **Ngày:** 2026-10-10
> **Phạm vi:** Phân tích dependency, đối chiếu hợp đồng hệ thống, xác định
> điều kiện triển khai và lập kế hoạch triển khai cho DEV-07 — module
> Marketing Recommendation ở prototype layer.
> **Architecture:** Option A (ADR-0005) — offline, single-machine,
> file-based. No backend, no API, no database, no worker, no queue.
> **Does NOT** tự tạo MKT framework, không dùng internal clustering
> metric làm business effectiveness, không tự phát minh segment name
> marketing-y, không promote prototype → research evidence.

---

## Mục lục

1. [Executive Summary](#1-executive-summary)
2. [Tài liệu đã kiểm tra](#2-t%C3%A0i-li%E1%BB%87u-%C4%91%C3%A3-ki%E1%BB%83m-tra)
3. [MKT-01..MKT-05 evidence matrix](#3-mkt-01mkt-05-evidence-matrix)
4. [DEV-06 / Customer Profile input contract](#4-dev-06--customer-profile-input-contract)
5. [DEV-07 functional và technical contract](#5-dev-07-functional-v%C3%A0-technical-contract)
6. [Conflict / dependency register](#6-conflict--dependency-register)
7. [Các quyết định cần owner/mentor xác nhận](#7-c%C3%A1c-quy%E1%BA%BFt-%C4%91%E1%BB%8Bnh-c%E1%BA%A7n-ownermentor-x%C3%A1c-nh%E1%BA%ADn)
8. [Kiến trúc đề xuất và data flow](#8-ki%E1%BA%BFn-tr%C3%BAc-%C4%91%E1%BB%81-xu%E1%BA%A5t-v%C3%A0-data-flow)
9. [Danh sách file dự kiến](#9-danh-s%C3%A1ch-file-d%E1%BB%B1-ki%E1%BA%BFn)
10. [Implementation phases và test plan](#10-implementation-phases-v%C3%A0-test-plan)
11. [Acceptance Criteria có thể kiểm chứng](#11-acceptance-criteria-c%C3%B3-th%E1%BB%83-ki%E1%BB%83m-ch%E1%BB%A9ng)
12. [Blockers, risks và exit criteria](#12-blockers-risks-v%C3%A0-exit-criteria)
13. [Kết luận](#13-k%E1%BA%BFt-lu%E1%BA%ADn)

---

## 1. Executive Summary

DEV-07 thuộc EPIC-11 system design (sau SYS-01..06, sau DEV-06 segmentation
module đã implemented) và nằm trong prototype layer theo ADR-0005.

**Trạng thái thực tế tại thời điểm planning:**

- MKT-01..MKT-05 **chưa tồn tại** trong repository (verified bằng
  `Grep` + `Glob` toàn repo).
- `E-MKT` (MarketingRecommendation) chỉ là **schema shell** trong
  `SYS-03` §15.1 với `availability = NOT_AVAILABLE` cho tất cả segment.
- `SYS-04` §15.1 ghi rõ Marketing handoff = `REVIEW_REQUIRED`.
- `SYS-06` §9 S-13 (Marketing screen) chỉ là **placeholder** với badge
  `REVIEW_REQUIRED` — chưa có functional UI.
- `docs/system/DEV-07_planning_report.md` đã tồn tại (untracked) với
  phạm vi tương đương; báo cáo này **bổ sung và làm rõ** một số điểm
  mà planning_report hiện tại còn chưa chính xác về citation.

**Kết luận ngắn:**

- DEV-07 implement Phase A (REVIEW_REQUIRED shell + read-only
  recommendation view theo DEV-06 segmentation output) **CÓ THỂ triển
  khai ngay** vì input contract (DEV-06 `SegmentationManifest v1.0.0`)
  đã ổn định.
- DEV-07 Phase B (recommendation generation thực sự theo MKT framework)
  **BỊ BLOCK** cho đến khi MKT-01..MKT-05 được tạo và approved.
- Phát biện quan trọng: Planning report hiện tại dẫn chiếu
  "S1–S4 archetypes" như là canonical segment templates (CP-04 §5.3)
  — đây là **citation sai**: CP-04 §5.3 chỉ có **sample segment names**;
  phần "construction rules" ở CP-04 §4.3 (RFM tiers + behavioural
  modifiers) mới là thứ gần với "template" nhất. Báo cáo này đề xuất
  dùng CP-04 §4.3 + §4.4 làm cơ sở cho Phase B, không phải archetype
  S1–S4 chưa từng tồn tại.

---

## 2. Tài liệu đã kiểm tra

| Tài liệu | Vai trò cho DEV-07 | Sections đã đọc / verified |
|---|---|---|
| `AGENTS.md` | Global rules binding. | Toàn bộ (§2 principles, §3 stage guardrails, §6 escalation, §2.10 human approval gate, §2.11 Git ops owner). |
| `README.md` | Project context. | Toàn bộ (high-level). |
| `docs/system/SYS-01_requirements.md` | FR-MKT-01..06; §6.7 contract. | §2.8, §6.7, §13 (OQ-01, OQ-02); §12.5 (MKT framework absent). |
| `docs/system/SYS-02_architecture.md` | Layer architecture; file-based boundary. | §1, §1.12, §1.14, §2.1, §2.2 (verified consistent with Option A). |
| `docs/system/SYS-03_data_model.md` | E-MKT schema shell (REVIEW_REQUIRED); relationships. | §3.6, §4.7, §15.1 (E-MKT schema), §18.1 (1:0..1 E-SEG → E-MKT), §27 (OQ-DM-02..03, OQ-DM-14). |
| `docs/system/SYS-04_ml_processing_pipeline.md` | S10 Marketing handoff; FR-MKT mapping. | §2.1, §3.7, §5.1, §12.2, §15.1, §15.2, §23 traceability, §25 OQ-PIPE-05, §26.8. |
| `docs/system/SYS-05_api_design.md` | API contract reference (REVIEW_REQUIRED for current phase). | §15 (Tech stack nào ghi rõ REQ for current prototype phase = backend). |
| `docs/system/SYS-06_ui_ux_design.md` | S-13 Marketing screen spec; status taxonomy. | §5.1 (Sidebar), §9 (S-13), §10.4 (status badge), §18.3 (route `#/marketing`), §19 (open questions #3), §20 (OOS-UI-06). |
| `docs/system/DEV-06_customer_segment_module.md` | Input contract source; pattern reference. | §1.1, §3 (input contract), §7 (API mapping), §14 (DECIDED). |
| `docs/system/DEV-07_planning_report.md` | Existing planning report (untracked). | Toàn bộ — verified content vs source documents; found 1 citation discrepancy (S1–S4 archetypes). |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture Option A; EPIC-12 boundary. | Toàn bộ. |
| `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006) | DBSCAN noise policy prototype default. | Toàn bộ (noise_policy_used = "exclude" default). |
| `docs/decisions/0003-algorithm-scope.md` (ADR-0003) | 5 algorithms only. | Toàn bộ. |
| `docs/decisions/0004-research-questions.md` (ADR-0004) | RQ1/RQ2/RQ3; internal metrics only. | Toàn bộ. |
| `docs/decisions/README.md` | ADR immutability convention. | Toàn bộ (any change → new ADR). |
| `docs/evaluation/CP-01.md` | Segment size distribution; noise separate. | §3–§5 (high-level). |
| `docs/evaluation/CP-02.md` | Feature profile direction (HIGHER/LOWER/COMPARABLE). | §3 (high-level). |
| `docs/evaluation/CP-03.md` | Distinguishing features classification. | §3 (high-level). |
| `docs/evaluation/CP-04.md` | Segment naming framework (RFM tiers + modifiers). | §3 (input), §4.1 (RFM core tiers), §4.2 (behavioural modifiers), §4.3 (construction rules), §4.4 (hard NO), §5 (segment profile summary). |
| `docs/evaluation/CP-05.md` | 6 evaluation axes; `is_interpretation_ready`; `business_relevance` bounded; DBSCAN noise separate. | §5–§11 (per-axis), §12 (DBSCAN handling), §17 (limitations). |
| `src/customer_segmentation/prototype/segmentation/manifest.py` | DEV-06 `SegmentationManifest v1.0.0` schema — input contract mà DEV-07 đọc. | Toàn bộ (verified dataclass fields, hard invariants). |
| `src/customer_segmentation/prototype/segmentation/scope.py` | DEV-06 scope enums (`PROFILED_PROTOTYPE`). | Toàn bộ (verified closed sets). |
| `src/customer_segmentation/prototype/segmentation/storage.py` | DEV-06 storage path pattern; `segmentation_id` derivation (8 fields). | Toàn bộ (verified storage root resolution). |
| `configs/dev06_segmentation.yaml` | DEV-06 config — reference pattern cho `dev07.yaml`. | Toàn bộ (noise policy, statistics set, research_safety block, storage). |
| `configs/dev05_evaluation.yaml` | DEV-05 reference pattern (noise_policy, scope). | Toàn bộ. |
| `configs/dev04_clustering.yaml` | DEV-04 reference pattern. | Toàn bộ (high-level). |
| `docs/system/ui-prototype/index.html` | S-13 Marketing placeholder HTML. | `routes[]` (§506), `renderMarketing()` (§1584–1613). |

### 2.1. Tài liệu **KHÔNG** tồn tại trong repo (verified)

| Pattern | Kết quả grep/glob | Ý nghĩa |
|---|---|---|
| `MKT-01..MKT-05` (documents) | **0 file** | Framework Marketing chưa được tạo. |
| `docs/research/EPIC*` | Chỉ `EPIC06_DOCUMENTATION_CONTRACT.md` + `EPIC09_CP05_PLAN.md`. | Không có EPIC định nghĩa MKT. |
| `docs/marketing/` | Không có. | Thư mục mà Phase B sẽ đọc framework MKT chưa tồn tại. |
| `marketing` source code | Chỉ xuất hiện trong negation contexts (CP-05 plan, CP-02) và `SYS-03/04/06` placeholder mô tả. | Chưa có `prototype/marketing/` package. |

### 2.2. Existing HTML prototype state

- File: `docs/system/ui-prototype/index.html`.
- Route `#/marketing` đã được đăng ký (§506):
  ```js
  {hash:"#/marketing", title:"Marketing", render:renderMarketing, crumb:[["#/marketing","Marketing"]]}
  ```
- `renderMarketing()` (§1584–1613) chỉ là **1 static placeholder** với:
  - `mockBanner()` ở top.
  - `statusBadge("REVIEW_REQUIRED")` — big badge.
  - Heading "Marketing framework pending".
  - Body giải thích MKT-01..MKT-05 chưa tồn tại.
  - Bulleted list những gì module sẽ làm khi MKT framework có.

Đây là **functional shell** đã đúng theo SYS-06 §9 S-13 spec; chỉ cần
mở rộng khi DEV-07 Phase B được triển khai.

---

## 3. MKT-01..MKT-05 evidence matrix

Theo AGENTS.md §2.1, MKT-01..MKT-05 được nhắc đến trong SYS-01/SYS-03/
SYS-04/SYS-06 như là **business inputs** cho DEV-07. Bảng dưới đối chiếu
từng task với bằng chứng thực tế trong repository.

| Task | Artifact thực tế | Business rules | Mapping contract | Evidence | KPI definitions | Limitation | Approval status |
|---|---|---|---|---|---|---|---|
| **MKT-01** (Framework overview) | **ABSENT** — không có file `MKT-01*.md` trong repo (grep + glob confirmed). | Không tìm thấy. | Không tìm thấy. | Không có evidence ngoài references trong SYS-01 §6.7 / SYS-04 §15.1 / SYS-06 §9 rằng MKT-01 *sẽ* tồn tại. | Không tìm thấy. | Không tìm thấy. | **Chưa được tạo.** |
| **MKT-02** (Marketing Objective template per segment) | **ABSENT** — không có file. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | **Chưa được tạo.** |
| **MKT-03** (Strategy + Recommended Action template) | **ABSENT** — không có file. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | **Chưa được tạo.** |
| **MKT-04** (KPI definitions) | **ABSENT** — không có file. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | **Chưa được tạo.** |
| **MKT-05** (Limitation framework) | **ABSENT** — không có file. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | Không tìm thấy. | **Chưa được tạo.** |

**Phân loại trạng thái (theo brief):**

| Trạng thái | MKT-01 | MKT-02 | MKT-03 | MKT-04 | MKT-05 |
|---|---|---|---|---|---|
| Đã tìm thấy nội dung | ❌ | ❌ | ❌ | ❌ | ❌ |
| Nội dung được kế thừa từ tài liệu khác | ❌ | ❌ | ❌ | ❌ | ❌ |
| Chưa xác minh | ❌ | ❌ | ❌ | ❌ | ❌ |
| Thiếu hoặc mâu thuẫn | ✅ (thiếu hoàn toàn) | ✅ | ✅ | ✅ | ✅ |
| Cần project owner/mentor xác nhận | ✅ | ✅ | ✅ | ✅ | ✅ |

**Ghi chú quan trọng:**

- Theo `SYS-01` §2.8, đã verify bằng grep toàn `docs/`: không tồn tại
  tài liệu nào có nhãn `MKT-01..MKT-05`. Các reference duy nhất đến
  "marketing" là các **negation** trong CP-05 plan / CP-02 (cùng pattern)
  và các placeholder mô tả trong SYS-03/04/06.
- Theo `SYS-01` §13 OQ-01, mentor / human researcher cần quyết định:
  (a) tạo MKT framework trước SYS-06, hoặc (b) đợi EPIC-09/10 xong rồi
  tạo. Hiện chưa có evidence nào rằng (a) hay (b) đã được chọn.
- Theo `SYS-03` §15.1 và `SYS-04` §15.1, current prototype scope ghi rõ
  Marketing = `REVIEW_REQUIRED` cho đến khi có MKT framework — đây là
  **methodology lock** hiện hành.

**Kết luận:** Toàn bộ MKT-01..MKT-05 đều **thiếu hoàn toàn**. Không có
bằng chứng nào về business rules, mapping contract, evidence, KPI
definitions, limitation, hay approval status. Đây là **primary blocker**
cho DEV-07 Phase B.

---

## 4. DEV-06 / Customer Profile input contract

### 4.1. Nguồn input bắt buộc

DEV-07 đọc **read-only** output của DEV-06 segmentation:

| Input | Path / Source | Schema |
|---|---|---|
| **SegmentationManifest** | `<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/segmentation/<segmentation_id>/segmentation_manifest.json` | `SegmentationManifest v1.0.0` (`src/customer_segmentation/prototype/segmentation/manifest.py`) |
| **segment_profiles.csv** | Cùng thư mục trên | per-segment × per-feature statistics (9 closed set: mean/median/std/q1/q3/min/max + categorical helpers) |
| **segment_characteristics.json** | Cùng thư mục trên | per-segment × 4-rule characteristic (mean_high_<feature>, mean_low_<feature>, median_above_dataset_median_<feature>, top_category_<feature>_<value>) |
| **segment_sizes_long.csv** | Cùng thư mục trên | segment_id, count, percentage, percentage_base, is_noise |
| **clustering_manifest.json** | DEV-04 output, 1 level up | `ClusteringManifest v1.0.0` |

### 4.2. Các trường DEV-06 manifest cần cho DEV-07

Từ `SegmentationManifest` dataclass (verified bằng `Read`):

| Trường | DEV-07 dùng để |
|---|---|
| `segmentation_id` | Provenance; reference. |
| `clustering_id`, `preprocessed_id`, `dataset_id` | Provenance chain. |
| `algorithm`, `algorithm_version`, `algorithm_family` | Algorithm context. |
| `ml_dataset_sha256`, `feature_set_sha256`, `preprocessing_config_sha256` | Reproducibility. |
| `noise_policy_used` | Hard rule: DBSCAN noise excluded (per ADR-0006 default "exclude"). |
| `segment_sizes` (list[`SegmentSize`]) | Filter noise; count segments; per-segment `percentage`. |
| `profiles` (list[`FeatureProfile`]) | RFM tier derivation từ direction (HIGHER/LOWER/COMPARABLE) — dùng cho Phase B mapping theo CP-04 §4.1. |
| `characteristics` (list[`CharacteristicEntry`]) | Per-segment behavioral evidence; segment_id=-1 (noise) được loại. |
| `preprocessing_warning` | Post-preprocessing disclaimer (mandatory field) — DEV-07 KHÔNG carry forward trong Phase A (intentional; see note below). Phase B sẽ re-evaluate. |
| `research_safety` (always `PROFILED_PROTOTYPE`, `automatically_promoted_to_research=False`) | DEV-07 set `scope = "MARKETING_PROTOTYPE"`, all False. |

### 4.3. CP-04 / CP-05 evidence cho DEV-07

| Artifact | Path | DEV-07 dùng |
|---|---|---|
| `reports/profiling/cp04/cp04_segment_naming.csv` | Per-segment × `segment_name` + `naming_status` (`NAMED`/`COMPARATIVE`/`NOISE`/`NOT_AVAILABLE`) | Reference segment name trong Phase B UI; Phase A chỉ show name + status. |
| `reports/profiling/cp04/cp04_segment_profiles.csv` | Per-segment × feature statistics | Cross-reference evidence. |
| `reports/profiling/cp05/cp05_final_segment_definition.csv` | Per-segment × 6 evaluation axes status | `is_interpretation_ready`, `interpretation_readiness`, `business_relevance_status`. |

### 4.4. Hard contracts từ DEV-06 → DEV-07

- **DBSCAN noise (segment_id = -1) KHÔNG được đưa vào MKT input** —
  `SegmentSize.__post_init__` enforce `is_noise=True ↔ segment_id=-1`.
- `percentage_base ∈ {"n_samples_input", "n_samples_used_for_compute"}`
  — closed set; không tự ý thêm denominator.
- `noise_policy_used` ∈ `{"include", "exclude", "n/a"}` — DEV-07 KHÔNG
  tạo noise policy mới; dùng đúng giá trị từ DEV-06.
- `preprocessing_warning` KHÔNG được carry forward trong Phase A
  (intentional; see owner decision recorded in
  `docs/system/DEV-07_owner_decision_brief.md` §3.5 Option (c)).
  Schema E-MKT (SYS-03 §15.1) giữ nguyên — không thêm field
  `preprocessing_warning` ở Phase A. Carry-over là quyết định/thay
  đổi contract riêng, không tự thực hiện trong Phase A.
  Phase B sẽ re-evaluate carry-over khi mở rộng UI (`renderMarketing()`
  per SYS-06 §9 S-13).

### 4.5. Cách DEV-07 resolve input (proposed)

```python
def resolve_segmentation_input(segmentation_id: str) -> SegmentationManifest:
    # Reuse DEV-06 reader pattern
    from customer_segmentation.prototype.segmentation.storage import (
        resolve_segmentation_path,
    )
    from customer_segmentation.prototype.segmentation.manifest import (
        read_segmentation_manifest,
    )

    path = resolve_segmentation_path(segmentation_id)  # <storage_root>/.../segmentation_manifest.json
    manifest = read_segmentation_manifest(path)
    return manifest
```

DEV-07 **không** modify DEV-06 modules; chỉ **import + read** theo
public API hiện có.

---

## 5. DEV-07 functional và technical contract

### 5.1. Input contract

| Trường | Required | Source | Validation |
|---|---|---|---|
| `segmentation_id` (str, regex `^seg_[0-9a-f]{24}$`) | Yes | CLI arg | Pattern check. |
| `path` tới SegmentationManifest | Conditional | CLI arg (mutually exclusive với `segmentation_id`) | Path exists, SHA-256 stable. |
| Config file path | No | `configs/dev07_marketing.yaml` (default) | YAML parse + schema check. |
| MKT framework path | No (Phase A) / Required (Phase B) | `docs/marketing/MKT-0X_*.md` (Phase B) | Existence check (Phase B only). |

### 5.2. Định danh và lựa chọn Segment

- DEV-07 chỉ làm việc với `segment_id` từ `SegmentationManifest`.
- DBSCAN noise (`is_noise=True`, `segment_id=-1`) bị **exclude ngay từ
  Stage A validation** — counter `n_segments_noise` trong manifest.
- COMPARATIVE / NOT_AVAILABLE segments: vẫn listed nhưng có
  `availability = REVIEW_REQUIRED` (Phase A) hoặc `AVAILABLE` với empty
  template (Phase B nếu MKT framework không cover).
- EXP-03 segments (`labels_persisted = False`): `availability = NOT_AVAILABLE`
  theo CP-01 §3.2 (per `EV03-HP-01`).

### 5.3. Quy tắc mapping Segment → Objective → Strategy → Action → KPI → Limitation

**Phase A (MKT-01..MKT-05 absent):**

```
segment_id ∈ valid_segments (excluding noise):
    recommendation_id = "mkt_" + SHA-256(segmentation_id + segment_id)[:24]
    availability = REVIEW_REQUIRED
    marketing_objective = "PENDING_MKT_FRAMEWORK"
    strategy = "PENDING_MKT_FRAMEWORK"
    recommended_action = "PENDING_MKT_FRAMEWORK"
    kpi = None                # KHÔNG generate KPI
    evidence_ref = [paths to DEV-06 segmentation artifacts]
    limitation = "Marketing framework (MKT-01..MKT-05) not implemented in this prototype scope."
    interpretation_readiness = (from CP-05 evidence, if available)
    is_interpretation_ready = (from CP-05 evidence, if available)
    limitation_note = (derived from CP-04/CP-05 evidence)
```

**Phase B (MKT-01..MKT-05 tồn tại, sau owner approval):**

Mapping từ CP-04 segment_name tokens → MKT archetype/template. **KHÔNG
hard-code mapping**; dùng parsing logic từ CP-04 §4.1–§4.3 (RFM tiers +
behavioural modifiers + construction rules).

Lưu ý quan trọng: planning_report hiện tại tham chiếu "S1–S4 archetypes
(CP-04 §5.3)". Đây là **citation sai**:
- CP-04 §5.3 = "Sample segment names" (concrete examples).
- CP-04 §4.3 = "Construction rules" (RFM tiers + behavioural modifiers).
- CP-04 §4.1 = "RFM core tiers" (Recent/Older × Frequent/Occasional × HighValue/LowValue).
- CP-04 §4.2 = "Behavioural modifiers" (LongTenured/IrregularCadence/Bulk/Active).

DEV-07 Phase B sẽ dựa trên **CP-04 §4.1–§4.3** (tokenized segment name
→ RFM tier + modifier), không phải "S1–S4" archetype giả định.

### 5.4. Evidence / Rationale và Limitation

| Field | Source | Phase A value | Phase B value |
|---|---|---|---|
| `evidence_ref` | Filesystem paths đến DEV-06 / CP-04 / CP-05 artifacts. | Auto-populated. | Auto-populated. |
| `limitation` | MKT framework (when exists) | "Marketing framework (MKT-01..MKT-05) not implemented in this prototype scope." | Per MKT-05. |
| `limitation_note` | Derived từ CP-04 §4.4 (NO marketing terms) + CP-05 business relevance | Hard-coded disclaimer. | Per MKT-05. |

**Limitation framing (CP-05 §10.4, carry-over):**

- KHÔNG claim về CLV / LTV / churn / retention / purchase probability.
- KHÔNG dùng internal clustering metric (silhouette, DBI, CH, WCSS,
  ARI / AMI) như business effectiveness.
- KHÔNG gọi segment là "best", "winner", "target", "champion", "loyal",
  "VIP", "at-risk" (CP-04 §4.4 hard NO).
- KHÔNG raw "post-preprocessing" values khi present cho user (Phase B
  khi MKT framework + UI mở rộng). Phase A: KHÔNG carry forward
  `preprocessing_warning` từ DEV-06 — đây là quyết định có chủ đích
  (intentional), documented in `docs/system/DEV-07_owner_decision_brief.md`
  §3.5 Option (c). Witness tests trong
  `tests/test_dev07_pipeline.py::TestPreprocessingWarningCarryOver`
  document behavior hiện tại (no propagation). Phase B sẽ re-evaluate.

### 5.5. KPI — định nghĩa, đơn vị, nguồn dữ liệu, điều kiện tính và giới hạn

**Phase A:** `kpi = None`. KHÔNG tự tạo KPI definition.

**Phase B:** KPI definitions đến từ MKT-04. DEV-07 chỉ **render** KPI
đã được approved; KHÔNG compute từ internal clustering metric.

Allowed KPI categories (per FR-MKT-05, chỉ là ví dụ — KHÔNG phải đề xuất
override MKT-04):

- Survey-based: customer retention rate (cần external data, KHÔNG compute
  từ RFM dataset hiện tại).
- Transaction-based: average order value, repeat purchase frequency
  (compute từ raw `data/raw/primary/Online Retail.xlsx` — nhưng đó là
  raw data, KHÔNG thuộc prototype layer scope hiện tại).
- Composition: product category diversity, tenure growth.

**KHÔNG được phép làm KPI** (FR-MKT-05, CON-07):

- silhouette_score, davies_bouldin_index, calinski_harabasz_index,
  wcss, ari, ami, runtime, internal_metrics.

Validation rule (proposed):

```python
INTERNAL_METRIC_KPI_BLOCKLIST = frozenset({
    "silhouette_score", "silhouette",
    "davies_bouldin_index", "davies_bouldin",
    "calinski_harabasz_index", "calinski_harabasz",
    "wcss", "inertia",
    "ari", "adjusted_rand_index",
    "ami", "adjusted_mutual_info_score",
    "runtime", "execution_time",
})

def validate_kpi(kpi: list[str] | None) -> None:
    if kpi is None:
        return
    for k in kpi:
        if k.lower() in INTERNAL_METRIC_KPI_BLOCKLIST:
            raise MarketingValidationError(
                f"Internal clustering metric {k!r} not allowed as business KPI "
                "(FR-MKT-05, CON-07)."
            )
```

### 5.6. Xử lý missing, invalid, unsupported, incompatible inputs

| Tình huống | Behavior |
|---|---|
| `segmentation_id` không match regex `^seg_[0-9a-f]{24}$` | Fail-fast: `MarketingInputError("invalid segmentation_id")`. |
| Path đến SegmentationManifest không tồn tại | Fail-fast. |
| Manifest thiếu `research_safety` block | REJECT — DEV-07 chỉ chấp nhận `scope="PROFILED_PROTOTYPE"`. |
| `segment_id = -1` (DBSCAN noise) | SKIP entirely; count vào `n_segments_noise`. |
| `is_noise=True` không tương ứng `segment_id=-1` | REJECT (DEV-06 đã enforce; defensive). |
| Duplicate `segment_id` trong input | REJECT (`MarketingValidationError`). |
| `is_interpretation_ready = False` (CP-05 evidence) | Set `availability = NOT_AVAILABLE`; không xuất strategy. |
| `interpretation_readiness = NOT_ASSESSABLE` | Set `availability = REVIEW_REQUIRED`; vẫn show evidence refs. |
| MKT framework path không tồn tại (Phase A) | `mkt_framework_found=False`; tất cả recommendations = `REVIEW_REQUIRED`. |
| MKT framework path tồn tại nhưng malformed (Phase B) | Fail-fast với error message rõ. |

### 5.7. Output schema (proposed)

```python
@dataclass(frozen=True)
class MarketingRecommendationEntry:
    segment_id: int                  # DEV-06 segment_id (>= 0)
    cluster_label: int               # original cluster label
    availability: Literal["AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"]
    recommendation_id: str           # content-addressed
    marketing_objective: str | None
    strategy: str | None
    recommended_action: str | None
    kpi: list[str] | None
    evidence_ref: list[str]          # filesystem paths (relative)
    limitation: str | None
    limitation_note: str              # always present
    interpretation_readiness: str | None  # from CP-05 (READY/CONDITIONAL/LIMITED/NOT_ASSESSABLE) or None
    is_interpretation_ready: bool | None  # from CP-05 or None


@dataclass(frozen=True)
class MarketingRecommendationManifest:
    schema_version: str                # "1.0.0"
    marketing_id: str                 # content-addressed
    segmentation_id: str
    clustering_id: str
    preprocessed_id: str
    dataset_id: str
    availability: Literal["AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"]
    source_framework_version: str | None
    mkt_framework_found: bool
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    segmentation_manifest_sha256: str
    n_segments_input: int
    n_segments_with_recommendation: int
    n_segments_noise: int             # excluded
    n_segments_not_available: int
    noise_policy_used: str            # inherited from DEV-06 manifest
    recommendations: list[MarketingRecommendationEntry]
    environment: dict
    config_sha256: str
    research_safety: dict             # always: scope="MARKETING_PROTOTYPE", both flags False
    created_utc: str
    last_modified_utc: str
```

### 5.8. UI behavior và trạng thái hiển thị

**Phase A hiện trạng** (`renderMarketing` §1584–1613 của `index.html`)
đã đúng theo SYS-06 §9 S-13 spec. **Không cần thay đổi UI ở Phase A.**

Nếu DEV-07 Phase A được implement, có thể **mở rộng UI placeholder**
để show:

1. **Manifest metadata panel:**
   - `marketing_id`, `segmentation_id`, `clustering_id`.
   - `availability` badge (`REVIEW_REQUIRED`).
   - `mkt_framework_found = False`.
   - SHA-256 chain.
2. **Per-segment table:**
   - `segment_id`, `cluster_label`, `n_customers`, `percentage`.
   - `naming_status` (từ CP-04), `segment_name`.
   - `is_interpretation_ready` (từ CP-05).
   - `recommendation_availability` (REVIEW_REQUIRED / NOT_AVAILABLE).
3. **Empty recommendation panel:**
   - Hiển thị "PENDING_MKT_FRAMEWORK" cho mỗi field.
4. **Limitation footer:**
   - Bản hard-coded carry-over từ CP-04 §4.4 + CP-05 §10.4.
5. **Export action:**
   - Local-only (CSV + JSONL); NO `send`, `schedule`, `trigger` action.

**Phase B (sau khi MKT framework tồn tại)** — chỉ implement khi
MKT-01..MKT-05 đã approved:

- Mapping Phase B theo CP-04 §4.1–§4.3 (KHÔNG dùng "S1–S4 archetypes"
  như planning_report hiện tại vẫn còn tham chiếu — đã chỉnh ở §5.3).
- Render đầy đủ Marketing Objective, Strategy, Recommended Action, KPI,
  Evidence, Limitation per segment.
- KPI validation enforce FR-MKT-05 blocklist.

### 5.9. Export contract (Phase A: CSV + JSONL)

| Output | Schema | Path |
|---|---|---|
| `marketing_manifest.json` | `MarketingRecommendationManifest v1.0.0` | `<segmentation_dir>/marketing/<marketing_id>/marketing_manifest.json` |
| `recommendations.csv` | 1 row per recommendation, columns theo entry schema (JSON-serialize list fields). | Same dir. |
| `recommendations.jsonl` | 1 line per entry, JSON. | Same dir. |

**Không** thêm export format mới nếu không có yêu cầu contract mới.

### 5.10. Logging, error handling, validation, testability

- **Logging:** `logging_config.py` mirror pattern của
  `prototype/segmentation/logging_config.py`. Format:
  `%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s`.
- **Error handling:** explicit exception classes
  (`MarketingInputError`, `MarketingValidationError`,
  `MarketingManifestError`, `MarketingScopeError`). KHÔNG silent fail
  (AGENTS.md §2.8).
- **Validation:** Stage C trong pipeline (mirror DEV-06 segmentation
  pattern):
  - `check_segmentation_manifest_exists`
  - `check_segmentation_manifest_readable`
  - `check_schema_version_pinned`
  - `check_research_safety_block_valid`
  - `check_no_duplicate_segment_id`
  - `check_noise_segments_isolated`
  - `check_kpi_blocklist` (Phase B)
  - `check_mkt_framework_version` (Phase B)
- **Testability:** pure-function recommendation builder; filesystem
  I/O qua manifest reader; tất cả state qua dataclass.

---

## 6. Conflict / dependency register

| ID | Conflict / dependency | Nguồn | Ảnh hưởng | Phương án đề xuất |
|---|---|---|---|---|
| **CF-D07-01** | MKT-01..MKT-05 absent (verified) nhưng SYS-01 §6.7 FR-MKT-02 yêu cầu DEV-07 kế thừa từ MKT framework. | SYS-01 §6.7; SYS-01 §2.8; AGENTS.md §2.1 | DEV-07 Phase B không thể implement cho đến khi MKT framework tồn tại. | Phase A (REVIEW_REQUIRED shell) implement được ngay. Phase B blocked until MKT-01..MKT-05 created + approved. |
| **CF-D07-02** | SYS-01 §6.7 yêu cầu fields "Marketing Objective, Strategy, Recommended Action, KPI, Evidence, Limitation" — chưa rõ có khớp với MKT framework design thực tế khi MKT-01..05 được tạo. | SYS-01 §6.7; SYS-01 OQ-02 | Có thể phải adjust E-MKT fields khi MKT framework đến. | Document OQ-D07-01; Phase A dùng generic field names; Phase B re-validate khi MKT-01..05 tồn tại. |
| **CF-D07-03** | SYS-03 §15.1 E-MKT schema shell đã định nghĩa field semantics nhưng thiếu marketing-specific constraint (vd: KPI blocklist enforcement ở data layer). | SYS-03 §15.1 | DEV-07 phải enforce thêm ở application layer. | Phase A thêm `validate_kpi()` function; Phase B enforce chặt hơn. |
| **CF-D07-04** | Planning_report hiện tại tham chiếu "S1–S4 archetypes (CP-04 §5.3)" — citation sai. CP-04 §5.3 chỉ có sample names, không có archetype template S1–S4. | CP-04 §4.1–§4.4 vs §5.3 | Nếu implement theo plan hiện tại, DEV-07 sẽ có false architecture decision. | **Báo cáo này đề xuất dùng CP-04 §4.1–§4.3** (RFM tiers + behavioural modifiers + construction rules) thay cho S1–S4 archetype. Planning_report cần đính chính. |
| **CF-D07-05** | SYS-04 §15.1 nói "Prototype UI ẩn Marketing section cho đến khi MKT framework tồn tại". Nhưng SYS-06 §9 S-13 vẫn render placeholder page. | SYS-04 §15.1; SYS-06 §9 | Có thể hiểu nhầm "ẩn" = "không render". | Interpret: SYS-04 §15.1 dùng theo nghĩa "ẩn functional UI"; SYS-06 §9 cho phép render placeholder với badge REVIEW_REQUIRED. Phase A của DEV-07 giữ placeholder UI, không thay đổi behavior. |
| **CF-D07-06** | SYS-05 §15 ghi rõ API/DB là FUTURE_WORK; không có Marketing-specific API endpoint. | SYS-05 §15 | DEV-07 không tham chiếu API contract. | DEV-07 ở prototype layer dùng file-based I/O theo ADR-0005; SYS-05 chỉ là design reference cho EPIC-12. |
| **CF-D07-07** | DEV-06 plan §4.4 (hard NO marketing terms) và CP-04 §4.4 (NO "loyal", "champion", "VIP", "at-risk") — cần carry-forward vào DEV-07. | CP-04 §4.4; DEV-06 §4.4 | UI/manifest có thể vô tình xuất hiện marketing terms. | DEV-07 `validate_text_no_forbidden_tokens()` cho recommendation fields; methodology gate test (mirror CP-05 §17.2). |
| **CF-D07-08** | ADR-0006 (noise_policy default "exclude") + DEV-06 manifest default "exclude" → DEV-07 default exclude noise. | ADR-0006; DEV-06 config | DBSCAN noise KHÔNG được recommend. | DEV-07 đọc `noise_policy_used` từ DEV-06 manifest; default exclude nếu không có DEV-06 manifest. |
| **CF-D07-09** | CP-05 §11.5 cấm "priority_band" với ngữ nghĩa "nên target"; CP-05 §10.4 cấm business recommendation claim. | CP-05 §11.5, §10.4 | DEV-07 có thể vô tình tạo "priority". | DEV-07 KHÔNG compute priority; chỉ dùng `is_interpretation_ready` / `interpretation_readiness` (carry-over từ CP-05). |
| **CF-D07-10** | Boundary DEV-07 vs EPIC-12 chưa được document chính thức trong ADR. | ADR-0005 §"Scope of This Decision" | Có thể hiểu nhầm về scope. | ADR-0005 ghi rõ EPIC-12 = future production; DEV-07 = prototype. Không cần ADR mới ở planning stage. |

---

## 7. Các quyết định cần owner/mentor xác nhận

| OQ ID | Câu hỏi | Impact | Owner | Status |
|---|---|---|---|---|
| **OQ-D07-01** | MKT-01..MKT-05 scope: SYS-01 §6.7 yêu cầu 6 fields (Marketing Objective, Strategy, Recommended Action, KPI, Evidence, Limitation) — có khớp với MKT framework design thực tế không? | FR-MKT-03, FR-MKT-04; E-MKT schema | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-02** | DEV-07 nên implement Phase A (REVIEW_REQUIRED shell) trước khi MKT-01..MKT-05 tồn tại, hay đợi MKT framework xong rồi implement trực tiếp Phase B? | DEV-07 timeline | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-03** | S1–S4 archetypes có phải canonical segment archetypes cho MKT mapping không? Báo cáo này đề xuất KHÔNG dùng S1–S4 (chúng chưa từng tồn tại trong CP-04) — dùng CP-04 §4.1–§4.3 thay thế. | MKT-02/MKT-03 template matching (Phase B) | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-04** | KPI definitions trong MKT-04 nên ở đơn vị nào — survey-based (cần external data) hay transaction-based (compute từ raw data) hay composition-only? | FR-MKT-05; KPI implementation | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-05** | DEV-07 nên export ở format nào? Báo cáo này đề xuất CSV + JSONL (mirror DEV-06 pattern) — KHÔNG thêm Markdown report ở Phase A. | FR-MKT-04; export contract | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-06** | Phase A có cần mở rộng `renderMarketing()` HTML placeholder để show DEV-06 segmentation metadata + per-segment table, hay giữ placeholder hiện tại cho đến khi Phase B? | UI scope Phase A | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-07** | Có cần ADR mới (`0007-dev07-prototype-scope.md`) để document DEV-07 Phase A scope và Phase B gate, hay để ADR-0005 + planning_report đủ rồi? | Decision provenance | Mentor / human researcher | **REVIEW_REQUIRED** |
| **OQ-D07-08** | DEV-07 Phase A có nên `usage = "PROTOTYPE_VIEW_ONLY"` (read-only recommendations, no export) hay cho phép CSV + JSONL export? | Export scope | Mentor / human researcher | **REVIEW_REQUIRED** |

---

## 8. Kiến trúc đề xuất và data flow

### 8.1. Layer architecture (mirror DEV-06 pattern)

```
scripts/
└── dev07_run_marketing.py            # CLI entry point (mirror dev06_run_segmentation.py)

src/customer_segmentation/prototype/marketing/
├── __init__.py                       # Public API exports
├── scope.py                          # MarketingScope, AvailabilityStatus enums
├── manifest.py                       # MarketingRecommendationManifest dataclass + I/O
├── storage.py                        # derive_marketing_id(), resolve_marketing_path()
├── config_loader.py                  # load_dev07_config()
├── logging_config.py                 # Stage-aware logging (mirror segmentation)
├── pipeline.py                       # run_marketing_pipeline()
├── recommendation.py                 # build_recommendation() per segment
├── mkt_framework_loader.py           # load_mkt_framework() — returns None if absent
├── validation.py                     # validate_input(), validate_kpi(), validate_text()
├── display.py                        # format functions (mirror segmentation/display.py)
└── exceptions.py                     # MarketingInputError, MarketingValidationError, ...

configs/
└── dev07_marketing.yaml              # DEV-07 configuration (mirror dev06_segmentation.yaml)

tests/
├── test_dev07_manifest.py            # manifest schema tests
├── test_dev07_scope.py               # scope enum tests
├── test_dev07_storage.py             # storage / ID derivation
├── test_dev07_pipeline.py            # pipeline integration
├── test_dev07_recommendation.py      # recommendation generation
├── test_dev07_validation.py          # input validation, KPI blocklist, noise exclusion
├── test_dev07_mkt_framework.py       # MKT framework loader (absent + present)
├── test_dev07_research_safety.py     # research_safety block tests
├── test_dev07_cli.py                 # CLI tests
├── test_dev07_display.py             # format/display tests
└── test_dev07_forbidden_tokens.py    # methodology gate (mirror cp05/test methodology)
```

### 8.2. Storage path

```
<storage_root>/
└── datasets/
    └── <dataset_id>/
        └── preprocessed/
            └── <preprocessed_id>/
                └── clustering/
                    └── <clustering_id>/
                        └── segmentation/
                            └── <segmentation_id>/
                                ├── segmentation_manifest.json     # DEV-06
                                ├── segment_profiles.csv
                                ├── segment_characteristics.json
                                ├── segment_sizes_long.csv
                                └── marketing/                       ← DEV-07 NEW
                                    └── <marketing_id>/
                                        ├── marketing_manifest.json  # DEV-07
                                        ├── recommendations.csv     # DEV-07
                                        └── recommendations.jsonl   # DEV-07
```

`<storage_root>` resolved từ `configs/dev02_dataset_management.yaml`
(mirror DEV-06 pattern); KHÔNG có `--storage-root` CLI override.

### 8.3. `marketing_id` derivation (proposed, 9 canonical fields)

```python
marketing_id = "mkt_" + SHA-256(JSON canonical(
    segmentation_id,                # ^seg_[0-9a-f]{24}$
    clustering_id,                  # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    segmentation_manifest_sha256,   # SHA of the DEV-06 manifest file
    mkt_framework_version,          # null (Phase A) | "MKT-01..05__vN" (Phase B)
    mkt_framework_found,            # bool
    noise_policy_used,              # inherited from DEV-06
    schema_version,                 # MARKETING_MANIFEST_SCHEMA_VERSION
))[:24]
```

### 8.4. Data flow

```
CLI args (segmentation_id | path)
    │
    ▼
config_loader.load_dev07_config()
    │
    ▼
storage.resolve_marketing_path(segmentation_id)
    │
    ▼
manifest.read_segmentation_manifest(path)        # DEV-06 reader
    │
    ▼
validation.validate_input(manifest, config)
    │  ├─ regex check
    │  ├─ research_safety check
    │  ├─ noise segment isolation
    │  └─ duplicate check
    ▼
mkt_framework_loader.load_mkt_framework(config)
    │  └─ returns None (Phase A) | FrameworkRef (Phase B)
    ▼
recommendation.build_recommendations(manifest, mkt_framework, cp_evidence)
    │  ├─ exclude noise segments
    │  ├─ derive per-segment entry
    │  └─ validate per-entry (KPI blocklist, forbidden tokens)
    ▼
manifest.build_marketing_manifest(...)
    │
    ▼
manifest.write_marketing_manifest(path)
    │
    ▼
display.format_marketing_summary(manifest)        # optional CLI stdout
```

### 8.5. Relationship với DEV-04/05/06

- DEV-07 **read-only** DEV-06 output; KHÔNG modify DEV-06 contracts.
- DEV-07 reference DEV-06 path convention (`<clustering_id>/segmentation/
  <segmentation_id>/`); KHÔNG tạo path convention mới.
- DEV-07 reference CP-04/CP-05 outputs từ `reports/profiling/` nếu có;
  graceful degradation nếu không có.

---

## 9. Danh sách file dự kiến

### 9.1. Files cần tạo (Phase A)

| Path | Lý do |
|---|---|
| `src/customer_segmentation/prototype/marketing/__init__.py` | Public API surface. |
| `src/customer_segmentation/prototype/marketing/scope.py` | `MarketingScope` (Literal "MARKETING_PROTOTYPE" — single value), `AvailabilityStatus` enum. |
| `src/customer_segmentation/prototype/marketing/manifest.py` | `MarketingRecommendationManifest` dataclass, JSON I/O, atomic write (mirror DEV-06). |
| `src/customer_segmentation/prototype/marketing/storage.py` | `derive_marketing_id()`, `resolve_marketing_path()`, `find_existing_marketing()`. |
| `src/customer_segmentation/prototype/marketing/config_loader.py` | `load_dev07_config()`. |
| `src/customer_segmentation/prototype/marketing/logging_config.py` | Per-stage logging. |
| `src/customer_segmentation/prototype/marketing/pipeline.py` | `run_marketing_pipeline()` Stage A–H (mirror DEV-06 Stage A–H). |
| `src/customer_segmentation/prototype/marketing/recommendation.py` | `build_recommendation()` per segment. |
| `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` | `load_mkt_framework()` returns None if absent. |
| `src/customer_segmentation/prototype/marketing/validation.py` | `validate_input()`, `validate_kpi()`, `validate_text_no_forbidden_tokens()`. |
| `src/customer_segmentation/prototype/marketing/display.py` | `format_recommendation_table()`, `format_marketing_summary()`. |
| `src/customer_segmentation/prototype/marketing/exceptions.py` | `MarketingInputError`, `MarketingValidationError`, `MarketingManifestError`, `MarketingScopeError`. |
| `scripts/dev07_run_marketing.py` | CLI entry point (`profile`, `export`, `compare` subcommands). |
| `configs/dev07_marketing.yaml` | DEV-07 config (mirror `dev06_segmentation.yaml`). |
| `tests/test_dev07_*.py` (10 files, ~80–90 tests) | Mirror DEV-06 test pattern. |

### 9.2. Files KHÔNG tạo / KHÔNG sửa (Phase A)

| File / path | Lý do giữ nguyên |
|---|---|
| `docs/system/SYS-01_requirements.md` | Read-only trong task này; không tự ý sửa. |
| `docs/system/SYS-02_architecture.md` | Read-only. |
| `docs/system/SYS-03_data_model.md` | Read-only. |
| `docs/system/SYS-04_ml_processing_pipeline.md` | Read-only. |
| `docs/system/SYS-05_api_design.md` | Read-only. |
| `docs/system/SYS-06_ui_ux_design.md` | Read-only. |
| `docs/system/DEV-06_customer_segment_module.md` | Read-only. |
| `src/customer_segmentation/prototype/segmentation/**` | KHÔNG modify; DEV-07 chỉ read. |
| `src/customer_segmentation/clustering/**`, `evaluation/**`, `profiling/**` | KHÔNG modify. |
| `docs/marketing/**` | Thư mục MKT framework chưa tồn tại; KHÔNG tự tạo. |
| `pyproject.toml`, `.gitignore` | AGENTS.md §5 forbidden; KHÔNG thêm dependencies. |

### 9.3. Files được đề xuất cập nhật (ngoài scope DEV-07 implementation)

| File | Cập nhật đề xuất | Lý do |
|---|---|---|
| `docs/system/DEV-07_planning_report.md` | Đính chính §7.1 (S1–S4 archetypes → CP-04 §4.1–§4.3 construction rules); §10.4 nguồn evidence cho mapping. | Citation sai đã được verify. Planning_report cần khớp với evidence thực tế. |

Cập nhật này **ngoài scope** implementation; chỉ là đề xuất cho project
owner khi review planning_report.

---

## 10. Implementation phases và test plan

### 10.1. Phase A (implement ngay sau owner approval)

| Bước | Công việc | Ước lượng độ phức tạp |
|---|---|---|
| A.1 | Tạo `configs/dev07_marketing.yaml` (mirror `dev06_segmentation.yaml`). | Low. |
| A.2 | Tạo `src/customer_segmentation/prototype/marketing/scope.py` (enum, schema version pin). | Low. |
| A.3 | Tạo `src/customer_segmentation/prototype/marketing/exceptions.py`. | Low. |
| A.4 | Tạo `src/customer_segmentation/prototype/marketing/manifest.py` (dataclass, atomic write). | Medium. |
| A.5 | Tạo `src/customer_segmentation/prototype/marketing/storage.py` (path resolution, `marketing_id` derivation). | Medium. |
| A.6 | Tạo `src/customer_segmentation/prototype/marketing/config_loader.py`. | Low. |
| A.7 | Tạo `src/customer_segmentation/prototype/marketing/logging_config.py`. | Low. |
| A.8 | Tạo `src/customer_segmentation/prototype/marketing/mkt_framework_loader.py` (return None nếu absent). | Low. |
| A.9 | Tạo `src/customer_segmentation/prototype/marketing/validation.py` (input, KPI blocklist, forbidden tokens). | Medium. |
| A.10 | Tạo `src/customer_segmentation/prototype/marketing/recommendation.py` (per-segment builder). | Medium. |
| A.11 | Tạo `src/customer_segmentation/prototype/marketing/pipeline.py` (Stage A–H). | Medium. |
| A.12 | Tạo `src/customer_segmentation/prototype/marketing/display.py`. | Low. |
| A.13 | Tạo `src/customer_segmentation/prototype/marketing/__init__.py`. | Low. |
| A.14 | Tạo `scripts/dev07_run_marketing.py` (CLI). | Medium. |
| A.15 | Tạo tests (~80–90 tests across 10 files). | High. |
| A.16 | Validation: `pytest`, `ruff check`, `black --check`. | Low. |
| A.17 | Update `docs/system/DEV-07_planning_report.md` đính chính (nếu owner approve). | Low. |

### 10.2. Phase B (BLOCKED — chờ MKT-01..MKT-05 + owner approval)

| Bước | Công việc | Ước lượng độ phức tạp |
|---|---|---|
| B.1 | Verify MKT-01..MKT-05 tồn tại trong `docs/marketing/` (Phase B trigger). | Low. |
| B.2 | Mở rộng `mkt_framework_loader.py` để parse framework files. | Medium. |
| B.3 | Mở rộng `recommendation.py` để fill template fields theo MKT framework + CP-04 §4.1–§4.3 parsing. | High. |
| B.4 | Mở rộng `validation.py` với MKT-version-specific checks. | Medium. |
| B.5 | Mở rộng `display.py` + HTML prototype (nếu owner approve) để render full fields. | Medium. |
| B.6 | Tests cho Phase B (~30–40 extra tests). | High. |
| B.7 | ADR mới nếu cần (per `docs/decisions/README.md` immutability). | Low. |
| B.8 | Validation: `pytest`, `ruff check`, `black --check`. | Low. |

### 10.3. Test plan (Phase A)

| Category | Tests | Focus |
|---|---|---|
| Manifest schema | 8 | Required fields, JSON roundtrip, atomic write. |
| Scope enums | 4 | `MarketingScope`, `AvailabilityStatus`, `MarketingStage`. |
| Storage / ID | 5 | `derive_marketing_id`, `resolve_marketing_path`, path containment. |
| Config loader | 4 | YAML parse, schema check, default. |
| Logging | 3 | Format, level, log file. |
| MKT framework loader | 5 | Absent path (Phase A), present path (Phase B placeholder). |
| Validation | 12 | Input validation, KPI blocklist, forbidden tokens, noise exclusion, duplicate. |
| Recommendation | 10 | Per-segment builder, Phase A REVIEW_REQUIRED, Phase B AVAILABLE. |
| Pipeline | 8 | Stage A–H, full pipeline Phase A. |
| Display | 6 | Format functions. |
| Research safety | 5 | `automatically_promoted_to_research=False`, `appeared_in_research_evidence=False`, `scope="MARKETING_PROTOTYPE"`. |
| CLI | 8 | Subcommands, exit codes, error paths. |
| Methodology gate | 6 | Forbidden tokens (mirror CP-05 §17.2). |
| **Total** | **~84** | |

### 10.4. Test plan (Phase B, partial, blocked)

Phase B tests chỉ viết sau khi MKT-01..MKT-05 tồn tại. Ước lượng
30–40 tests bổ sung.

---

## 11. Acceptance Criteria có thể kiểm chứng

### 11.1. Phase A

| AC | Description | Test |
|---|---|---|
| **AC-D07-01** | Phase A implement `E-MKT shell` với `availability = REVIEW_REQUIRED` cho mọi recommendation khi MKT framework absent. | `test_recommendation_availability_review_required_when_mkt_absent` |
| **AC-D07-02** | CLI `python scripts/dev07_run_marketing.py --help` chạy được. | `test_dev07_cli_help` |
| **AC-D07-03** | CLI `python scripts/dev07_run_marketing.py profile --segmentation-id seg_xxx` chạy được và output manifest + recommendations.csv + recommendations.jsonl. | `test_dev07_cli_profile_run` |
| **AC-D07-04** | DBSCAN noise (segment_id=-1) bị exclude khỏi recommendation list; `n_segments_noise` được populate. | `test_dev07_noise_excluded`, `test_dev07_noise_count` |
| **AC-D07-05** | `noise_policy_used` được inherit từ DEV-06 manifest; default = "exclude". | `test_dev07_noise_policy_inherited` |
| **AC-D07-06** | `research_safety.scope = "MARKETING_PROTOTYPE"`, `automatically_promoted_to_research=False`, `appeared_in_research_evidence=False` luôn luôn. | `test_dev07_research_safety_block` |
| **AC-D07-07** | `marketing_id` deterministic; cùng input → cùng `marketing_id`. | `test_dev07_marketing_id_deterministic` |
| **AC-D07-08** | `marketing_manifest.json` JSON roundtrip không mất field. | `test_dev07_manifest_roundtrip` |
| **AC-D07-09** | Input validation fail-fast với error rõ ràng khi `segmentation_id` invalid / path không tồn tại / manifest malformed. | `test_dev07_validation_fail_fast` |
| **AC-D07-10** | `preprocessing_warning` KHÔNG được carry-forward từ DEV-06 manifest vào DEV-07 display trong Phase A (quyết định có chủ đích; owner-approved Option (c) per `DEV-07_owner_decision_brief.md` §3.5). Witness tests `TestPreprocessingWarningCarryOver` xác nhận Phase A không propagate field. Phase B sẽ re-evaluate khi UI mở rộng (`renderMarketing()` per SYS-06 §9 S-13). | `test_dev07_preprocessing_warning_carried` |
| **AC-D07-11** | KHÔNG có "best", "winner", "optimal", "recommended" (ngoại trừ trong field name), "final", "superior", "champion", "loyal", "VIP", "at-risk" trong output text. | `test_dev07_methodology_gate_forbidden_tokens` |
| **AC-D07-12** | KHÔNG có internal clustering metric (silhouette, DBI, CH, WCSS, ARI, AMI) trong KPI field. | `test_dev07_kpi_blocklist_enforced` |
| **AC-D07-13** | EXP-03 segments (`labels_persisted=False`) hiển thị `availability = NOT_AVAILABLE`. | `test_dev07_exp03_not_available` |
| **AC-D07-14** | `pytest tests/test_dev07_*.py` pass toàn bộ (~84 tests). | CI check. |
| **AC-D07-15** | `ruff check .` clean. | CI check. |
| **AC-D07-16** | `black --check .` clean. | CI check. |
| **AC-D07-17** | KHÔNG có dependency mới trong `pyproject.toml`. | Code review. |
| **AC-D07-18** | KHÔNG có Git operation (commit / push / PR / merge / branch). | Log audit. |
| **AC-D07-19** | KHÔNG có modification của DEV-06 / SYS-* contracts. | Code review. |
| **AC-D07-20** | `marketing_manifest.json` SHA-256 identical trước/sau re-run với cùng input. | `test_dev07_reproducibility` |

### 11.2. Phase B (PENDING — chỉ viết sau khi MKT-01..MKT-05 tồn tại)

| AC | Description |
|---|---|
| AC-D07-21 | MKT framework version được parse + populate `source_framework_version` field. |
| AC-D07-22 | Mapping logic dùng CP-04 §4.1–§4.3 (RFM tiers + behavioural modifiers + construction rules), KHÔNG hard-code "S1–S4 archetype". |
| AC-D07-23 | Recommendation `marketing_objective`, `strategy`, `recommended_action` được fill từ MKT framework templates. |
| AC-D07-24 | `kpi` được fill từ MKT-04, validate theo FR-MKT-05 blocklist. |
| AC-D07-25 | `limitation` được fill từ MKT-05 framework. |
| AC-D07-26 | HTML prototype `renderMarketing()` mở rộng để render full fields (sau owner approval). |

---

## 12. Blockers, risks và exit criteria

### 12.1. Blockers

| ID | Blocker | Impact | Unblock condition |
|---|---|---|---|
| **B-01** | MKT-01..MKT-05 chưa tồn tại trong repo. | Phase B không thể implement. | (a) MKT-01..MKT-05 được tạo trong `docs/marketing/`; (b) mentor approve framework design; (c) ADR mới (nếu cần) ghi nhận MKT adoption. |
| **B-02** | MKT framework scope chưa được confirm khớp với SYS-01 §6.7 (6 fields). | Field semantics có thể thay đổi. | OQ-D07-01 resolved. |
| **B-03** | Owner chưa quyết định DEV-07 Phase A có nên mở rộng HTML placeholder hay giữ nguyên. | UI scope Phase A. | OQ-D07-06 resolved. |
| **B-04** | Owner chưa quyết định Phase A có cho phép export hay read-only. | Export scope Phase A. | OQ-D07-08 resolved. |

### 12.2. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **R-01** | Phase A implementation bị hiểu nhầm là "Phase B" (functional recommendation). | Medium | Medium | Phase A chỉ render REVIEW_REQUIRED shell + DEV-06 metadata; không generate recommendation thực. Methodology gate test AC-D07-11. |
| **R-02** | DEV-07 accidentally promote prototype output thành research evidence. | Low | High | `research_safety` block luôn `False`/`MARKETING_PROTOTYPE`; CI check. |
| **R-03** | DBSCAN noise bị include trong recommendation. | Low | High | `validate_segment_for_marketing()` enforce `is_noise=True → skip`; CI test. |
| **R-04** | Marketing terms (champion, loyal, VIP) xuất hiện trong output. | Low | High | `validate_text_no_forbidden_tokens()`; methodology gate test AC-D07-11. |
| **R-05** | Internal clustering metric (silhouette, DBI) bị dùng làm KPI. | Low | High | `validate_kpi()` blocklist; CI test AC-D07-12. |
| **R-06** | DEV-07 accidentally modify DEV-06 contracts. | Low | High | Import blocklist (mirror DEV-06 R-DEV-06-15 pattern); code review. |
| **R-07** | MKT framework khi được tạo conflict với CP-04 §4.4 hard NO. | Medium | Medium | Phase B re-validate; nếu conflict → escalate owner (AGENTS.md §6). |
| **R-08** | Phase B yêu cầu DEV-07 Phase A API contract thay đổi. | Medium | Medium | Schema version pin `1.0.0`; backward compat qua minor version bump (mirror SYS-05 §12). |

### 12.3. Exit criteria

**Phase A READY khi:**

1. Tất cả 20 AC (AC-D07-01..20) PASS.
2. Code review confirm không có modification của DEV-06 / SYS-* / AGENTS.md
   / `.gitignore` / `pyproject.toml` / `SYS-01..06`.
3. `pytest`, `ruff check`, `black --check` clean.
4. `marketing_manifest.json` SHA-256 stable qua rerun.
5. Methodology gate test PASS (no forbidden tokens).
6. Owner review planning_report + implementation plan.

**Phase B READY khi:**

1. Phase A READY + verified.
2. MKT-01..MKT-05 tồn tại trong `docs/marketing/`.
3. OQ-D07-01..08 resolved (ngoại trừ OQ-D07-03, OQ-D07-06, OQ-D07-08 có
   thể resolve sau).
4. Owner approve Phase B implementation scope.
5. ADR mới (nếu cần) ghi nhận MKT framework adoption.
6. Phase B tests (~30–40 tests) PASS.

---

## 13. Kết luận

### 13.1. Status: **READY FOR OWNER REVIEW** (cho Phase A planning)

**Có đủ điều kiện để lập kế hoạch triển khai DEV-07 Phase A** —
input contract (DEV-06 `SegmentationManifest v1.0.0`) đã ổn định,
architecture (Option A) đã lock, tất cả 6 FR-MKT-01..06 đã được
document trong SYS-01 §6.7, E-MKT schema shell đã định nghĩa trong
SYS-03 §15.1, storage path đã chốt theo pattern của DEV-04/05/06,
methodology gates đã rõ (FR-MKT-05 KPI blocklist, FR-MKT-06 noise
exclusion, FR-SEG-08 no marketing terms).

### 13.2. Status: **BLOCKED** (cho Phase B implementation)

Phase B (recommendation generation thực sự theo MKT framework) **bị
block** bởi 4 blockers B-01..B-04 ở §12.1. Cần owner / mentor quyết
định trước.

### 13.3. Summary

| Item | Value |
|---|---|
| Files inspected | 27 source documents + 5 source files + 1 HTML prototype + 4 configs. |
| MKT-01..MKT-05 status | **ABSENT** (verified by grep + glob). |
| EPIC-12 relationship | Sequential; DEV-07 = prototype layer, EPIC-12 = production frontend (FUTURE_WORK). |
| Architecture | Option A (ADR-0005): offline, file-based, no backend/API/DB. |
| Implementation approach | Two-phase: Phase A (REVIEW_REQUIRED shell) + Phase B (full when MKT exists). |
| CRITICAL blockers | 4 (B-01..B-04). |
| Open questions | 8 (OQ-D07-01..08). |
| Discrepancies với planning_report hiện tại | 1 (CF-D07-04: S1–S4 archetypes citation). |
| Proposed files (Phase A) | 13 source + 1 config + 1 script + 10 test files (~84 tests). |
| Proposed files (Phase B) | ~30–40 extra tests; minor extensions to existing files. |
| Out-of-scope items | 23 items (mirror §13 của `DEV-07_planning_report.md`). |

### 13.4. Bước tiếp theo cần project owner xác nhận

1. **Approve / reject DEV-07 Phase A implementation scope** — đặc biệt
   là OQ-D07-06 (HTML placeholder scope) và OQ-D07-08 (export scope).
2. **Quyết định về MKT-01..MKT-05 timeline** — Phase B hoàn toàn block
   bởi điều này (OQ-D07-02 + B-01).
3. **Approve đính chính `DEV-07_planning_report.md`** §7.1 nếu muốn
   giữ consistency với báo cáo này.
4. **Approve / reject đề xuất KHÔNG tạo ADR mới `0007-dev07-prototype-scope.md`**
   ở planning stage (OQ-D07-07).
5. **Approve / reject việc tạo module `prototype/marketing/` package**
   (mirror `prototype/segmentation/` package) — đây là đề xuất chính
   của báo cáo này.

### 13.5. Hard stop gate

> **HARD STOP: KHÔNG implement code trong báo cáo này.**
>
> Báo cáo này là **planning artifact only**. Mọi hành động sau bị
> **cấm** cho đến khi owner review và explicit approval:
>
> ❌ Tạo bất kỳ file nào dưới `src/customer_segmentation/prototype/marketing/`
> ❌ Tạo `scripts/dev07_run_marketing.py`
> ❌ Tạo `configs/dev07_marketing.yaml`
> ❌ Tạo bất kỳ test file nào dưới `tests/test_dev07_*.py`
> ❌ Modify bất kỳ existing contract / source document nào
> ❌ Tạo ADR mới
> ❌ Bất kỳ Git operation nào (add / commit / push / PR / branch)
> ❌ Claim bất kỳ acceptance criteria nào complete
> ❌ Implement Phase B recommendation generation
>
> **Được phép:**
> ✅ Đọc báo cáo này
> ✅ Đề xuất thay đổi báo cáo
> ✅ Respond to owner review feedback
> ✅ Update báo cáo nếu owner yêu cầu

---

## Phụ lục A — Glossary

| Thuật ngữ | Ý nghĩa |
|---|---|
| **MKT-NN** | Marketing Recommendation framework (MKT-01..MKT-05) — **chưa tồn tại** trong repo. |
| **DEV-07** | Marketing Recommendation Module — prototype layer, thuộc EPIC-11 system design follow-up. |
| **E-MKT** | Logical entity MarketingRecommendation trong SYS-03 §15.1 (REVIEW_REQUIRED). |
| **Phase A** | DEV-07 implementation khi MKT-01..MKT-05 chưa tồn tại (REVIEW_REQUIRED shell). |
| **Phase B** | DEV-07 implementation khi MKT-01..MKT-05 đã tồn tại và được approve. |
| **REVIEW_REQUIRED** | Trạng thái yêu cầu mentor / human researcher quyết định. |
| **MARKETING_PROTOTYPE** | Scope enum value duy nhất cho DEV-07 research_safety.scope. |
| **KPI blocklist** | Closed set of internal clustering metrics KHÔNG được phép làm business KPI (FR-MKT-05, CON-07). |
| **Construction rules** | CP-04 §4.3 — quy tắc ghép `[RecencyTier] [FrequencyTier] [MonetaryTier?] [Modifier?]` để tạo segment name. **KHÔNG phải** "S1–S4 archetype template". |
| **NAMING_PENDING** | Segment có labels nhưng chưa qua CP-04 naming. |
| **Adversarial citation** | Citation tham chiếu nguồn không tồn tại (vd: "S1–S4 archetypes (CP-04 §5.3)"). Báo cáo này đính chính 1 instance. |

---

## Phụ lục B — Cross-reference: planning_report.md vs báo cáo này

| Aspect | `DEV-07_planning_report.md` (existing, untracked) | Báo cáo này |
|---|---|---|
| Scope | Phase 1 reconnaissance + planning | Phase 1 reconnaissance + planning |
| MKT absence analysis | ✅ (§4) | ✅ (§3) — same conclusion |
| Input contract | ✅ (§5.3, §6) | ✅ (§4) — verified against `manifest.py` |
| E-MKT schema | ✅ (§6.1, §6.2) | ✅ (§5.7) — same fields, same constraints |
| Two-phase approach | ✅ (§4.3) | ✅ (§5.3, §10) — same approach |
| FR-MKT-01..06 traceability | ✅ (§10.1) | ✅ (§5, §11) — same mapping |
| S1–S4 archetypes citation | **Citation sai** (§7.1, §10.4) — CP-04 §5.3 chỉ có sample names, không có archetype S1–S4. | **Đính chính** (§5.3, CF-D07-04) — dùng CP-04 §4.1–§4.3 thay thế. |
| Open questions | 5 (OQ-D07-01..05) | 8 (OQ-D07-01..08) — thêm OQ-D07-06..08. |
| Risks | 7 (R-01..07) | 8 (R-01..08) — thêm R-08 về schema version. |
| Blocker analysis | 1 (CF-D07-01) | 4 (B-01..B-04) — explicit blocker list. |
| File list | 18 files (§11.1) | 25 files (§9.1) — bao gồm exceptions.py, mkt_framework_loader.py riêng. |
| Test count | 85 (§11.2) | ~84 (§10.3) — similar size, different categorization. |
| Hard stop gate | ✅ (§15) | ✅ (§13.5) — same gate, additional notes. |

**Báo cáo này không thay thế planning_report hiện tại** mà bổ sung và
đính chính. Owner có thể:
- (a) merge nội dung báo cáo này vào planning_report hiện tại và xóa
  file này;
- (b) giữ cả 2 file, đánh dấu planning_report là cũ và báo cáo này
  là canonical;
- (c) quyết định khác.

---

*File này là DEV-07 Implementation Plan thuộc EPIC-11 system design.
KHÔNG implement code. Chờ owner review và approval trước khi triển
khai DEV-07 Phase A.*