# ADR-0006 — DEV-05 Prototype-Layer DBSCAN Noise Policy (Uniform Exclusion)

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, status enum, command, file path, task ID,
> OQ ID, ADR ID theo convention hiện có.

- **Status**: Accepted (prototype scope only)
- **Date**: 2026-10-09
- **Deciders**: Human researcher (prototype owner cho DEV-05 phase)
- **Task ID**: DEV-05 (Prototype Evaluation Module)

## Context

DEV-05 plan (`docs/system/DEV-05_evaluation_module.md` v1.1) mở open
question **OQ-EVAL-NOISE** (đã hợp nhất từ OQ-EVAL-01 và OQ-EVAL-02
trước đó): liệu DEV-05 prototype layer có nên áp dụng một uniform
DBSCAN-noise exclusion policy trên cả ba internal metric (Silhouette,
Davies-Bouldin, Calinski-Harabasz), hay giữ sklearn default per-metric
(silhouette-only exclusion)?

Research-layer status của DBSCAN noise handling **không bị thay đổi bởi
ADR này**. Research layer có:

| Layer | Decision | Status (giữ nguyên) |
|---|---|---|
| `SYS-01 §11 CON-15` | DBSCAN silhouette: noise excluded (sklearn convention) | LOCKED ở research layer |
| `SYS-04 §12.2` + G5 | DBSCAN noise excluded from silhouette (CON-15) | LOCKED ở research layer |
| `METHODOLOGY_LOCK_STATUS §3 WA-08` | Noise exclusion (DBSCAN -1 excluded from metrics) | `WORKING_ASSUMPTION` (giữ nguyên) |
| `EXP01_baseline_experiment_PLAN.md` EXP01-MET-01 | Noise exclusion policy (silhouette/DBI/CH/WCSS exclude noise) | `PENDING_REVIEW` (giữ nguyên) |
| `MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47 | "Accept (internal metrics + WCSS exclude DBSCAN noise)" checkbox | NOT TICKED (giữ nguyên) |

DEV-05 là một **prototype-layer** module consume DEV-04 clustering
output và tính 3 internal metric. Prototype layer wrap trực tiếp
`sklearn.metrics.{silhouette_score, davies_bouldin_score,
calinski_harabasz_score}` vì `internal_metrics.py` trong research core
raise `NotImplementedError` (EPIC-08 owned; theo
`docs/system/SYS-04_ml_processing_pipeline.md` §13.3 và
`docs/research/ML04_DBSCAN.md` discussion).

Vì DEV-05 tính ba metric value trực tiếp bằng prototype-layer wrapper
(không qua research-core placeholder), prototype layer phải chọn một
trong:

- **(A) Uniform exclusion** — silhouette, DBI, CH đều filter
  `ClusterLabel = -1` row trong in-memory trước khi gọi sklearn. Điều
  này lệch khỏi sklearn default cho DBI và CH.
- **(B) Per-metric lock** — silhouette exclude noise (CON-15 LOCKED);
  DBI / CH giữ sklearn default (silhouette-only exclusion).
- **(C) Record-both-and-let-researcher-decide** — emit hai field song
  song cho mỗi metric. Schema change; mâu thuẫn với AC (một row trên
  một metric).
- **(D) Defer DBSCAN hoàn toàn khỏi DEV-05** — emit 3 metric chỉ trên
  non-density algorithm.

Theo `AGENTS.md §2.9` và `§2.10`, quyết định này ảnh hưởng tới việc
diễn giải mọi DBSCAN clustering evaluation mà DEV-05 surface; do đó
nó yêu cầu document tường minh trong role-bound archive
(`docs/decisions/`).

## Decision

**DEV-05 prototype layer chấp nhận option (A) — uniform DBSCAN-noise
exclusion trên cả ba internal metric — như một prototype-scope
decision được ghi bởi ADR này.**

Cụ thể:

1. **Default `noise_policy = "exclude"`** trong
   `configs/dev05_evaluation.yaml`.
2. **CLI flag `--noise-policy include|exclude`** (default resolve từ
   config) expose cả hai mode cho per-call override. Cả hai mode luôn
   được ghi rõ ràng; không emit âm thầm.
3. **Hiệu lực (exclude, default)** — với `algorithm_family ==
   "density_based"` (DBSCAN) run, row có `ClusterLabel == -1` được
   **loại bỏ khỏi in-memory copy của X và labels** trước khi truyền
   cho bất kỳ sklearn metric function nào. Original
   `cluster_labels_*.parquet` không bị động vào (R-EVAL-14, §5.4.5
   của plan).
4. **Hiệu lực (include, override)** — không áp dụng filter; sklearn
   default có hiệu lực (treat `-1` như một cluster thường cho DBI/CH).
   Manifest ghi `noise_policy_used = "include"`.
5. **Manifest ghi provenance** (theo plan §5.4.4):
   `noise_policy_used`, `noise_count`, `noise_ratio`,
   `n_samples_input`, `n_samples_used_for_compute`, `n_clusters_realized`.
6. **Idempotent-distinct qua `evaluation_id` derivation** (theo plan
   §4.4) — đổi `noise_policy` cho ra một `evaluation_id` khác, nên
   `--noise-policy include` và `--noise-policy exclude` không bao giờ
   ghi đè lẫn nhau âm thầm.
7. **`reason = DBSCAN_NOISE_EXCLUDED`** được emit trên cả ba metric
   entry khi DBSCAN noise row bị filter ra và filter subset có ≥ 2
   unique non-noise label (status vẫn là `VALID_VALUE`, với reason
   đóng vai trò audit annotation).
8. **Compare output surface per-row provenance** (theo plan §9.3,
   §9.5) — evaluation trong cùng compatibility group khác nhau ở
   `n_samples_used_for_compute`, `noise_count`, `noise_ratio`, hoặc
   `noise_policy_used` PHẢI được flag tường minh; disclaimer "no
   ranking, recommendation, or winner annotation is emitted" là bắt
   buộc.

## Scope (chính xác)

| Trong scope của ADR này | Ngoài scope của ADR này |
|---|---|
| DEV-05 prototype layer (`customer_segmentation.prototype.evaluation.*`) | Research core (`customer_segmentation.evaluation.*` — READ-ONLY theo AGENTS.md §2.4) |
| `configs/dev05_evaluation.yaml` (tạo trong Phase 2) | `configs/transformation.yaml`, `configs/clustering.yaml`, `configs/exp0X_*.yaml` (research config) |
| `scripts/dev05_evaluate_clustering.py` (tạo trong Phase 2) | `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`, `scripts/run_ml0X_*.py` (research scripts) |
| `data/prototype/<ds>/preprocessed/<pp>/clustering/<cl>/evaluation/<ev>/` (subdir MỚI dưới DEV-04 output) | `data/raw/**`, `data/processed/**`, `data/interim/**`, `reports/**`, `data/prototype/<ds>/preprocessed/<pp>/clustering/<cl>/` other than `evaluation/` |
| Status của OQ-EVAL-NOISE cho DEV-05 implementation | Status của CON-15, WA-08, EXP01-MET-01, `MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47 |
| ARI / AMI / WCSS / stability / runtime — ngoài scope (EPIC-08 owned) | ARI / AMI / WCSS / stability / runtime (EPIC-08 owned, untouched) |
| Lệch khỏi sklearn default cho DBI / CH, **như một prototype-layer decision**, với explicit deviation annotation trong mọi artifact | Promotion của quyết định này lên research methodology; bất kỳ thay đổi nào về cách diễn giải `data/processed/final_clustering_dataset.parquet` artifact |

## Status of this decision

Đây là một **prototype-layer** decision được prototype owner chấp nhận
cho current prototype phase (theo ADR-0005 Option A architecture). Nó
**KHÔNG** phải research methodology decision.

`TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED` (`AGENTS.md` §2.10). Đạt
`TECHNICALLY IMPLEMENTED` KHÔNG promote bất kỳ evaluation result nào
lên research evidence. Mentor / human researcher approval vẫn cần
trước khi prototype evaluation result có thể được cite làm research
evidence.

Cụ thể:

- `SYS-01 §11 CON-15` — **không đổi** (silhouette exclusion LOCKED ở
  research layer).
- `METHODOLOGY_LOCK_STATUS §3 WA-08` — **không đổi** (vẫn
  `WORKING_ASSUMPTION` cho tới khi mentor review form được ký).
- `EXP01_baseline_experiment_PLAN.md` EXP01-MET-01 — **không đổi**
  (vẫn `PENDING_REVIEW`).
- `MENTOR_REVIEW_FORM_EXP01_EXP05.md` — **KHÔNG BỊ SỬA** bởi ADR này
  hay bởi DEV-05 plan. Tick trên line 47 (và bất kỳ line liên quan
  nào) được dành cho mentor / human researcher.

ADR này tường minh KHÔNG promote uniform exclusion policy lên research
methodology. Một ADR riêng hoặc mentor action là cần thiết cho sự
promotion đó.

### Dễ hơn

- DEV-05 prototype implementation có thể tiến hành với một noise-handling
  decision đã được document, traceable; không cần OQ resolution thêm
  cho prototype layer.
- Comparison output cho DBSCAN + non-DBSCAN run là interpretively
  consistent: `n_samples_used_for_compute` là uniform qua ba metric
  row trong cùng một evaluation (silhouette / DBI / CH đều thấy cùng
  filtered subset).
- Per-row provenance field làm filter effect auditable từ manifest mà
  không cần re-run metric.

### Khó hơn hoặc rủi ro hơn

- DEV-05 DBI / CH value **không trực tiếp comparable** với một naïve
  sklearn call (sklearn default treat `-1` như một cluster). Plan
  surface điều này per-row trong compare output (§9.3, §9.5) và trong
  mandatory disclaimer, nhưng reviewer phải đọc manifest cẩn thận.
- Nếu mentor sau đó quyết định option (B) ở research layer, DEV-05
  prototype sẽ diverge khỏi research layer decision cuối cùng. Resolution
  sẽ yêu cầu: (i) DEV-05 v2 tương lai với silhouette-only exclusion,
  hoặc (ii) superseding ADR.
- Researcher đọc DEV-05 output KHÔNG được diễn giải chúng như research
  evidence; `AGENTS.md` §2.10 phải được honour tại mọi cite.

## Alternatives considered

### Option B — Per-metric lock (silhouette-only exclusion)

**Bị reject** cho prototype layer. Rationale:

- Cho ra `n_samples_used_for_compute` khác nhau giữa các metric row
  trong cùng một evaluation khi DBSCAN noise hiện diện. Side-by-side
  reporting (AC-4 của DEV-05) trở nên interpretively asymmetric.
- DEV-05 plan §5.4.2 document concern này chi tiết.

### Option C — Record-both-and-let-researcher-decide

**Bị reject**. Rationale:

- Mâu thuẫn với AC's "one row per metric" constraint.
- Sẽ yêu cầu schema change mà plan tường minh defer (Option B trong
  plan §8.5 là "CLI + HTML static report", deferring any schema
  expansion).
- Đã capture trong plan §5.4 footnote; có thể revisited trong một
  DEV increment tương lai sau khi Phase 2 stabilise.

### Option D — Defer DBSCAN hoàn toàn khỏi DEV-05

**Bị reject**. Rationale:

- Loại bỏ một trong 5 thuật toán (ADR-0003) khỏi prototype evaluation
  surface, phá vỡ symmetry với EXP-01/05 evidence base.
- Plan §1.2 / §4.1 / §5.2 yêu cầu DBSCAN là first-class input.

## Consequences (technical)

Khi Phase 2 implementation bắt đầu dưới ADR này:

1. `configs/dev05_evaluation.yaml` sẽ khai báo `noise_policy:
   "exclude"` (default; CLI override cho phép).
2. `src/customer_segmentation/prototype/evaluation/metrics.py` sẽ
   áp dụng filter cho cả ba metric call khi
   `noise_policy_used == "exclude"` và `algorithm_family ==
   "density_based"`.
3. `src/customer_segmentation/prototype/evaluation/manifest.py` sẽ
   ghi tất cả provenance field liệt kê ở trên.
4. `tests/test_dev05_metrics.py` và `tests/test_dev05_pipeline.py` sẽ
   assert: `test_metrics_dbscan_noise_excluded_uniformly_for_all_three`,
   `test_metrics_dbscan_all_noise_returns_not_applicable_three_times`,
   `test_metrics_non_dbscan_noise_count_null` (mirror plan §11 Phase 2C).
5. R-EVAL-14 (noise immutability) test sẽ assert
   `sha256(cluster_labels_*.parquet)` không đổi trước vs sau run, cộng
   với AST scan xác nhận không có in-place mutation helper.
6. `research_safety.automatically_promoted_to_research = False`,
   `appeared_in_research_evidence = False`,
   `scope = "EVALUATED_PROTOTYPE"` (R-EVAL-01..03).

## References

- `docs/system/DEV-05_evaluation_module.md` v1.1 → v1.2 (Phase 1 plan;
  ADR này được tham chiếu trong §15 và §18).
- `docs/system/SYS-01_requirements.md` §11 CON-15, §14 — silhouette
  exclusion LOCKED ở research layer (KHÔNG đổi bởi ADR này).
- `docs/system/SYS-04_ml_processing_pipeline.md` §12.2, G5 — silhouette
  exclusion LOCKED ở research layer (KHÔNG đổi bởi ADR này).
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` §3 WA-08 —
  `WORKING_ASSUMPTION` (KHÔNG đổi bởi ADR này).
- `docs/research/EXP01_baseline_experiment_PLAN.md` EXP01-MET-01 —
  `PENDING_REVIEW` (KHÔNG đổi bởi ADR này).
- `docs/research/review/MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47 —
  KHÔNG bị sửa bởi ADR này.
- `docs/decisions/0003-algorithm-scope.md` (ADR-0003) — 5 thuật toán,
  K-Medoids OUT.
- `docs/decisions/0004-research-questions.md` (ADR-0004) — định nghĩa
  RQ1/RQ2/RQ3.
- `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) —
  Option A file-based batch / offline prototype architecture; ADR này
  được scope cho prototype phase đó.
- `AGENTS.md` §2.5, §2.6, §2.9, §2.10, §2.11, §6 — research integrity,
  no silent policy change, human approval gate, không có Git operation
  bởi agent, escalation protocol.
- `docs/research/ML04_DBSCAN.md` — sklearn default behaviour cho
  DBI/CH và noise handling discussion.
- `docs/research/review/FULL_RESEARCH_READINESS_AUDIT_FE01_EXP05.md`
  — research-layer evidence base hiện đang dùng uniform exclusion trong
  EXP-01 / EXP-05 (pending mentor review).

## Immutability

Theo `docs/decisions/README.md`, ADR này là immutable khi đã accepted.
Nếu quyết định sau đó bị reverse hoặc extend, một ADR mới phải
supersede ADR này (vd. `0007-dev05-prototype-noise-policy-update.md`).
File cũ không bị edit.
