# DEV-05 — Prototype Evaluation Module

> **Mã task:** DEV-05
> **Tên:** Prototype Evaluation Module (Jira pipeline: `Calculate Metrics / Display Metrics / Compare Experiments`)
> **Plan version:** v1.2 (revision: 2026-10-09 — OQ-EVAL-NOISE resolved by ADR-0006 for prototype scope; research-layer status preserved; see footer for diff summary)
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config, no ADR, no SYS edit, no Git op). Phase 2 (implementation) yêu cầu human approval token chính xác `APPROVE PHASE 2`. OQ-EVAL-NOISE đã được ghi nhận bằng ADR-0006 cho prototype scope; research-layer status (CON-15, WA-08, EXP01-MET-01, MENTOR_REVIEW_FORM) **không bị** thay đổi.
> **Ngày:** 2026-10-09
> **Phạm vi:** Cung cấp **prototype-layer** capability để tính, lưu, hiển thị và so sánh ba internal clustering metric (Silhouette Score, Davies-Bouldin Index, Calinski-Harabasz Index) trên output của DEV-04. Một evaluation pass mỗi lần gọi, liên kết 1-1 với một DEV-04 clustering run (một `clustering_id`). Output được ghi vào `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/evaluation/<evaluation_id>/` (subdirectory mới của cùng `clustering_id`, không flat lên `clustering/<evaluation_id>/` để bảo toàn ranh giới evaluation-vs-clustering).
> **Does NOT** sửa ML-01 framework, không tự đánh dấu "best", "winner", "optimal", "recommended", không ranking thuật toán, không promote prototype evaluation thành research evidence, không tự ý chạy metric trên research dataset thật trong Phase 1, không mở rộng scope sang EPIC-09 / visualization.
> **Architecture:** Option A (ADR-0005) — offline, single-machine, file-based. No backend, no API, no database, no worker, no queue.
> **Kế thừa:** DEV-04 output contract (`docs/system/DEV-04_completion_summary.md` + `prototype.clustering.manifest.ClusteringManifest`) là input contract bắt buộc. DEV-05 mirror các pattern từ research core evaluation (`customer_segmentation.evaluation.*`) — `MetricsResult` shape, `MISSING` sentinel, `MISSING_REASON_*` taxonomy, status/reason enum — theo SYS-04 §6, §12 (CON-07) và SYS-04 §12.2 (metric applicability rules), nhưng Phase 2 implementation sẽ **wrap trực tiếp `sklearn.metrics.{silhouette_score, davies_bouldin_score, calinski_harabasz_score}`** trong `customer_segmentation.prototype.evaluation.metrics` (vì `internal_metrics.py` của research core chỉ có `NotImplementedError` stub — EPIC-08 owned). DEV-05 KHÔNG import từ `customer_segmentation.evaluation.*` ở runtime (enforced bằng `tests/test_dev05_import_blocklist.py`).

---

## Mục lục

