# DEV-07 — Marketing Recommendation Module (Prototype Layer)

> **Mã task:** DEV-07
> **Tên:** Marketing Recommendation Module
> **Trạng thái:** PLAN ONLY — PHASE 1 (reconnaissance + planning; no code, no config,
> no ADR, no SYS edit, no Git op).
> **Ngày:** 2026-10-10
> **Phạm vi:** Cung cấp **prototype-layer** capability để liệt kê
> customer segments từ DEV-06 segmentation output và cung cấp
> structured Marketing Recommendation dựa trên MKT framework (hiện tại
> chưa tồn tại), theo FR-MKT-01..06.
> Output = recommendation JSON/CSV, ghi vào
> `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/segmentation/<segmentation_id>/marketing/<marketing_id>/`.
> **Architecture:** Option A (ADR-0005) — offline, single-machine,
> file-based. No backend, no API, no database, no worker, no queue.
> **Does NOT** sửa contracts của DEV-02/03/04/05/06,
> không tự tạo MKT framework, không dùng internal clustering metric
> như business effectiveness, không tự đặt "best/winner/optimal/recommended"
> claim, không promotion prototype → research evidence, không campaign
> automation.

---

## Mục lục

1. [Task scope và non-goals](#1-task-scope-v%C3%A0-non-goals)
2. [Source documents và contract references](#2-source-documents-v%C3%A0-contract-references)
3. [EPIC-12 dependency analysis](#3-epic-12-dependency-analysis)
4. [MKT-01..MKT-05 absence analysis](#4-mkt-01mkt-05-absence-analysis)
5. [Current architecture và relevant contracts](#5-current-architecture-v%C3%A0-relevant-contracts)
6. [Input/output data contract](#6-inputoutput-data-contract)
7. [Proposed recommendation framework và mapping](#7-proposed-recommendation-framework-v%C3%A0-mapping)
8. [UI behavior specification](#8-ui-behavior-specification)
9. [Handling of missing, invalid, ambiguous, unsupported evidence](#9-handling-of-missing-invalid-ambiguous-unsupported-evidence)
10. [Acceptance-criteria traceability](#10-acceptance-criteria-traceability)
11. [Proposed implementation files và tests](#11-proposed-implementation-files-v%C3%A0-tests)
12. [Conflicts, risks, dependencies, unresolved decisions](#12-conflicts-risks-dependencies-unresolved-decisions)
13. [Out-of-scope items](#13-out-of-scope-items)
14. [Validation plan và completion criteria](#14-validation-plan-v%C3%A0-completion-criteria)
15. [Explicit stop gate](#15-explicit-stop-gate)

---

## 1. Task scope và non-goals

### 1.1. Task scope (in-scope)

DEV-07 cung cấp **prototype-layer** Marketing Recommendation dựa trên
DEV-06 segmentation output:

| Deliverable | Description |
|---|---|
| MKT-01 | Segment list → recommendation mapping (per segment) |
| MKT-02 | Marketing Objective per segment (grounded in CP-04/CP-05 evidence) |
| MKT-03 | Strategy + Recommended Action (evidence-backed, not invented) |
| MKT-04 | KPI definition per recommendation (separate from clustering metrics) |
| MKT-05 | Limitation + Evidence reference per recommendation |
| E-MKT shell | `availability = REVIEW_REQUIRED` cho đến khi MKT-01..MKT-05 tồn tại |

**Note:** MKT-01..MKT-05 là các tài liệu **chưa tồn tại** trong repo.
DEV-07 implement sẽ tạo **prototype-layer framework** để kế thừa
khi MKT-01..MKT-05 được tạo, theo nguyên tắc:

- Nếu MKT-01..MKT-05 **chưa tồn tại**: DEV-07 chỉ expose
  `availability = REVIEW_REQUIRED` shell với thông tin từ DEV-06.
- Nếu MKT-01..MKT-05 **đã tồn tại**: DEV-07 implement đầy đủ
  theo MKT framework.

### 1.2. Non-goals (out-of-scope, bắt buộc)

| ❌ | Non-goal | Nguồn |
|---|---|---|
| ❌ | Tự phát minh MKT framework (strategy, KPI, action) khi MKT-01..MKT-05 chưa tồn tại | AGENTS.md §2.1; SYS-01 FR-MKT-02; SYS-01 OQ-01 |
| ❌ | Campaign automation (email / SMS / push / schedule) | SYS-01 OOS-01; FR-MKT-04 |
| ❌ | Dùng internal clustering metric (silhouette, DBI, CH, WCSS, ARI/AMI) như business effectiveness | AGENTS.md §2.5; FR-MKT-05; CON-07 |
| ❌ | Dùng DBSCAN noise (label = -1) làm segment target | AGENTS.md §2.5; FR-MKT-06; CON-08; CP-05 §12 |
| ❌ | "Best / winner / optimal / recommended / final / superior" claim | AGENTS.md §2.5; FR-EVAL-09; NFR-06 |
| ❌ | Đặt tên segment business-y ("Champions", "Loyal", "VIP", "At-Risk") | AGENTS.md §3; CP-04 §4.4 |
| ❌ | Composite score / weighted ranking / overall segment ranking | AGENTS.md §2.6; FR-EVAL-08 |
| ❌ | Build backend / API / database / worker / queue | ADR-0005 Option A |
| ❌ | Modify DEV-02 / DEV-03 / DEV-04 / DEV-05 / DEV-06 output contracts | AGENTS.md §2.2 |
| ❌ | Modify research-core profiling modules (CP-01..05) | AGENTS.md §2.4; CP-05 §2.2 |
| ❌ | Promote prototype marketing recommendation to research evidence | AGENTS.md §2.10; research_safety block |
| ❌ | Git operations (commit / push / PR / merge / branch) | AGENTS.md §2.11 |
| ❌ | Thêm dependencies mới | AGENTS.md §5 |

### 1.3. Boundary với EPIC-12

DEV-07 và EPIC-12 có mối quan hệ **sequential**:

| Concern | DEV-07 (prototype layer) | EPIC-12 (production frontend) |
|---|---|---|
| Timing | Current phase | FUTURE_WORK |
| Architecture | Option A (offline, file-based) | May add API/backend/database |
| Frontend | CLI + HTML prototype (S-13 placeholder) | React/Vue production frontend |
| MKT framework | REVIEW_REQUIRED shell | Full implementation when MKT-01..05 exist |
| Deployment | Local single-machine | Cloud/multi-service |

DEV-07 **không phải** EPIC-12. DEV-07 implement prototype-layer
Marketing Recommendation shell. EPIC-12 wire với API thật khi có.

---

## 2. Source documents và contract references

> Mỗi phát biểu trong plan trích từ doc X phải đính kèm section reference.
> Plan **không** dùng statement nào không có nguồn.

| Tài liệu | Vai trò cho DEV-07 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules (binding) | Toàn bộ (§2 principles, §3 stage guardrails, §6 escalation) |
| `docs/system/SYS-01_requirements.md` | FR-MKT-01..06; CON-12; OQ-01, OQ-02; §6.7 | §6.7 (FR-MKT), §8 (OOS-13), §13 (OQ-01, OQ-02), §2.8 (Marketing context) |
| `docs/system/SYS-03_data_model.md` | E-MKT schema shell; availability enum | §15.1 (E-MKT), §3.6 (status taxonomy) |
| `docs/system/SYS-04_ml_processing_pipeline.md` | S10 Marketing Handoff; CON-12; FR-MKT-01..06 mapping | §2.7 (S10), §5.1 (FR-MKT), §12.2 (OOS-13), §15.1 (OQ-PIPE-05) |
| `docs/system/SYS-05_api_design.md` | F-MKT endpoints; `availability` enum mapping | §G.3 (status enum), §15 (OQ-09..11) |
| `docs/system/SYS-06_ui_ux_design.md` | S-13 Marketing placeholder; §9 (S-13 spec); §2.2 OOS-UI-06; §18.3 routing | §9 (S-13), §2.2 (OOS-UI-06), §5.1 (sitemap), §10.4 (status badges), §18.3 (routing), §19 (open questions #3) |
| `docs/system/DEV-06_customer_segment_module.md` | DEV-06 plan; segmentation output contracts; pattern reference | Toàn bộ (§1.1 scope, §4 contracts, §5 module API) |
| `docs/system/DEV-06_remediation_report.md` | DEV-06 final status | Toàn bộ |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture Option A; EPIC-12 boundary | Toàn bộ |
| `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006) | Prototype-layer noise policy; scope precision | Toàn bộ |
| `docs/evaluation/CP-04.md` | Segment naming framework; NAMED/COMPARATIVE/NOISE status | §4 (naming), §5 (profiles), §6 (validation), §8 (limitations) |
| `docs/evaluation/CP-05.md` | 6 evaluation axes; `is_interpretation_ready`; `interpretation_readiness`; business relevance bounded | §5 (distinctiveness), §6 (interpretability), §10 (business relevance), §11 (final definition), §12 (DBSCAN handling), §17 (findings) |
| `docs/research/EPIC09_CP05_PLAN.md` | EPIC-09 / CP-05 plan | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/manifest.py` | DEV-06 `SegmentationManifest` schema v1.0.0 | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/scope.py` | DEV-06 `ProfiledScope`, `SegmentationStage` | Toàn bộ |
| `src/customer_segmentation/prototype/evaluation/manifest.py` | DEV-05 `EvaluationManifest` pattern reference | §1 (docstring), §manifest schema |
| `src/customer_segmentation/prototype/evaluation/compare.py` | DEV-05 comparison pattern reference | Skim pattern |
| `configs/dev06_segmentation.yaml` | DEV-06 config; research_safety pattern | Toàn bộ |
| `configs/dev05_evaluation.yaml` | DEV-05 noise_policy pattern | Skim |
| `docs/system/ui-prototype/index.html` | S-13 placeholder marketing screen | §1582-1612 (renderMarketing) |
| `docs/decisions/0003-algorithm-scope.md` (ADR-0003) | 5 algorithms only; K-Medoids OUT | Toàn bộ |
| `docs/decisions/0004-research-questions.md` (ADR-0004) | RQ1/RQ2/RQ3; internal metrics only | Toàn bộ |

---

## 3. EPIC-12 dependency analysis

### 3.1. EPIC-12 là gì

EPIC-12 là **production frontend implementation phase**, bao gồm:
- React / Vue / Svelte production frontend
- Real API call (wire to backend)
- Authentication / Authorization thật
- Production build + CI/CD
- Model registry, dataset promotion endpoints
- Full API implementation (per SYS-05)

Đây là **FUTURE_WORK** — chưa được implement, không có trong current
prototype phase.

### 3.2. DEV-07 vs EPIC-12 boundary

```
DEV-07:  Prototype-layer Marketing Recommendation
         ├─ CLI: scripts/dev07_run_marketing.py
         ├─ Module: src/customer_segmentation/prototype/marketing/
         ├─ Config: configs/dev07_marketing.yaml
         ├─ Storage: data/prototype/.../marketing/<mkt_id>/
         └─ HTML: S-13 Marketing screen (vanilla HTML prototype, #/marketing route)
              ↓
EPIC-12: Production frontend implementation
         ├─ Real API call (SYS-05 endpoints)
         ├─ Backend service
         └─ Database
```

### 3.3. DEV-07 không phụ thuộc EPIC-12

DEV-07 **hoàn toàn độc lập** với EPIC-12:
- DEV-07 chạy offline, file-based, single-machine (ADR-0005)
- DEV-07 dùng vanilla HTML prototype (`#/marketing` route)
- DEV-07 **không** gọi SYS-05 API endpoints (không có backend)
- DEV-07 output là filesystem artefacts (JSON manifests + CSV)

EPIC-12 sẽ **wire** với backend API sau. DEV-07 là bước trung gian
để:
1. Define MKT framework contract
2. Implement prototype-layer recommendation generation
3. Update HTML prototype S-13 từ placeholder → functional shell

### 3.4. Routing trong HTML prototype

HTML prototype đã có route `#/marketing` với `renderMarketing` function
(§1584-1612 của `index.html`). DEV-07 sẽ thay thế placeholder bằng
functional content khi DEV-07 được implement.

---

## 4. MKT-01..MKT-05 absence analysis

### 4.1. Xác nhận absence bằng grep

Đã verify toàn bộ `docs/` bằng `grep -r "MKT-0[1-5]"` — **không có
kết quả nào** ngoài các reference đến absence status.

### 4.2. Impact của absence

| Trạng thái | Impact trên DEV-07 |
|---|---|
| MKT-01..MKT-05 absent | FR-MKT-01: UI phải hiển thị `REVIEW_REQUIRED` message |
| No marketing framework | FR-MKT-02: DEV-07 không tự phát minh framework |
| No strategy/action/KPI template | FR-MKT-03: DEV-07 implement shell với placeholder fields |
| No business KPI definition | FR-MKT-05: DEV-07 không dùng silhouette/DBI/CH/WCSS |

### 4.3. Two-phase approach

Do MKT-01..MKT-05 chưa tồn tại, DEV-07 sẽ implement theo 2 phase:

**Phase A (immediate — khi MKT-01..MKT-05 absent):**
- DEV-07 implement **E-MKT shell** với `availability = REVIEW_REQUIRED`
- Tất cả recommendation fields = `null` hoặc `"PENDING_MKT_FRAMEWORK"`
- S-13 HTML placeholder update thành structured shell
- CLI + module tồn tại nhưng không generate recommendation thực
- Ghi log rõ: "Marketing framework not found — recommendations not generated"

**Phase B (sau khi MKT-01..MKT-05 được tạo):**
- DEV-07 mở rộng để đọc MKT framework
- Implement MKT-01..MKT-05 contracts đầy đủ
- Recommendation generation thực sự
- Phase B requires: (a) MKT-01..MKT-05 tồn tại, (b) human approval

### 4.4. Khi nào DEV-07 implement Phase B?

DEV-07 Phase B chỉ được implement khi **tất cả** conditions sau đạt:
1. MKT-01..MKT-05 tồn tại trong `docs/marketing/` hoặc tương đương
2. Human researcher approve MKT framework scope
3. DEV-07 Phase A đã verified (tests pass, lint clean)
4. ADR mới ghi nhận MKT framework adoption (nếu cần)

---

## 5. Current architecture và relevant contracts

### 5.1. Existing prototype layer structure

```
src/customer_segmentation/prototype/
├── clustering/          # DEV-04: clustering execution
│   ├── manifest.py      # ClusteringManifest v1.0.0
│   ├── scope.py         # AlgorithmScope
│   ├── storage.py       # derive_clustering_id, run dir resolution
│   ├── pipeline.py      # run_clustering_pipeline()
│   ├── config_loader.py
│   ├── logging_config.py
│   └── __init__.py
├── evaluation/          # DEV-05: evaluation
│   ├── manifest.py       # EvaluationManifest v1.0.0
│   ├── scope.py         # MetricScope
│   ├── storage.py       # derive_evaluation_id
│   ├── pipeline.py      # run_evaluation_pipeline()
│   ├── metrics.py       # metric computation
│   ├── compare.py       # compare_evaluations()
│   ├── display.py       # format functions
│   ├── config_loader.py
│   ├── logging_config.py
│   └── __init__.py
├── segmentation/        # DEV-06: customer profiling (prototype layer)
│   ├── manifest.py      # SegmentationManifest v1.0.0
│   ├── scope.py        # ProfiledScope
│   ├── storage.py      # derive_segmentation_id
│   ├── pipeline.py     # run_segmentation_pipeline()
│   ├── profile.py      # segment list + sizes
│   ├── characteristics.py  # characteristic derivation
│   ├── compare.py      # compare_segmentations()
│   ├── display.py      # format functions
│   ├── config_loader.py
│   ├── logging_config.py
│   ├── validation.py
│   └── __init__.py
└── [NEW] marketing/    # DEV-07: marketing recommendation
    ├── manifest.py     # MarketingRecommendationManifest v1.0.0
    ├── scope.py        # MarketingScope, RecommendationStatus
    ├── storage.py      # derive_marketing_id
    ├── pipeline.py     # run_marketing_pipeline()
    ├── recommendation.py # recommendation generation
    ├── mapping.py      # segment → recommendation mapping
    ├── display.py      # format functions
    ├── config_loader.py
    ├── logging_config.py
    ├── validation.py
    └── __init__.py
```

### 5.2. Storage path hierarchy

```
data/prototype/
└── datasets/
    └── <dataset_id>/
        └── preprocessed/
            └── <preprocessed_id>/
                └── clustering/
                    └── <clustering_id>/
                        ├── clustering_manifest.json       (DEV-04)
                        ├── cluster_labels_*.parquet
                        └── evaluation/
                            └── <evaluation_id>/
                                └── evaluation_manifest.json  (DEV-05)
                        └── segmentation/
                            └── <segmentation_id>/
                                ├── segmentation_manifest.json  (DEV-06)
                                ├── segment_profiles.csv
                                ├── segment_characteristics.json
                                └── segment_sizes_long.csv
                                └── marketing/               ← DEV-07 NEW
                                    └── <marketing_id>/
                                        ├── marketing_manifest.json  (DEV-07)
                                        ├── recommendations.csv
                                        └── recommendations.json
```

### 5.3. Input contracts (read-only)

| Input | Source | Schema |
|---|---|---|
| `segmentation_manifest.json` | DEV-06 output | `SegmentationManifest v1.0.0` (src/prototype/segmentation/manifest.py) |
| `segment_profiles.csv` | DEV-06 output | per-segment × per-feature statistics |
| `segment_characteristics.json` | DEV-06 output | per-segment characteristics |
| `segment_sizes_long.csv` | DEV-06 output | segment_id, count, pct, is_noise |
| `clustering_manifest.json` | DEV-04 output | `ClusteringManifest v1.0.0` |
| `evaluation_manifest.json` | DEV-05 output (optional) | `EvaluationManifest v1.0.0` |
| MKT-01..MKT-05 framework | `docs/marketing/` (when exist) | TBD |

### 5.4. Output contracts

| Output | Schema |
|---|---|
| `marketing_manifest.json` | `MarketingRecommendationManifest v1.0.0` |
| `recommendations.csv` | per-recommendation flat table |
| `recommendations.json` | nested per-segment recommendation |
| Per-segment log files | `marketing_<segment_id>.log` |

---

## 6. Input/output data contract

### 6.1. MarketingRecommendationManifest schema (proposed)

```python
@dataclass
class MarketingRecommendationManifest:
    # --- Identity ---
    marketing_id: str                        # content-addressed from 8 fields
    segmentation_id: str                     # DEV-06 source
    clustering_id: str                       # DEV-04 source
    preprocessed_id: str                     # DEV-03 source
    dataset_id: str                          # DEV-02 source

    # --- MKT Framework ---
    availability: Literal["AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"]
    source_framework_version: str | None     # e.g. "MKT-01..MKT-05__v1" or null
    mkt_framework_found: bool               # True if MKT-01..MKT-05 exists

    # --- Provenance ---
    ml_dataset_sha256: str                  # canonical (from clustering manifest)
    feature_set_sha256: str                  # canonical
    preprocessing_config_sha256: str         # canonical
    segmentation_manifest_sha256: str         # DEV-06 manifest SHA
    segmentation_id: str                     # alias for readability

    # --- Segment coverage ---
    n_segments_input: int                   # from segmentation manifest
    n_segments_with_recommendation: int     # count non-null recommendations
    n_segments_noise: int                   # DBSCAN noise segments (excluded)
    n_segments_not_available: int           # segments with availability = NOT_AVAILABLE

    # --- Recommendations ---
    recommendations: list[RecommendationEntry]

    # --- Config ---
    noise_policy_used: str                  # "exclude" | "include" | "n/a"
    config_sha256: str

    # --- Environment ---
    environment: EnvironmentBlock           # python_version, platform, etc.

    # --- Research safety ---
    research_safety: ResearchSafetyBlock    # always: automatically_promoted_to_research=false, scope="MARKETING_PROTOTYPE", appeared_in_research_evidence=false

    # --- Manifest ---
    schema_version: str = "1.0.0"
    created_utc: str
    last_modified_utc: str


@dataclass
class RecommendationEntry:
    segment_id: str                         # from segmentation manifest
    cluster_label: int                      # original cluster label from clustering
    is_noise: bool                          # must be False (noise excluded)
    availability: Literal["AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"]
    marketing_objective: str | None           # from MKT-01..MKT-05 or null
    strategy: str | None                     # from MKT framework or null
    recommended_action: str | None          # from MKT framework or null
    kpi: list[str] | None                   # from MKT framework or null
    evidence_ref: list[str] | None          # references to CP-04/CP-05 evidence
    limitation: str | None                  # from MKT framework or null
    interpretation_readiness: str | None     # from CP-05: READY/CONDITIONAL/LIMITED/NOT_ASSESSABLE
    is_interpretation_ready: bool | None     # from CP-05: True/False/None
    limitation_note: str                     # always: why recommendation is/isn't generated
```

### 6.2. E-MKT schema alignment

Proposed schema trên tuân thủ SYS-03 §15.1 E-MKT:

| E-MKT field (SYS-03) | DEV-07 field mapping | Status |
|---|---|---|
| `recommendation_id` | `marketing_id` | ✅ canonical |
| `segment_id` | `RecommendationEntry.segment_id` | ✅ FK to E-SEG |
| `availability` | `availability` (top-level + per-entry) | ✅ |
| `marketing_objective` | `marketing_objective` | ✅ Conditional |
| `strategy` | `strategy` | ✅ Conditional |
| `recommended_action` | `recommended_action` | ✅ Conditional |
| `kpi` | `kpi` | ✅ list[str] |
| `evidence_ref` | `evidence_ref` | ✅ FK to E-SPR |
| `limitation` | `limitation` | ✅ Conditional |
| `source_framework_version` | `source_framework_version` | ✅ |
| `computed_at_utc` | `created_utc` | ✅ |
| `notes` | (merged into limitation_note) | ✅ |

### 6.3. Research safety block (always)

```python
@dataclass
class ResearchSafetyBlock:
    automatically_promoted_to_research: bool = False   # ALWAYS False
    appeared_in_research_evidence: bool = False          # ALWAYS False
    scope: str = "MARKETING_PROTOTYPE"                # ALWAYS this value
    disclaimer: str = (
        "no ranking, recommendation, or winner annotation is emitted; "
        "descriptive recommendation only; "
        "not research evidence; not campaign automation"
    )
```

---

## 7. Proposed recommendation framework và mapping

### 7.1. CP-04 naming framework as templates

CP-04 §4.1 định nghĩa 3 RFM core tier groups (Recency × Frequency × Monetary):

| Tier group | Tiers | Rule (direction so với dataset median) |
|---|---|---|
| Recency | `Recent` / `Older` / `Mixed` | direction ∈ {LOWER, HIGHER, COMPARABLE/NA} |
| Frequency | `Frequent` / `Occasional` / `Mixed` | direction ∈ {HIGHER, LOWER, COMPARABLE/NA} |
| Monetary | `HighValue` / `LowValue` / `Mixed` | direction ∈ {HIGHER, LOWER, COMPARABLE/NA} |

CP-04 §4.2 định nghĩa 4 behavioural modifiers (áp dụng khi
feature direction = HIGHER VÀ classification = HIGH_DIFFERENCE_OBSERVED
theo CP-03):

| Modifier | Rule | Interpretation |
|---|---|---|
| `LongTenured` | TenureDays HIGHER + HIGH | Quan hệ dài hơn |
| `IrregularCadence` | PurchaseIntervalStd HIGHER + HIGH | Cadence biến động lớn |
| `Bulk` | TotalQuantity HIGHER + Monetary HIGHER (cả hai HIGH) | Nhiều items + giá trị cao mỗi invoice |
| `Active` | ActiveDays HIGHER + HIGH + Frequency direction ≠ ActiveDays direction | Calendar-level activity độc lập |

CP-04 §4.3 định nghĩa construction rules để ghép segment name từ
RFM tiers + behavioural modifiers (tổng số từ ≤ 4; nếu không thỏa
điều kiện nào → "Comparative Segment A/B/C" + rationale).

**Hard constraint:** CP-04 segment names được cấu trúc theo §4.1 +
§4.2 + §4.3, **không phải** archetype cố định. CP-04 §4.4 cấm
marketing terms ("loyal", "champion", "VIP", "at-risk") trong segment
name. DEV-07 **không được** hard-code mapping từ segment name → MKT
template; Phase B mapping dựa trên parsing `[RecencyTier]
[FrequencyTier] [MonetaryTier?] [Modifier?]` của CP-04 §4.3.

**Lưu ý quan trọng về citation:** Bản gốc của planning_report này từng
tham chiếu "S1–S4 archetypes (CP-04 §5.3)". Citation này **không
chính xác** — CP-04 §5.3 chỉ chứa sample segment names (concrete
examples như "Recent Frequent HighValue LongTenured", "Older
Occasional"), không phải archetype templates. Phần có cấu trúc
template-like thực sự nằm ở §4.1–§4.3 như trình bày ở trên.
Đính chính đã được thực hiện (xem commit message khi planning_report
được owner commit).

### 7.2. Mapping flow

```
DEV-06 SegmentationManifest
  ├─ segments: list[SegmentSummary]
  │    ├─ segment_id
  │    ├─ cluster_label
  │    ├─ is_noise (MUST be False for MKT)
  │    ├─ naming_status (NAMED/COMPARATIVE/NOISE)
  │    └─ segment_name (from CP-04)
  │
  ├─ Read MKT framework (if exists)
  │    ├─ MKT-01: framework definition
  │    ├─ MKT-02: objective templates
  │    ├─ MKT-03: strategy + action templates
  │    ├─ MKT-04: KPI definitions
  │    └─ MKT-05: limitation framework
  │
  └─ DEV-07 Mapper
       ├─ Validate: is_noise == False (or skip)
       ├─ Validate: segment in supported segment list
       ├─ Map: CP-04 segment_name → MKT template (if MKT framework exists)
       │    (parse [RecencyTier] [FrequencyTier] [MonetaryTier?] [Modifier?]
       │     per CP-04 §4.3; no hard-coded archetype table)
       ├─ Fill: objective, strategy, action, KPI, evidence, limitation
       │    (from MKT framework OR REVIEW_REQUIRED placeholder)
       └─ Output: RecommendationEntry per segment
```

### 7.3. MKT framework contract (proposed, to be defined in MKT-01..MKT-05)

Khi MKT-01..MKT-05 được implement, chúng cần định nghĩa:

| MKT doc | Content needed for DEV-07 |
|---|---|
| MKT-01 | Framework overview: objectives, KPI types, evidence requirements |
| MKT-02 | Marketing Objective templates per CP-04 §4.3 tokenization (RFM tiers + behavioural modifiers, including COMPARATIVE fallback) |
| MKT-03 | Strategy + Recommended Action templates per archetype |
| MKT-04 | KPI definitions per strategy (measurable, not clustering metrics) |
| MKT-05 | Limitation framework: what cannot be claimed, evidence requirements |

**DEV-07 implement Phase A (MKT absent):**
- Tất cả template fields = `"PENDING_MKT_FRAMEWORK"`
- `availability = REVIEW_REQUIRED` cho toàn bộ recommendations
- Ghi rõ limitation: "Marketing framework MKT-01..MKT-05 not found"

**DEV-07 implement Phase B (MKT exists):**
- DEV-07 đọc MKT-01..MKT-05 từ `docs/marketing/` hoặc tương đương
- Map segment → template theo archetype matching
- Fill recommendation fields

### 7.4. Evidence grounding

Mỗi recommendation phải có `evidence_ref` trỏ đến CP-04/CP-05
evidence:

| Evidence source | What to reference |
|---|---|
| CP-04 segment naming | `segment_name`, `naming_status`, `naming_rationale` |
| CP-05 interpretability | `interpretability_status`, `interpretability_note` |
| CP-05 business relevance | `business_relevance_status`, `business_interpretation_text` |
| CP-05 consistency | `consistency_status`, `consistency_note` |
| CP-05 size | `size_band`, `n_customers`, `statistical_reliability_flag` |

**Constraint:** `evidence_ref` phải reference **filesystem path** đến
CP-04/CP-05 artifacts, không phải internal metric value.

### 7.5. KPI separation from clustering metrics

FR-MKT-05 cấm dùng internal clustering metric làm business KPI.
DEV-07 cần rõ ràng:

| ✅ Allowed KPI (MKT-04 framework) | ❌ NOT allowed (internal clustering metric) |
|---|---|
| Customer retention rate (survey-based) | Silhouette Score |
| Average order value (from transaction data) | Davies-Bouldin Index |
| Repeat purchase frequency (from transaction data) | Calinski-Harabasz Index |
| Product category diversity | WCSS |
| Customer tenure growth | ARI / AMI |
| Response rate (if campaign exists) | Runtime |

**Note:** KPI definitions chỉ có thể được implement đầy đủ khi
MKT-04 tồn tại. Phase A: KPI = `null`.

---

## 8. UI behavior specification

### 8.1. S-13 Marketing screen (SYS-06 §9)

#### 8.1.1. Phase A (MKT-01..MKT-05 absent)

```
┌─────────────────────────────────────────────────────────┐
│ [REVIEW_REQUIRED badge]                                 │
│                                                          │
│ Marketing Recommendation                                 │
│                                                          │
│ Marketing framework pending                               │
│                                                          │
│ MKT-01..MKT-05 not found in repository.                │
│ Recommendations cannot be generated until the            │
│ Marketing framework is implemented.                      │
│                                                          │
│ [Available segments: N]                                 │
│ [Noise segments excluded: N]                            │
│ [Recommendations pending: N]                             │
│                                                          │
│ Limitations:                                            │
│ • Marketing framework (MKT-01..MKT-05) does not exist   │
│ • No strategy, action, KPI, or objective is generated   │
│ • DBSCAN noise (label=-1) is excluded from segments     │
│ • Internal clustering metrics are not used as KPIs       │
│ • This module does not perform campaign automation      │
└─────────────────────────────────────────────────────────┘
```

#### 8.1.2. Phase B (MKT-01..MKT-05 exists)

```
┌─────────────────────────────────────────────────────────┐
│ [Marketing Recommendation]                              │
│                                                          │
│ Segment selector: [dropdown: all named segments]        │
│ Filter: [All] [NAMED RFM tier combinations] [COMPARATIVE]│
│                                                          │
│ ┌─ Segment: Recent Frequent HighValue LongTenured ─────┐ │
│ │ CP-04 tokenization: Recent + Frequent + HighValue + │
│ │   LongTenured (per CP-04 §4.1–§4.3)                 │ │
│ │ Cluster size: 555 (12.7%)                           │ │
│ │ Interpretation readiness: CONDITIONAL                 │ │
│ │                                                      │ │
│ │ Marketing Objective:                                  │ │
│ │   "Retain recently active, high-value customers..."  │ │
│ │   [Source: MKT-02 / CP-04 §4.3 tokenization]        │ │
│ │                                                      │ │
│ │ Strategy:                                            │ │
│ │   "Priority engagement with personalized offers..."   │ │
│ │   [Source: MKT-03 / matching CP-04 tokenization]    │ │
│ │                                                      │ │
│ │ Recommended Action:                                  │ │
│ │   "Launch loyalty program targeting this cohort..."  │ │
│ │   [Source: MKT-03 / matching CP-04 tokenization]    │ │
│ │                                                      │ │
│ │ KPI:                                                  │ │
│ │   • Repeat purchase rate within 90 days              │ │
│ │   • Average order value vs baseline                  │ │
│ │   • Program enrollment rate                           │ │
│ │   [Source: MKT-04 / matching KPI template]           │ │
│ │                                                      │ │
│ │ Evidence:                                            │ │
│ │   • CP-04 segment profile (segment_profiles.csv)     │ │
│ │   • CP-05 interpretability: PARTIALLY_INTERPRETABLE  │ │
│ │   • CP-05 business relevance: SUPPORTED               │ │
│ │   • CP-05 consistency: CONSISTENT                     │ │
│ │                                                      │ │
│ │ Limitation:                                           │ │
│ │   "Recommendation is based on observed RFM behavior;  │ │
│ │    does not account for unobserved factors..."       │ │
│ │   [Source: MKT-05 / limitation framework]            │ │
│ │                                                      │ │
│ │ [Export] [View evidence]                              │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ [Export all recommendations]                             │
│ [Disclaimer: no ranking/recommendation/winner annotation] │
└─────────────────────────────────────────────────────────┘
```

### 8.2. Segment selector behavior

| Condition | Behavior |
|---|---|
| No segmentation run | Show "No segmentation available — run segmentation first" |
| DBSCAN noise segments | Excluded from selector (FR-MKT-06) |
| COMPARATIVE segments | Shown with warning that strategy mapping may be approximate |
| EXP-03 NOT_AVAILABLE segments | Shown as disabled with note |
| Segment with `is_interpretation_ready=False` | Shown with amber warning |

### 8.3. Objective, Strategy, Action, KPI, Evidence, Limitation fields

Each field follows this pattern:

| Field | Source | Fallback (MKT absent) |
|---|---|---|
| Marketing Objective | MKT-02 template | `"PENDING_MKT_FRAMEWORK"` |
| Strategy | MKT-03 template | `"PENDING_MKT_FRAMEWORK"` |
| Recommended Action | MKT-03 template | `"PENDING_MKT_FRAMEWORK"` |
| KPI | MKT-04 template | `null` (no KPI generated) |
| Evidence | CP-04/CP-05 filesystem paths | Auto-populated from DEV-06 output |
| Limitation | MKT-05 framework | `"Marketing framework not implemented"` |

### 8.4. KPI display (FR-MKT-05 enforcement)

WCSS / silhouette / DBI / CH / ARI / AMI **không bao giờ** xuất hiện
trong KPI section. UI kiểm tra:

```
IF kpi_value IN {silhouette_score, davies_bouldin_index,
                  calinski_harabasz_index, wcss, ari, ami}:
    DISPLAY ERROR "Internal clustering metric not allowed as KPI"
    DO NOT DISPLAY value
```

---

## 9. Handling of missing, invalid, ambiguous, unsupported evidence

### 9.1. Missing segment profile

| Scenario | Behavior |
|---|---|
| Segment not in DEV-06 output | `availability = NOT_AVAILABLE`; `limitation_note = "Segment not found in segmentation output"` |
| Segment `is_noise = True` | Skip entirely; count in `n_segments_noise` |
| No CP-04 naming evidence | `availability = NOT_AVAILABLE`; `limitation_note = "CP-04 naming not available"` |
| No CP-05 evaluation | `availability = REVIEW_REQUIRED`; fill available evidence only |

### 9.2. Invalid segment evidence

| Scenario | Behavior |
|---|---|
| Segment `is_noise = True` but somehow included | REJECT; log error; skip segment |
| Cluster label = -1 (noise) | REJECT; log error; skip segment |
| CustomerID leakage in feature | REJECT; log error; abort |
| Duplicate segment_id | REJECT; raise `MarketingRecommendationError` |

### 9.3. Ambiguous archetype mapping

| Scenario | Behavior |
|---|---|
| Segment name matches multiple CP-04 §4.3 tokenizations | `strategy = "AMBIGUOUS_MAPPING"`; list all matching token combinations |
| Segment is COMPARATIVE (CP-04 §4.3 fallback, không match RFM tier pattern) | Use COMPARATIVE template if available; else `REVIEW_REQUIRED` |
| Segment has no behavioral modifier | Use base CP-04 §4.3 tokenization (RFM tiers only, modifier optional) |

### 9.4. Unsupported profile evidence

| Scenario | Behavior |
|---|---|
| CP-05 `is_interpretation_ready = False` | `availability = NOT_AVAILABLE`; `limitation_note` references reason |
| CP-05 `interpretation_readiness = NOT_ASSESSABLE` | Show with amber warning; `availability = REVIEW_REQUIRED` |
| DBSCAN `K_realized ≠ requested K` | Include segment; add limitation note about DBSCAN variability |
| EXP-03 segment (`labels_persisted = False`) | `availability = NOT_AVAILABLE`; `limitation_note = "EXP-03 labels not persisted"` |

### 9.5. DBSCAN noise handling (FR-MKT-06, CON-08, CP-05 §12)

```python
def validate_segment_for_marketing(segment: SegmentSummary) -> ValidationResult:
    if segment.is_noise:
        return ValidationResult(
            valid=False,
            reason="DBSCAN noise (label=-1) is not a customer segment",
            action="skip"
        )
    if segment.cluster_label == -1:
        return ValidationResult(
            valid=False,
            reason="Cluster label -1 reserved for DBSCAN noise",
            action="skip"
        )
    return ValidationResult(valid=True, reason=None, action=None)
```

All noise segments are:
1. **Excluded** from recommendation list
2. **Counted** in `n_segments_noise` in manifest
3. **Never mapped** to recommendation
4. **Logged** with reason

---

## 10. Acceptance-criteria traceability

### 10.1. FR-MKT traceability

| AC | Description | DEV-07 implementation | Test |
|---|---|---|---|
| FR-MKT-01 | REVIEW_REQUIRED gate: only show when MKT-01..MKT-05 exists | `mkt_framework_found` flag; `availability` enum; Phase A = REVIEW_REQUIRED | `test_mkt_framework_detection_absent`, `test_availability_review_required` |
| FR-MKT-02 | Inherit from MKT-01..MKT-05, don't invent | Template loading from `docs/marketing/`; Phase A = no generation | `test_no_invented_framework`, `test_template_loading` |
| FR-MKT-03 | Full fields: objective, strategy, action, KPI, evidence, limitation | `RecommendationEntry` dataclass with all 7 fields | `test_recommendation_entry_complete`, `test_evidence_refs` |
| FR-MKT-04 | No campaign automation (view/export only) | No "send", "schedule", "trigger" actions in CLI or UI | `test_no_campaign_actions` |
| FR-MKT-05 | No internal clustering metric as KPI | KPI validation; explicit allowlist | `test_kpi_no_clustering_metric`, `test_kpi_validation` |
| FR-MKT-06 | No DBSCAN noise (label=-1) as segment | Noise validation + exclusion | `test_noise_excluded`, `test_noise_count_in_manifest` |

### 10.2. Additional acceptance criteria

| AC | Description | Implementation | Test |
|---|---|---|---|
| AC-MKT-07 | Segment list from DEV-06 segmentation output | Read `segmentation_manifest.json` | `test_read_segmentation_manifest` |
| AC-MKT-08 | Recommendation output in filesystem artefacts | JSON + CSV in storage path | `test_recommendation_output_format` |
| AC-MKT-09 | Manifest includes provenance chain | `ml_dataset_sha256`, `segmentation_id`, `clustering_id` | `test_provenance_chain` |
| AC-MKT-10 | Research safety block always false | `automatically_promoted_to_research=False` | `test_research_safety_block` |
| AC-MKT-11 | DBSCAN noise count reported | `n_segments_noise` in manifest | `test_noise_count_report` |
| AC-MKT-12 | HTML prototype S-13 updated | Replace placeholder with functional shell | Manual verification |
| AC-MKT-13 | CLI sub-commands | `profile`, `export`, `compare` | `test_dev07_cli` |

### 10.3. Research constraints traceability

| Constraint | Source | DEV-07 enforcement |
|---|---|---|
| CON-07 (internal metrics only) | AGENTS.md §2.5; ADR-0004 | KPI validation; explicit blocklist |
| CON-08 (DBSCAN noise not segment) | CP-01 §4.4; CP-05 §12 | Noise validation + skip |
| CON-09 (no cross-algorithm mapping) | CP-05 §14 | DEV-07 only reads single segmentation |
| CON-12 (Marketing inherits MKT) | SYS-01 §2.8; FR-MKT-02 | No framework invention |
| CON-13 (no commit/push/PR) | AGENTS.md §2.11 | No Git actions in CLI |
| CON-16 (status taxonomy) | CP-01 §3.3 | NAMED/COMPARATIVE/NOISE/NOT_AVAILABLE |

---

## 11. Proposed implementation files và tests

### 11.1. Files to create

```
src/customer_segmentation/prototype/marketing/
├── __init__.py                    # public API exports
├── scope.py                       # MarketingScope, AvailabilityStatus, RecommendationStatus enums
├── manifest.py                    # MarketingRecommendationManifest, RecommendationEntry, ResearchSafetyBlock
├── storage.py                    # derive_marketing_id(), marketing_run_dir(), storage_root resolution
├── config_loader.py              # load_dev07_config()
├── logging_config.py             # stage-aware logging (SegmentationStage-like)
├── pipeline.py                    # run_marketing_pipeline()
├── recommendation.py             # generate_recommendation(), parse_cp04_segment_name()
├── mapping.py                    # cp04_tokenization(), CP-04 §4.3 mapping resolution
├── validation.py                 # validate_segment_for_marketing(), validate_kpi()
├── display.py                    # format_recommendation_table(), format_marketing_summary()
├── mkt_framework_loader.py        # load_mkt_framework() — returns None if absent
└── __init__.py

scripts/
└── dev07_run_marketing.py        # CLI entry point: profile, export, compare

configs/
└── dev07_marketing.yaml         # DEV-07 configuration

tests/
├── test_dev07_manifest.py       # manifest schema tests
├── test_dev07_scope.py          # scope enum tests
├── test_dev07_storage.py        # storage / ID derivation tests
├── test_dev07_pipeline.py       # pipeline integration tests
├── test_dev07_recommendation.py # recommendation generation tests
├── test_dev07_mapping.py        # archetype mapping tests
├── test_dev07_validation.py     # validation tests (noise, KPI)
├── test_dev07_display.py       # format/display tests
├── test_dev07_mkt_framework.py  # MKT framework loading tests (absent + present)
├── test_dev07_research_safety.py # research safety block tests
├── test_dev07_cli.py            # CLI tests
└── test_dev07_compare.py        # compare recommendations tests

docs/system/
└── DEV-07_planning_report.md    # this file
```

### 11.2. Test matrix

| Category | Tests | Focus |
|---|---|---|
| Manifest schema | 8 | Required fields, JSON roundtrip, atomic write |
| Scope enums | 6 | AvailabilityStatus, RecommendationStatus, MarketingScope |
| Storage / ID | 5 | derive_marketing_id, directory creation, path resolution |
| Pipeline | 6 | Full pipeline, MKT absent path, MKT present path |
| Recommendation | 10 | Per-segment, evidence grounding, limitation |
| Mapping | 8 | CP-04 §4.3 tokenization, COMPARATIVE, ambiguous, no-match |
| Validation | 10 | Noise exclusion, KPI blocklist, duplicate segment |
| Display | 6 | Table format, summary format, disclaimer |
| MKT framework | 8 | Absent (Phase A), present (Phase B), invalid framework |
| Research safety | 5 | always_false flags, disclaimer presence |
| CLI | 8 | profile, export, compare subcommands |
| Compare | 5 | cross-segmentation recommendations |
| **Total** | **85** | |

---

## 12. Conflicts, risks, dependencies, unresolved decisions

### 12.1. Confirmed conflicts (HARD STOP)

> **Conflict #1 (CRITICAL):** MKT-01..MKT-05 chưa tồn tại trong repository,
> nhưng FR-MKT-02 yêu cầu DEV-07 kế thừa từ MKT framework.
> AGENTS.md §2.1 cấm tự phát minh framework.
> **→ Dừng tại planning stage. Không implement Phase B cho đến khi
> MKT-01..MKT-05 được tạo.**

| Conflict | Reference | Resolution approach |
|---|---|---|
| CF-D07-01: MKT-01..MKT-05 absent, FR-MKT-02 requires inheritance | SYS-01 §6.7; SYS-01 OQ-01; AGENTS.md §2.1 | DEV-07 Phase A implement REVIEW_REQUIRED shell; Phase B blocked until MKT-01..MKT-05 exists |
| CF-D07-02: SYS-01 brief §6.7 requires "objective, strategy, action, KPI, evidence, limitation" — unclear if this matches MKT-01..MKT-05 structure | SYS-01 §6.7; SYS-01 OQ-02 | Document as open question OQ-D07-01; Phase A uses generic field names |
| CF-D07-03: E-MKT schema (SYS-03 §15.1) is a shell — field semantics when MKT absent unclear | SYS-03 §15.1 | DEV-07 adds `mkt_framework_found` + `limitation_note` for clarity |

### 12.2. Open questions cần human decision

| OQ ID | Question | Impact | Trạng thái |
|---|---|---|---|
| **OQ-D07-01** | MKT-01..MKT-05 scope: SYS-01 brief §6.7 yêu cầu 6 fields — có khớp với actual MKT framework design không? | FR-MKT-03, FR-MKT-04 | REVIEW_REQUIRED — cần human researcher quyết định MKT framework design trước Phase B |
| **OQ-D07-02** | DEV-07 nên implement Phase A (shell) trước khi MKT-01..MKT-05 tồn tại, hay đợi MKT framework xong rồi implement trực tiếp Phase B? | DEV-07 timeline | REVIEW_REQUIRED — cần human researcher decision |
| **OQ-D07-03** | CP-04 §4.3 construction rules có phải là canonical tokenization để map CP-04 segment_name → MKT template không, hay cần thêm category khác (vd: business-only categories từ MKT framework)? | MKT-02/MKT-03 template matching | REVIEW_REQUIRED — cần human researcher decision |
| **OQ-D07-04** | KPI definitions trong MKT-04 nên ở đơn vị nào — survey-based (requiring external data) hay transaction-based (có thể compute từ raw data)? | FR-MKT-05, KPI separation | REVIEW_REQUIRED — ảnh hưởng KPI implementation |
| **OQ-D07-05** | DEV-07 nên expose "Export recommendations" ở format nào? CSV + JSON (hiện tại) hay thêm Markdown report? | FR-MKT-04 (view/export only) | REVIEW_REQUIRED — cần decision về export format |

### 12.3. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| R-01: MKT-01..MKT-05 never created, DEV-07 stays as Phase A shell forever | Medium | Low (shell is valid) | Document Phase B criteria; not a blocker |
| R-02: MKT framework design conflicts with CP-04 segment archetypes | Medium | Medium | DEV-07 implements flexible archetype matching; no hard-coded mapping |
| R-03: MKT-04 KPI definitions conflict with FR-MKT-05 (using clustering metrics) | Low | High | Explicit KPI blocklist; validation test |
| R-04: DEV-07 accidentally promotes prototype output to research evidence | Low | High | `research_safety` block always False; methodology gate test |
| R-05: DBSCAN noise (label=-1) accidentally included in recommendations | Low | High | Explicit validation; CI test |
| R-06: Human researcher expects DEV-07 to generate actual marketing recommendations (Phase B quality) in Phase A | Medium | Medium | Clear disclaimer in Phase A; no invented framework |
| R-07: DEV-07 Phase B requires changes to Phase A API contracts | Medium | Medium | Version pinning in manifest schema; backward compatibility analysis required |

### 12.4. Dependencies

| Dependency | Type | Blocking? | Notes |
|---|---|---|---|
| DEV-06 (segmentation) | Must | Yes | DEV-07 reads DEV-06 output |
| MKT-01..MKT-05 | For Phase B only | No (Phase A first) | Block Phase B implementation |
| CP-04 (segment naming) | Must | Yes | DEV-07 reads CP-04 evidence |
| CP-05 (segment evaluation) | Should | No | DEV-07 enhances with CP-05 evidence; graceful degradation if absent |
| DEV-05 (evaluation) | Optional | No | DEV-07 may reference for provenance |
| EPIC-12 | Not at all | No | DEV-07 is prototype-layer; EPIC-12 is future production |

### 12.5. Assumptions

| # | Assumption | Basis |
|---|---|---|
| A-01 | MKT-01..MKT-05 sẽ được tạo trong tương lai gần | SYS-01 OQ-01 recorded; FR-MKT-01..06 exist |
| A-02 | **INVALID** — citation sai được phát hiện sau reconnaissance. CP-04 §5.3 chỉ chứa sample segment names (concrete examples), KHÔNG có "S1–S4 archetypes". Mapping logic đúng dựa trên CP-04 §4.1–§4.3 (RFM tiers + behavioural modifiers + construction rules). Đã đính chính trong §7.1. | Đính chính đã thực hiện bằng StrReplace surgical vào §7.1, §7.2, §7.3, §9.3, §11.1, §11.2, §12.2 (OQ-D07-03). |
| A-03 | DEV-07 Phase A (shell) có giá trị ngay cả khi không có actual recommendation | S-13 placeholder đã được SYS-06 specify |
| A-04 | CP-05 artifacts (CP-05 implementation) sẽ tồn tại khi DEV-07 Phase B được implement | CP-05 plan exists; CP-05 IMPLEMENTED + VERIFIED |

---

## 13. Out-of-scope items

| # | Item | Reason |
|---|---|---|
| OOS-01 | Backend REST / GraphQL API | ADR-0005 Option A; SYS-05 FUTURE_WORK |
| OOS-02 | Database (SQLite / PostgreSQL / etc.) | ADR-0005 Option A |
| OOS-03 | Campaign automation (email / SMS / push / schedule) | FR-MKT-04; SYS-01 OOS-01 |
| OOS-04 | Real-time recommendation engine | SYS-01 OOS-08 |
| OOS-05 | K-Medoids algorithm option | ADR-0003 OUT OF SCOPE |
| OOS-06 | RFM-only feature set option | ADR-0004 RQ2 reformulated |
| OOS-07 | Cross-algorithm segment mapping (K-Means C1 = GMM C3) | CP-05 §14; FR-SEG-10 |
| OOS-08 | Composite scoring / algorithm ranking | AGENTS.md §2.6; FR-EVAL-08 |
| OOS-09 | "Best / winner / optimal / recommended / final" claims | AGENTS.md §2.5; NFR-06 |
| OOS-10 | Hard-coded segment names ("Champions", "Loyal", "VIP") | AGENTS.md §3; CP-04 §4.4 |
| OOS-11 | ARI / AMI / NMI / Hungarian stability metric computation | EPIC-08 owns; CP-05 §9 |
| OOS-12 | PCA / UMAP / t-SNE visualization | EPIC-10 owns; CP-05 §2.2 |
| OOS-13 | MKT framework tự tạo (strategy / KPI / action) | AGENTS.md §2.1; FR-MKT-02 |
| OOS-14 | Internal clustering metrics (silhouette / DBI / CH / WCSS) as KPIs | FR-MKT-05; CON-07 |
| OOS-15 | DBSCAN noise (label=-1) in recommendation | FR-MKT-06; CON-08 |
| OOS-16 | Production frontend (React / Vue / Svelte) | EPIC-12 owns; SYS-06 OOS-UI-01 |
| OOS-17 | Authentication / Authorization | EPIC-12 owns; SYS-06 OOS-UI-03 |
| OOS-18 | Git operations (commit / push / PR / merge) | AGENTS.md §2.11 |
| OOS-19 | New dependencies (khác numpy, pandas, pyarrow, pyyaml, scikit-learn) | AGENTS.md §5; SYS-01 OOS-14 |
| OOS-20 | Modifying DEV-02/03/04/05/06 contracts | AGENTS.md §2.2; phase isolation |
| OOS-21 | Rerunning clustering or segmentation from DEV-07 | AGENTS.md §2.9; not in scope |
| OOS-22 | Statistical significance testing | CP-05 §2.2; not in scope |
| OOS-23 | CLV / LTV / churn / retention / purchase probability inference | CP-05 §10.4 hard constraints |

---

## 14. Validation plan và completion criteria

### 14.1. Validation plan

**Pre-implementation (before Phase 2 code):**
1. Human researcher review DEV-07 plan (this document)
2. Resolve OQ-D07-01..OQ-D07-05 (human decisions)
3. Verify no conflict with existing approved documents

**Post-implementation (Phase 1 — Phase A shell):**
1. `pytest tests/test_dev07_*.py` — all tests pass
2. `ruff check src/customer_segmentation/prototype/marketing/ tests/`
3. `black --check src/customer_segmentation/prototype/marketing/ tests/`
4. `python scripts/dev07_run_marketing.py --help` — CLI accessible
5. Manual: open HTML prototype → `#/marketing` — S-13 shows REVIEW_REQUIRED shell
6. Verify: no invented strategy/action/KPI in Phase A output
7. Verify: noise segments excluded
8. Verify: research_safety block always False

**Post-implementation (Phase 2 — Phase B, after MKT-01..MKT-05):**
1. All Phase 1 validations
2. MKT-01..MKT-05 framework verified present
3. Recommendation generation functional (with evidence grounding)
4. KPI validation passes (no clustering metrics)
5. MKT framework loader tests pass (absent + present)
6. Cross-segmentation compare functional
7. Export (CSV + JSON) functional

### 14.2. Completion criteria

**Phase A (immediate, MKT-01..MKT-05 absent):**

| Criterion | Evidence |
|---|---|
| All 85 tests pass | `pytest tests/test_dev07_*.py -v` |
| Lint clean | `ruff check .` |
| Format clean | `black --check .` |
| CLI functional | `python scripts/dev07_run_marketing.py profile --help` works |
| S-13 HTML updated | Manual browser verification |
| No invented framework | Code review; no template generation in Phase A |
| Noise excluded | `n_segments_noise` manifest field populated |
| Research safety block correct | `test_research_safety_block` passes |
| No new dependencies | `pip list` matches `pyproject.toml` |
| Storage path correct | Manifest written to `data/prototype/.../marketing/<id>/` |

**Phase B (deferred, requires MKT-01..MKT-05 + human approval):**

| Criterion | Evidence |
|---|---|
| MKT-01..MKT-05 framework verified | `docs/marketing/` exists with all 5 docs |
| Human approval for Phase B | Human researcher approval token |
| Recommendations generated per archetype | `test_recommendation_generation` passes |
| KPI validation enforced | `test_kpi_no_clustering_metric` passes |
| Evidence refs populated | `test_evidence_refs` passes |
| MKT framework loader tests | `test_mkt_framework_*` all pass |
| All Phase A criteria still pass | Regression tests |

### 14.3. Phase gate

DEV-07 Phase B chỉ được implement khi:

```
✅ DEV-07 Phase A verified (tests pass, lint clean, S-13 functional)
✅ MKT-01..MKT-05 tồn tại trong repository
✅ OQ-D07-01..OQ-D07-05 resolved (human decisions recorded)
✅ Human researcher approve Phase B implementation
✅ ADR mới ghi nhận MKT framework adoption (nếu required)
```

---

## 15. Explicit stop gate

> **HARD STOP: DO NOT IMPLEMENT CODE**
>
> This document is a **planning/report artifact only**. The following
> actions are **forbidden** until human review and explicit approval:
>
> ❌ Writing any Python code under `src/customer_segmentation/prototype/marketing/`
> ❌ Creating `scripts/dev07_run_marketing.py`
> ❌ Creating `configs/dev07_marketing.yaml`
> ❌ Creating any test file under `tests/test_dev07_*.py`
> ❌ Modifying any existing contract or source document
> ❌ Creating new ADR
> ❌ Any Git operation (add / commit / push / PR / branch)
> ❌ Claiming any acceptance criteria are complete
> ❌ Implementing Phase B recommendation generation
>
> **What IS allowed:**
> ✅ Reading this document
> ✅ Proposing changes to this plan
> ✅ Responding to human review feedback
> ✅ Creating/updating this planning report

### 15.1. Report summary

| Item | Value |
|---|---|
| Files inspected | 28 source documents, 15 source files, 1 HTML prototype |
| MKT-01..MKT-05 status | ABSENT (verified by grep) |
| EPIC-12 relationship | Sequential; DEV-07 is prototype-layer, EPIC-12 is production frontend |
| Architecture | Option A (ADR-0005): offline, file-based, no backend/API/DB |
| Implementation approach | Two-phase: Phase A (REVIEW_REQUIRED shell) + Phase B (full when MKT exists) |
| CRITICAL conflict | CF-D07-01: MKT framework absent, FR-MKT-02 requires inheritance → stopped at planning |
| Open questions | 5 (OQ-D07-01..05) |
| Proposed files | 18 new files (10 source + 1 config + 1 script + 6 test categories = 85 tests) |
| Out-of-scope items | 23 items |
| Blocking dependencies | DEV-06 (MUST), MKT-01..MKT-05 (for Phase B only) |

---

*Document này là DEV-07 Planning Report thuộc EPIC-11 system design.
Không implement code. Chờ human review trước khi implementation.*