1. [Task scope và non-goals](#1-task-scope-v%C3%A0-non-goals)
2. [Source documents và contract references](#2-source-documents-v%C3%A0-contract-references)
3. [Current-state analysis](#3-current-state-analysis)
4. [Input/output contracts](#4-inputoutput-contracts)
5. [Metric semantics và edge-case policy](#5-metric-semantics-v%C3%A0-edge-case-policy)
6. [Module/API design](#6-moduleapi-design)
7. [Storage schema và path](#7-storage-schema-v%C3%A0-path)
8. [Display strategy](#8-display-strategy)
9. [Experiment comparison semantics](#9-experiment-comparison-semantics)
10. [Research-safety invariants](#10-research-safety-invariants)
11. [Implementation phases theo dependency order](#11-implementation-phases-theo-dependency-order)
12. [Acceptance criteria mapping](#12-acceptance-criteria-mapping)
13. [Test matrix](#13-test-matrix)
14. [Risks và mitigations](#14-risks-v%C3%A0-mitigations)
15. [Open questions/decisions cần human approval](#15-open-questionsdecisions-c%E1%BA%A7n-human-approval)
16. [Files dự kiến tạo/sửa](#16-files-d%E1%BB%B1-ki%E1%BA%BFn-t%E1%BA%A1os%E1%BB%ADa)
17. [Verification commands dự kiến](#17-verification-commands-d%E1%BB%B1-ki%E1%BA%BFn)
18. [Explicit stop gate trước implementation](#18-explicit-stop-gate-tr%C6%B0%E1%BB%9Bc-implementation)

---

## 1. Task scope và non-goals

### 1.1. Task scope (in-scope, đối chiếu Jira pipeline)

DEV-05 cung cấp **prototype-layer evaluation capability** cho output của DEV-04. Ba trục Jira + acceptance criteria:

| # | Jira pipeline | Acceptance criterion | DEV-05 deliverable (dự kiến Phase 2) |
|---|---|---|---|
| 1 | **Calculate Metrics** | Metrics được tính | `customer_segmentation.prototype.evaluation.metrics.compute_internal_metrics(X, labels, *, noise_label)` trả về `EvaluationMetricsResult` với 3 metric + status; wrap `sklearn.metrics.{silhouette_score, davies_bouldin_score, calinski_harabasz_score}` |
| 2 | (implicit) lưu metrics | Metrics được lưu | `evaluation_manifest.json` (atomic write) + `evaluation_metrics_<evaluation_id>.csv` (long-format) + ghi vào log của prototype layer |
| 3 | **Display Metrics** | Metrics hiển thị | CLI `scripts/dev05_evaluate_clustering.py` in bảng metrics; helper `customer_segmentation.prototype.evaluation.report.format_metrics_table(result)` |
| 4 | **Compare Experiments** | Có thể so sánh Experiment | `compare_evaluations(evaluation_manifests: list[Path])` / CLI `--compare` nhận nhiều `evaluation_id` / `clustering_id` và in metric side-by-side với compatibility check |
| 5 | (Jira scope conf.) | `Save Result` | Ghi evaluation_manifest.json + metrics long-format csv + log file đúng contract §7 |

**Phân biệt rõ với research core (EPIC-08 / EVA-02/03/05):**

| Concern | EPIC-08 (research) | DEV-05 (prototype) |
|---|---|---|
| Owner | Research core (`customer_segmentation.evaluation.*`) | Prototype layer (`customer_segmentation.prototype.evaluation.*`) |
| Input | `data/processed/clustering_experiments/experiment_log_*.json` (từ ML-01 research runs, 185 dòng EXP-01..05) | `clustering_manifest.json` + `cluster_labels_*.parquet` (từ DEV-04 prototype runs) |
| Metric payload | `MetricsResult` (placeholder) + EVA-01/02 computed metrics + EVA-03 ARI/AMI (deferred) | `EvaluationMetricsResult` (status + value + reason) cho 3 metric dev-05 cover |
| Output | `reports/evaluation/eva0X/` (185-row EVA-01 repository, ... ) | `data/prototype/<ds>/preprocessed/<pp>/clustering/<clustering_id>/evaluation/<evaluation_id>/` |
| Promotion gate | Mentor + ADR (research methodology) | **NOT** promoted; `automatically_promoted_to_research = false` always |
| Noise policy | SYS-04 §12.2 + CON-15 = **silhouette** must exclude DBSCAN noise (research-layer lock); DBI / CH not yet locked at research layer | **DEV-05 prototype proposal (PENDING_HUMAN_REVIEW):** exclude noise from all three metrics (`silhouette`, `davies_bouldin`, `calinski_harabasz`) for consistency. Recorded in `noise_policy_used` field of `evaluation_manifest.json`. See §5.4 (full specification) + §15 OQ-EVAL-NOISE (consolidated). |
| Stability / ARI / AMI / Hungarian / statistical tests / CI / runtime-variance | EPIC-08 owned, deferred (SYS-04 §13, EPIC08-*) — `REVIEW_REQUIRED` | **OUT OF SCOPE** — DEV-05 chỉ compute 3 internal metric |

### 1.2. Non-goals (out-of-scope, bắt buộc)

| ❌ | Non-goal | Nguồn |
|---|---|---|
| ❌ | Ranking algorithms, "best/winner/optimal/recommended/final" framing | AGENTS.md §2.5, §2.6, §2.10 |
| ❌ | Modify ML-01 framework / 5 algorithm adapters | AGENTS.md §3 "Clustering", ADR-0003 |
| ❌ | Modify research-core `customer_segmentation.evaluation.*` (read-only reuse) | AGENTS.md §2.4, §3 |
| ❌ | Hyperparameter sweep / K-sweep / preprocessing sensitivity sweep | EPIC-07 owned; out-scope per ADR-0005 architecture |
| ❌ | ARI / AMI / Hungarian / stability / statistical test / CI / runtime comparison | EPIC-08 owned; SYS-04 §13.3 deferred; `REVIEW_REQUIRED` |
| ❌ | Visualization (matplotlib/seaborn charts, dashboard) | EPIC-10 owned; SYS-06 owned |
| ❌ | Segment profiling / cluster naming ("Champions", "Loyal") | EPIC-09 / CP-01..05 owned; AGENTS.md §3 "Profiling" |
| ❌ | Modify DEV-02 / DEV-03 / DEV-04 output contracts / manifests | AGENTS.md §2.2 phase isolation |
| ❌ | Modify DEV-04 pipeline / config / scope enum | AGENTS.md §2.2 |
| ❌ | Build backend / API / database / worker / queue | ADR-0005 Option A; SYS-05 API = `FUTURE_WORK` per ADR-0005 |
| ❌ | Promote prototype evaluation to research evidence | AGENTS.md §2.10 |
| ❌ | Run metric evaluation trên `data/processed/final_clustering_dataset.parquet` hoặc `data/raw/primary/Online Retail.xlsx` Phase 1 | AGENTS.md §2.12, §2.7 |
| ❌ | Git operations (commit / push / PR / merge / branch) | AGENTS.md §2.11 |
| ❌ | Adjust dataset, preprocessing, features, transformation, scaling, algorithm, threshold, n_clusters, eps, min_samples, ... tuỳ ý | AGENTS.md §2.9 no silent methodology change |
| ❌ | Bổ sung visualization library mới (giữ phụ thuộc theo `pyproject.toml`) | AGENTS.md §5 |
| ❌ | Self-resolve methodology gates pending (chờ mentor) | AGENTS.md §2.10, §6 |

### 1.3. Acceptance Criteria (4 mục của Jira — đối chiếu)

| AC | Description (verbatim từ task brief) | Phạm vi DEV-05 |
|---|---|---|
| AC-1 | Metrics được tính | Bao phủ. Output = 3 metric (silhouette, DBI, CH) per evaluation pass. |
| AC-2 | Metrics được lưu | Bao phủ. Ghi `evaluation_manifest.json` + `evaluation_metrics_<evaluation_id>.csv` + log. |
| AC-3 | Metrics hiển thị | Bao phủ. CLI in bảng + helper format cho notebook (nếu sau này DEV-09 cần). Phase 2 in stdout; notebook reader = future DEV. |
| AC-4 | Có thể so sánh Experiment | Bao phủ. `compare_evaluations(...)` + CLI `--compare`. Compatibility check dựa trên shared dataset/preprocessing/feature space (xem §9). |

> **Lưu ý AGENTS.md §6.2:** Không tự bổ sung AC mới. Mọi yêu cầu kỹ thuật phát sinh (vd. "WCSS diagnostic only") được ghi rõ là **implementation requirement** chứ không phải AC. Field `wcss` trong kết quả sẽ xuất hiện với `is_diagnostic_only=true` mirror SYS-04 §12.1 (CON-07 §12.3), nhưng không tự promote thành AC chính thức.

---

## 2. Source documents và contract references

> Mỗi phát biểu trong plan trích từ doc X phải đính kèm section reference. Plan **không** dùng statement nào không có nguồn (AGENTS.md §2.1, §2.7).

| Tài liệu | Vai trò cho DEV-05 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules | Toàn bộ (binding) |
| `docs/decisions/0003-algorithm-scope.md` (ADR-0003) | 5 algorithms only; K-Medoids OUT OF SCOPE | Toàn bộ |
| `docs/decisions/0004-research-questions.md` (ADR-0004) | RQ1/RQ2/RQ3 scope; metric treatment; "no best/winner" interpretation boundary | Toàn bộ |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture contract (Option A) | Toàn bộ |
| `docs/system/SYS-01_requirements.md` | FR-VIZ-03 (display), FR-EVAL-01 (compute), CON-07 (internal metrics only), CON-15 (DBSCAN noise) | §10 functional req., §11 constraints, §13 OQ |
| `docs/system/SYS-04_ml_processing_pipeline.md` | CON-07 (§12.1 metrics table), §12.2 metric applicability, §12.3 constraints (no composite_score, no ranking), §13 EPIC-08 deferred scope | §6 metric conventions, §12 Evaluation, §13 Stability, §24.5 EPIC-08 deferred list, §25 review-required |
| `docs/system/SYS-05_api_design.md` | API/E.5 endpoint `POST /api/v1/evaluation/compare` (FUTURE_WORK per ADR-0005) — reference for `compare_evaluations(...)` response shape | §9 E-EVAL/E.5 (skim; design reference only) |
| `docs/system/DEV-01_project_setup.md` | Project setup context (skim cho §3.0) | Header |
| `docs/system/DEV-02_dataset_management.md` | DEV-02 contract; storage root resolution pattern (mirror cho DEV-05) | §14 input contract (skim) |
| `docs/system/DEV-03_completion_summary.md` + `docs/system/DEV-03_preprocessing.md` | DEV-03 output contract; manifest schema reference (`preprocessed_manifest.json` → `ml_dataset_block`); storage pattern | §10 manifest schema, §3 storage architecture, §14 input contract for downstream |
| `docs/system/DEV-04_completion_summary.md` + `docs/system/DEV-04_clustering_execution.md` | DEV-04 manifest schema (`ClusteringManifest`); storage sub-path layout; `cluster_labels_<experiment_id>.parquet` schema; research-safety pattern (`automatically_promoted_to_research=false`, `scope="CLUSTERED_PROTOTYPE"`); idempotency / atomic publish pattern (mirror cho DEV-05 evaluation_result idempotency) | §3 hiện trạng, §6 storage, §10 manifest, §11 safety; reference implementation of frozen dataclass manifest + atomic write + research_safety block |
| `docs/research/ML01_Clustering_Experiment_Framework.md` | ML-01 framework contract (research); `MetricsResult` placeholder contract (silhouette/DBI/CH = `None` until EPIC-08 populates) | skim header + §metrics |
| `docs/methodology/research_questions.md` | RQ1/RQ2/RQ3, interpretation boundary, "no best" claim | full skim |
| `docs/methodology/methodology_overview.md` | C7 working config, benchmarking protocol | skim §3.6 metric conventions |
| `docs/evaluation/EVA-01.md` | Reference cho `EvaluationMetricsResult.status` taxonomy (mirror `MISSING_REASON_*` + `metric_status ∈ {VALID_VALUE, NOT_APPLICABLE, MISSING, COMPUTATION_ERROR}` per SYS-04 §12.2) | §3 input, §4 method, §5 validation |
| `docs/evaluation/CP-01..05.md` | Future cluster profiling (out of scope) | header only (out of scope) |
| `src/customer_segmentation/clustering/registry.py` | `AlgorithmRegistry`, 5 algorithm names | full |
| `src/customer_segmentation/clustering/result.py` | `MetricsResult` dataclass (placeholder contract), `ExperimentResult`, `ExperimentStatus`, `AlgorithmFamily` | full |
| `src/customer_segmentation/clustering/artifacts.py` | `write_cluster_labels`, `write_algorithm_output`, `write_experiment_artifacts` patterns (mirror cho DEV-05 writers) | full skim for IO style |
| `src/customer_segmentation/clustering/validation.py` | `validate_clustering_matrix`, `validate_customer_alignment`, `ValidationReport`, `IdentifierLeakageError` (re-evaluate `X` + `labels` pre-metric) | full skim |
| `src/customer_segmentation/clustering/runner.py` | `ExperimentRunner.run()` (read-only) — DEV-05 NEVER invokes; only consumes `ExperimentResult.status` to decide if metrics compute is allowed | full skim |
| `src/customer_segmentation/evaluation/internal_metrics.py` | **TODO placeholder** (`silhouette_score_safe`, `calinski_harabasz_safe`, `davies_bouldin_safe` raise `NotImplementedError`). DEV-05 will wrap `sklearn.metrics` directly — see §5 và §6 vì đây là research-core owned code (chưa implement, EPIC-08 owned). | full |
| `src/customer_segmentation/evaluation/eva02/metrics.py` | Reference cho `metric_status` semantics (mirror pattern) | skim §97-155 |
| `src/customer_segmentation/evaluation/experiment_results/schema.py` | `MISSING` sentinel, `MISSING_REASON_*` taxonomy, `STANDARD_COLUMNS`, source-experiment enum pattern (mirror cho DEV-05 evaluation manifest schema) | skim §99-330 |
| `src/customer_segmentation/evaluation/eva03/load.py` | Reference parquet-round-trip pattern (mirror cho DEV-05 metrics CSV → stable schema) | skim |
| `src/customer_segmentation/prototype/clustering/manifest.py` | Pattern reference: `ResearchSafetyBlock`, `InputIdentityBlock`, `EnvironmentBlock`, frozen dataclass, `manifest_to_dict`, `write_*_manifest` (atomic temp+rename) | full |
| `src/customer_segmentation/prototype/clustering/storage.py` | Pattern reference: `derive_clustering_id`, `prototype_clustering_*_dir`, `find_existing`, idempotency check, `DETERMINISTIC_ALGORITHMS` (mirror; không cần cho evaluation nhưng pattern cho `evaluation_id` derivation) | full skim |
| `src/customer_segmentation/prototype/clustering/pipeline.py` | Pattern reference: stages, `_load_dev03_ml_dataset`, atomic publish, Stage 0→6 lifecycle (mirror; DEV-05 evaluation pipeline = Stage A→E with similar discipline) | full skim for Stage patterns |
| `src/customer_segmentation/prototype/clustering/scope.py` | Pattern reference: `StrEnum`, frozen constants, `DETERMINISTIC_ALGORITHMS` (mirror cho DEV-05 `EvaluatedScope` enum) | full skim |
| `src/customer_segmentation/prototype/clustering/config_loader.py` | Pattern reference: dataclass-frozen YAML loader, `VALID_LOG_LEVELS`, structured error (`Dev04ConfigError` mirror → `Dev05ConfigError`) | full skim for style |
| `src/customer_segmentation/prototype/clustering/logging_config.py` | Pattern reference: `PerStageLogger`, `configure_logging`, `finalize_logging` (mirror cho DEV-05 evaluation logging) | full skim |
| `src/customer_segmentation/prototype/clustering/__init__.py` | Pattern reference: public API re-export list | full |
| `scripts/dev04_run_clustering.py` | Pattern reference: CLI structure (mirror cho `scripts/dev05_evaluate_clustering.py`) | full skim |
| `configs/dev04_clustering.yaml` | Pattern reference: YAML layout, validation block, research_safety block (mirror cho `configs/dev05_evaluation.yaml`) | full |
| `tests/test_dev04_*.py` | Pattern reference: 11 test files; safety/scope/manifest/storage/cli/pipeline/safety/research_safety/import_blocklist/runtime_dependencies (mirror cho DEV-05 — same coverage matrix) | skim file names + headers |
| `tests/conftest.py` | Shared fixtures (mirror; add `synthetic_dev04_artefact` if needed for DEV-05 evaluation tests) | full |
| `tests/test_dev04_*.py::test_dev04_storage`, `test_dev04_manifest`, `test_dev04_pipeline`, `test_dev04_safety` | Pattern cho test organization of atomic publish, idempotency, atomic-write corrupts — mirror cho DEV-05 tests | skim headers |
| `configs/clustering.yaml` | ML-01 framework config (read-only ref) — DEV-05 không touch; mirror input-validation defaults từ `validation:` block | skim |
| `.gitignore` | `data/prototype/**` ignored; `reports/evaluation/**` placeholder only | full skim for `data/prototype` dir handling |

> **NOT read in depth** (out of plan scope): notebooks/**, reports/fe0*/**, reports/exp0*/**, docs/research/review/**, docs/research/algorithm_theory_v3_exports/**, src/customer_segmentation/clustering/{baseline,cluster_number,hyperparameter_search,preprocessing_feature_sensitivity,stability,metrics}.py (EPIC-08 owned), src/customer_segmentation/profiling/**, src/customer_segmentation/visualization/**, src/customer_segmentation/evaluation/eva03/{perturbation,seed_stability,hungarian,hyperparameter_stability,cluster_size}.py (EPIC-08 stability out of scope).

---

## 3. Current-state analysis

### 3.1. Source code đã tồn tại

**Research core — READ-ONLY đối với DEV-05:**

```
src/customer_segmentation/clustering/             (READ-ONLY)
├── result.py                                     (MetricsResult placeholder — silhouette/DBI/CH = None;
                                                   DEV-05 consume ExperimentResult.cluster_result only,
                                                   compute metrics OUT-OF-BAND)
├── validation.py                                 (validate_clustering_matrix — reuse cho input validation
                                                   trước metric compute)
├── artifacts.py, runner.py, registry.py          (read-only references)

src/customer_segmentation/evaluation/             (READ-ONLY; reuse IF usable, but most are EVA-specific)
├── internal_metrics.py                           (TODO; silhouette_score_safe/calinski_harabasz_safe/
                                                   davies_bouldin_safe raise NotImplementedError;
                                                   not usable for DEV-05 — DEV-05 wraps sklearn directly)
├── comparison.py                                 (TODO; placeholders for compare_algorithms; out of scope)
├── eva01..03/                                    (185-row research evaluation; out of scope per DEV-05
                                                   non-goals; reference cho MISSING/VALID_VALUE taxonomy)
└── experiment_results/                           (MISSING sentinel; FIELD_TYPES; STANDARD_COLUMNS;
                                                   mirror cho DEV-05 manifest schema)
```

**Prototype layer (consumed by DEV-05):**

```
src/customer_segmentation/prototype/clustering/    (DEV-04 output — consumed via public API)
├── __init__.py                                   (PUBLIC: ClusteringManifest, build_/read_/write_clustering_manifest,
                                                   ClusteringManifestError, ClusteringPipelineResult,
                                                   run_clustering_pipeline, ...)
├── manifest.py                                   (ClusteringManifest dataclass; ResearchSafetyBlock;
                                                   InputIdentityBlock; EnvironmentBlock;
                                                   CLUSTERING_MANIFEST_SCHEMA_VERSION = "1.0.0")
├── pipeline.py                                   (run_clustering_pipeline return ClusteringPipelineResult
                                                   with .cluster_labels_path, .manifest_path, .lifecycle, ...)
├── storage.py                                    (prototype_clustering_run_dir; resolve_storage_root;
                                                   pattern cho DEV-05 evaluation_id derivation)
├── config_loader.py                              (yaml loader pattern, structured errors)
├── logging_config.py                             (PerStageLogger pattern)
└── scope.py                                      (ClusteredScope StrEnum pattern; DETERMINISTIC_ALGORITHMS)
```

**Prototype layer (DEV-05 needs to ADD — package doesn't exist yet):**

```
src/customer_segmentation/prototype/evaluation/   (NEW package)
├── __init__.py                                   (new — public API re-exports)
├── scope.py                                      (new — EvaluatedScope StrEnum;
                                                   MetricName StrEnum = {SILHOUETTE, DAVIES_BOULDIN,
                                                   CALINSKI_HARABASZ};
                                                   MetricStatus StrEnum = {VALID_VALUE, NOT_APPLICABLE,
                                                   MISSING, COMPUTATION_ERROR};
                                                   NoisePolicy StrEnum / constants = {INCLUDE, EXCLUDE})
├── metrics.py                                    (new — wrap sklearn.metrics.{silhouette_score,
                                                   davies_bouldin_score, calinski_harabasz_score};
                                                   return EvaluationMetricsResult with status+reason;
                                                   handle edge cases per §5)
├── manifest.py                                   (new — EvaluationManifest dataclass;
                                                   EvaluationMetricsBlock;
                                                   EvaluationMetricEntry (per metric: value, status,
                                                   reason, is_diagnostic_only);
                                                   ResearchSafetyBlock (mirror DEV-04 pattern,
                                                   scope="EVALUATED_PROTOTYPE");
                                                   InputIdentityBlock (mirror);
                                                   EnvironmentBlock (mirror);
                                                   EVALUATION_MANIFEST_SCHEMA_VERSION = "1.0.0";
                                                   atomic write + read; mirror DEV-04 manifest
                                                   module verbatim for I/O discipline)
├── storage.py                                    (new — derive_evaluation_id (content-addressed);
                                                   prototype_evaluation_base_dir;
                                                   prototype_evaluation_run_dir;
                                                   prototype_evaluation_metrics_path;
                                                   find_existing_evaluation (idempotency);
                                                   resolve_storage_root (mirror DEV-04);
                                                   path-containment defence)
├── config_loader.py                              (new — Dev05Config dataclass (frozen);
                                                   Validation/NoisePolicy/Comparison/Storage/Logging/
                                                   ResearchSafety sub-blocks;
                                                   load_dev05_config; Dev05ConfigError;
                                                   DEFAULT_DEV05_CONFIG_PATH = configs/dev05_evaluation.yaml;
                                                   DEV05_CONFIG_TOP_KEY = "dev05_evaluation")
├── logging_config.py                             (new — mirror DEV-04 pattern;
                                                   PerStageLogger, configure_logging, finalize_logging;
                                                   DEV05_LOGGER_NAME)
├── pipeline.py                                   (new — run_evaluation_pipeline(dataset_id,
                                                   preprocessed_id, clustering_id, *,
                                                   config_path, force_recompute, label_col);
                                                   Stages A: preflight → B: lookup
                                                   (ClusteringManifest + cluster_labels parquet +
                                                   re-load ML Dataset for X) → C: alignment check
                                                   → D: compute metrics → E: write manifest +
                                                   metrics.csv → F: publish → G: finalize log;
                                                   EvaluationPipelineResult dataclass;
                                                   Top-level try/finally cleanup pass (mirror
                                                   R-17 from DEV-04 plan))
├── compare.py                                    (new — compare_evaluations(manifests: list[Path]) →
                                                   ComparisonReport (compatibility_key shared, metric table
                                                   side-by-side, no ranking);
                                                   CompatibilityKey dataclass (shared_dataset_id +
                                                   shared_preprocessed_id + shared_ml_dataset_sha256 +
                                                   shared_feature_set_sha256 + shared_preprocessing_config_sha256);
                                                   INCOMPATIBLE group labelled, NEVER mixed silently)
└── display.py                                    (new — format_metrics_table(result: EvaluationMetricsResult)
                                                   → str;
                                                   format_comparison_report(report: ComparisonReport)
                                                   → str;
                                                   format_manifest_path(manifest_path: Path) →
                                                   str (one-row per metric);
                                                   CLI printer uses these)
```

### 3.2. Configs hiện có

```
configs/
├── aggregation.yaml, clustering.yaml, dataset.yaml, eva03_stability_evaluation.yaml,
├── exp01..05_*.yaml, experiment.yaml, feature_engineering.yaml, features.yaml,
├── outlier.yaml, preprocessing.yaml, transformation.yaml
├── dev02_dataset_management.yaml                 (DEV-02 config — precedent)
├── dev03_preprocessing.yaml                      (DEV-03 config — precedent)
├── dev04_clustering.yaml                         (DEV-04 config — sibling precedent, mirror structure)
└── dev05_evaluation.yaml                         (NEW Phase 2 — single source of truth cho DEV-05)
```

### 3.3. Scripts hiện có

```
scripts/
├── run_fe01..fe06_*.py                           (research FE — NOT to be modified)
├── run_exp01..exp05_*.py                         (research EXP — NOT to be modified)
├── run_ml02..ml06_*.py                           (research ML — NOT to be modified)
├── run_eva0X.py, run_cp0X.py                     (research evaluation + profiling — NOT to be modified)
├── build_*.py, generate_*.py, audit_dataset.py   (other research scripts — NOT to be modified)
├── dev02_import_dataset.py                       (DEV-02 CLI — pattern to mirror)
├── dev03_preprocess_dataset.py                   (DEV-03 CLI — pattern to mirror)
├── dev04_run_clustering.py                       (DEV-04 CLI — pattern to mirror)
└── dev05_evaluate_clustering.py                  (NEW Phase 2 — CLI orchestration cho DEV-05)
```

### 3.4. Tests hiện có

```
tests/
├── test_*.py (research core — NOT to be modified)
├── test_dev02_*.py (12 files — pattern to mirror)
├── test_dev03_*.py (15 files — pattern to mirror)
├── test_dev04_*.py (11 files — pattern to mirror):
│     test_dev04_scope.py (9)
│     test_dev04_config.py (17)
│     test_dev04_storage.py (18)
│     test_dev04_manifest.py (12)
│     test_dev04_logging.py (10)
│     test_dev04_cli.py (5)
│     test_dev04_pipeline.py (7)
│     test_dev04_safety.py (26)
│     test_dev04_research_safety.py (6)
│     test_dev04_import_blocklist.py (32)
│     test_dev04_runtime_dependencies.py (16)
│   Total DEV-04: 158 tests.
└── test_dev05_*.py  (NEW Phase 2 — same coverage matrix as DEV-04, adjusted cho evaluation semantics)
```

### 3.5. Current-state cho cả 3 metric internal

- **`src/customer_segmentation/evaluation/internal_metrics.py`** chỉ có TODO + `NotImplementedError`. **Không thể reuse trực tiếp** vì code chưa tồn tại. EPIC-08 owned (theo comment trong source + SYS-04 §13.3 EPIC-08 deferred). DEV-05 sẽ wrap `sklearn.metrics.{silhouette_score, davies_bouldin_score, calinski_harabasz_score}` trực tiếp trong `customer_segmentation.prototype.evaluation.metrics` — KHÔNG sửa `customer_segmentation.evaluation.*`.
- **Tại sao wrap direct sklearn không qua research core wrapper?** Lý do:
  1. `internal_metrics.py` thuộc research core (READ-ONLY theo AGENTS.md §2.4).
  2. Adding the `_safe` wrappers would resolve EPIC-08 owned code (out of scope per phase isolation).
  3. The wrappers include semantic decisions (DBSCAN noise handling per CON-15 for silhouette + the DEV-05 prototype proposal in §5.4 for DBI/CH; edge-case statuses per SYS-04 §12.2) — DEV-05 implements these locally. The prototype-layer wrapper is functionally separate from the research-core placeholder (`internal_metrics.py` `silhouette_score_safe` etc. raise `NotImplementedError` per EPIC-08 ownership) until EPIC-08 unifies.
  4. Cross-check: research core `internal_metrics.py` is named `_safe` (signal of intent to add status+reason pattern matching SYS-04 §12.2). DEV-05 mirrors that pattern **at prototype scope**.

### 3.6. Trạng thái implementation-stage (project context)

| Stage | Status | Implication cho DEV-05 |
|---|---|---|
| EPIC-06 (5 clustering adapters) | ✅ Done | DEV-05 consumes cluster outputs from any of 5 algorithms |
| EPIC-07 (185 runs EXP-01..05) | ✅ Done | Research evidence base — DEV-05 không touch research outputs |
| EPIC-08 (EVA-01..05 + ARI/AMI) | 🟡 Active (mostly deferred; EVA-01 done) | DEV-05 prototype layer chỉ compute 3 internal metric; ARI/AMI out-of-scope |
| DEV-01..04 | ✅ TECHNICALLY_IMPLEMENTED | DEV-05 là downstream của DEV-04 |
| DEV-05 | ❌ Plan Phase 1 | This document |
| DEV-06..09 | ❌ pending | Out of scope |

---

## 4. Input/output contracts

### 4.1. Input contract — DEV-05 nhận gì từ DEV-04?

DEV-05 được gọi với 3 string identifier, resolve thành artifact chain:

```
dataset_id            : str       # DEV-02 dataset id
preprocessed_id       : str       # DEV-03 preprocessed id
clustering_id         : str       # DEV-04 clustering id (regex ^cl_[0-9a-f]{24}$)
```

Từ đó DEV-05 thực hiện 3 lần lookup và 1 lần read:

| Lookup | Artifact | Source | Schema requirement |
|---|---|---|---|
| L1 | `clustering_manifest.json` | `data/prototype/<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/` | DEV-04 `ClusteringManifest` schema v1.0.0 (per `CLUSTERING_MANIFEST_SCHEMA_VERSION`); required: `clustering_id`, `preprocessed_id`, `ml_dataset_sha256`, `algorithm`, `algorithm_family`, `experiment_id`, `cluster_labels_path`, `experiment_log_path`, `feature_set`, `feature_count`, `n_samples`, `n_clusters`, `hyperparameters`, `seed_policy`, `seed`, `config_sha256`, `research_safety` |
| L2 | `cluster_labels_<experiment_id>.parquet` | same dir as L1 | Columns: `CustomerID` (str/int), `ClusterLabel` (int64, DBSCAN noise = -1), `IsNoise` (bool); algorithm-specific extras `Probability_*` (GMM), `Membership_*` (FCM). Validate row count == L1.n_samples; validate `ClusterLabel` dtype == `int64`. |
| L3 | `experiment_log_<experiment_id>.json` | same dir as L1 | DEV-04 ExperimentResult payload; used to confirm `status = SUCCESS` (L4 acceptance) and to source `random_seed`, `execution_time`, `n_clusters`, `algorithm_version`, library_versions cho metadata reuse. |
| L4 (re-load X) | DEV-03 ML Dataset parquet | `data/prototype/.../<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_<...>.parquet` (path from DEV-03 manifest `ml_dataset_block.artifact_path`) | Re-load is required vì cluster_labels_*.parquet has ClusterLabel but **feature matrix is required to compute metric**. DEV-05 re-loads X từ DEV-03 ML Dataset (READ-ONLY), aligned by row order with `ClusterLabel`. |

**Identity link giữa DEV-05 evaluation pass và DEV-04 clustering run:**

- `evaluation_id` (DEV-05 content-addressed) trỏ tới `evaluation_manifest.json`'s `clustering_id_pointer` (= DEV-04's `clustering_id` of the input), `preprocessed_id`, `dataset_id`, `ml_dataset_sha256`, `feature_set_sha256`, `algorithm`, `algorithm_family`. Đây là provenance chain — evaluation single clustering run, linkable upstream.

**Validation pipeline trước metric compute** (parallel với ClusterRunner validation; reuse nhưng instantiated ở prototype layer):

1. `validate_evaluation_inputs(L2 + L4)` returns `EvaluationValidationReport`:
   - `cluster_labels_n_rows == X.shape[0]` (alignment). FAIL → `MetricStatus.ALIGNMENT_ERROR`.
   - `CustomerID uniqueness` (per L2 customer_metadata_df reuse nếu có, else assume positionally aligned per DEV-04 contract).
   - `X has no NaN/Inf, all numeric` (reuse `validate_clustering_matrix` flags from customer_segmentation.clustering.validation).
   - `cluster_labels unique set >= 1` (input ok).
   - `cluster_labels.min() >= noise_label` (-1 if DBSCAN).
2. Compute passes only if validation `all_passed`.

### 4.2. Invalid-input handling — what fails vs what is recorded as NOT_APPLICABLE?

DEV-05 phân biệt ba loại failure theo nguyên nhân (giữ chặt với SYS-04 §12.2 và §12.3 G5):

| Failure type | Detection | `MetricStatus` | `MetricReason` (representative) | Example |
|---|---|---|---|---|
| **Input invalid** | `validate_evaluation_inputs` failed ở Stage C trước khi vào sklearn | `MetricStatus.COMPUTATION_ERROR` | `ALIGNMENT_ERROR`, `NAN_OR_INF_INPUT`, `SCHEMA_CORRUPT`, `CLUSTER_DTYPE_INVALID`, `MANIFEST_MISSING`, `IO_ERROR` | X có NaN/Inf; `X.shape[0] != labels.shape[0]`; cluster_labels parquet corrupt; required manifest field missing |
| **Pipeline / runtime exception** | sklearn ném exception không mong đợi, hoặc trả NaN/Inf mà không raise | `MetricStatus.COMPUTATION_ERROR` | `SKLEARN_EXCEPTION`, `DEGENERATE_RESULT`, `DEGENERATE_FEATURE_SPACE` | sklearn `ValueError` ngoài các case đã liệt kê; sklearn returns `nan` thay vì raise |
| **Algorithmic degeneracy** — input hợp lệ nhưng metric không áp dụng được cho data này | Skipped sau input-validation thành công: filter noise / count unique labels → không đủ điều kiện | `MetricStatus.NOT_APPLICABLE` | `ALL_NOISE`, `SINGLE_CLUSTER`, `INSUFFICIENT_CLUSTERS` (chú thích: `DBSCAN_NOISE_EXCLUDED` KHÔNG thuộc `NOT_APPLICABLE` — nó chỉ xuất hiện ở `VALID_VALUE` xem hai dòng dưới; xem §5.3 và §5.4.6) | DBSCAN all-noise; K=1; mỗi sample một cluster riêng |
| **Manifest invalid / metric skipped** | Algorithmic-family check fails, or the evaluation pass aborts before compute | `MetricStatus.MISSING` | `ALGORITHM_FAMILY_NOT_SUPPORTED`, `DEV05_DISABLED`, `PENDING_HUMAN_REVIEW` | (placeholder, không áp dụng với 3 metric trong DEV-05 vì cả 5 algorithms đều hỗ trợ cả 3 metric) |
| **Metric computed ok, không filter noise** | sklearn trả finite float, không áp dụng filter (non-DBSCAN hoặc `noise_policy = include`) | `MetricStatus.VALID_VALUE` | `COMPUTED` (default) | normal case, K-Means K=4, etc. |
| **Metric computed ok, sau khi filter DBSCAN noise** | sklearn trả finite float trên subset post-filter, có ≥ 2 cluster non-noise | `MetricStatus.VALID_VALUE` | `DBSCAN_NOISE_EXCLUDED` (audit annotation rằng filter đã được áp dụng; KHÔNG đổi status khỏi `VALID_VALUE`) | DBSCAN run với 1194 non-noise rows pass filter và compute thành công |

Quy ước quan trọng:
- Phân biệt rõ `COMPUTATION_ERROR` (cause is reproducible/debuggable — xem log) và `NOT_APPLICABLE` (không phải bug, là thuộc tính của data + metric cho evaluation này). Cả hai đều có `metric_value = None`.
- `MISSING` chỉ dùng khi evaluation pass không thử compute (manifest invalid). Trong DEV-05, hầu hết cases sẽ rơi vào `COMPUTATION_ERROR` hoặc `NOT_APPLICABLE`.

`MetricStatus` = enum đóng (mirror EVA-01 `metric_status` pattern + SYS-04 §12.2):

```python
class MetricStatus(StrEnum):
    VALID_VALUE = "VALID_VALUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING = "MISSING"             # evaluation pass did not attempt (e.g. wrong algorithm family)
    COMPUTATION_ERROR = "COMPUTATION_ERROR"

# Subgrouping for clarity (informative; actual storage is just MetricStatus + MetricReason):
#   VALID_VALUE     → reason ∈ {COMPUTED, DBSCAN_NOISE_EXCLUDED}
#   NOT_APPLICABLE  → reason ∈ {ALL_NOISE, SINGLE_CLUSTER, INSUFFICIENT_CLUSTERS}
#   MISSING         → reason ∈ {ALGORITHM_FAMILY_NOT_SUPPORTED, DEV05_DISABLED, PENDING_HUMAN_REVIEW}
#   COMPUTATION_ERROR → reason ∈ {ALIGNMENT_ERROR, NAN_OR_INF_INPUT, SCHEMA_CORRUPT,
#                                  SKLEARN_EXCEPTION, MANIFEST_MISSING, IO_ERROR,
#                                  DEGENERATE_RESULT, DEGENERATE_FEATURE_SPACE,
#                                  CLUSTER_DTYPE_INVALID}
# Any other reason / status combination MUST raise a config-validation error during construction.
```

`MetricReason` = enum đóng với reason string (mirror `MISSING_REASON_*` taxonomy của EVA-01):

```python
class MetricReason(StrEnum):
    # VALID_VALUE reasons — usually blank or "computed"
    COMPUTED = "COMPUTED"
    # NOT_APPLICABLE reasons
    ALL_NOISE = "ALL_NOISE"
    SINGLE_CLUSTER = "SINGLE_CLUSTER"
    INSUFFICIENT_CLUSTERS = "INSUFFICIENT_CLUSTERS"
    DBSCAN_NOISE_EXCLUDED = "DBSCAN_NOISE_EXCLUDED"   # emitted on all three metrics when DBSCAN noise rows were filtered
    DEGENERATE_FEATURE_SPACE = "DEGENERATE_FEATURE_SPACE"  # X has zero variance OR singular covariance
    # COMPUTATION_ERROR reasons
    ALIGNMENT_ERROR = "ALIGNMENT_ERROR"
    NAN_OR_INF_INPUT = "NAN_OR_INF_INPUT"
    SCHEMA_CORRUPT = "SCHEMA_CORRUPT"
    SKLEARN_EXCEPTION = "SKLEARN_EXCEPTION"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    IO_ERROR = "IO_ERROR"   # storage read failure when loading X / cluster_labels
    DEGENERATE_RESULT = "DEGENERATE_RESULT"   # sklearn returned NaN/Inf without raising
    CLUSTER_DTYPE_INVALID = "CLUSTER_DTYPE_INVALID"
    # MISSING reasons
    ALGORITHM_FAMILY_NOT_SUPPORTED = "ALGORITHM_FAMILY_NOT_SUPPORTED"
    DEV05_DISABLED = "DEV05_DISABLED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
```

`metric_value` = `None` khi `MetricStatus != VALID_VALUE` (mirror SYS-04 §12.3 — no `0 / -1` defaults).

### 4.3. Output contract — DEV-05 emit gì?

Per evaluation pass (1 DEV-05 call), output layout dưới:

```
<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/
    evaluation/<evaluation_id>/
        evaluation_manifest.json            (atomic write — frozen dataclass schema v1.0.0)
        metrics_long.csv                     (3 rows: silhouette / davies_bouldin / calinski_harabasz;
                                              columns: metric_name, value, status, reason,
                                              is_diagnostic_only, lower_is_better, computation_time_seconds)
        <evaluation_id>.log                  (per-stage log; mirror DEV-04 logging)
```

**Layout rationale:** evaluation lives as **subdirectory of clustering run dir** (not flat under `clustering/`), lý do:
- Giữ ranh giới evaluation-vs-clustering rõ ràng (một cluster run có nhiều evaluation pass nếu user re-runs).
- Tránh collision với `clustering_id` dir name (evaluation_id ≠ clustering_id format).
- Garbage collection / cleanup dễ hơn (xóa clustering run → xóa cả evaluation subtree).

### 4.4. Eval `evaluation_id` derivation — content-addressed

```
evaluation_id = "ev_" + SHA256(canonical JSON(
    clustering_id,            # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    ml_dataset_sha256,
    config_sha256,           # DEV-05 config hash
    noise_policy,            # enum: INCLUDE | EXCLUDE
    metric_set_hash,         # SHA256 of frozenset(["silhouette","davies_bouldin","calinski_harabasz"]) canonical
    schema_version,          # EVALUATION_MANIFEST_SCHEMA_VERSION
))[:24]
```

Lý do design:
- Same clustering + same config + same noise_policy + same metric set = same `evaluation_id` ⇒ idempotent.
- `noise_policy` change → different `evaluation_id` ⇒ tránh silent noise-policy swap.
- `metric_set` change (thêm/bớt metric) → different `evaluation_id` ⇒ bắt buộc re-run if set changes (mirror DEV-04 derivation discipline).
- `schema_version` bump ⇒ forced re-run for new schema (defence against silently reinterpreting old manifests).

### 4.5. CLI surface (draft — subject to refinement in Phase 2)

```
python scripts/dev05_evaluate_clustering.py \
    --dataset-id <ds_xxx> \
    --preprocessed-id <pp_yyy> \
    --clustering-id <cl_xxxxxxxxxxxxxxxxxxxxxxxx> \
    [--config configs/dev05_evaluation.yaml] \
    [--noise-policy include|exclude]  (default from config)
    [--metrics silhouette,davies_bouldin,calinski_harabasz]  (CSV; default = all 3)
    [--force-recompute]                # override idempotent CACHED
    [--compare <evaluation_id1> <evaluation_id2> ...]   # comparison mode (alternative to compute)
```

CLI policy (mirror DEV-04):
- 1 evaluation pass per CLI invocation (no sweep in DEV-05 — sweep is downstream DEV's job).
- `--compare` triggers `compare_evaluations` mode with compatibility check; refuses to print table if no shared compatibility_key.
- No `--storage-root` (always read from `configs/dev02_dataset_management.yaml`).
- No `--metrics-on-research-data` flag (no such concept; CLI never loads `data/processed/final_clustering_dataset.parquet`).
- No auto-promote; CLI exit code 0 only on success; evaluation output exists regardless of metric validity.

### 4.6. Display Metrics (Jira AC-3)

**Minimum viable output (Phase 2):** CLI prints bảng metrics trên stdout. Format như:

```
Clustering: ds_xxx/pp_yyy/cl_xx...
Algorithm : kmeans (n_clusters=4)
Samples   : 4371
Metrics:
    silhouette        :   0.372  (VALID_VALUE)
    davies_bouldin    :   1.064  (VALID_VALUE)
    calinski_harabasz : 1234.567 (VALID_VALUE)
Manifest  : <path>/evaluation_manifest.json
Log       : <path>/<evaluation_id>.log
```

**Display strategy cho Phase 2** (subject to §8):
1. CLI stdout table — tối thiểu.
2. `evaluation_manifest.json` — machine-readable single source of truth.
3. `metrics_long.csv` — machine-readable, row-per-metric, future notebook display (DEV-07+) có thể read.
4. Notebook / HTML output / dashboard — **OUT OF SCOPE Phase 2** (EPIC-10 owned, SYS-06 owned).

### 4.7. Compare Experiments contract — outcome shape

`compare_evaluations([Path1, Path2, ...])` returns `ComparisonReport`:

```python
@dataclass(frozen=True)
class ComparisonReport:
    schema_version: str
    compared_at_utc: str
    groups: list[ComparisonGroup]   # grouped by compatibility_key
    incompatibility_reasons: list[IncompatibilityReason]

@dataclass(frozen=True)
class ComparisonGroup:
    compatibility_key: CompatibilityKey
    evaluations: list[EvaluationRef]    # ordered as input
    metrics_table: pd.DataFrame          # rows = evaluation_ref; cols = metric_name (multi-index: value + status)
    metric_set: frozenset[str]
```

Compatibility check (`CompatibilityKey`) required fields:
- `dataset_id` (str, equality)
- `preprocessed_id` (str, equality)
- `ml_dataset_sha256` (str, equality) **AND** `feature_set_sha256` (str, equality) **AND** `preprocessing_config_sha256` (str, equality)

If any of those differ → groups split, `incompatibility_reasons` list tells user WHY. **Never silently merge** — comparison only emits rows that share the same key. **No ranking, no winner column, no composite score** (mirror SYS-04 §12.3 G5 + AGENTS.md §2.5).

Within one group, table format:

```
                       silhouette     davies_bouldin    calinski_harabasz
                       value   status value   status   value   status
cl_xx[+]algo=kmeans    0.372   VALID  1.064   VALID    1234.57 VALID
cl_xx[+]algo=dbscan    0.281   VALID  1.402   VALID     872.10 VALID
cl_xx[+]algo=dbscan(n=-1)  --  --    --     --        --      --
```

(Algorithm column = DEV-05 does NOT add `best`/`recommended`/score columns. Just raw values + status.)

### 4.8. Storage path placement — defense in depth

`prototype_evaluation_run_dir()` returns absolute path; path-containment check via `Path.resolve() + relative_to(storage_root.resolve())` (mirror DEV-04 `prototype_clustering_*_dir`). Clustering_id regex `^cl_[0-9a-f]{24}$` enforced. Evaluation_id regex `^ev_[0-9a-f]{24}$` enforced.

---

## 5. Metric semantics và edge-case policy

### 5.1. Three metrics — semantic specification

DEV-05 covers **3 internal metrics** (per AC + SYS-04 §12.1 CON-07). Semantics locks to sklearn defaults; DEV-05 does NOT change conventions.

| Metric | sklearn function | Direction | Range (typical) | Implemented? |
|---|---|---|---|---|
| Silhouette Score | `sklearn.metrics.silence_score` | higher = better | [-1, 1] | ✅ wrapped from DEV-05 |
| Davies-Bouldin Index | `sklearn.metrics.davies_bouldin_score` | lower = better | [0, +∞) | ✅ wrapped from DEV-05 |
| Calinski-Harabasz Index | `sklearn.metrics.calinski_harabasz_score` | higher = better | [0, +∞) | ✅ wrapped from DEV-05 |

WCSS: **NOT** in scope for DEV-05 (per task brief + AC). If accidental WCSS appears in any DEV-05 output, must be flagged as out-of-spec and removed before Phase 2 implementation. (SYS-04 §12.1 has WCSS as diagnostic_only — that lives in research core, not DEV-05.)

### 5.2. Per-metric specification — Từng metric một

#### 5.2.1. Silhouette Score

| Item | Detail |
|---|---|
| **Input** | `X: np.ndarray` shape `(n_samples, n_features)`, `labels: np.ndarray` shape `(n_samples,)`, dtype int64 (incl. -1 for DBSCAN noise), `metric: Literal["euclidean"] = "euclidean"` (DEV-05 default; config could allow override in future not Phase 2) |
| **sklearn convention** | Higher = better, range [-1, 1]. sklearn raises `ValueError` if `n_labels < 2`, `n_labels > n_samples - 1`, or if `X.shape[0] != labels.shape[0]`. Per CON-15, **noise points are EXCLUDED** from X + labels BEFORE calling sklearn — i.e. DEV-05 filters out `labels == noise_label` rows before silhouette compute. |
| **Edge cases & status** | All noise (after DBSCAN filter → empty X) → `NOT_APPLICABLE / ALL_NOISE`. Single cluster (only one unique non-noise label) → `NOT_APPLICABLE / SINGLE_CLUSTER`. Two labels only `n_labels == 2`: sklearn allows it — return `VALID_VALUE`. Alignment error → `COMPUTATION_ERROR / ALIGNMENT_ERROR`. NaN/Inf in X → `COMPUTATION_ERROR / NAN_OR_INF_INPUT`. sklearn raises ValueError (other than the matrix-alignment one) → `COMPUTATION_ERROR / SKLEARN_EXCEPTION` |
| **Storage** | `silhouette_value: float | None`, `silhouette_status: MetricStatus`, `silhouette_reason: MetricReason` |
| **Diagnostic only?** | No (per SYS-04 §12.1: silhouette has `is_diagnostic_only = false`) |
| **Reproducibility** | Deterministic; no seed required |

#### 5.2.2. Davies-Bouldin Index

| Item | Detail |
|---|---|
| **Input** | `X: np.ndarray` shape `(n_samples, n_features)`, `labels: np.ndarray` shape `(n_samples,)` |
| **sklearn convention** | Lower = better, range `[0, +∞)`. sklearn raises `ValueError` if fewer than 2 clusters or unique labels > sample count. |
| **DEV-05 noise policy (PENDING_HUMAN_REVIEW — see §15 OQ-EVAL-NOISE)** | **EXCLUDE** points with `ClusterLabel = -1` from X and labels BEFORE passing them to sklearn. The reasoning — extending SYS-04 §12.2 / CON-15 uniformly to all three internal metrics — is documented in §5.4. **Conformity to sklearn default: this is a deviation.** DEV-05 records `noise_policy_used = "exclude"` in `evaluation_manifest.json` and emits `reason = DBSCAN_NOISE_EXCLUDED` for any DBSCAN run that had noise points filtered out. |
| **Edge cases & status** | After exclusion: not enough rows left (i.e. `n_samples - noise_count < 2`) → `NOT_APPLICABLE / ALL_NOISE` (DBSCAN all noise). After exclusion: only one unique non-noise label → `NOT_APPLICABLE / SINGLE_CLUSTER`. After exclusion: noisy reality but valid labeling → return numeric value as `VALID_VALUE`. sklearn raises ValueError → `COMPUTATION_ERROR / SKLEARN_EXCEPTION`. NaN/Inf in X → `COMPUTATION_ERROR / NAN_OR_INF_INPUT`. |
| **Storage** | `davies_bouldin_value: float | None`, `davies_bouldin_status: MetricStatus`, `davies_bouldin_reason: MetricReason` |
| **Diagnostic only?** | No |
| **Reproducibility** | Deterministic; no seed required |

> **Why this differs from sklearn default behaviour:** sklearn's `davies_bouldin_score` accepts any integer `labels` (including `-1`) and treats each unique label as a cluster. Including DBSCAN noise under label `-1` would silently inflate `n_clusters_realized` and the DBI pairwise scatter accounting. DEV-05 explicit uniform-exclusion is documented as the **prototype proposal**, pending human sign-off (see §15).

#### 5.2.3. Calinski-Harabasz Index

| Item | Detail |
|---|---|
| **Input** | `X: np.ndarray` shape `(n_samples, n_features)`, `labels: np.ndarray` shape `(n_samples,)` |
| **sklearn convention** | Higher = better, range `[0, +∞)`. sklearn raises `ValueError` if fewer than 2 clusters. |
| **DEV-05 noise policy (PENDING_HUMAN_REVIEW — see §15 OQ-EVAL-NOISE)** | **EXCLUDE** points with `ClusterLabel = -1` from X and labels BEFORE passing them to sklearn, just like §5.2.1 silhouette and §5.2.2 DBI. The CH formula uses `n_clusters_realized - 1` in the denominator and `n_samples - n_clusters_realized` in another term; including noise inflates `n_clusters_realized` and biases the score. **Conformity to sklearn default: this is a deviation**, explicitly recorded as the prototype proposal. See §5.4 for the consolidated rationale and §15 for the open question. |
| **Edge cases & status** | After exclusion: not enough rows left → `NOT_APPLICABLE / ALL_NOISE`. After exclusion: only one unique non-noise label → `NOT_APPLICABLE / SINGLE_CLUSTER`. Degenerate X (zero variance, singular covariance) → `COMPUTATION_ERROR / DEGENERATE_FEATURE_SPACE` if sklearn raises. NaN/Inf in X → `COMPUTATION_ERROR / NAN_OR_INF_INPUT`. sklearn raises other ValueError → `COMPUTATION_ERROR / SKLEARN_EXCEPTION`. |
| **Storage** | `calinski_harabasz_value: float | None`, `calinski_harabasz_status: MetricStatus`, `calinski_harabasz_reason: MetricReason` |
| **Diagnostic only?** | No |
| **Reproducibility** | Deterministic; no seed required |

> **Why this differs from sklearn default behaviour (same as DBI):** sklearn's `calinski_harabasz_score` treats `labels = -1` as a regular cluster. DEV-05 prototype-layer explicit filter brings all three internal metrics under a uniform policy; without it, even though silhouette excludes noise, DBI and CH could still be biased by noise — producing interpretively asymmetric evidence across algorithms.

### 5.3. Edge-case policy matrix

Status taxonomy: `VALID_VALUE` = ok, `NOT_APPLICABLE` = metric không áp dụng được cho input này, `MISSING` = không thử compute (manifest invalid / algorithm family mismatch), `COMPUTATION_ERROR` = input hợp lệ nhưng compute pipeline lỗi (sklearn exception, NaN/Inf, alignment, ...). `metric_value = None` khi `status ∈ {NOT_APPLICABLE, MISSING, COMPUTATION_ERROR}`.

| Edge case | silhouette | DBI | CH |
|---|---|---|---|
| Chỉ có một cluster non-noise sau khi filter | `NOT_APPLICABLE / SINGLE_CLUSTER` | `NOT_APPLICABLE / SINGLE_CLUSTER` | `NOT_APPLICABLE / SINGLE_CLUSTER` |
| Mỗi sample là một cluster riêng (n_samples unique non-noise labels) | sklearn raises `n_labels > n_samples - 1` → `COMPUTATION_ERROR / SKLEARN_EXCEPTION` | sklearn raises → `COMPUTATION_ERROR / SKLEARN_EXCEPTION` | sklearn raises → `COMPUTATION_ERROR / SKLEARN_EXCEPTION` |
| Labels rỗng / không align với X | impossible by construction (validation step A rejects before compute); nếu vẫn xảy ra → `COMPUTATION_ERROR / ALIGNMENT_ERROR` | same | same |
| DBSCAN noise label `-1` | **EXCLUDED** (CON-15 + DEV-05 uniform policy). All rows are noise → `NOT_APPLICABLE / ALL_NOISE`. Non-trivial non-noise subset → emit value with `reason = DBSCAN_NOISE_EXCLUDED` (per §5.4) | **EXCLUDED** (DEV-05 prototype proposal, PENDING_HUMAN_REVIEW — see §15). Same handling as silhouette | **EXCLUDED** (DEV-05 prototype proposal, PENDING_HUMAN_REVIEW — see §15). Same handling as silhouette |
| All labels = noise | `NOT_APPLICABLE / ALL_NOISE` | `NOT_APPLICABLE / ALL_NOISE` | `NOT_APPLICABLE / ALL_NOISE` |
| Feature matrix có NaN/Inf | `COMPUTATION_ERROR / NAN_OR_INF_INPUT` | same | same |
| Sai kích thước `X.shape[0] != labels.shape[0]` | `COMPUTATION_ERROR / ALIGNMENT_ERROR` | same | same |
| ClusterLabel dtype không phải int64 | `COMPUTATION_ERROR / SCHEMA_CORRUPT` (validation stage rejects; if it slips through, sklearn raises) | same | same |
| Manifest corrupt / required field missing | `MISSING / MANIFEST_MISSING` (whole evaluation pass aborts before compute; metric row written but with no value) | same | same |
| Algorithm family không hỗ trợ metric nào (n/a in DEV-05 scope) | `MISSING / ALGORITHM_FAMILY_NOT_SUPPORTED` | same | same |
| Storage read / I/O exception khi load cluster_labels / X | `COMPUTATION_ERROR / IO_ERROR` (manifest still written so audit can see failure) | same | same |
| sklearn raises exception không nằm trong các case đã liệt kê | `COMPUTATION_ERROR / SKLEARN_EXCEPTION` (raw exception message NOT surfaced; reason code only — siehe R-EVAL-12) | same | same |
| Sklearn trả NaN/Inf (rare nhưng có thể xảy ra ở degenerate input) | `COMPUTATION_ERROR / DEGENERATE_RESULT` | same | same |

**Quy ước phân biệt ba loại failure** (mirror SYS-04 §12.2, phân biệt rõ theo yêu cầu revision):
- **`COMPUTATION_ERROR`**: pipeline/runtime failure (sklearn exception, NaN/Inf, alignment, storage I/O, schema corrupt). Cause is reproducible / debuggable; dev đọc log tìm được root cause.
- **`NOT_APPLICABLE`**: input hợp lệ nhưng metric không hợp lệ trên data này (e.g. ALL_NOISE, SINGLE_CLUSTER). Không phải bug — nó là thuộc tính của data + metric. Có thể reporting "metric không áp dụng" mà không sai.
- **`MISSING`**: evaluation pass không thử compute (ví dụ algorithm family mismatch với metric — DEV-05 không có case này vì cả 5 algorithms đều hỗ trợ 3 metric; placeholder cho future use).

`metric_value = None` cho cả ba nhóm failure trên. **Tuyệt đối không thay bằng `0` hoặc `-1`.**

### 5.4. DBSCAN noise policy — how DEV-05 handles `-1`

> **Important status disclaimer.** This section is the **prototype-layer proposal** for DEV-05. Concretely:
>
> - **Locked at research layer (SYS-04 §12.2 + CON-15):** DBSCAN noise must be excluded from **silhouette** computation. This is research methodology and is not changed by DEV-05.
> - **Prototype-layer proposal (DEV-05, status `WORKING_ASSUMPTION` until §15 OQ-EVAL-NOISE is resolved):** extend the same uniform **exclude** treatment to **Davies-Bouldin** and **Calinski-Harabasz** so that all three internal metrics use the same point-set. This is a documented deviation from sklearn's defaults for DBI/CH and is **gating on human review** (see §15).
> - DEV-05 does NOT alter the upstream `cluster_labels_*.parquet` artifact nor any relabel / permutation mapping. The noise filter happens **in-memory only**, after the alignment check, before calling sklearn.

#### 5.4.1. Policy text (canonical)

DEV-05 applies DBSCAN noise handling as a **single uniform policy** across all three internal metrics:

- **Default policy:** `noise_policy = "exclude"`.
- **Effect:** when `algorithm_family = "density_based"` (i.e. clustering run used DBSCAN), rows where `ClusterLabel == noise_label` (i.e. `ClusterLabel == -1`) are **removed from the in-memory copy of X and labels** before being passed to any of the three sklearn metric functions. The original `cluster_labels_*.parquet` is untouched.
- **Scoping:** the policy applies uniformly to silhouette / DBI / CH. There is no per-metric override.
- **Recorded:** `noise_policy_used` is a frozen field in `evaluation_manifest.json`. For non-DBSCAN algorithms, `noise_policy_used = "exclude"` is still recorded (and `noise_count = null`, `noise_ratio = null`), making the manifest self-describing rather than algorithm-dependent.

#### 5.4.2. Why uniform exclusion (not "silhouette-only")

The user-facing motivation is descriptive-comparison consistency: if silhouette excludes noise but DBI and CH count it (sklearn default), the three values cannot be jointly interpreted for the same clustering — `n_samples_used_for_compute` differs across metrics within the same evaluation. This makes "side-by-side" reporting (per AC-4) less honest than it appears.

The technical motivation: DBI's pairwise scatter accounting inflates when `-1` is treated as an extra cluster (DBI is meant for compact, well-separated clusters, not noise); CH's `n_clusters_realized - 1` denominator and trace terms are biased when noise is counted as a cluster.

The arguments **against** uniform exclusion: it deviates from sklearn default for DBI/CH (so the values are not directly comparable to a "naïve sklearn" call), and it forces a methodology decision that the research layer (SYS-04 / EPIC-08) has not yet locked at the level of DBI/CH.

#### 5.4.3. Configurability — override per call

The `--noise-policy` CLI flag (and the `noise_policy:` YAML key) is a `Literal["include", "exclude"]` selector. **For both values, no silent metric emission occurs:** if a researcher picks `include`, the manifest records `noise_policy_used = "include"`, and the run is idempotent-distinct (different `evaluation_id` derivation; see §4.4).

The default in `configs/dev05_evaluation.yaml` is `exclude`. The CLI default is also `exclude`. Switching the default later requires editing the config + manifest schema — clearly a methodology change requiring an ADR or an entry in completion summary §15.

#### 5.4.4. What gets reported in the manifest and CSV (DBSCAN-specific row surface)

In addition to the three metric entries (each with `value | status | reason | is_diagnostic_only | lower_is_better | computation_time_seconds`), the manifest must surface provenance numbers that allow reviewers to audit the noise filter effect without re-running the metric:

| Field | Type | Source | Meaning |
|---|---|---|---|
| `n_samples_input` | `int` | `clustering_manifest.json::n_samples` | Total rows in input cluster_labels. Equal to `X.shape[0]`. |
| `noise_count` | `int \| null` | computed from `labels` | Number of rows with `ClusterLabel == -1`. `null` for non-DBSCAN. |
| `noise_ratio` | `float \| null` | computed | `noise_count / n_samples_input`. `null` for non-DBSCAN. |
| `n_samples_used_for_compute` | `int` | computed | Rows actually passed to sklearn after noise filter (and after the rare cluster-relabel sanity check). Equal to `n_samples_input - noise_count` when `noise_policy_used = "exclude"` and algorithm is DBSCAN; equal to `n_samples_input` when policy is `include` or algorithm is non-DBSCAN. |
| `n_clusters_realized` | `int` | computed | Unique non-noise labels (under exclude) or unique labels (under include). |
| `noise_policy_used` | `Literal["include","exclude"]` | recorded | The actual policy applied. |

The CSV (`metrics_long.csv`) keeps **exactly 3 rows**, one per metric (per §7.3). The provenance numbers above live in the JSON manifest only. Reporting them as a separate CSV is **out of scope** for DEV-05 Phase 2 (would expand scope beyond the 3 metric rows).

#### 5.4.5. Things DEV-05 does NOT do for noise (immutability discipline)

AGENTS.md §3 row "Clustering" + §2.1 explicitly forbid silently modifying labels. DEV-05:

- Does **NOT** modify the upstream `cluster_labels_*.parquet`. The noise filter is in-memory only.
- Does **NOT** relabel noise (`-1` → another integer) for any reason.
- Does **NOT** drop, recode, or treat DBSCAN noise as a regular cluster for output storage.
- Does **NOT** introduce a "best-effort" imputation for missing labels or features.
- Does **NOT** apply Hungarian matching / cluster permutation to align labels across evaluations. (EPIC-08 owned.)
- Does **NOT** alter DEV-03 ML Dataset parquet, DEV-04 `experiment_log_*.json`, or any research-core artifact.

Any methodology decision touching noise / label semantics must be discussed as OQ in §15 (do not auto-resolve).

#### 5.4.6. Interaction with edge cases (uniform exclusion view)

After applying `noise_policy = exclude`:

- **All rows are noise** (DBSCAN emitted only `-1`): `n_samples_used_for_compute == 0` for **all three metrics** → each entry is `NOT_APPLICABLE / ALL_NOISE`. The manifest still has 3 rows; the JSON still has the provenance fields above.
- **After exclusion, fewer than 2 unique non-noise labels** (e.g. DBSCAN returned one cluster + noise): each entry is `NOT_APPLICABLE / SINGLE_CLUSTER` for silhouette, DBI, CH — sklearn would raise `ValueError` if called; we capture it as `NOT_APPLICABLE` because the input (after filter) is formally degenerate for that metric's definition.
- **Non-DBSCAN runs:** `noise_count = null`, `noise_ratio = null`, but the filter is a **no-op** since the input labels never include `-1`. Numbers are computed identically. `n_samples_used_for_compute == n_samples_input`.

### 5.5. Metric status semantics — lock-down (no fake defaults)

Mirror SYS-04 §12.3 G5 + the per-AC requirements in §4.2. The following rules are **non-negotiable** for Phase 2 implementation:

1. **`metric_value = None` iff `metric_status != VALID_VALUE`.**
2. **No fake defaults** (no `0`, no `-1`, no `0.0`, no `numpy.nan` substitution, no string `"n/a"` cast). Per SYS-04 §12.3. NaN-as-value is **also forbidden** — `None` only.
3. **`status` enum** is closed: `{VALID_VALUE, NOT_APPLICABLE, MISSING, COMPUTATION_ERROR}`.
4. **`reason` enum** is closed (see §4.2). One reason per entry; for `VALID_VALUE` the only valid reason is `COMPUTED`.
5. **Status surfaced in every output** (CSV row, JSON manifest, CLI table). Consumer of a metrics CSV must always look at `status` before trusting `value`.
6. **Computation_time_seconds** for each metric is set even when status != VALID_VALUE (records "how long did we spend trying").
7. **`lower_is_better`** is `True` only for DBI; `False` for silhouette and CH (per sklearn convention).
8. **`is_diagnostic_only`** is `False` for all three DEV-05 metrics (WCSS, which would be `True`, is out-of-scope per AC and §1.2; it lives in research core if ever needed).

DEV-05 **MUST NOT** coerce exception objects into `0` or `-1` to "make the metric numeric." The reason string is the contract for failure diagnosis; numeric fake values would hide it.

### 5.6. Không tự ý xử lý noise / cluster-relabel / change labels

AGENTS.md §3 row "Clustering" và §2.1 nghiêm cấm thay đổi labels. DEV-05 **không**:

- **Sửa / overwite / relabel / drop noise rows** trong `cluster_labels_*.parquet`. Filter noise chỉ xảy ra trên một **bản copy in-memory** của `X` và `labels` trước khi gọi sklearn, theo `noise_policy` (§5.4).
- **Lưu lại** mảng `X` / `labels` đã filter xuống disk (manifest lưu noise count + n_samples_used_for_compute để audit; không lưu bản đã filter).
- Coi noise là một cluster thông thường (sklearn default sẽ làm vậy cho DBI/CH; DEV-05 chủ động ngăn theo §5.4).
- Đổi labels từ `-1` sang integer nào khác.
- Relabel clusters (Hungarian / permutation mapping) — đó là EPIC-08 owned.
- Filter / drop cluster members ngoài noise filter nêu trên.
- Apply any "best-effort" imputation, capping, outlier removal, hay normalization. Nếu feature matrix có NaN/Inf → `COMPUTATION_ERROR / NAN_OR_INF_INPUT`, không tự "fix".

Mọi quyết định tác động tới noise/label semantics là **methodology decision** → ghi OQ-EVAL-NOISE trong §15 (không tự giải quyết).

---

## 6. Module/API design

### 6.1. Public API surface — `customer_segmentation.prototype.evaluation`

```python
# Core entry point
def run_evaluation_pipeline(
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    *,
    config_path: str | Path | None = None,
    noise_policy: Literal["include", "exclude"] | None = None,
    metrics: list[str] | None = None,        # subset of ["silhouette", "davies_bouldin", "calinski_harabasz"]
    force_recompute: bool = False,
) -> EvaluationPipelineResult: ...

@dataclass(frozen=True)
class EvaluationPipelineResult:
    evaluation_id: str
    clustering_id: str                     # upstream DEV-04 id
    dataset_id: str
    preprocessed_id: str
    storage_root: Path
    evaluation_dir: Path
    manifest_path: Path
    metrics_csv_path: Path
    log_path: Path
    lifecycle: str                          # "SUCCESS" | "CACHED" | "FAILED"
    duration_seconds: float
    metrics_result: EvaluationMetricsResult  # 3-metric block
    manifest: EvaluationManifest | None
    stage_logs: list[dict[str, Any]]

# Metric compute primitive (callable for tests / notebook use)
@dataclass(frozen=True)
class EvaluationMetricsResult:
    silhouette: EvaluationMetricEntry
    davies_bouldin: EvaluationMetricEntry
    calinski_harabasz: EvaluationMetricEntry
    n_samples_input: int                   # rows in cluster_labels at input time
    n_samples_used_for_compute: int         # rows actually passed to sklearn (after noise filter)
    n_clusters_realized: int                # unique non-noise label count after filter
    noise_count: int | None                 # DBSCAN only (= labels == -1 count); null otherwise
    noise_ratio: float | None               # DBSCAN only (= noise_count / n_samples_input); null otherwise
    computation_time_seconds: float
    noise_policy_used: str                 # "include" | "exclude"
    algorithm_family: str                  # from DEV-04 manifest
    algorithm: str                         # from DEV-04 manifest

@dataclass(frozen=True)
class EvaluationMetricEntry:
    metric_name: str       # "silhouette" | "davies_bouldin" | "calinski_harabasz"
    value: float | None
    status: MetricStatus
    reason: MetricReason
    is_diagnostic_only: bool = False
    lower_is_better: bool = False
    computation_time_seconds: float | None = None

# Manifest
@dataclass(frozen=True)
class EvaluationManifest:
    schema_version: str
    evaluation_id: str
    scope: str                              # always "EVALUATED_PROTOTYPE"
    clustering_id: str                      # upstream
    preprocessed_id: str
    dataset_id: str
    ml_dataset_sha256: str
    feature_set_sha256: str                 # derived from feature_set contents
    preprocessing_config_sha256: str       # from DEV-03 manifest config_hash
    algorithm: str
    algorithm_family: str
    algorithm_version: str
    n_samples: int
    n_features: int
    feature_set: list[str]
    feature_count: int
    hyperparameters: dict[str, Any]
    seed_policy: str                       # from DEV-04 cluster manifest
    seed: int | None
    noise_policy_used: str
    metric_set: list[str]                  # ["silhouette", "davies_bouldin", "calinski_harabasz"]
    metrics: EvaluationMetricsResult
    environment: EnvironmentBlock
    created_utc: str
    last_seen_utc: str
    log_file: str
    research_safety: ResearchSafetyBlock    # automatically_promoted_to_research=False,
                                           # scope="EVALUATED_PROTOTYPE",
                                           # appeared_in_research_evidence=False
```

### 6.2. Module dependency tree (no circular)

```
customer_segmentation.prototype.evaluation
├── scope                 (StrEnum: EvaluatedScope, MetricName, MetricStatus, MetricReason; NO deps)
├── config_loader         (Dev05Config dataclass; depends on scope + storage)
├── storage               (path resolution + content-addressed id; depends on dev02 storage helper)
├── manifest              (frozen dataclass; depends on scope + result)
├── metrics               (EvaluationMetricsResult builder; depends on scope; calls sklearn.metrics)
├── logging_config        (PerStageLogger facade; depends on scope)
├── compare               (CompatibilityKey + ComparisonReport + compare_evaluations; depends on
│                          manifest + storage)
├── display               (format_* functions; depends on metrics + manifest + compare)
└── pipeline              (run_evaluation_pipeline; orchestrates all of the above; top-level
                            try/finally cleanup pass — MIRROR DEV-04 plan §6.5 R-17 + F1 invariant)
```

External deps:

- `customer_segmentation.clustering.validation.validate_clustering_matrix` (read-only) — for validating X before metric compute.
- `customer_segmentation.clustering.config.compute_text_sha256` (read-only) — for DEV-05 config_sha256.
- `customer_segmentation.transformation.versioning.compute_file_sha256` (read-only) — for X / labels / manifest file SHA.
- `customer_segmentation.dataset_management.storage.resolve_storage_root` (read-only) — for shared storage root.
- `customer_segmentation.prototype.preprocessing.storage.DEFAULT_DEV02_CONFIG_PATH` (read-only).
- `sklearn.metrics.{silhouette_score, davies_bouldin_score, calinski_harabasz_score}` (DEPS in pyproject.toml; scikit-learn>=1.4).

**Forbidden:** import from `customer_segmentation.evaluation.*` (research core) at runtime in DEV-05. Reason: those are research-owned and may carry contract changes from EPIC-08 (EVA-02/03 in active state) which would create a binding contract we cannot guarantee mirror. **Phase 2 implementation must add explicit `import_blocklist` test** denying `customer_segmentation.evaluation.*` (mirror DEV-04 `test_dev04_import_blocklist.py`).

### 6.3. Error hierarchy (mirror DEV-04)

```python
class Dev05Error(ValueError): ...                    # base
class Dev05ConfigError(Dev05Error): ...              # YAML malform
class Dev05StoragePathError(Dev05Error): ...         # path escape / id regex
class Dev05ManifestCorrupt(Dev05Error): ...          # lookup manifest unreadable
class Dev05ManifestSchemaError(Dev05Error): ...      # schema missing required field
class Dev05AlignmentError(Dev05Error): ...           # X.shape vs labels.shape
class Dev05CollisionError(Dev05Error): ...           # evaluation_id collision (vanishingly small)
class Dev05UnsupportedMetricError(Dev05Error): ...   # unknown metric name in CLI/config
class Dev05IncompatibleComparisonError(Dev05Error):  # for --compare when no shared key
```

All errors are fail-closed; no silent override.

### 6.4. Side-effect discipline

- DEV-05 NEVER writes to:
  - `data/raw/**`
  - `data/processed/**`
  - `data/interim/**`
  - `reports/**` (except as `gitignored` prototype artefacts — but reports is `gitignored`; **still** DO NOT write here per ADR scope)
  - `data/prototype/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/` **other than the evaluation/ subtree** (DEV-04 owns that dir; appending `evaluation/` is the only legitimate write).
  - DEV-04 staging / backup / failed-tracking dirs (`_staging_*`, `_backup_*`, `_failed_*`).
  - DEV-04 clustering_manifest.json (READ-ONLY after publish).

- DEV-05 NEVER mutates:
  - DEV-03 ML Dataset parquet.
  - DEV-04 cluster_labels_*.parquet (READ-ONLY).
  - DEV-04 experiment_log_*.json (READ-ONLY).
  - DEV-03 manifest (READ-ONLY).
  - Research-core artefacts.

- DEV-05 ONLY writes to:
  - `data/prototype/<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/evaluation/<evaluation_id>/` (new subdir of clustering id dir).

This discipline is verified by **research_safety tests** (mirror `test_dev04_research_safety.py` and `test_dev04_import_blocklist.py`).

---

## 7. Storage schema và path

### 7.1. Path layout (per clustering run, optional)

```
<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/
├── clustering_manifest.json           (DEV-04 — READ-ONLY for DEV-05)
├── cluster_labels_<experiment_id>.parquet   (DEV-04 — READ-ONLY for DEV-05)
├── experiment_log_<experiment_id>.json      (DEV-04 — READ-ONLY for DEV-05)
├── algorithm_output_<experiment_id>.parquet (DEV-04, GMM/FCM only — READ-ONLY)
├── <clustering_id>.log                      (DEV-04 — READ-ONLY)
└── evaluation/                              (NEW — DEV-05 owns this subtree)
    └── <evaluation_id>/
        ├── evaluation_manifest.json      (DEV-05 — atomic write)
        ├── metrics_long.csv              (DEV-05 — 3 rows + header)
        └── <evaluation_id>.log           (DEV-05 — per-stage log)
```

Lý do dùng subdirectory `evaluation/<evaluation_id>/` thay vì flat `evaluation/<evaluation_id>/`:

- Giữ ranh giới evaluation-vs-clustering rõ ràng.
- Cho phép nhiều evaluation pass per clustering run (nếu user re-run với noise_policy khác hoặc config_sha256 khác → khác evaluation_id, hai dir cùng tồn tại).
- Tránh collision `evaluation_id` với `clustering_id` namespace.

### 7.2. `evaluation_manifest.json` schema (frozen dataclass → JSON)

```json
{
  "schema_version": "1.0.0",
  "evaluation_id": "ev_xxxxxxxxxxxxxxxxxxxxxxxx",
  "scope": "EVALUATED_PROTOTYPE",
  "clustering_id": "cl_xxxxxxxxxxxxxxxxxxxxxxxx",
  "preprocessed_id": "pp_xxxxxxxxxxxxxxxxxxxxxxxx",
  "dataset_id": "ds_xxxxxxxxxxxxxxxxxxxxxxxx",
  "ml_dataset_sha256": "<64-hex>",
  "feature_set_sha256": "<64-hex of sorted joined feature names>",
  "preprocessing_config_sha256": "<64-hex from DEV-03 manifest config_hash>",
  "algorithm": "kmeans",
  "algorithm_family": "hard",
  "algorithm_version": "sklearn_1.5.x",
  "n_samples": 4371,
  "n_features": 14,
  "feature_set": ["Recency", "Frequency", "Monetary", "Tenure", ...],
  "feature_count": 14,
  "hyperparameters": {"n_clusters": 4, "init": "k-means++", ...},
  "seed_policy": "stochastic",
  "seed": 42,
  "noise_policy_used": "exclude",
  "metric_set": ["silhouette", "davies_bouldin", "calinski_harabasz"],
  "metrics": {
    "silhouette":        {"value": 0.372, "status": "VALID_VALUE", "reason": "COMPUTED",
                          "is_diagnostic_only": false, "lower_is_better": false,
                          "computation_time_seconds": 0.83},
    "davies_bouldin":    {"value": 1.064, "status": "VALID_VALUE", "reason": "COMPUTED", ...},
    "calinski_harabasz": {"value": 1234.567, ...}
  },
  "n_samples_input": 4371,
  "n_samples_used_for_compute": 4371,
  "n_clusters_realized": 4,
  "noise_count": null,
  "noise_ratio": null,
```

Example — DBSCAN run with noise (after filter):

```json
{
  "schema_version": "1.0.0",
  "evaluation_id": "ev_xxxxxxxxxxxxxxxxxxxxxxxx",
  "scope": "EVALUATED_PROTOTYPE",
  "clustering_id": "cl_xxxxxxxxxxxxxxxxxxxxxxxx",
  "preprocessed_id": "pp_xxxxxxxxxxxxxxxxxxxxxxxx",
  "dataset_id": "ds_xxxxxxxxxxxxxxxxxxxxxxxx",
  "ml_dataset_sha256": "<64-hex>",
  "feature_set_sha256": "<64-hex of sorted joined feature names>",
  "preprocessing_config_sha256": "<64-hex from DEV-03 manifest config_hash>",
  "algorithm": "dbscan",
  "algorithm_family": "density_based",
  "algorithm_version": "sklearn_1.5.x",
  "n_samples": 4371,
  "n_features": 14,
  "feature_set": ["Recency", "Frequency", "Monetary", "Tenure", ...],
  "feature_count": 14,
  "hyperparameters": {"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
  "seed_policy": "deterministic",
  "seed": null,
  "noise_policy_used": "exclude",
  "metric_set": ["silhouette", "davies_bouldin", "calinski_harabasz"],
  "metrics": {
    "silhouette":        {"value": 0.281, "status": "VALID_VALUE", "reason": "DBSCAN_NOISE_EXCLUDED", ...},
    "davies_bouldin":    {"value": 1.402, "status": "VALID_VALUE", "reason": "DBSCAN_NOISE_EXCLUDED", ...},
    "calinski_harabasz": {"value": 872.10, "status": "VALID_VALUE", "reason": "DBSCAN_NOISE_EXCLUDED", ...}
  },
  "n_samples_input": 4371,
  "n_samples_used_for_compute": 1194,
  "n_clusters_realized": 2,
  "noise_count": 3177,
  "noise_ratio": 0.7268359643102265,
  "noise_policy_used": "exclude",
  "environment": {
    "python": "3.11.x", "platform": "Linux", "release": "...", "machine": "x86_64",
    "key_libraries": {"numpy": "...", "pandas": "...", "scikit-learn": "..."}
  },
  "created_utc": "2026-10-09T...Z",
  "last_seen_utc": "2026-10-09T...Z",
  "log_file": "ev_xxxx....log",
  "research_safety": {
    "automatically_promoted_to_research": false,
    "scope": "EVALUATED_PROTOTYPE",
    "appeared_in_research_evidence": false,
    "read_only_paths_unmodified": ["data/raw/primary", "data/processed", "reports", ...]
  }
}
```

### 7.3. `metrics_long.csv` schema

```csv
metric_name,value,status,reason,is_diagnostic_only,lower_is_better,computation_time_seconds
silhouette,0.372,VALID_VALUE,COMPUTED,false,false,0.83
davies_bouldin,1.064,VALID_VALUE,COMPUTED,false,true,0.21
calinski_harabasz,1234.567,VALID_VALUE,COMPUTED,false,false,0.04
```

Per row per metric. NaN → literal `""` (empty) when status != VALID_VALUE; the `status` column tells reader not to read `value`. (DEFENSIVE: no `MISSING` literal here — that's a research-core pattern. DEV-05 uses blank+status pattern to keep CSV round-trip clean.)

Phase 2 tests must assert round-trip invariants:
1. CSV row count == `len(metric_set)` (always 3 for default config).
2. For each row: `status == "VALID_VALUE" ⟺ value is non-null float`.
3. Read-back yields same EvaluationMetricsResult dict.

### 7.4. Naming convention

| Object | Format | Example | Validation |
|---|---|---|---|
| `evaluation_id` | `^ev_[0-9a-f]{24}$` | `ev_abcdef0123456789abcdef01` | regex enforced in `derive_evaluation_id` |
| Run directory | `<evaluation_id>` | `ev_abcdef0123456789abcdef01/` | sanity regex on traversal defence |
| Manifest filename | `evaluation_manifest.json` | same | constant |
| Metrics CSV | `metrics_long.csv` | same | constant |
| Log file | `<evaluation_id>.log` | `ev_xxx.log` | inferred id |

### 7.5. Collision + idempotency

`find_existing_evaluation(...)` mirrors `find_existing_clustering` (DEV-04):

- Same `evaluation_id` + same canonical payload (10 fields: clustering_id, preprocessed_id, dataset_id, ml_dataset_sha256, config_sha256, noise_policy, metric_set_hash, schema_version, algorithm_family, hyperparameters) → `CACHED`.
- Same id, different payload → `Dev05ManifestCorrupt` or `Dev05CollisionError` depending on whether the stored manifest is parseable.
- `--force-recompute` overrides CACHED → re-compute + atomic rename staging → final.

### 7.6. Atomic write

`write_evaluation_manifest` (mirror `write_clustering_manifest` from DEV-04):

- Write to `evaluation_manifest.json.tmp` in same dir.
- `os.replace(tmp, final)` on success.
- On exception: `tmp.unlink()` (best-effort `suppress(OSError)`).

### 7.7. Backup / recovery (R-13 mirror)

If a previous `--force-recompute` crashed, `_staging_<uuid>/` or `_backup_<uuid>/` may exist. DEV-05 implements `recover_orphan_backups` mirroring DEV-04 R-13:

- Scan `evaluation/` for `_backup_*` dirs from another run_uuid.
- For each, if `final_dir/` doesn't exist: atomic rename `backup_dir/<evaluation_id>` → `final_dir`.
- NEVER restore from `_backup_*_corrupt/`.
- Skip malformed backup containers (best effort, log + skip).

### 7.8. Path containment defence

`Path.resolve() + relative_to(storage_root.resolve())` — every computed path inside `prototype_evaluation_*_dir()` must fail-closed if it escapes storage root. Regex check on `evaluation_id` (`^ev_[0-9a-f]{24}$`) before any filesystem call.

---

## 8. Display strategy

### 8.1. Acceptance criterion reframing

AC-3 says "metrics hiển thị" (metrics are displayed). UI unspecified. AGENTS.md §6 + ADR-0005 Option A forbid building backend/API/frontend/UI. Therefore **minimum-viable display**:

1. CLI table on stdout (default in `--compute` mode) — always-on.
2. `evaluation_manifest.json` — machine-readable; future tools can read it (notebook downstream DEVs).
3. `metrics_long.csv` — machine-readable; copy-pasteable into notebook for ad-hoc viewing.
4. (Future, out of scope Phase 2): notebook / HTML / dashboard — owned by EPIC-10 / SYS-06; reference is `docs/system/ui-prototype/index.html`.

### 8.2. CLI display (Phase 2 minimum)

```
$ python scripts/dev05_evaluate_clustering.py \
    --dataset-id ds_xxx --preprocessed-id pp_yyy --clustering-id cl_xx...

[INFO] DEV-05 evaluation pipeline starting
[INFO] Clustering: cl_xx...
       Algorithm : kmeans (n_clusters=4, seed=42)
       Samples   : 4371
       Feature set: 14 features (RFM Extended)
[INFO] Computing 3 metrics ... [OK]
[INFO] Metrics:
       silhouette        :   0.372  [VALID_VALUE]   (higher = better)
       davies_bouldin    :   1.064  [VALID_VALUE]   (lower  = better)
       calinski_harabasz : 1234.57 [VALID_VALUE]   (higher = better)
[INFO] Manifest : /.../evaluation_manifest.json
[INFO] CSV      : /.../metrics_long.csv
[OK]   Lifecycle : SUCCESS (duration: 1.234s)
```

In fail cases:

```
[ERROR] COMPUTATION_ERROR / SKLEARN_EXCEPTION (matrix not symmetric)
       silhouette        :   --    [COMPUTATION_ERROR]
       davies_bouldin    :   --    [COMPUTATION_ERROR]
       calinski_harabasz :   --    [COMPUTATION_ERROR]
[ERROR] Manifest : /.../evaluation_manifest.json (still written with status)
[FAIL] Lifecycle : FAILED (duration: 0.512s)
```

### 8.3. Notebook / programmatic display (helper, no UI)

`customer_segmentation.prototype.evaluation.display.format_metrics_table(result: EvaluationMetricsResult) -> str` returns a printable table (textwrap-aligned columns). Notebook-friendly: `print(format_metrics_table(result))`.

`format_comparison_report(report: ComparisonReport) -> str` mirrors for comparison output.

These are utility functions; NOT a UI backend. They honour the same restrictions (no ranking, no winner column).

### 8.4. What DEV-05 does NOT do for display

- No HTML page.
- No PNG / chart.
- No dashboard.
- No API endpoint.
- No notebook authoring (Phase 2).
- No auto-launch of any UI.

### 8.5. Trade-offs for display strategy (for §15 decision)

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: CLI-only | Simple, Option A compliant, no UI deps | Cannot view from Jupyter / browser interactively | **PROPOSED** for Phase 2 |
| B: CLI + HTML static report | Viewable in browser via single file; mirrors EVA-01/02 markdown | Requires tiny HTML template + slug; minor new code surface | DEFERRED to future DEV (DEV-09?) |
| C: CLI + notebook sample | Demonstrable in notebooks; reaches researcher | New notebook file; reviewers may treat as "evaluation" rather than prototype | DEFERRED to future DEV |
| D: Backend / API | SYS-05 §9.5 group E reference | Violates ADR-0005 Option A | EXCLUDED |

---

## 9. Experiment comparison semantics

### 9.1. Scope of comparison

"Compare Experiments" trong task brief có hai cách đọc:

1. Compare **multiple evaluation passes** (multiple `evaluation_id`s) that share a compatible upstream (cùng DEV-03 ML Dataset, cùng DEV-04 algorithm set hoặc khác algorithm nhưng input tương thích). Đây là cách DEV-05 implement.
2. Compare **multiple experiments** từ EPIC-07 research layer (185 runs). **OUT OF SCOPE DEV-05** — research layer is owned by EPIC-08 / EVA-01..05.

DEV-05 chỉ so sánh evaluations **trong prototype layer** (DEV-04 outputs). Và phải đảm bảo "comparable" trước khi so sánh.

### 9.2. Compatibility check — `CompatibilityKey`

`compare_evaluations([Path1, Path2, ...])` chỉ emit row trong bảng khi các evaluations **chia sẻ** tất cả:

- `dataset_id` (string equality)
- `preprocessed_id` (string equality)
- `ml_dataset_sha256` (string equality) — guarantee same feature matrix file.
- `feature_set_sha256` (string equality, derived from DEV-04 manifest feature_set canonical) — guarantee same column space.
- `preprocessing_config_sha256` (string equality, from DEV-03 manifest's `config_hash`) — guarantee same preprocessing.

Nếu **bất kỳ** field nào khác → evaluation đó bị tách nhóm (`ComparisonGroup`). Trong `ComparisonReport.incompatibility_reasons`, user thấy:

```
Group A (clusterings sharing the same ML Dataset + preprocessing + feature space):
   ev_x (clustering=cl_a, algorithm=kmeans)
   ev_y (clustering=cl_b, algorithm=dbscan)

Group B (incompatible with Group A — different ml_dataset_sha256):
   ev_z (clustering=cl_c, algorithm=gmm)
   Reason : ml_dataset_sha256 mismatch ('ba54...' vs 'df53...')

Group C (incompatible with above — different preprocessing_config_sha256):
   ev_w (clustering=cl_d, algorithm=fuzzy_cmeans)
   Reason : preprocessing_config_sha256 mismatch
```

Within one group, comparison emits values + statuses per metric, side-by-side.

### 9.3. Per-row provenance — every compare row keeps audit info

Every row in the comparison table is a `(evaluation, metric_value)` pair. To prevent silent comparisons across inputs that have been preprocessed differently or filtered differently, each comparison row must surface these provenance fields **alongside** the metric values. Without them, "DBI = 1.402 in row A vs DBI = 0.95 in row B" would be unreadable.

| Per-row provenance field | Where it comes from | Why included |
|---|---|---|
| `evaluation_id` | argument passed to `compare_evaluations` | row reference key |
| `clustering_id` | `evaluation_manifest.json::clustering_id` | upstream pointer to DEV-04 run |
| `algorithm` + `algorithm_version` | `evaluation_manifest.json::algorithm[_version]` | which algorithm computed labels |
| `seed` / `seed_policy` | `evaluation_manifest.json` | traceability |
| `n_samples_input` | manifest | input size |
| `n_samples_used_for_compute` | manifest (post-filter) | actual sample count used by sklearn |
| `noise_count` | manifest (`null` if non-DBSCAN) | shows whether filter was active |
| `noise_ratio` | manifest (`null` if non-DBSCAN) | same, normalised |
| `noise_policy_used` | manifest | which policy was applied |

A comparison **must explicitly flag** rows where `(n_samples_used_for_compute, noise_count, noise_ratio, noise_policy_used)` differ across the group. If two evaluations were computed on different sample subsets (e.g. one with `noise_count = 0` and one with `noise_count = 3177`), the comparison output must surface that difference as a textual caveat under the table — **not** silently interpret the metric values as comparable. Concretely: if you see DBSCAN with `n_samples_used_for_compute = 1194` next to K-Means with `n_samples_used_for_compute = 4371`, the report says so plainly and refuses to imply equivalence.

Note that **a metric value computed on a smaller sample set is not, by itself, "better" or "worse" than one computed on a larger set.** DEV-05 does not claim otherwise. This caveat is mandatory output text, not a comment.

### 9.4. Per-metric value rendering

| Status | Display |
|---|---|
| `VALID_VALUE` | numeric value (e.g., `0.372`) |
| `NOT_APPLICABLE` | `--` (em-dash) with reason suffix `(*SINGLE_CLUSTER)` |
| `MISSING` | `n/a` with reason suffix |
| `COMPUTATION_ERROR` | `--` with reason suffix `(*SKLEARN_EXCEPTION)` |

CSV emission respects the same:
- `value` column: blank when status != VALID_VALUE (per §7.3).
- `status` column: enum.
- `reason` column: enum.

### 9.5. Comparison output shape (revised)

`ComparisonReport` (return value): has `groups` list (1+ groups, each with `metrics_table: pd.DataFrame`). CLI `--compare <ev_id1> <ev_id2> ...` prints:

```
DEV-05 — Comparison report
Built at 2026-10-09T...Z
3 evaluation(s) across 1 compatibility group(s).

Group 1 (n=2 evaluations)
  Compatibility key:
    dataset_id           : ds_xxx
    preprocessed_id      : pp_yyy
    ml_dataset_sha256    : ba54...
    feature_set_sha256   : <hash>
    preprocessing_config : <hash>
    metric_set           : {silhouette, davies_bouldin, calinski_harabasz}
  Evaluations:
    ev_x  → clustering=cl_aaa  algorithm=kmeans  seed=42         n_used=4371  noise=null      noise_policy=exclude
    ev_y  → clustering=cl-bbb  algorithm=dbscan  eps=0.5,ms=5   n_used=1194  noise=3177(0.73) noise_policy=exclude

  Metrics table:
    ref       | silhouette          | davies_bouldin       | calinski_harabasz
    ev_x k=4  | 0.372        VALID  | 1.064        VALID   | 1234.57   VALID
    ev_y dbs  | 0.281        VALID  | 1.402        VALID   | 872.10    VALID

  Caveat: row ev_y was computed on n_used=1194 (DBSCAN noise excluded).
          Comparing ev_x and ev_y directly is a *descriptive*
          observation; DEV-05 does NOT emit ranking, recommendation,
          or winner annotation per AGENTS.md §2.5 + SYS-04 §12.3 G5.

Group 2 (n=1 evaluation) — omitted if singleton (or shown separately
                              under "singleton" header; see §15 OQ-EVAL-04)
```

Two textual elements are mandatory in the output:
1. **Per-group provenance** line(s) before the metrics table.
2. **A "no ranking, recommendation, or winner" disclaimer** after the metrics table.

The disclaimer text must include the word "ranking" / "recommendation" / "winner" only to *negate* the concept (this is the single approved occurrence of those substrings in DEV-05 output, per the conformance test in §13.1 and R-EVAL-08).

### 9.6. Compare Experiments MUST NOT

- Aggregate metric values into composite score / mean / sum / weighted score.
- Declare ANY evaluation or algorithm as "best", "recommended", "winner", "optimal", "final".
- Sort the comparison table by any metric (left-to-right ordering preserved by user input order).
- Imply that one algorithm is "better" than another based on a single metric, regardless of how suggestive the values are.
- Merge measurements of different `CompatibilityKey` into a single row.
- Treat metric values from rows with different `n_samples_used_for_compute` as numerically equivalent without flagging the difference.
- Conclude that a higher silhouette / lower DBI / higher CH automatically proves an algorithm is better — even when provenance matches.
- Apply Hungarian matching / cluster permutation / relabel to align labels across the comparison set (EPIC-08 owned).

### 9.7. Compare Experiments MAY

- Compute **per-evaluation-pair** differences if explicitly requested (`--diff` flag, future). For Phase 2 minimum: only `value | status` reporting, plus provenance. Pairwise diff is a follow-up enhancement, not Phase 2 minimum.
- Display input order as user passed — do not reorder by metric.

---

## 10. Research-safety invariants

### 10.1. The invariants (extended)

DEV-05 **MUST** uphold:

| # | Invariant | Verification |
|---|---|---|
| R-EVAL-01 | `automatically_promoted_to_research = False` always in `research_safety` block | Unit test on EvaluationManifest construction + on-disk JSON read after run |
| R-EVAL-02 | `appeared_in_research_evidence = False` always | Unit test (same as R-EVAL-01) |
| R-EVAL-03 | `scope = "EVALUATED_PROTOTYPE"` always | Unit test |
| R-EVAL-04 | No write to `data/raw/**`, `data/interim/**`, `data/processed/**`, `data/external/**` | Research-safety test mocking `Path.write_text` and asserting no calls into git-ignored research dirs |
| R-EVAL-05 | No write to `reports/**` | Research-safety test |
| R-EVAL-06 | No write to `data/prototype/<ds>/preprocessed/<pp>/clustering/<cl>/` **other than** `evaluation/<ev_id>/` subtree | Research-safety test: enumerate `prototype/` parents during run; confirm `writes_inside(parent)` call list matches `evaluation/<ev_id>/` only |
| R-EVAL-07 | No write to DEV-02..DEV-04 staging / backup / failed-tracking dirs (`_staging_*`, `_backup_*`, `_failed_*`) | Research-safety test |
| R-EVAL-08 | `comparison` does NOT emit ranking, ranking, score-aggregate, sorting by metric, "best" column | Comparison output string scan (regex deny-list: `(?i)\bbest\b`, `recommended`, `optimal`, `winner`, `ranking`, `score`, `aggregate` outside of "no ranking is emitted" disclaimer) |
| R-EVAL-09 | Evaluation pass NEVER reads `data/processed/final_clustering_dataset.parquet` (research FE-06 output) | Runtime test: monkey-patch `pandas.read_parquet` and assert it is never called with FE-06 path |
| R-EVAL-10 | DEV-05 NEVER mutates DEV-03 ML Dataset parquet file bytes (sha256 unchanged before/after run) | File-hash integrity test |
| R-EVAL-11 | DEV-05 NEVER mutates DEV-04 cluster_labels / experiment_log sha256 before/after run | File-hash integrity test |
| R-EVAL-12 | `evaluation_metric_set` is restricted to the 3 internal metric names; no WCSS / runtime / stability injected | Unit test on `EvaluationMetricEntry.metric_name` factory + `metric_set` validator |
| R-EVAL-13 | Phase 1 plan only; no evaluation on real research dataset (no test invokes DEV-05 against `data/processed/final_clustering_dataset.parquet`) | Test inventory check: any test that uses real FE-06 data → REVIEW_REQUIRED |
| R-EVAL-14 | **Noise / label immutability.** DEV-05 NEVER modifies, overwrites, relabels, or drops rows in `cluster_labels_*.parquet`; NEVER writes a "filtered" copy of X or labels to disk; NEVER introduces label relabel / permutation / Hungarian matching. | File-hash integrity test on `cluster_labels_*.parquet` before vs after run + AST scan of `src/customer_segmentation/prototype/evaluation/*.py` for forbidden mutation calls on those paths. Confirm no in-place mutation helpers exist (no `df["ClusterLabel"] = ...`, no `df.drop(...)` then `to_parquet(...)` on a path under DEV-04's tree). |
| R-EVAL-15 | **Source-agnostic metric set.** DEV-05 only depends on the 3 sklearn metric functions enumerated above; no ARI / AMI / WCSS / runtime / stability helpers imported or invoked. | Static AST scan of `prototype/evaluation/metrics.py` against `sklearn.metrics` `__all__` diff; runtime patched call count check. |
| R-EVAL-16 | **Manifest / metric consistency.** The set of metric rows in `metrics_long.csv` and the keys in `evaluation_manifest.json::metrics` are always identical (no row in CSV without a JSON entry, no JSON entry without a CSV row). | Unit test: construct result with valid entries; assert set-equality of CSV metric_names and JSON metric_keys. |
| R-EVAL-17 | **Atomic publish.** A manifest or CSV never appears in `evaluation/<ev_id>/` unless written atomically (temp file + rename). Partial writes are not visible. | Mock filesystem test; partial-write fails when process is killed mid-write; subsequent re-run restores idempotency. |

### 10.2. Research-core impact — what DEV-05 does and does NOT touch

| Touch | Decision |
|---|---|
| `customer_segmentation.clustering.*` (5 adapters, registry, runner) | **NOT modified.** DEV-05 only reads `ClusteringManifest`, `cluster_labels_*.parquet`, `experiment_log_*.json` from disk. |
| `customer_segmentation.evaluation.*` (research core) | **NOT modified.** DEV-05 mirrors MISSING/MISSING_REASON pattern locally; does NOT import from research core at runtime. |
| `customer_segmentation.transformation.versioning.compute_file_sha256` (read-only utility) | Read-only; same as DEV-04. |
| `customer_segmentation.dataset_management.storage.resolve_storage_root` | Read-only. |
| `customer_segmentation.prototype.preprocessing.storage.DEFAULT_DEV02_CONFIG_PATH` | Read-only constant import. |
| `customer_segmentation.clustering.validation.validate_clustering_matrix` | Read-only reuse (for X validation). Same as DEV-04. |
| `customer_segmentation.clustering.config.compute_text_sha256` | Read-only reuse. |

### 10.3. EPIC-08 owned — out of scope

The following are EPIC-08 owned and **MUST NOT** be touched by DEV-05 (mirror SYS-04 §13.3 + ADR-0004 RQ1 "Stability: ... ARI/AMI computation deferred to EPIC-08"):

- ARI / AMI computation.
- Hungarian cluster matching.
- Statistical paired tests (t / Wilcoxon).
- Confidence intervals (bootstrap / percentile).
- Runtime variance (`mean / std / min / max` over n_repeat=5).
- Composite scores / ranking / weights / winners.
- External validation.
- WCSS (this lives in research core; DEV-05 produces only 3 internal metric per task brief).

### 10.4. Human approval gate

`TECHNICALLY IMPLEMENTED` ≠ `RESEARCH DECISION APPROVED` (per AGENTS.md §2.10). DEV-05 plan explicitly states that reaching `TECHNICALLY IMPLEMENTED` does NOT promote any evaluation result to research evidence; mentor approval required to use these metrics as research evidence.

---

## 11. Implementation phases theo dependency order

### Phase 2A: Scope, config, storage primitive (no compute, no I/O side effects)

1. `scope.py` — define `EvaluatedScope`, `MetricName`, `MetricStatus`, `MetricReason` enums + frozen constants.
2. `config_loader.py` — `Dev05Config` (frozen dataclass), `load_dev05_config`, `Dev05ConfigError`. Mirror DEV-04 `config_loader.py` structure.
3. `storage.py` — `derive_evaluation_id`, `prototype_evaluation_*_dir`, `resolve_storage_root` (delegate to dev02). Path-containment regex. NO I/O side effects.
4. `configs/dev05_evaluation.yaml` — single source of truth (mirror `configs/dev04_clustering.yaml` layout).
5. Tests covering scope, config, storage primitives (mirror DEV-04's `test_dev04_scope.py`, `test_dev04_config.py`, `test_dev04_storage.py`).

### Phase 2B: Manifest schema + atomic write (no compute yet)

6. `manifest.py` — `EvaluationManifest`, `ResearchSafetyBlock` (mirror DEV-04), `EvaluationMetricsResult`, `EvaluationMetricEntry`. Atomic write helper.
7. Tests covering manifest I/O, round-trip, corrupt paths, atomic-write invariants (mirror DEV-04's `test_dev04_manifest.py`).

### Phase 2C: Metric compute primitive + edge-case policy (synthetic only)

8. `metrics.py` — `compute_internal_metrics(X, labels, *, noise_label, noise_policy, metric_set)` returning `EvaluationMetricsResult`. Wrap sklearn.metrics, handle edge cases per §5. **Applies uniform DBSCAN noise exclusion by default** (§5.4) with `noise_policy = "exclude"` parameter to override per call. NO manifest I/O. NO mutation of any caller-provided arrays. Pure function (with documented time-of-call side effects on internal numpy arrays only).
9. Tests covering metric computation on synthetic fixtures with **expected values verified against sklearn directly** + edge-case fixtures (single cluster, all-noise, DBSCAN noise exclusion applied uniformly to silhouette / DBI / CH, NaN/Inf, alignment error, manifest schema mismatch). Specifically:
   - `test_metrics_valid_value_three_metrics_synthetic_blob` — happy path; numeric values within 1e-6 tolerance of sklearn direct call.
   - `test_metrics_dbscan_noise_excluded_uniformly_for_all_three` — labels `[0, 0, 1, -1, -1, -1]` → noise_count = 3, n_used = 3, all three metrics computed on the 3-row subset; each reason = `DBSCAN_NOISE_EXCLUDED`.
   - `test_metrics_dbscan_all_noise_returns_not_applicable_three_times` — labels all `-1` → 3 metric entries each `NOT_APPLICABLE / ALL_NOISE`.
   - `test_metrics_non_dbscan_noise_count_null` — K-Means labels — noise_count = None, noise_ratio = None, n_used = n_samples_input.
   - `test_metrics_single_cluster_returns_not_applicable_three_times` — labels all `0` → 3 metric entries each `NOT_APPLICABLE / SINGLE_CLUSTER`.
   - `test_metrics_nan_input_returns_computation_error` — X with NaN → 3 metric entries each `COMPUTATION_ERROR / NAN_OR_INF_INPUT`.
   - `test_metrics_inconsistent_dim_raises_alignment_error` — X.shape[0] != labels.shape[0] → wrap as `COMPUTATION_ERROR / ALIGNMENT_ERROR`.
   - `test_metrics_sklearn_raises_unexpected_valueerror` — monkey-patch sklearn to raise → `COMPUTATION_ERROR / SKLEARN_EXCEPTION`; raw exception message is NOT surfaced per R-EVAL-12.
   - `test_metrics_metric_set_unsupported_raises_error` — `metric_set = {"auc_roc"}` → `Dev05UnsupportedMetricError`.

### Phase 2D: Validation primitive

10. Inline `validate_evaluation_inputs(X, cluster_labels_df, *, customer_key)` — return `EvaluationValidationReport`. Reuse `validate_clustering_matrix` from research core for X. Check alignment between X and cluster_labels_df; check IsNoise column; check ClusterLabel dtype.
11. Tests covering validation report, status coverage.

### Phase 2E: Logging façade

12. `logging_config.py` — `PerStageLogger`, `configure_logging`, `finalize_logging` (mirror DEV-04).
13. Tests covering logger façade (mirror `test_dev04_logging.py`).

### Phase 2F: Pipeline + atomic publish

14. `pipeline.py` — `run_evaluation_pipeline(...)` orchestrates Stages A→G (mirror DEV-04 Stages 0→6 + 5b pattern):
    - A (preflight): load DEV-05 config + read DEV-04 clustering_manifest.
    - B (lookup): read DEV-04 `cluster_labels_*.parquet` + DEV-03 ML Dataset parquet (for X); resolve paths.
    - C (validation): `validate_evaluation_inputs`; FAIL → status `FAILED`, write manifest with metric statuses `MISSING/MANIFEST_MISSING`.
    - D (compute): `compute_internal_metrics`; on sklearn exception → `COMPUTATION_ERROR / SKLEARN_EXCEPTION`.
    - E (manifest): atomic write `evaluation_manifest.json` (in staging).
    - F (publish): atomic `os.rename(staging → final)`.
    - G (finalize log).
15. Test covering end-to-end happy path (synthetic DEV-04 artefact, synthetic ML Dataset), CACHED idempotency, FAILED paths (validation fail, sklearn exception, manifest corrupt).
16. Pipeline safety (mirror DEV-04 R-17 + R-15 + F1 invariant):
    - Top-level try/finally with cleanup pass.
    - FAILED log preservation to `_failed_<evaluation_id>_<run_uuid>/`.
    - Cleanup pass skips `_failed_*`, `_backup_*_corrupt/`, scoped to current run_uuid.
    - F1 invariant: skip staging cleanup when `state.unpreserved_log_in_staging=True`.

### Phase 2G: CLI + display

17. `display.py` — `format_metrics_table`, `format_comparison_report`, `format_manifest_path`.
18. `scripts/dev05_evaluate_clustering.py` — argparse mirror `scripts/dev04_run_clustering.py`.
19. `tests/test_dev05_cli.py` — argparse coverage.
20. Manual smoke test of CLI on synthetic fixture (no real data — fixture only).

### Phase 2H: Compare + research-safety

21. `compare.py` — `CompatibilityKey`, `ComparisonGroup`, `ComparisonReport`, `compare_evaluations`, `Dev05IncompatibleComparisonError`. NO ranking logic; structured compatibility.
22. `tests/test_dev05_compare.py` — happy path, compatibility mismatch, no shared key, single-evaluation case.
23. CLI `--compare` mode wiring.
24. Research-safety tests (mirror `test_dev04_research_safety.py`):
    - R-EVAL-01..R-EVAL-17 invariant coverage.
    - Static + runtime scan for forbidden imports / libs.

### Phase 2I: Import blocklist + runtime dependency tests

25. `tests/test_dev05_import_blocklist.py` — forbid import of `customer_segmentation.evaluation.*` (research core) at runtime; forbid research subpackages at static scan level.
26. `tests/test_dev05_runtime_dependencies.py` — no new third-party libs declared; only declared deps used.

### Phase 2J: Integration test sweep + docs sync

27. Full integration test on synthetic fixture (rounds trip: import dataset (DEV-02 stub) → preprocess (DEV-03 stub) → cluster (DEV-04 stub) → evaluate (DEV-05) → compare two evaluations).
28. `docs/system/DEV-05_completion_summary.md` — final completion summary mirroring DEV-04 §1-§11.

### Phase 2 ordering dependency graph

```
Phase 2A (scope/config/storage) → Phase 2B (manifest) → Phase 2C (metrics compute)
                                                       ↓
                                          Phase 2D (validation) → Phase 2E (logging)
                                                                     ↓
                                                       Phase 2F (pipeline + safety)
                                                       ↓
                              Phase 2G (display + CLI) ↔ Phase 2H (compare + research-safety)
                                                                     ↓
                                                       Phase 2I (import blocklist + runtime deps)
                                                                     ↓
                                                       Phase 2J (integration + completion summary)
```

Có thể chạy 2G & 2H song song nếu muốn (cùng phụ thuộc 2F).

---

## 12. Acceptance criteria mapping

| AC | Code path | Test files | Verification evidence dự kiến |
|---|---|---|---|
| **AC-1**: Metrics được tính | `src/customer_segmentation/prototype/evaluation/metrics.py::compute_internal_metrics`; sklearn wrappers `silhouette_score` / `davies_bouldin_score` / `calinski_harabasz_score` | `tests/test_dev05_metrics.py` (mirror `test_dev04_safety.py` size); `tests/test_dev05_pipeline.py::test_compute_three_metrics`; `tests/test_dev05_pipeline.py::test_pipeline_dbscan_noise_excluded_uniformly_three_metrics`; `tests/test_dev05_pipeline.py::test_pipeline_dbscan_all_noise_lifecycle_failed`; `tests/test_dev05_pipeline.py::test_pipeline_single_cluster_not_applicable`; `tests/test_dev05_metrics.py::test_metrics_valid_value_three_metrics_synthetic_blob` | Pytest test logs show 3 metric values for `VALID_VALUE` case; edge-case tests check status == NOT_APPLICABLE for SINGLE_CLUSTER / ALL_NOISE; CLI smoke test on synthetic fixture |
| **AC-2**: Metrics được lưu | `src/customer_segmentation/prototype/evaluation/manifest.py::write_evaluation_manifest`; `manifest_to_dict`; `metrics_long.csv` writer (CSV step in pipeline) | `tests/test_dev05_manifest.py` (round-trip, atomic write, corrupt handle); `tests/test_dev05_pipeline.py::test_manifest_written_atomic`; `tests/test_dev05_pipeline.py::test_metrics_csv_round_trip`; `tests/test_dev05_safety.py` (atomic publish, corrupt manifest) | Pytest assertions: manifest JSON loads back with same fields; CSV row count == metric_set size; on-disk file sha256 stable across rerun (CACHED idempotent); atomic write — partial write never seen |
| **AC-3**: Metrics hiển thị | `src/customer_segmentation/prototype/evaluation/display.py::format_metrics_table`; `scripts/dev05_evaluate_clustering.py` argparser wiring | `tests/test_dev05_display.py::test_format_metrics_table_valid`; `tests/test_dev05_display.py::test_format_metrics_table_not_applicable`; `tests/test_dev05_cli.py::test_cli_default_prints_table` | Pytest assertions on format string contains metric name + value + status; CLI smoke test stdout contains "silhouette", "davies_bouldin", "calinski_harabasz" headers |
| **AC-4**: Có thể so sánh Experiment | `src/customer_segmentation/prototype/evaluation/compare.py::compare_evaluations`, `CompatibilityKey`, `ComparisonReport`; CLI `--compare` flag | `tests/test_dev05_compare.py::test_compare_two_compatible_evaluations`; `tests/test_dev05_compare.py::test_compare_incompatible_groups_split`; `tests/test_dev05_compare.py::test_compare_no_shared_key_raises`; `tests/test_dev05_compare.py::test_compare_no_ranking_no_winner`; `tests/test_dev05_cli.py::test_cli_compare_two_evaluations` | Pytest assertions: groups have shared `CompatibilityKey`; metrics_table has expected columns; output string check (regex) confirms NO `best`/`recommended`/`optimal`/`winner`/`ranking`/`score`/`aggregate` outside of "no ranking is emitted" disclaimer; CLI smoke test stdout shows side-by-side table |

Plus:

- **R-EVAL-01..R-EVAL-17** (research-safety) — covered by `tests/test_dev05_research_safety.py` (mirror `test_dev04_research_safety.py`).
- **Import blocklist** — covered by `tests/test_dev05_import_blocklist.py`.
- **Runtime dependencies** — covered by `tests/test_dev05_runtime_dependencies.py`.
- **Conformance (DEV-04 contract, AGENTS.md §3, AGENTS.md §2.5, §2.10, §2.4, §2.12)** — covered by `tests/test_dev05_conformance.py` (NEW — assert DEV-05 source has no `banned` substrings in display path: "best", "winner", "optimal", "recommended" outside test context).

---

## 13. Test matrix

### 13.1. Unit tests (component-level)

| Module | Test file | Focus |
|---|---|---|
| scope | `tests/test_dev05_scope.py` | StrEnum invariants; status/reason enum membership closed; EvaluatedScope exactly 1 value |
| config_loader | `tests/test_dev05_config.py` | YAML parsing; defaults; error paths; frozenset invariants |
| storage | `tests/test_dev05_storage.py` | `evaluation_id` derivation; `^ev_[0-9a-f]{24}$` regex enforcement; path containment defence; `find_existing_evaluation` idempotency; collision detection |
| manifest | `tests/test_dev05_manifest.py` | round-trip; atomic write; corrupt/empty/missing fields; stable/runtime field classification; ResearchSafetyBlock invariants |
| logging_config | `tests/test_dev05_logging.py` | PerStageLogger façade; per-stage; finalize idempotent |
| metrics (unit) | `tests/test_dev05_metrics.py` | Wraps sklearn correctly; on synthetic blobs returns values close to expected (use sklearn direct as baseline); edge cases (single cluster, all-noise, NaN/Inf); status enum correct |
| validation | `tests/test_dev05_validation.py` | Alignment error case; NaN/Inf case; cluster_label dtype case; all-noise case |
| compare | `tests/test_dev05_compare.py` | Compatibility partition; no-ranking guarantee; output format |
| display | `tests/test_dev05_display.py` | format_metrics_table happy path; format_metrics_table with NOT_APPLICABLE rows; format_comparison_report happy path; **scan output for banned substrings** |
| CLI | `tests/test_dev05_cli.py` | argparse; --compare flag; --force-recompute flag; --noise-policy flag; --metrics CSV; help text |
| pipeline integration | `tests/test_dev05_pipeline.py` | end-to-end with synthetic DEV-04 artefact; CACHED idempotency; FAILED paths |
| safety | `tests/test_dev05_safety.py` | atomic publish; cleanup invariants; failed-log preservation; F1 invariant; corrupt manifest detection; idempotency tampering detection |
| research_safety | `tests/test_dev05_research_safety.py` | R-EVAL-01..R-EVAL-17 invariants; mutation tests on filesystem mock |
| import_blocklist | `tests/test_dev05_import_blocklist.py` | forbid `customer_segmentation.evaluation.*` imports at static + runtime scan; forbid research subpackages |
| runtime_dependencies | `tests/test_dev05_runtime_dependencies.py` | no new third-party libs declared; only declared deps |
| conformance | `tests/test_dev05_conformance.py` | display.py + compare.py + format strings contain no banned word (regex `(?i)\bbest\b\|recommended\|optimal\|winner\b\|ranking\|composite_score` outside test context) — DENY-LIST TEST |

Target count: **160-200 tests** (mirror DEV-04's 158 + ~5-30 new for compare + display + conformance).

### 13.2. Integration tests (cross-module)

| Test | Path | Mô tả |
|---|---|---|
| `test_pipeline_compute_all_three_metrics` | `test_dev05_pipeline.py` | Full happy path: synthetic DEV-04 artefact + ML Dataset → compute → manifest → CSV all populated |
| `test_pipeline_cached_on_second_run` | `test_dev05_pipeline.py` | Re-run identical config → CACHED; same manifest path; same evaluation_id |
| `test_pipeline_force_recompute_overrides_cache` | `test_dev05_pipeline.py` | `--force-recompute` → SUCCESS; manifest updated under backup/restore pattern |
| `test_pipeline_dbscan_noise_excluded_uniformly_three_metrics` | `test_dev05_pipeline.py` | DBSCAN labels `[0, 0, 1, -1, -1, -1]` → all three metrics computed on the 3-row non-noise subset; each `reason = DBSCAN_NOISE_EXCLUDED`; `noise_count = 3`, `noise_ratio = 0.5`, `n_samples_used_for_compute = 3` |
| `test_pipeline_dbscan_all_noise_lifecycle_failed` | `test_dev05_pipeline.py` | DBSCAN labels all `-1` → manifest written with each metric `NOT_APPLICABLE / ALL_NOISE`; `lifecycle = FAILED`; `noise_count = n_samples_input`; `n_samples_used_for_compute = 0` |
| `test_pipeline_non_dbscan_no_noise_filter` | `test_dev05_pipeline.py` | K-Means labels — `noise_count = null`, `noise_ratio = null`; `n_samples_used_for_compute == n_samples_input`; 3 metrics VALID |
| `test_pipeline_validation_fail_blocks_compute` | `test_dev05_pipeline.py` | X.shape[0] != labels.shape[0] → manifest written with `COMPUTATION_ERROR / ALIGNMENT_ERROR`; lifecycle = FAILED |
| `test_pipeline_nan_input_blocks_compute` | `test_dev05_pipeline.py` | X contains NaN → manifest written with `COMPUTATION_ERROR / NAN_OR_INF_INPUT`; lifecycle = FAILED; input cluster_labels parquet sha256 unchanged |
| `test_pipeline_atomic_publish_partial_write_not_visible` | `test_dev05_safety.py` | Inject `OSError` mid-rename → `evaluation/<ev_id>/` directory not visible to `Path.exists()`; on re-run, recovery succeeds |
| `test_compare_two_compatible_evaluations` | `test_dev05_compare.py` | Two evaluations sharing `CompatibilityKey` → single group; side-by-side metric table; provenance line per row |
| `test_compare_incompatible_groups_split` | `test_dev05_compare.py` | Two evaluations with mismatched `ml_dataset_sha256` → two groups; `incompatibility_reasons` populated; no row merging |
| `test_compare_does_not_rank` | `test_dev05_compare.py` | Output string scan: NO `best` / `recommended` / `optimal` / `winner` / `ranking` outside the disclaimer; disclaimer text contains "no ranking, recommendation, or winner" verbatim |
| `test_compare_provenance_per_row_surfaces_noise_diff` | `test_dev05_compare.py` | Mixing K-Means (noise_count = null) + DBSCAN (noise_count = 3177) in same group → output includes per-row `n_used=...` and explicit caveat about differing `n_samples_used_for_compute` |
| `test_compare_no_metric_equivalence_claim_across_filtered_rows` | `test_dev05_compare.py` | Same metric, different `n_samples_used_for_compute` → report MUST surface the difference; never silently comparable |
| `test_research_safety_noise_immutability_R_EVAL_14` | `test_dev05_research_safety.py` | `sha256(cluster_labels_*.parquet)` unchanged before vs after run; AST scan finds no mutation helper calls |
| `test_research_safety_manifest_csv_consistency_R_EVAL_16` | `test_dev05_research_safety.py` | set of CSV metric_names == keys in manifest::metrics |
| `test_research_safety_atomic_publish_R_EVAL_17` | `test_dev05_research_safety.py` | mock filesystem; partial-write scenario; re-run idempotency |

### 13.3. Research-safety regression tests

| Test | Path | Verifies |
|---|---|---|
| `test_research_safety_evaluation_manifest_promotion_false` | `test_dev05_research_safety.py` | `automatically_promoted_to_research = False` |
| `test_research_safety_scope_evaluated_prototype` | `test_dev05_research_safety.py` | `scope = "EVALUATED_PROTOTYPE"` |
| `test_research_safety_no_write_research_paths` | `test_dev05_research_safety.py` | run pipeline with mock storage root; assert no Path.write_* under data/raw/**, data/processed/**, data/interim/**, reports/** |
| `test_research_safety_no_read_fe06_final_dataset` | `test_dev05_research_safety.py` | runtime scan + static AST scan: no reference to `final_clustering_dataset.parquet` |
| `test_research_safety_no_modify_dev04_outputs` | `test_dev05_research_safety.py` | sha256(cluster_labels_*.parquet) unchanged before vs after run; sha256(ml_dataset_*.parquet) unchanged; sha256(clustering_manifest.json) unchanged |
| `test_research_safety_no_write_to_dev04_dirs_other_than_evaluation` | `test_dev05_research_safety.py` | Path containment test: only writes inside `evaluation/<ev_id>/` |
| `test_compare_emits_no_winner` | `test_dev05_research_safety.py` | ComparisonReport string output scan (mirror display tests) — checks NO `best` / `recommended` / `optimal` / `winner` / `score` / `aggregate` outside the disclaimer |
| `test_compare_per_row_provenance_present` | `test_dev05_research_safety.py` | Provenance columns (clustering_id, algorithm, n_used, noise_count, noise_ratio, noise_policy_used) present in every comparison row output |

### 13.4. Static checks

- `ruff check src/customer_segmentation/prototype/evaluation/ scripts/dev05_evaluate_clustering.py tests/test_dev05_*.py tests/conftest.py` → all checks passed.
- `ruff format --check ...` → unchanged.
- `black --check ...` → unchanged.

### 13.5. Runtime verification (Phase 2 final)

- `pytest -q tests/test_dev05_*.py tests/test_dev04_*.py tests/test_dev03_*.py tests/test_dev02_*.py tests/test_ml01_*.py` → all green; no regression.
- No test against real FE-06 dataset (`data/processed/final_clustering_dataset.parquet`) per R-EVAL-13.

### 13.6. Tests not runnable without further decisions

| Test | Reason |
|---|---|
| Real-data compute on `data/processed/final_clustering_dataset.parquet` | R-EVAL-13 + AGENTS.md §2.12 — researcher-only |
| ARI/AMI | OQ-EVAL-EPIC08 still REVIEW_REQUIRED |
| `metric_set` variants beyond {silhouette, davies_bouldin, calinski_harabasz} | Out of scope for DEV-05 |

---

## 14. Risks và mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| R-1: Path-traversal via crafted `evaluation_id` raises OSError instead of ValueError, leaking path info | Medium | Enforce regex `^ev_[0-9a-f]{24}$` BEFORE any `Path()` constructor + `Path.resolve() + relative_to(root)` test. Dedicated unit test. Mirror DEV-04 `test_dev04_storage.py::test_path_containment`. |
| R-2: `noise_policy` default confuses researchers (uniform exclusion is a methodology deviation from sklearn defaults for DBI and CH) | High (methodology) | Document default `exclude` in config YAML header (per §5.4); record `noise_policy_used` in manifest; CLI explicit `--noise-policy include\|exclude` exposes both modes; per-row provenance surfaces `noise_count` / `noise_ratio` / `noise_policy_used` so comparison output never silently treats differing subsets as equivalent; human-researcher sign-off pending on §15 OQ-EVAL-NOISE before Phase 2 starts. Status `WORKING_ASSUMPTION` until OQ resolves. |
| R-3: Sklearn changes signature between versions and breaks DEV-05 silently | Low | Pin `scikit-learn>=1.4,<2.0` (already in `pyproject.toml` runtime deps). Capture `library_versions` in manifest environment block. |
| R-4: `compute_internal_metrics` accidentally called with raw `X` that includes CustomerID → identifier leakage | High | Reuse `validate_clustering_matrix` from research core (which has `IdentifierLeakageError`). If it raises, evaluation pipeline aborts with CLEAR error. Defensive: before passing X to sklearn, project out any column whose name matches `CustomerID` / `customer_id` (configurable behaviour) — prefer leak-detection over silent projection. |
| R-5: Researcher reads metric value as research evidence | High (methodology) | `research_safety.automatically_promoted_to_research=False` + completion summary explicit statement + README note. AC-2 manifest README/usage doc tells reader "this is prototype evidence; for research use re-run via EPIC-08 in research core". |
| R-6: Phase 2 implementation accidentally mutates `data/processed/...` (R-EVAL-04) | High | Research-safety test (`test_research_safety_no_write_research_paths`) with Path write mocks — must pass. |
| R-7: Phase 2 runs metrics on real research dataset accidentally | High (R-EVAL-13) | All tests use synthetic fixtures (per DEV-04 pattern in `tests/conftest.py`). Test inventory: assert no fixture path contains `data/processed/` or `data/raw/`. |
| R-8: Display emits "best" / "winner" string inadvertently (Hyrum's-law slip) | High (AGENTS.md §2.5) | Conformance test (`test_dev05_conformance.py`) scans all of `display.py`, `compare.py`, `pipeline.py` print paths for banned substrings. |
| R-9: WCSS / ARI / stability accidentally included via `metric_set="*"` glob | Medium | `metric_set` validator: parsed as closed enum of {silhouette, davies_bouldin, calinski_harabasz}; unknown name → `Dev05UnsupportedMetricError`. Test coverage. |
| R-10: Re-compute path silently overwrites prior evaluation manifest without preserving audit | Medium | `--force-recompute` backup-first (copy current manifest to `_backup_<run_uuid>/`, then atomic publish). Mirror DEV-04 R-17. |
| R-11: `evaluation_id` collision (vanishingly small) | Low | content-addressed derives from 10-field canonical; explicit `Dev05CollisionError` raised and refused (mirror DEV-04). |
| R-12: Manifest schema bump breaks backward-read | Medium | `schema_version` is part of `evaluation_id` derivation; if schema_version changes, all old `evaluation_id`s are invalidated (defence against silently reinterpreting). Phase 2 may add explicit migration helper but deferred. |
| R-13: Phase 2A can't be coded without consolidated decision on §15 OQ-EVAL-NOISE (uniform DBSCAN noise exclusion for all three metrics) | High (blocking) | OQ-EVAL-NOISE MUST be resolved (or explicitly deferred with `WORKING_ASSUMPTION`) before Phase 2 implementation begins. The proposal is documented in §5.4 with clear separation between what is locked (SYS-04 §12.2 / CON-15 silhouette-only) and what is the prototype-layer proposal (DBI + CH joined to silhouette for symmetry). Phase 2 implementation must NOT auto-resolve this OQ. See §15. |
| R-14: Phase 2 produces a partial manifest / CSV on the file system (e.g., process killed during write, FS error mid-rename) → later reads a half-written evaluation as if it were valid | High | **Atomic publish** for both JSON manifest and CSV (write to `*.tmp` then `os.replace`; on exception, `tmp.unlink`). **Idempotent re-run** with content-addressed `evaluation_id` ensures the next run either overwrites a full copy or recovers from `_backup_<run_uuid>/`. R-EVAL-17 invariant + `test_dev05_safety.py::test_atomic_publish_*` tests must pass. Mirror DEV-04 R-13 / R-17 / F1. |
| R-15: Display string contains a banned substring (`best`, `winner`, `recommended`, ...) outside the disclaimer text — Hyrum's-law slip | High (AGENTS.md §2.5, SYS-04 §12.3 G5) | Conformance test (`test_dev05_conformance.py` + `test_dev05_research_safety.py::test_compare_emits_no_winner`) scans `display.py`, `compare.py`, `pipeline.py` print paths with regex deny-list. Single allowed occurrence is in the disclaimer phrase "no ranking, recommendation, or winner annotation is emitted". |
| R-16: Storage path traversal: crafted `evaluation_id` (or upstream `clustering_id`) yields an OSError inside `os.replace` / `Path.resolve()`, leaking path info | Medium | `^ev_[0-9a-f]{24}$` regex enforced BEFORE any `Path()` constructor; `Path.resolve() + relative_to(storage_root.resolve())` test on every computed path; explicit `Dev05StoragePathError`. Mirror DEV-04 `test_dev04_storage.py::test_path_containment`. |
| R-17: `--force-recompute` overwrites prior manifest without preserving audit trail | Medium | Backup-first pattern: copy current `evaluation_manifest.json` + `metrics_long.csv` + log to `_backup_<run_uuid>/` before atomic re-publish. `_backup_*_corrupt/` is never restored. R-17 / F1 mirror DEV-04. |
| R-18: Two evaluations in compare group are computed on different sample subsets (different `noise_count`, different `noise_policy_used`) but the report silently treats them as comparable | High (interpretation) | Comparison output **must surface** the difference via per-row provenance line. `test_compare_provenance_per_row_surfaces_noise_diff` enforces this. Researcher cannot make a `is better` claim without first acknowledging the filter asymmetry. |

---

## 15. Open questions/decisions cần human approval

Danh sách OQ (open questions) cần human input trước Phase 2 implementation. Ghi "DEFERRED" đối với bất kỳ OQ nào không resolve được trước khi code.

| ID | Question | Status | Options | Recommendation (low-risk default) |
|---|---|---|---|---|
| **OQ-EVAL-NOISE** *(consolidates OQ-EVAL-01 + OQ-EVAL-02 from prior plan version)* | DEV-05 prototype should apply a **uniform DBSCAN noise exclusion policy** to all three internal metrics (silhouette, DBI, CH), or keep sklearn default per-metric? | **RESOLVED — PROTOTYPE SCOPE** *(see `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006), Accepted 2026-10-09; status `WORKING_ASSUMPTION` for prototype layer; research-layer status UNCHANGED)* | (A) **Uniform exclusion** — silhouette, DBI, CH all filter `ClusterLabel = -1` rows in-memory before calling sklearn. This deviates from sklearn defaults for DBI and CH. **(A) ADOPTED for DEV-05 prototype layer** per ADR-0006. (B) **Per-metric lock** — silhouette excludes noise (CON-15 LOCKED); DBI / CH keep sklearn default (silhouette-only exclusion). (C) **Record-both-and-let-researcher-decide** — emit two parallel fields per metric (e.g. `silhouette_with_noise`, `silhouette_without_noise`); AC says 1 row per metric, so this is a schema change. (D) **Defer DBSCAN entirely from DEV-05** — emit 3 metrics only on non-density algorithms. | **(A) ADOPTED for DEV-05 prototype layer** per ADR-0006. Rationale recorded in ADR-0006 (Context / Decision / Scope / Alternatives). Researcher-layer status of CON-15, WA-08, EXP01-MET-01, and `MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47 is **explicitly NOT modified** by this resolution — see ADR-0006 §"Scope" and §"Status of this decision". Prototype implementation follows §5.4 with `noise_policy = "exclude"` as default; CLI flag `--noise-policy include\|exclude` provides per-call override; manifest records `noise_policy_used` + provenance fields (§5.4.4); `evaluation_id` derivation includes `noise_policy` for idempotent-distinct reruns (§4.4); compare output surfaces per-row provenance and forbids silent equivalence across differing `n_samples_used_for_compute` (§9.3, §9.5, §9.6). |
| **OQ-EVAL-03** | WCSS / inertia có nên emit ở DEV-05 không? AC nói chỉ 3 metric. | **OPEN — DECIDED** | Three options | **DECIDED NO** (per AC verbatim + R-EVAL-12). WCSS excluded from DEV-05 entirely; it lives in research core if needed. `is_diagnostic_only` always `false` because DEV-05 only emits 3 metric names. |
| **OQ-EVAL-04** | `compare_evaluations` — nếu chỉ 1 evaluation được pass vào, emit gì? | **RESOLVED — IMPLEMENTER DECISION (Phase 2 start)** | (A) error raise `Dev05IncompatibleComparisonError`; (B) emit singleton group with `n=1` row; (C) print "no comparison possible with single evaluation". | **(B) ADOPTED** — emit singleton group with `n=1` row. Rationale: a singleton evaluation is still informative (the metric readout is what the user gets anyway); compare is about *cross*-comparison but a singleton group surfaces the single evaluation's metrics + provenance under the standard `ComparisonReport` shape without raising. Edge case: if singleton group is the only group, the per-group header + provenance lines still emit, and the disclaimer "no ranking, recommendation, or winner" is still printed. |
| **OQ-EVAL-05** | `--compare` mode có nên là CLI sub-mode (default behaviour khi flag) hay sub-command? | **RESOLVED — IMPLEMENTER DECISION (Phase 2 start)** | (A) sub-mode (current default in §4.5); (B) sub-command; (C) separate script `dev05_compare.py`. | **(A) ADOPTED** — `--compare` is a sub-mode flag of the same CLI entry point `scripts/dev05_evaluate_clustering.py`. Rationale: mirrors DEV-04 single-CLI convention (`scripts/dev04_run_clustering.py`); minimises new surface area (no separate `dev05_compare.py`); user ergonomics — one script, one help screen, one set of flags. The flag is detected by the CLI parser: presence of `--compare` short-circuits the compute path and routes to `compare_evaluations(...)`; absence runs the compute path per §4.5. |
| **OQ-EVAL-06** | Hiển thị metric missing nên dùng `--` (em-dash) hay `n/a`? | **RESOLVED — IMPLEMENTER DECISION (Phase 2 start)** | (A) `--`; (B) `n/a`; (C) blank. | **(A) ADOPTED with CSV carve-out** — display `--` (em-dash) in CLI stdout + comparison report; **blank** in `metrics_long.csv`. Rationale: human-display prefers em-dash to make "no numeric value" visually distinct from a sentinel like `0` or `-1`; machine-readable CSV uses blank cell with a `status` column populated (reader must look at `status` to know whether the cell is intentionally blank for `NOT_APPLICABLE` / `COMPUTATION_ERROR` / `MISSING`). The CSV convention matches §7.3 ("`value` column: blank when status != VALID_VALUE"). For NOT_APPLICABLE rows in the comparison report, the value rendering is `--` plus a parenthetical reason suffix `(*SINGLE_CLUSTER)` / `(*ALL_NOISE)` etc. per §9.4. |
| **OQ-EVAL-07** | Có nên compute metric trên **soft probabilities** (GMM) / **soft membership** (FCM) để derive additional metric (e.g. partition coefficient, fuzzy silhouette)? | **OPEN — DEFERRED (DO NOT IMPLEMENT IN DEV-05)** | (A) NO (out of scope); (B) YES (extend AC) | **Recommend (A) NO** for DEV-05. Adding fuzzy-specific metric would change AC. EPIC-08 owns. If needed, future DEV-09 (profiling) or EPIC-08 may extend. |
| **OQ-EVAL-EPIC-08** | EPIC-08 still has many REVIEW_REQUIRED decisions per SYS-04 §13.3 / §25 (ARI method, statistical test, CI method, runtime comparison protocol, visualization scope). Does DEV-05 need to wait for any of these? | **OPEN — DEFERRED (DOES NOT BLOCK DEV-05)** | n/a | **Recommend no wait.** DEV-05 covers only the 3 internal metrics locked by CON-07 (silhouette / DBI / CH). EPIC-08 owns stability / ARI / AMI / runtime — out of DEV-05 scope. When EPIC-08 closes its deferred decisions, DEV-05 may need a future increment to mirror them, but that's post-Phase-2. **Action**: Ghi note này vào `docs/system/DEV-05_completion_summary.md` §15 "Open questions" section. |

> **Note on methodology-bound decisions:**
> - **OQ-EVAL-NOISE** affects **interpretation of every DBSCAN clustering evaluation**. The `(A)` proposal — uniform exclusion — is a deliberate methodology deviation from sklearn default for DBI / CH. Resolution: **RESOLVED for DEV-05 prototype layer by ADR-0006** (`docs/decisions/0006-dev05-prototype-noise-policy.md`, Accepted 2026-10-09). The resolution is **prototype-scope only** and does NOT modify research-layer status of CON-15, WA-08, EXP01-MET-01, or `MENTOR_REVIEW_FORM_EXP01_EXP05.md` (per AGENTS.md §2.10 — `TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED`). If mentor later picks (B), (C), or (D) at the research layer, a new ADR must supersede ADR-0006; the old file is not edited (per `docs/decisions/README.md` immutability).
> - **OQ-EVAL-07** affects interpretation of GMM / FCM evaluations. Same §2.9 path; recommendation is NO (out of scope).
> - Phase 2 implementation **MUST NOT** auto-resolve any of the above. Resolution must happen *before* Phase 2 code with documented researcher sign-off in completion summary §15.

---

## 16. Files dự kiến tạo/sửa

### 16.1. Source code mới (Phase 2 — chưa tạo ở Phase 1)

```
src/customer_segmentation/prototype/evaluation/
├── __init__.py                                 # NEW — public API re-exports
├── scope.py                                    # NEW — EvaluatedScope, MetricName, MetricStatus, MetricReason enums + frozen constants
├── config_loader.py                            # NEW — Dev05Config (frozen), load_dev05_config, Dev05ConfigError
├── storage.py                                  # NEW — derive_evaluation_id, prototype_evaluation_*_dir, path-containment, find_existing_evaluation
├── manifest.py                                 # NEW — EvaluationManifest + sub-blocks + ResearchSafetyBlock + atomic write + read
├── metrics.py                                  # NEW — compute_internal_metrics(X, labels, *, noise_label, noise_policy, metric_set) → EvaluationMetricsResult
├── logging_config.py                           # NEW — PerStageLogger, configure_logging, finalize_logging
├── pipeline.py                                 # NEW — run_evaluation_pipeline + Stage A→G + cleanup pass (F1 invariant + R-17 mirror)
├── compare.py                                  # NEW — CompatibilityKey, ComparisonGroup, ComparisonReport, compare_evaluations
└── display.py                                  # NEW — format_metrics_table, format_comparison_report, format_manifest_path
```

### 16.2. CLI script mới

```
scripts/dev05_evaluate_clustering.py            # NEW — argparse mirror scripts/dev04_run_clustering.py
```

### 16.3. Config mới

```
configs/dev05_evaluation.yaml                   # NEW — single source of truth cho DEV-05
```

### 16.4. Test files mới

```
tests/conftest.py                              # MODIFIED — add `synthetic_dev04_artefact` fixture (extend existing DEV-04 fixture OR add DEV-05 equivalent)
tests/test_dev05_scope.py                      # NEW — scope enums
tests/test_dev05_config.py                     # NEW — config loader tests
tests/test_dev05_storage.py                    # NEW — evaluation_id derivation, path containment
tests/test_dev05_manifest.py                   # NEW — manifest I/O, atomic write, round-trip
tests/test_dev05_metrics.py                    # NEW — sklearn wrappers + edge cases + synthetic fixtures with expected values
tests/test_dev05_validation.py                 # NEW — input validation cases
tests/test_dev05_logging.py                    # NEW — PerStageLogger façade
tests/test_dev05_pipeline.py                   # NEW — end-to-end with synthetic DEV-04 artefact
tests/test_dev05_safety.py                     # NEW — atomic publish, cleanup invariants, R-17, F1
tests/test_dev05_cli.py                        # NEW — argparse + --compare
tests/test_dev05_display.py                    # NEW — display functions + banned-substring scan
tests/test_dev05_compare.py                    # NEW — comparison logic + compatibility partition + no-ranking
tests/test_dev05_research_safety.py            # NEW — R-EVAL-01..R-EVAL-17 invariants
tests/test_dev05_import_blocklist.py           # NEW — forbid evaluation.* imports
tests/test_dev05_runtime_dependencies.py       # NEW — no new third-party libs
tests/test_dev05_conformance.py                # NEW — banned-substring static scan (no best/winner/optimal/...)
```

**Target test count: ~165-200 tests.** Mirror DEV-04 (158) + ~10-15 compare/display/conformance + ~5-10 metrics/validation.

### 16.5. Files KHÔNG sửa (binding)

- `AGENTS.md` (READ-ONLY).
- `README.md` (READ-ONLY ở Phase 1; document lifecycle change will be Phase 2 closing summary).
- `docs/decisions/0001-*.md` … `0005-*.md` (READ-ONLY; new ADR may be needed at Phase 2 closing if open questions resolve to methodology change).
- `docs/methodology/*`, `docs/data_dictionary/*`, `docs/research/*` (READ-ONLY).
- `src/customer_segmentation/clustering/**`, `src/customer_segmentation/evaluation/**` (research core, READ-ONLY).
- `src/customer_segmentation/prototype/clustering/**` (DEV-04, READ-ONLY sau khi publish).
- `src/customer_segmentation/dataset_management/**` (DEV-02, READ-ONLY).
- `tests/test_dev04_*` (existing regression tests, must remain green).
- `tests/conftest.py` (chỉ ADD fixtures, KHÔNG modify existing DEV-03/04 fixtures).
- `pyproject.toml` (READ-ONLY; no new deps).
- `.gitignore` (READ-ONLY).

### 16.6. Completion summary (Phase 2 closing)

```
docs/system/DEV-05_completion_summary.md        # NEW — at Phase 2 closing; mirror DEV-04 §1-§11 structure
```

(Phase 1 không tạo completion summary; completion summary là ở Phase 2 closing.)

---

## 17. Verification commands dự kiến

(Phase 2 only; Phase 1 không chạy.)

```bash
# 1. Lint (ruff)
ruff check src/customer_segmentation/prototype/evaluation/ \
          scripts/dev05_evaluate_clustering.py \
          tests/test_dev05_*.py tests/conftest.py

# 2. Format check (black + ruff format)
ruff format --check src/customer_segmentation/prototype/evaluation/ \
                    scripts/dev05_evaluate_clustering.py \
                    tests/test_dev05_*.py tests/conftest.py
black --check src/customer_segmentation/prototype/evaluation/ \
              scripts/dev05_evaluate_clustering.py \
              tests/test_dev05_*.py tests/conftest.py

# 3. All tests
pytest -q tests/test_dev05_*.py

# 4. Regression (full project)
pytest -q

# 5. Static safety scan (no banned import)
python -c "
import ast, pathlib
SRC = pathlib.Path('src/customer_segmentation/prototype/evaluation')
forbidden = ['customer_segmentation.evaluation']
for p in SRC.rglob('*.py'):
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if any(f in n.name for f in forbidden):
                    print(f'FORBIDDEN: {p}:{node.lineno}: {n.name}')
        if isinstance(node, ast.ImportFrom):
            if node.module and any(f in node.module for f in forbidden):
                print(f'FORBIDDEN: {p}:{node.lineno}: {node.module}')
"

# 6. Manual CLI smoke (synthetic fixture, NOT real data)
python scripts/dev05_evaluate_clustering.py \
    --dataset-id ds_dev04test01 \
    --preprocessed-id pp_dev04test01 \
    --clustering-id <id from previous DEV-04 run on synthetic> \
    --config configs/dev05_evaluation.yaml
# Expected: stdout contains 'silhouette', 'davies_bouldin', 'calinski_harabasz';
# manifest + metrics_long.csv + log written; lifecycle = SUCCESS.

# 7. Compare smoke
python scripts/dev05_evaluate_clustering.py \
    --compare ev_xx ev_yy ev_zz
# Expected: stdout contains 'Compatibility key', side-by-side metric table;
# NO 'best', 'recommended', 'optimal', 'winner', 'ranking' (outside disclaimer).
```

Phase 2 completion requires: **all tests green** + **lint/format clean** + **no forbidden imports** + **CLI smoke output verified by operator reading stdout + 0 regression tests broken**.

---

## 18. Explicit stop gate trước implementation

**DEV-05 — Phase 1 STOP GATE.**

Phase 1 deliverable = this document (`docs/system/DEV-05_evaluation_module.md`). Phase 1 KHÔNG bao gồm:

- Implementation code (no `src/customer_segmentation/prototype/evaluation/*` files created).
- Config file (`configs/dev05_evaluation.yaml` not created).
- CLI script (`scripts/dev05_evaluate_clustering.py` not created).
- Tests under `tests/test_dev05_*` not created.
- Any edit to existing source/test/config.
- Running any clustering / evaluation against real data (no sklearn call on `data/processed/final_clustering_dataset.parquet`).
- Running any DEV-04 pipeline / pre-existing CLI against any data.
- Git operations (no commit / push / PR / merge / branch).

Phase 1 IS complete when this plan document is reviewed by human and passes the §1-§17 sections consistently.

**Approval token for Phase 2 (exact-match required, no paraphrase):**

```
APPROVE PHASE 2
```

Implementation **MUST NOT** start without this exact token from human reviewer. As of plan v1.2:

- **OQ-EVAL-NOISE** is **RESOLVED for the DEV-05 prototype layer** by `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006, Accepted 2026-10-09). The prototype implementation may proceed with uniform DBSCAN-noise exclusion for silhouette / DBI / CH (`noise_policy = "exclude"` default, CLI override available) once `APPROVE PHASE 2` is granted. ADR-0006 is prototype-scope; it does NOT modify the research-layer status of CON-15, WA-08, EXP01-MET-01, or `MENTOR_REVIEW_FORM_EXP01_EXP05.md`.
- **OQ-EVAL-04** (singleton compare), **OQ-EVAL-05** (CLI mode), **OQ-EVAL-06** (display convention) — **RESOLVED by implementer at Phase 2 start** (decisions in §15 table). AI implementer picks (B) / (A) / (A-with-CSV-carve-out) respectively per the §15 recommendation rows.
- **OQ-EVAL-EPIC-08** — note in completion summary §15; does not block DEV-05.

**Post-Phase-2 expectations (not Phase 1 deliverables):**

| Item | Owner |
|---|---|
| **OQ-EVAL-NOISE** — RESOLVED for prototype layer by ADR-0006; research-layer status (CON-15, WA-08, EXP01-MET-01, MENTOR_REVIEW_FORM line 47) **NOT modified** by ADR-0006 and still pending mentor / human researcher | Human researcher (mentor) at research layer; AI implementer at prototype layer |
| OQ-EVAL-04, OQ-EVAL-05, OQ-EVAL-06 — RESOLVED by AI implementer at Phase 2 start per §15 table | AI implementer (decided; recorded in §15) |
| OQ-EVAL-EPIC-08 — Note in completion summary §15 | AI implementer |
| Code creation in §16.1–§16.5 | AI implementer (Phase 2) |
| `docs/system/DEV-05_completion_summary.md` | AI implementer (Phase 2 closing) |
| Final research approval of DEV-05 outputs | Mentor / human researcher (post Phase 2) |

> **Reminder (AGENTS.md §2.10):** `TECHNICALLY IMPLEMENTED` ≠ `RESEARCH DECISION APPROVED`. Reaching `TECHNICALLY IMPLEMENTED` does NOT constitute research evidence; mentor approval required for that. The prototype-layer uniform-exclusion decision (ADR-0006) is one of the artefacts that **must not be cited as research evidence** until the mentor review form is signed and the research-layer status of CON-15 / WA-08 / EXP01-MET-01 is promoted by an additional ADR.

---

*Plan version: v1.2 (2026-10-09, Phase 1 revision). v1.2 changes: **OQ-EVAL-NOISE resolved for DEV-05 prototype layer** by `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006, Accepted 2026-10-09) adopting option (A) uniform DBSCAN noise exclusion across silhouette / DBI / CH with `noise_policy = "exclude"` default and CLI override; ADR-0006 is prototype-scope only and **does not modify** research-layer status of `SYS-01 §11 CON-15`, `SYS-04 §12.2`, `WA-08` (`METHODOLOGY_LOCK_STATUS`), `EXP01-MET-01` (`EXP01_baseline_experiment_PLAN.md`), or `MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47; plan §15 OQ table updated to RESOLVED status with explicit scope; plan §18 stop gate updated so `APPROVE PHASE 2` token is the only remaining gate before Phase 2 implementation can begin (OQ-EVAL-NOISE no longer blocks prototype implementation; OQ-EVAL-04/05/06 remain DEFERRED for AI implementer at Phase 2 start; OQ-EVAL-EPIC-08 noted in completion summary). v1.1 changes (preserved): consolidated OQ-EVAL-01/02 → **OQ-EVAL-NOISE** with `WORKING_ASSUMPTION = uniform DBSCAN noise exclusion across all three internal metrics, pending human sign-off`; rewrote §5.2.2 DBI, §5.2.3 CH, §5.3 edge-case matrix, §5.4 (new sub-sections 5.4.1–5.4.6) for the uniform policy; added `n_samples_input`, `noise_ratio` to `EvaluationMetricsResult` and DBSCAN example to manifest schema; expanded §9.3 per-row provenance + §9.5 caveat for differing `n_samples_used_for_compute`; added R-EVAL-14..R-EVAL-17 to §10.1 (noise immutability, source-agnostic metric set, manifest/CSV consistency, atomic publish); updated test matrix; added R-14..R-18 risks; §4.2 row inconsistency correction (moved `DBSCAN_NOISE_EXCLUDED` from NOT_APPLICABLE column to VALID_VALUE row; split "Metric computed ok" into two rows for clarity). Plan expires if not approved within 90 days of authoring; otherwise remains the binding source of truth for DEV-05 Phase 2 within the current prototype phase (ADR-0005 Option A).*
