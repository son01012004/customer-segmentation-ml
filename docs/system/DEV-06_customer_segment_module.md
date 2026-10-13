# DEV-06 — Customer Segment Module (Prototype Layer)

> **Mã task:** DEV-06
> **Tên:** Customer Segment Module (Jira pipeline: `Display segments /
> Display size / Display characteristics / Provide profiles / Provide
> comparison`)
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config,
> no ADR, no SYS edit, no Git op). Phase 2 (implementation) yêu cầu
> human approval token chính xác `APPROVE PHASE 2`.
> **Ngày:** 2026-10-10
> **Phạm vi:** Cung cấp **prototype-layer** capability để liệt kê,
> đo kích thước, lập hồ sơ (profile) và so sánh các customer
> segment từ output của DEV-04 clustering run, kết hợp với feature
> matrix của DEV-03 ML Dataset. Output = segment table + per-segment
> profile JSON/CSV + per-segment characteristics JSON + so sánh side-by-side,
> ghi vào
> `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/segmentation/<segmentation_id>/`.
> **Does NOT** sửa DEV-02/03/04/05 source hoặc contracts, không tự
> đặt tên segment business-y ("Champions", "Loyal"), không tạo
> ranking/điểm tổng hợp, không tự promote prototype segment output
> thành research evidence, không tự chạy trên `data/raw/primary/**` hoặc
> `data/processed/**` trong Phase 1, không tự decision noise policy
> thay cho ADR-0006.
> **Architecture:** Option A (ADR-0005) — offline, single-machine,
> file-based. No backend, no API, no database, no worker, no queue.
> **Kế thừa:**
> - DEV-04 `ClusteringManifest` v1.0.0 +
>   `cluster_labels_<experiment_id>.parquet` (CustomerID + ClusterLabel
>   + IsNoise + optional Probability_*/Membership_*).
> - DEV-03 `PreprocessedManifest` v1.0.0 + `ml_dataset_*.parquet` (feature
>   matrix sau transformation/scaling — giá trị đã được scale, KHÔNG phải
>   giá trị thô từ raw).
> - DEV-05 `EvaluationManifest` v1.0.0 (link provenance tới
>   evaluation pass; OPTIONAL input cho so sánh — nếu người dùng muốn
>   gắn metric vào segment table).
> - ADR-0006 (noise policy `"exclude"` mặc định cho prototype layer).
> - ADR-0003 (5 algorithms: kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans;
>   K-Medoids OUT OF SCOPE).
> - ADR-0004 (research questions RQ1/RQ2/RQ3 — KHÔNG thuộc DEV-06 scope;
>   chỉ tương tác gián tiếp qua output contract).
> **Ranh giới nghiêm ngặt với EPIC-09 / CP-01..05 (research layer):**
> DEV-06 chỉ làm **descriptive profiling** dựa trên statistics khách
> quan (mean / median / IQR / min / max / unique-count cho numerical;
> mode / top-k / value-counts cho categorical) và đo **size /
> percentage / characteristic**; **KHÔNG** làm "interpretability
> scoring", "distinctiveness index", "behavioral consistency" hay
> "business relevance" — những phần đó thuộc CP-01..05 (research layer),
> chưa được research-layer LOCK và KHÔNG được sao chép vào prototype.

---

## Mục lục

1. [Task scope và non-goals](#1-task-scope-v%C3%A0-non-goals)
2. [Source documents và contract references](#2-source-documents-v%C3%A0-contract-references)
3. [Current-state analysis](#3-current-state-analysis)
4. [Input/output contracts](#4-inputoutput-contracts)
5. [Module/API design](#5-moduleapi-design)
6. [Segment / noise / percentage semantics](#6-segment--noise--percentage-semantics)
7. [Feature profile và customer-characteristic rules](#7-feature-profile-v%C3%A0-customer-characteristic-rules)
8. [Comparison semantics](#8-comparison-semantics)
9. [Storage schema, provenance, determinism, safety](#9-storage-schema-provenance-determinism-safety)
10. [Implementation phases theo dependency order](#10-implementation-phases-theo-dependency-order)
11. [Acceptance criteria mapping](#11-acceptance-criteria-mapping)
12. [Test matrix](#12-test-matrix)
13. [Risks và mitigations](#13-risks-v%C3%A0-mitigations)
14. [Open questions / decisions cần human approval](#14-open-questions--decisions-c%E1%BA%A7n-human-approval)
15. [Files dự kiến tạo/sửa](#15-files-d%E1%BB%B1-ki%E1%BA%BFn-t%E1%BA%A1os%E1%AD%ADa)
16. [Verification commands dự kiến](#16-verification-commands-d%E1%BB%B1-ki%E1%BA%BFn)
17. [Explicit stop gate trước implementation](#17-explicit-stop-gate-tr%C6%B0%E1%BB%9Bc-implementation)

---

## 1. Task scope và non-goals

### 1.1. Task scope (in-scope, đối chiếu Jira description)

DEV-06 cung cấp **prototype-layer** capability để **đọc** clustering
output (DEV-04) + feature matrix (DEV-03) và **mô tả** các customer
segment theo 6 trục Jira + 5 acceptance criteria:

| # | Jira scope | DEV-06 deliverable (dự kiến Phase 2) |
|---|---|---|
| 1 | **Segment List** | `customer_segmentation.prototype.segmentation.profile.list_segments(segmentation_manifest)` → `list[SegmentSummary]` (id, size, percentage, source clustering_id) |
| 2 | **Segment Size** | `compute_segment_sizes(cluster_labels_df)` → `dict[segment_id, int]`; persisted as `segment_sizes.csv` |
| 3 | **Segment Percentage** | `compute_segment_percentages(sizes, *, n_samples, noise_policy)` → `dict[segment_id, float]`; denominator phải được recorded trong manifest (`n_samples_total`, `n_samples_used_for_compute`); theo noise policy (ADR-0006) |
| 4 | **Feature Profile** | `compute_feature_profiles(ml_dataset_df, cluster_labels_df, *, feature_set, noise_policy)` → `dict[segment_id, FeatureProfile]` với: per-feature mean / median / std / q1 / q3 / min / max (numerical) hoặc top-k categories + value_counts (categorical) — dựa trên feature type từ DEV-03 preprocessing manifest |
| 5 | **Customer Characteristics** | `compute_segment_characteristics(ml_dataset_df, cluster_labels_df, *, feature_set, thresholds)` → `dict[segment_id, CharacteristicReport]` với các đặc trưng traceable: ví dụ `Recency_quartile_distribution`, `Monetary_decile_distribution`; derived từ statistics ở (4), KHÔNG tự đặt tên business-y |
| 6 | **Segment Comparison** | `compare_segmentations([segmentation_manifest_paths])` → `ComparisonReport` với compatibility check dựa trên shared dataset_id + preprocessed_id + ml_dataset_sha256 + algorithm_family (mirror DEV-05 `compare_evaluations` pattern) |

**Phân biệt rõ với EPIC-09 / CP-01..05 (research layer):**

| Concern | EPIC-09 / CP-01..05 (research) | DEV-06 (prototype) |
|---|---|---|
| Owner | Research core (`customer_segmentation.profiling.*` hoặc `customer_segmentation.evaluation.experiment_results.*` — chưa implemented) | Prototype layer (`customer_segmentation.prototype.segmentation.*`) |
| Input | `data/processed/clustering_experiments/...` (185 runs EXP-01..05) | `data/prototype/.../clustering/<clustering_id>/...` (per-user, per-dataset) |
| Output | `reports/profiling/cp0X/...` (research evidence) | `data/prototype/.../segmentation/<segmentation_id>/...` (prototype) |
| Distinctiveness / Interpretability / Behavioral consistency / Business relevance scoring | IN SCOPE (CP-01..04) | **OUT OF SCOPE** (DESCRIPTIVE ONLY) |
| Composite score / ranking / "best segment" / segment naming ("Champions", "Loyal") | OUT OF SCOPE per AGENTS.md §3 "Profiling" + ADR-0003 + AGENTS.md §2.5 | **OUT OF SCOPE** (per AGENTS.md §3) |
| Promotion gate | Mentor + ADR (research methodology) | **NOT** promoted; `automatically_promoted_to_research = false` always |
| Noise policy | SYS-04 §12.2 + CON-15 = silhouette exclude noise; DBI / CH not yet locked at research layer | ADR-0006 (prototype default = "exclude"); same `noise_policy` field in DEV-06 manifest |

### 1.2. Non-goals (out-of-scope, bắt buộc)

| ❌ | Non-goal | Nguồn |
|---|---|---|
| ❌ | Đặt tên business-y cho segment ("Champions", "Loyal Customers", "At-Risk", ...) | AGENTS.md §3 "Profiling" row |
| ❌ | Composite score / ranking / "best segment" / winner / optimal / recommended | AGENTS.md §2.5, §2.6, §2.10 |
| ❌ | Causal / business interpretation ("likely to churn", "high-value target", ...) | AGENTS.md §2.5, §2.6 |
| ❌ | Modify DEV-02 / DEV-03 / DEV-04 / DEV-05 output contracts / manifests / source | AGENTS.md §2.2 phase isolation |
| ❌ | Modify research-core `customer_segmentation.evaluation.*` / `customer_segmentation.clustering.*` / `customer_segmentation.preprocessing.*` (read-only) | AGENTS.md §2.4, §3 |
| ❌ | EPIC-09 / CP-01..05 (Distinctiveness, Interpretability, Behavioral consistency, Business relevance, Final segment definition) | EPIC-09 owned; CP-01..05 plans not yet LOCKED; out-of-scope cho prototype layer |
| ❌ | Visualization (matplotlib / seaborn / plotly charts) | EPIC-10 owned; import blocklist theo R-DEV-06-NN |
| ❌ | Build backend / API / database / worker / queue | ADR-0005 Option A |
| ❌ | Promote prototype segmentation to research evidence | AGENTS.md §2.10 |
| ❌ | Run segmentation on `data/raw/primary/**` hoặc `data/processed/**` Phase 1 | AGENTS.md §2.12, §2.7 |
| ❌ | Read FE-06 `final_clustering_dataset.parquet` (research evidence) | AGENTS.md §2.3, R-DEV-06-09 |
| ❌ | Git operations (commit / push / PR / merge / branch) | AGENTS.md §2.11 |
| ❌ | Self-resolve noise policy decision (chỉ consume `noise_policy_used` từ DEV-05 manifest hoặc default từ ADR-0006) | AGENTS.md §2.9 |
| ❌ | Auto-invent new features / new statistics không có nguồn từ DEV-03 | AGENTS.md §2.1 |
| ❌ | Adjust clustering algorithm / threshold / n_clusters / eps / min_samples / noise policy tuỳ ý | AGENTS.md §2.9 |
| ❌ | Bổ sung library mới (giữ phụ thuộc theo `pyproject.toml` — numpy, pandas, pyarrow, pyyaml, scikit-learn) | AGENTS.md §5 |

### 1.3. Acceptance Criteria (5 mục của Jira — đối chiếu)

| AC | Description (verbatim từ task brief) | Phạm vi DEV-06 |
|---|---|---|
| AC-1 | Display segments. | Bao phủ. CLI `scripts/dev06_run_segmentation.py profile` in bảng segment list (id, size, pct); helper `format_segments_table(segments)` cho notebook. |
| AC-2 | Display size. | Bao phủ. `segment_sizes.csv` (id, count) + display bảng. |
| AC-3 | Display characteristics. | Bao phủ. `segment_characteristics.json` (per-segment CharacteristicReport) + display bảng flat. KHÔNG business naming; chỉ traceable statistics. |
| AC-4 | Provide profiles. | Bao phủ. `segment_profiles.csv` (per-segment × per-feature statistics, long-format) + `segment_profiles.json` (nested per-segment). |
| AC-5 | Provide comparison. | Bao phủ. `compare_segmentations(...)` + CLI `scripts/dev06_run_segmentation.py compare`. Compatibility check shared (dataset_id, preprocessed_id, ml_dataset_sha256, feature_set_sha256, algorithm_family). KHÔNG ranking. |

> **Lưu ý AGENTS.md §6.2:** Không tự bổ sung AC mới. Mọi yêu cầu kỹ thuật phát sinh (vd. "per-feature IQR display") là **implementation requirement**, không phải AC.

---

## 2. Source documents và contract references

> Mỗi phát biểu trong plan trích từ doc X phải đính kèm section reference.
> Plan **không** dùng statement nào không có nguồn (AGENTS.md §2.1, §2.7).

| Tài liệu | Vai trò cho DEV-06 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules (binding) | Toàn bộ |
| `docs/decisions/0003-algorithm-scope.md` (ADR-0003) | 5 algorithms only; K-Medoids OUT | Toàn bộ |
| `docs/decisions/0004-research-questions.md` (ADR-0004) | RQ1/RQ2/RQ3; DEV-06 KHÔNG cite làm research evidence | Toàn bộ |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture contract (Option A) | Toàn bộ |
| `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006) | Prototype-layer DBSCAN noise policy default = `"exclude"`; DEV-06 inherits | Toàn bộ |
| `docs/system/DEV-02_dataset_management.md` | DEV-02 storage contract; storage root resolution | Skim (§4, §7) |
| `docs/system/DEV-03_completion_summary.md` | DEV-03 ML Dataset output contract (`ml_dataset_*.parquet` + `PreprocessedManifest` v1.0.0) | Toàn bộ |
| `docs/system/DEV-04_clustering_execution.md` | DEV-04 plan; `ClusteringManifest` v1.0.0 schema | Toàn bộ |
| `docs/system/DEV-04_completion_summary.md` | DEV-04 implementation status; `cluster_labels_*.parquet` columns | Toàn bộ |
| `docs/system/DEV-05_evaluation_module.md` | DEV-05 plan; `EvaluationManifest` v1.0.0 schema; noise_policy_used field | Toàn bộ |
| `docs/system/DEV-05_completion_summary.md` | DEV-05 implementation status; pattern reference cho segmentation manifest | Toàn bộ |
| `docs/system/DEV-05_final_review_report.md` | DEV-05 final review status (`READY WITH ACCEPTED LIMITATIONS`) | Toàn bộ |
| `docs/research/EPIC09_CP05_PLAN.md` | EPIC-09 / CP-05 plan; ranh giới rõ ràng với DEV-06 | Toàn bộ (skim header + §1.3 "Ranh giới cứng") |
| `configs/dev05_evaluation.yaml` | Reference cho format `noise_policy` config block | Toàn bộ |
| `src/customer_segmentation/prototype/clustering/manifest.py` | `ClusteringManifest` dataclass + `ResearchSafetyBlock` shape; `CLUSTERING_MANIFEST_SCHEMA_VERSION = "1.0.0"` | Toàn bộ (skim) |
| `src/customer_segmentation/prototype/clustering/storage.py` | `prototype_clustering_run_dir` regex; `resolve_storage_root` pattern | Skim |
| `src/customer_segmentation/clustering/artifacts.py` | `cluster_labels_*.parquet` columns: CustomerID, ClusterLabel, IsNoise, optional Probability_*/Membership_* | §42..95 |
| `src/customer_segmentation/clustering/result.py` | `ClusterResult` schema; `noise_label = -1` (DBSCAN convention) | §148..280 |
| `src/customer_segmentation/prototype/preprocessing/manifest.py` | `PreprocessedManifest` v1.0.0; `MLDatasetBlock`; `PREPROCESSED_MANIFEST_SCHEMA_VERSION = "1.0.0"` | Skim header |
| `src/customer_segmentation/prototype/evaluation/manifest.py` | `EvaluationManifest` v1.0.0 pattern reference cho `SegmentationManifest` | Skim header + dataclass shape |
| `src/customer_segmentation/prototype/evaluation/scope.py` | `StrEnum` + frozen-set pattern; `EvaluatedScope` 1-value pattern | Skim |
| `src/customer_segmentation/prototype/evaluation/storage.py` | `derive_evaluation_id` + `compute_config_sha256` pattern; `prototype_evaluation_run_dir` regex | Skim |
| `src/customer_segmentation/prototype/evaluation/compare.py` | `CompatibilityKey` + `compare_evaluations` pattern reference | Skim |
| `docs/data_dictionary/data_dictionary.md` | Source schema cho raw data; DEV-06 chỉ consume từ DEV-03, KHÔNG re-read raw | §Column reference (skim) |

---

## 3. Current-state analysis

### 3.1. Data flow hiện tại (đã verify bằng source inspection)

```
data/raw/primary/Online Retail.xlsx                              (FE-02 source — KHÔNG DEV-06 read)
        │
        ▼ DEV-02
data/prototype/.../datasets/<ds_id>/manifest.json + source.parquet
        │
        ▼ DEV-03
data/prototype/.../preprocessed/<pp_id>/
        ├── preprocessed_manifest.json (PreprocessedManifest v1.0.0)
        │       └── ml_dataset_block.artifact_path → ml_dataset_<sha>.parquet
        └── ml_dataset_<sha>.parquet
                columns: CustomerID + (feature_set from preprocessing.feature_set)
                values: TRANSFORMED + SCALED (per DEV-03 default config)
        │
        ▼ DEV-04
data/prototype/.../clustering/<cl_id>/
        ├── clustering_manifest.json (ClusteringManifest v1.0.0)
        │       fields: clustering_id, preprocessed_id, ml_dataset_sha256,
        │               algorithm, algorithm_family, n_clusters, n_samples,
        │               feature_set, hyperparameters, ...
        ├── cluster_labels_<exp_id>.parquet
        │       columns: CustomerID (or RowIndex), ClusterLabel (int64),
        │               IsNoise (bool), [Probability_*]?, [Membership_*]?
        ├── experiment_log_<exp_id>.json (full ExperimentResult)
        └── (optional) algorithm_output_<exp_id>.parquet
        │
        ▼ DEV-05 (optional, per ADR-0006)
data/prototype/.../clustering/<cl_id>/evaluation/<ev_id>/
        ├── evaluation_manifest.json (EvaluationManifest v1.0.0)
        │       fields: evaluation_id, clustering_id, preprocessed_id,
        │               dataset_id, noise_policy_used, metric_set, metrics
        └── metrics_long.csv
        │
        ▼ DEV-06 (planned)
data/prototype/.../clustering/<cl_id>/segmentation/<seg_id>/
        ├── segmentation_manifest.json (SegmentationManifest v1.0.0 — NEW)
        ├── segment_sizes.csv
        ├── segment_profiles.csv
        ├── segment_profiles.json
        ├── segment_characteristics.json
        └── <seg_id>.log
```

**Quan sát (verified bằng source):**

1. `cluster_labels_*.parquet` có cột `ClusterLabel` (int64, `DBSCAN_NOISE_LABEL = -1` per
   `src/customer_segmentation/clustering/result.py:227`) và cột `IsNoise` (bool, derived
   `out["IsNoise"] = (out["ClusterLabel"] == cluster_result.noise_label).astype(bool)`
   per `artifacts.py:79`). Đây là nguồn `ClusterLabel` cho DEV-06. Trong default DEV-04
   call, cột CustomerID được attach; fallback `RowIndex` chỉ dùng khi caller không
   cung cấp `customer_metadata_df` (không phải default flow).
2. `ml_dataset_*.parquet` (DEV-03 output) là feature matrix đã scale, có thể chứa cột
   `CustomerID` (nếu DEV-03 config `feature_generation.aggregation.customer_key =
   "CustomerID"`). DEV-04 `_split_matrix` (pipeline.py:296..317) detect `CustomerID` /
   `customer_id` / `Customer ID` và tách ra khỏi feature matrix; nhưng file trên disk
   vẫn giữ CustomerID. DEV-06 dùng CustomerID (nếu có) hoặc row-index position
   (fallback) để align với `cluster_labels_*.parquet`.
3. CustomerID alignment: trong default DEV-04 flow, `cluster_labels_*.parquet` có cùng
   row order với `ml_dataset_*.parquet` (per DEV-04 contract; verified trong
   `artifacts.py:64..67` + `pipeline.py:1246..1250`).
4. `ClusteringManifest` v1.0.0 có `algorithm_family` (string enum: `hard` |
   `density_based` | `model_based` | `fuzzy` | `other`; per
   `src/customer_segmentation/clustering/result.py:70..81`).
5. `ClusteringManifest` KHÔNG có `preprocessing_config_sha256` (đã verify qua source).
   `preprocessing_config_sha256` chỉ có ở `PreprocessedManifest` (`PREPROCESSED_MANIFEST_SCHEMA_VERSION = "1.0.0"`). Vì vậy DEV-06 phải đọc `PreprocessedManifest` (L3) để lấy `config_hash`/`preprocessing_config_sha256` chính xác (KHÔNG dùng fallback placeholder như DEV-05 pipeline.py:363).
6. `ClusteringManifest` KHÔNG có `noise_policy_used` (chỉ DEV-05 EvaluationManifest
   mới có). DEV-06 sẽ dùng: nếu user cung cấp `--evaluation-id` (DEV-05 manifest
   path), đọc `noise_policy_used` từ đó; nếu không, dùng config default
   (`"exclude"` per ADR-0006) hoặc CLI override.
7. `clustering_manifest.json` (DEV-04) có `feature_set` (list[str]) — list chính xác
   các cột feature trong `ml_dataset_*.parquet` (loại CustomerID). DEV-06 dùng để
   xác định per-feature type.
8. **Non-DBSCAN algorithms (K-Means / Agglomerative / GMM / Fuzzy C-Means) KHÔNG sinh
   noise label = -1.** Vì vậy với các algorithm này, `ClusterLabel.min() >= 0`,
   `noise_count = null`, `noise_ratio = null`, `n_clusters_input = n_segments`.
   Field `noise_policy_used` trong DEV-06 manifest chỉ có ý nghĩa khi
   `algorithm_family == "density_based"`.

### 3.2. Reusable code (read-only) từ DEV-04 / DEV-05

| Code từ DEV-04/05 | Vai trò cho DEV-06 | Read-only? |
|---|---|---|
| `read_clustering_manifest(Path)` | Load `clustering_manifest.json` | ✅ read-only |
| `read_evaluation_manifest(Path)` (optional) | Load `evaluation_manifest.json` để lấy `noise_policy_used` | ✅ read-only |
| `prototype_clustering_run_dir(...)` regex | Path resolution pattern | ✅ read-only |
| `resolve_storage_root(...)` | Storage root từ `configs/dev02_dataset_management.yaml` | ✅ read-only |
| `compute_config_sha256(config_text)` | SHA-256 cho config reproducibility | ✅ read-only |
| `ClusteringManifest.algorithm_family` enum | Phân loại hard / density_based / model_based / fuzzy | ✅ read-only |
| `DBSCAN_NOISE_LABEL = -1` constant | Sentinel cho noise label | ✅ read-only |
| `PerStageLogger` pattern | Per-stage logging façade | Mirror pattern; KHÔNG import từ `evaluation.logging_config` (sẽ tự tạo bản sao trong `segmentation.logging_config`) |
| `Atomic write` pattern (staging → `os.rename`) | Để bảo toàn dữ liệu khi ghi | Mirror; không extend module có sẵn |
| `CompatibilityKey` pattern | Compare-segmentation compatibility check | Mirror; không extend |

**Quyết định (dự kiến Phase 2):** DEV-06 KHÔNG import trực tiếp từ
`customer_segmentation.prototype.evaluation.*` hay
`customer_segmentation.prototype.clustering.*` ở runtime (mirror R-DEV-06-15
import-blocklist). Chỉ import:
- `customer_segmentation.prototype.clustering.manifest.read_clustering_manifest` (cần cho load clustering_id source)
- `customer_segmentation.prototype.preprocessing.manifest.read_preprocessed_manifest` (cần cho load ml_dataset_block reference)
- `customer_segmentation.clustering.result.AlgorithmFamily` enum
- `customer_segmentation.clustering.artifacts.DBSCAN_NOISE_LABEL` constant

Lý do: bảo toàn ranh giới module; sau này nếu DEV-04/05 refactor internal,
DEV-06 chỉ phụ thuộc vào dataclass public fields + enum + hằng số — không
phụ thuộc internal helpers.

### 3.3. DEV-04/05 invariants mà DEV-06 phải tôn trọng (đã verify)

- DEV-04 chỉ ghi artifact vào `clustering/<cl_id>/`; DEV-06 chỉ đọc.
- DEV-05 chỉ ghi artifact vào `evaluation/<ev_id>/`; DEV-06 chỉ đọc (optional).
- DEV-04 `clustering_manifest.json` SHA được bảo toàn qua mọi stage; DEV-06
  không modify manifest.
- DEV-05 manifest có `research_safety.automatically_promoted_to_research = false`
  always; DEV-06 mirror pattern với `SegmentationScope.PROFILED_PROTOTYPE`.
- DEV-04 / DEV-05 storage layout: `data/prototype/.../clustering/<cl_id>/...`.
  DEV-06 output đặt cùng cấp `evaluation/` subdir: `clustering/<cl_id>/segmentation/<seg_id>/...`.

---

## 4. Input/output contracts

### 4.1. Input contracts

DEV-06 consume (READ-ONLY) từ 3 nguồn:

| Layer | File | Schema | Required? |
|---|---|---|---|
| L1 | `data/prototype/.../clustering/<cl_id>/clustering_manifest.json` | `ClusteringManifest` v1.0.0 (per `src/customer_segmentation/prototype/clustering/manifest.py:CLUSTERING_MANIFEST_SCHEMA_VERSION`) | **Required** |
| L2 | `data/prototype/.../clustering/<cl_id>/cluster_labels_<exp_id>.parquet` (path from L1.cluster_labels_path) | Columns: `CustomerID` (default) hoặc `RowIndex` (fallback), `ClusterLabel` (int64, -1 = noise for DBSCAN), `IsNoise` (bool), optional `Probability_*` (GMM) / `Membership_*` (FCM) | **Required** |
| L3 | `data/prototype/.../preprocessed/<pp_id>/preprocessed_manifest.json` | `PreprocessedManifest` v1.0.0; `ml_dataset_block.artifact_path` (cho L4) + `config_hash` (canonical `preprocessing_config_sha256`) | **Required** — L3 cần để có canonical `preprocessing_config_sha256` (KHÔNG dùng fallback placeholder như DEV-05 vì ảnh hưởng comparison key) |
| L4 | `data/prototype/.../preprocessed/<pp_id>/ml_dataset_<sha>.parquet` (path from L3) | Columns: `CustomerID` (optional) + `feature_set` columns (per L1.feature_set). Giá trị đã qua transformation + scaling per DEV-03 `optional_transform` config. | **Required** |
| L5 (optional) | `data/prototype/.../clustering/<cl_id>/evaluation/<ev_id>/evaluation_manifest.json` | `EvaluationManifest` v1.0.0; `noise_policy_used` field (canonical noise policy của upstream evaluation pass) | Optional — nếu cung cấp, DEV-06 dùng `noise_policy_used` của L5 làm default; nếu không, dùng config `"exclude"` per ADR-0006. **KHÔNG yêu cầu L5 tồn tại** (DEV-06 hoạt động độc lập với DEV-05). |

**Validation rules (Stage B, parallel DEV-05):**

1. L1 exists, parses to `ClusteringManifest`, schema_version == "1.0.0".
2. L1.cluster_labels_path tồn tại (dùng để load L2).
3. L2 exists, has `ClusterLabel` column (dtype int64), `IsNoise` (dtype bool). Có
   thể có `CustomerID` (preferred) hoặc `RowIndex` (fallback).
4. L3 exists, `ml_dataset_block.artifact_path` non-empty, `config_hash` non-empty.
5. L4 exists at `L3.ml_dataset_block.artifact_path`.
6. `L1.n_samples == L2.shape[0] == L4.shape[0]` (row alignment).
7. `L1.feature_set` ⊆ L4.columns (excluding CustomerID if present).
8. CustomerID alignment (nếu cả L2 và L4 có CustomerID): `L2.CustomerID ==
   L4.CustomerID` (row-by-row). Nếu L2 chỉ có `RowIndex`: position-based
   alignment (assume same order). Nếu L4 có CustomerID nhưng L2 chỉ có
   `RowIndex`: vẫn dùng position-based (verified DEV-04 contract).
9. `ClusterLabel` values ⊆ `[noise_label]` ∪ `[0, L1.n_clusters-1]`. Warn if
   unexpected. **Non-DBSCAN algorithms (algorithm_family != "density_based"):
   `ClusterLabel.min() >= 0`** (no noise label).
10. (Optional) L5 if provided: schema_version == "1.0.0", `clustering_id ==
    L1.clustering_id`. Cross-check `ml_dataset_sha256` L5 == L4 sha256.

### 4.2. Output contracts (DEV-06 emits)

Per segmentation pass (1 DEV-06 call), output layout dưới:

```
<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/
    segmentation/<segmentation_id>/
        segmentation_manifest.json            (atomic write — frozen dataclass schema v1.0.0; NEW)
        segment_sizes.csv                     (id, count) — 1 row per segment + noise
        segment_sizes_long.csv                (id, count, percentage, percentage_base) — 1 row per segment
        segment_profiles.csv                  (long-format: segment_id, feature_name, statistic, value, value_str)
        segment_profiles.json                 (nested: {segment_id: {feature_name: {statistic: value}}})
        segment_characteristics.json          (nested: {segment_id: {characteristic_id: {description, source_features, derived_stats}}})
        <segmentation_id>.log                 (per-stage log; mirror DEV-04 / DEV-05 pattern)
```

**`segmentation_manifest.json` schema (v1.0.0; NEW for DEV-06):**

```python
{
  "schema_version": "1.0.0",
  "segmentation_id": "seg_<24-hex-sha256>",   # content-addressed
  "scope": "PROFILED_PROTOTYPE",              # PROFILED_PROTOTYPE (1-value enum)
  "created_utc": "...",
  "last_seen_utc": "...",
  "log_file": "...",

  # Provenance pointers
  "clustering_id": "cl_...",
  "preprocessed_id": "pp_...",
  "dataset_id": "ds_...",
  "evaluation_id": "ev_..." or null,          # optional link to DEV-05
  "algorithm": "kmeans" | ...,
  "algorithm_family": "hard" | "density_based" | "model_based" | "fuzzy",
  "ml_dataset_sha256": "<64-hex>",
  "feature_set_sha256": "<64-hex>",
  "preprocessing_config_sha256": "<64-hex>",

  # Noise policy (mirrors DEV-05 evaluation manifest if available)
  "noise_policy_used": "exclude" | "include",
  "n_samples_input": int,
  "n_samples_used_for_compute": int,           # = n_samples_input - noise_count under exclude
  "n_clusters_input": int,                    # raw unique label count incl. -1
  "n_segments": int,                          # n_clusters_realized (post-noise-policy)
  "noise_count": int | null,
  "noise_ratio": float | null,

  # Feature profile
  "feature_set": list[str],                   # from L1.feature_set
  "statistics_computed": list[str],           # subset of {mean, median, std, q1, q3, min, max, topk_categories, value_counts}
                                                # — Phase 2: subset chosen by config

  # Inputs (paths)
  "input_clustering_manifest": "clustering_manifest.json",
  "input_cluster_labels": "cluster_labels_<exp_id>.parquet",
  "input_ml_dataset": "ml_dataset_<sha>.parquet",
  "input_evaluation_manifest": "evaluation_manifest.json" | null,

  # Determinism
  "config_sha256": "<64-hex>",                # SHA-256 of dev06 config YAML
  "feature_set_sha256": "<64-hex>",
  "environment": {
    "python": "3.11.x",
    "platform": "...",
    "key_libraries": {"pandas": "...", "numpy": "...", "scikit-learn": "..."}
  },

  # Research safety
  "research_safety": {
    "automatically_promoted_to_research": false,
    "appeared_in_research_evidence": false,
    "scope": "PROFILED_PROTOTYPE"
  }
}
```

**`segment_sizes_long.csv` schema (long-format):**

```csv
segment_id,count,percentage,percentage_base,is_noise
0,1180,0.6243,n_samples_used_for_compute,false
1,512,0.2707,n_samples_used_for_compute,false
2,201,0.1063,n_samples_used_for_compute,false
-1,2010,0.4791,n_samples_input,true
```

`percentage_base` documents the denominator explicitly per OQ-SEG-DENOM-01
(§6). See §6 for policy.

**`segment_profiles.csv` schema (long-format):**

```csv
segment_id,feature_name,statistic,value,value_str,is_diagnostic_only
0,Recency,mean,0.123,0.123,false
0,Recency,median,0.045,0.045,false
0,Recency,std,0.234,0.234,false
0,Recency,q1,-0.456,-0.456,false
0,Recency,q3,0.567,0.567,false
0,Recency,min,-1.234,-1.234,false
0,Recency,max,2.345,2.345,false
0,Monetary,mean,0.567,...
...
0,Country,topk_categories,3,United Kingdom|Netherlands|France,false
0,Country,value_counts,1234|234|45,United Kingdom:1234; Netherlands:234; France:45,false
```

**`segment_characteristics.json` schema (nested):**

```json
{
  "0": {
    "characteristic_id": "high_monetary_share",
    "description": "Mean Monetary > dataset mean + 1 std",
    "source_features": ["Monetary"],
    "derived_stats": {"Monetary_mean": 0.567, "dataset_Monetary_mean": 0.0, "dataset_Monetary_std": 0.234, "z_threshold": 1.0},
    "is_invariant": false
  },
  ...
}
```

**`comparison_report.json` schema (mirror DEV-05 `compare_evaluations`):**

```json
{
  "schema_version": "1.0.0",
  "compared_at_utc": "...",
  "groups": [
    {
      "compatibility_key": {
        "dataset_id": "ds_...",
        "preprocessed_id": "pp_...",
        "ml_dataset_sha256": "<64-hex>",
        "feature_set_sha256": "<64-hex>",
        "preprocessing_config_sha256": "<64-hex>"
      },
      "segmentations": ["seg_...", "seg_..."],
      "fields_compared": ["n_segments", "size_distribution", "feature_profiles"]
    }
  ],
  "incompatibility_reasons": [],
  "disclaimer": "no ranking, recommendation, or winner annotation is emitted; descriptive comparison only"
}
```

### 4.3. Identity / link chain

```
ds_id (DEV-02) ──→ pp_id (DEV-03) ──→ cl_id (DEV-04) ──→ ev_id (DEV-05, optional) ──→ seg_id (DEV-06)
   │                  │                  │                       │                          │
   │                  │                  │                       │                          │
   └── source_dataset ┴── ml_dataset_    ┴── cluster_labels     ┴── evaluation              ┴── segmentation
                      ── _sha256            _sha256?              _manifest.json            _manifest.json
```

- `segmentation_id` = `"seg_" + SHA256(canonical_json(...))[:24]`, canonical
  fields: 8 fields:
  1. `clustering_id`
  2. `preprocessed_id`
  3. `dataset_id`
  4. `ml_dataset_sha256`
  5. `feature_set_sha256`
  6. `preprocessing_config_sha256`
  7. `noise_policy_used`
  8. `schema_version = "1.0.0"`

  (Idempotent: same input + same config + same noise policy → same
  `segmentation_id`.)

---

## 5. Module/API design

### 5.1. Package layout (dự kiến Phase 2)

```
src/customer_segmentation/prototype/segmentation/
├── __init__.py                  (re-exports public API)
├── scope.py                     (enums + frozen constants: ProfiledScope, SegmentationStage, NOISE_POLICIES, STATISTICS_SET)
├── storage.py                   (content-addressed id, path resolution, segmentation_run_dir regex)
├── config_loader.py             (YAML loader → SegmentationConfig dataclass; default configs/dev06_segmentation.yaml)
├── manifest.py                  (SegmentationManifest dataclass; ResearchSafetyBlock; SEGMANIFEST_SCHEMA_VERSION = "1.0.0")
├── profile.py                   (per-segment feature profile computation: numerical statistics, categorical top-k)
├── characteristics.py           (per-segment characteristic derivation from profile stats; rules engine)
├── compare.py                   (CompatibilityKey + compare_segmentations + format_comparison_table)
├── display.py                   (format_segments_table, format_profiles_table, format_characteristics_table, banned-substring check)
├── logging_config.py            (PerStageLogger façade; mirror DEV-04/05 pattern)
├── pipeline.py                  (Stage A→H orchestrator: run_segmentation_pipeline)
└── validation.py                (Stage B input validation: validate_segmentation_inputs)
```

### 5.2. Public API (mirror DEV-05 pattern)

```python
# src/customer_segmentation/prototype/segmentation/__init__.py
from .scope import (
    ProfiledScope,                # PROFILED_PROTOTYPE (1-value)
    SegmentationStage,            # A → H enum
    NOISE_POLICIES,               # ("exclude", "include")
    STATISTICS_SET,               # closed set of statistic names
    run_segmentation_pipeline,    # top-level driver
)
from .manifest import (
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,  # "1.0.0"
    SegmentationManifest,
    SegmentSize,
    FeatureProfile,
    CharacteristicReport,
    ResearchSafetyBlock,
    read_segmentation_manifest,
    write_segmentation_manifest,
    build_segmentation_manifest,
)
from .profile import (
    compute_segment_sizes,
    compute_segment_percentages,
    compute_feature_profiles,
    format_profiles_long_csv,
)
from .characteristics import (
    derive_segment_characteristics,
    format_characteristics_json,
)
from .compare import (
    CompatibilityKey,
    ComparisonGroup,
    IncompatibilityReason,
    ComparisonReport,
    compare_segmentations,
)
from .display import (
    format_segments_table,
    format_profiles_table,
    format_characteristics_table,
    format_comparison_table,
    check_no_banned_substrings,
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
)
from .pipeline import (
    SegmentationPipelineResult,
    run_segmentation_pipeline,
)
```

### 5.3. CLI script (mirror DEV-05)

```
scripts/dev06_run_segmentation.py   (Phase 2 — DO NOT CREATE IN PHASE 1)
```

Sub-commands (mirror DEV-05):

- `profile --dataset-id <ds> --preprocessed-id <pp> --clustering-id <cl> [--evaluation-id <ev>] [--noise-policy exclude|include] [--config <yaml>]`
  → run full pipeline, write `segmentation_manifest.json` + 4 CSVs/JSONs.

- `list --segmentation-manifest <path>`
  → print segment list (id, size, percentage).

- `sizes --segmentation-manifest <path>`
  → print `segment_sizes_long.csv` as table.

- `profiles --segmentation-manifest <path> [--segment-id <id>]`
  → print per-segment feature profile.

- `characteristics --segmentation-manifest <path> [--segment-id <id>]`
  → print per-segment characteristic.

- `compare --segmentation-manifest <path1> <path2> [<path3> ...]`
  → run `compare_segmentations`, print compatibility report.

---

## 6. Segment / noise / percentage semantics

### 6.1. Segment list (AC-1)

**Definition:** Một segment là một unique value trong cột `ClusterLabel`
(đã áp dụng `noise_policy_used`):

- `noise_policy_used = "exclude"` (default per ADR-0006): segment IDs
  ∈ `[0, n_clusters-1]`. Noise (`ClusterLabel == -1`) **không** phải
  segment; được report riêng ở `noise_count` / `noise_ratio` /
  `segment_sizes_long.csv` với flag `is_noise = true`.
- `noise_policy_used = "include"`: segment IDs ∈ `[-1, n_clusters-1]`,
  trong đó `-1` là một segment (gọi là "noise segment" trong
  report, KHÔNG gọi là "real segment"). Flag `is_noise = true` cho
  segment `-1` để reader phân biệt.

**Source-of-truth:** `cluster_labels_<exp_id>.parquet` (DEV-04) + `L1.n_clusters`.

**Output:**

- `segment_sizes_long.csv`: 1 row per segment (bao gồm noise nếu `include`).
- `segment_sizes.csv`: chỉ non-noise segments (filter out noise để tránh
  nhầm lẫn với "real segment").

### 6.2. Segment size (AC-2)

**Definition:** `count(ClusterLabel == segment_id)`.

- Đơn vị: integer (number of customers).
- Source: `cluster_labels_<exp_id>.parquet`.
- Validation: `sum(counts for all segments) == n_samples_input` (hoặc
  `== n_samples_input - noise_count` nếu `exclude` và bỏ noise).

**Output:** `segment_sizes.csv` (id, count) + `segment_sizes_long.csv`
(id, count, percentage, percentage_base, is_noise).

### 6.3. Segment percentage (AC-3) — OQ-SEG-DENOM-01 (open question)

**Mở — cần human decision** (xem §14):

Có 2 baseline options:

| Option | Denominator (`percentage_base`) | Khi nào phù hợp | Ưu / nhược |
|---|---|---|---|
| **A: `n_samples_input`** | Tổng số customer trong DEV-03 ML Dataset (kể cả DBSCAN noise nếu có) | Đọc theo tỷ lệ "thị phần" trong toàn bộ customer base | Transparent; "Có bao nhiêu % tổng số customer thuộc segment này?" — câu hỏi analyst thường gặp. |
| **B: `n_samples_used_for_compute`** | Tổng số customer sau khi áp dụng `noise_policy` | So sánh segment composition bên trong nhóm non-noise | Khi noise = 50%, các non-noise segment có percentage tăng gấp đôi; có thể misleading. |

**Đề xuất Phase 2 (PROPOSED, PENDING_HUMAN_REVIEW — RECOMMENDATION A):**

- **Default `percentage_base = "n_samples_input"`** (A). Rationale: analyst-friendly,
  không bị "nhân đôi" khi noise cao; alignment với "Có bao nhiêu % customer?" mà
  user thường hỏi.
- **Cả hai percentages** (A và B) đều được recorded trong `segment_sizes_long.csv`:
  cột `percentage` (default = A) + cột `percentage_of_non_noise` (B; = NULL nếu
  không áp dụng được, vd. all-noise). Cột `percentage_base` documents rõ
  denominator mà `percentage` dùng.
- CLI flag `--percentage-base input|non_noise` (default `input`) cho phép override
  cột "primary" percentage; secondary column luôn cả hai.
- Rounding: 4 decimal places (mirror DEV-05 metric rounding).

**KHÔNG tự decision (theo AGENTS.md §2.9, §2.10):** đây là methodology choice
(ảnh hưởng mọi segment comparison) → escalate lên human owner.

### 6.4. Noise handling — OQ-SEG-NOISE-01 (open question)

**Mở — cần human decision:**

**Quan trọng — algorithm-family gating:**

- **DBSCAN (`algorithm_family == "density_based"`)**: có `ClusterLabel = -1` là
  noise. `noise_count`, `noise_ratio`, `n_clusters_input` đều có giá trị.
  `noise_policy_used` áp dụng (mặc định `"exclude"` per ADR-0006).
- **K-Means / Agglomerative / GMM / Fuzzy C-Means** (`algorithm_family !=
  "density_based"`): KHÔNG có noise. `ClusterLabel.min() >= 0`. Trong
  `segmentation_manifest.json`:
  - `noise_count = null`
  - `noise_ratio = null`
  - `n_clusters_input = n_segments`
  - `noise_policy_used = "n/a"` (closed enum thêm `"n/a"` value, mirror
    ADR-0006 style) — KHÔNG phải `"exclude"` vì không có noise để exclude.
  - Trong `segment_sizes_long.csv`: KHÔNG có row noise.

| Decision | Options | Impact | Owner |
|---|---|---|---|
| Default `noise_policy` (DBSCAN only) | A: `"exclude"` (per ADR-0006) / B: `"include"` (raw sklearn) | A: giữ consistent với DEV-05; B: hiển thị noise như segment riêng | Human owner (default: A, mirror ADR-0006) |
| Noise display strategy | A: noise KHÔNG xuất hiện trong segment list; B: noise xuất hiện với flag `is_noise=true`; C: noise summary ở cuối report | A: consistent với "real segments" semantics; B: full transparency; C: cleaner | Human owner (default: B) |
| Noise characteristics | Nếu show noise, có compute feature profile cho noise? | Nếu có, profile noise cũng phải tuân thủ same statistics; có thể gây hiểu nhầm "noise = real segment" | Human owner (default: KHÔNG compute profile cho noise) |

**Đề xuất Phase 2 (PROPOSED, PENDING_HUMAN_REVIEW):**
- Default `noise_policy = "exclude"` (DBSCAN only).
- Noise vẫn xuất hiện trong `segment_sizes_long.csv` với `is_noise=true`
  (full transparency) nhưng KHÔNG xuất hiện trong `segment_sizes.csv` (clean
  list cho human reading).
- Profile + characteristics KHÔNG compute cho noise (mặc định; dùng
  `--include-noise-profile` flag nếu muốn override) để tránh implying noise = segment.

### 6.5. Empty / single-segment edge cases

- **All-noise case** (`n_clusters_realized == 0` sau khi filter):
  - `n_segments = 0`; `segment_sizes.csv` empty.
  - `segment_profiles.csv` empty.
  - `segment_characteristics.json` empty.
  - `n_clusters_input = 0 or 1` (tuỳ DBSCAN output).
  - Display: emit `(no segments — all rows classified as noise)`.

- **Single-segment case** (K=1 hoặc tất cả label cùng giá trị):
  - `n_segments = 1`; segment ID = 0 (or 1, tuỳ algorithm).
  - Profile + characteristics vẫn compute (statistics vẫn valid cho 1 segment).
  - KHÔNG emit warning; chỉ ghi `n_segments = 1` trong manifest.

- **Empty cluster_labels** (ClusterLabel all NaN, or 0 rows):
  - Validation Stage B FAIL → `Dev06PipelineError`, no manifest written.

- **Label set mismatch** (`ClusterLabel.max() + 1 != n_clusters`):
  - Validation Stage B warning, KHÔNG fail (e.g. K-Means có thể tạo cluster
    rỗng nếu init xấu; vẫn compute size cho non-empty segments).

---

## 7. Feature profile và customer-characteristic rules

### 7.1. Feature type classification (mirror DEV-03)

DEV-06 xác định feature type từ 2 nguồn:

1. **DEV-03 `preprocessed_manifest.preprocessing_block.transformation` /
   `scaling` field:** nếu `scaling = "standard"` / `"robust"` / `"minmax"`,
   thì numeric features đã được scale (giá trị KHÔNG còn ở scale gốc).
2. **Per-column dtype** từ `ml_dataset_*.parquet`:
   - `int64` / `float64` → `numerical`
   - `category` / `object` (low-cardinality, ≤ 50 unique) → `categorical`
   - `object` (high-cardinality) → `text_or_id` (KHÔNG compute profile; warning)

**Tránh re-read DEV-03 manifest nếu không cần:** DEV-06 chỉ cần
`ml_dataset_block.artifact_path` + `preprocessing.feature_set` để biết
feature columns. Feature type phát hiện từ dtype là đủ.

### 7.2. Feature profile statistics (numerical)

Cho mỗi `segment_id`, mỗi `feature_name` ∈ `L1.feature_set`:

```python
{
  "mean": float,
  "median": float,
  "std": float,
  "q1": float,            # 25th percentile (linear interp)
  "q3": float,            # 75th percentile
  "min": float,
  "max": float,
  "missing_count": int,   # NaN count in this segment
  "missing_ratio": float, # NaN count / segment size
  "n_samples_used": int,  # non-NaN count in this segment
}
```

**Implementation:** `pandas.Series.describe()` cho `mean, std, min, max, q1, q3, median`
+ custom missing count.

**Edge case:** nếu segment size = 0 hoặc n_samples_used = 0, ghi `null`
cho tất cả statistics; KHÔNG dùng placeholder `0` (R-DEV-06-08, mirror
R-EVAL-08 no-fake-default).

**Edge case:** nếu variance = 0 (constant feature within segment), `std = 0`;
ghi `0.0` thật (không phải fake default).

### 7.3. Feature profile statistics (categorical)

Cho mỗi `segment_id`, mỗi `feature_name` categorical:

```python
{
  "topk_categories": list[str],          # top-k by count (k = config.topk, default 10)
  "topk_counts": list[int],
  "unique_count": int,                   # number of unique values
  "missing_count": int,
  "missing_ratio": float,
  "n_samples_used": int,
}
```

**Top-k config:** `STATISTICS_TOPK` default = 10 (config-overridable; per
OQ-SEG-DISPLAY-01).

**Tie-breaking cho top-K:** Nếu 2 categories có cùng count ở rank K, dùng
alphabetical order (ascending) để phá vỡ tie (deterministic).

**Out-of-top-K handling:** categories không nằm trong top-K được gộp thành
`other_count` (int) — tổng count của các categories bị omitted. Field
`topk_categories` KHÔNG đại diện cho toàn bộ distribution; chỉ là top-K.
Field `unique_count` documents tổng số unique values trong segment.

### 7.4. Customer characteristics — OQ-SEG-CHAR-01 (open question)

**Nguyên tắc (theo AGENTS.md §2.1, §2.5):**

- Characteristics phải **descriptive**, dựa trên statistics đã compute ở §7.2/7.3.
- KHÔNG tự đặt tên business-y ("Champions", "Loyal"); characteristics_id dùng
  format `descriptive_<statistic>_<feature>` (vd. `mean_high_monetary`,
  `top_country_uk`, `low_recency_mean`).
- Mỗi characteristic PHẢI có:
  - `description`: phát biểu toán học / thống kê, không phải interpretation.
    VD: `"Monetary mean is in the top quartile of segment means"` thay vì
    `"High-value customers"`.
  - `source_features`: list feature đã dùng để derive.
  - `derived_stats`: dict statistics tham chiếu.
  - `is_invariant`: false (characteristics KHÔNG phải business claim).

**Characteristic rules engine (PROPOSED Phase 2; cần human approval cho
default rule set — OQ-SEG-CHAR-01):**

| Rule ID | Description | Threshold (config) | Source features |
|---|---|---|---|
| `mean_high_<feature>` | Segment mean of `<feature>` > dataset mean + `N` * dataset std | N = 1.0 (default) | 1 numerical |
| `mean_low_<feature>` | Segment mean of `<feature>` < dataset mean - `N` * dataset std | N = 1.0 | 1 numerical |
| `median_above_dataset_median_<feature>` | Segment median > dataset median | n/a | 1 numerical |
| `top_category_<feature>_<value>` | Top-1 category of `<feature>` in segment is `<value>` | n/a | 1 categorical |
| `category_diversity_low_<feature>` | `unique_count / segment_size < threshold` | 0.1 (default) | 1 categorical |
| `missing_share_high_<feature>` | `missing_ratio > threshold` | 0.05 (default) | 1 numerical/categorical |

**Quyết định PENDING_HUMAN_REVIEW (OQ-SEG-CHAR-01):** default rule set
trên chỉ là đề xuất; mentor/human researcher cần approve trước Phase 2
vì rule set này sẽ là "vocabulary" của DEV-06 output.

**KHÔNG được phép:**
- Rule dẫn đến segment naming ("this is a 'loyal' segment").
- Rule dùng business claim ("likely to churn", "high LTV", "target for marketing").
- Rule sử dụng thresholds không có config record (vd. magic number).

### 7.5. Mapping to acceptance criteria

| AC | Implementation path |
|---|---|
| AC-1 Display segments | `display.format_segments_table(segment_sizes_long)` |
| AC-2 Display size | `display.format_sizes_table(segment_sizes)` |
| AC-3 Display characteristics | `display.format_characteristics_table(segment_characteristics)` |
| AC-4 Provide profiles | `profile.compute_feature_profiles(...)` → `segment_profiles.csv` + `segment_profiles.json` |
| AC-5 Provide comparison | `compare.compare_segmentations(...)` → `comparison_report.json` |

---

## 8. Comparison semantics

### 8.1. Comparison group key (mirror DEV-05 `CompatibilityKey`, narrowed per §14.2.7 / R-DEV-06-24)

Hai `segmentation_manifest` được gom vào cùng comparison group nếu và
chỉ nếu **tất cả 4 trường** sau khớp nhau:

1. `dataset_id` (DEV-02)
2. `preprocessed_id` (DEV-03)
3. `ml_dataset_sha256` (DEV-03)
4. `feature_set_sha256` (DEV-03 + DEV-04, derived)

> **Lưu ý:** `preprocessing_config_sha256` được ghi trong
> `segmentation_manifest.json` như provenance nhưng **KHÔNG** thuộc
> compatibility key (R-DEV-06-24). Lý do: `clustering_manifest.json`
> v1.0.0 không có field này; tái sử dụng theo cơ chế cũ sẽ kế thừa
> DEV-05 placeholder defect (`"f" * 64`) — xem §19.6.

Lý do: cùng dataset / preprocessing / feature space → comparable; khác
→ không comparable (xem §8.3 về exclusion semantics).

**Ngoài comparison group key, comparison row còn record (per-row provenance):**

- `algorithm`
- `algorithm_family`
- `noise_policy_used`
- `n_segments` (count, không phải thành viên của key)
- `noise_count`
- `noise_ratio`

Nếu 2 manifest cùng group key nhưng khác 1 trong các per-row fields
trên → emit `incompatibility_reasons` row (giữ trong group) nhưng
KHÔNG reject group (descriptive comparison vẫn có giá trị cho người
đọc; cảnh báo explicit). Đây là phân biệt quan trọng với
`exclusion_reasons` (xem §8.3).

### 8.2. Comparison output (không ranking)

**Output (`comparison_report.json`):**

```json
{
  "schema_version": "1.0.0",
  "compared_at_utc": "...",
  "groups": [
    {
      "compatibility_key": {...},
      "segmentations": ["seg_...", "seg_..."],
      "size_distribution": [
        {"segmentation_id": "seg_...", "segment_id": 0, "count": 1180, "percentage": 0.6243},
        ...
      ],
      "feature_profiles_diff": [
        {"feature_name": "Recency", "segment_id": 0, "seg1_mean": 0.123, "seg2_mean": 0.234, "delta": 0.111}
      ]
    }
  ],
  "incompatibility_reasons": [
    {"segmentation_id": "seg_...", "field_name": "algorithm", "stored_value": "kmeans", "compared_value": "dbscan"}
  ],
  "disclaimer": "no ranking, recommendation, or winner annotation is emitted; descriptive comparison only"
}
```

**KHÔNG emit:**

- `best_segmentation`, `best_segment`, `winner`, `recommended`.
- `composite_score` / `aggregate_score` / `overall_quality`.
- `rank` (numeric ordering) cho segments.
- Statistical significance tests (chi-square, t-test) — those are
  research-layer concerns, EPIC-08/09 owned.

**Disclaimer bắt buộc (mirror R-EVAL-08):**

> no ranking, recommendation, or winner annotation is emitted; descriptive comparison only.

### 8.3. Single-manifest, all-incompatible, and mixed-case edge cases (per P1-3 resolution, 2026-10-10)

Hai khái niệm lý do được tách bạch (R-DEV-06-26):

- **`incompatibility_reasons`** (đã có từ Phase 2D): per-row
  provenance diffs **trong cùng** group. Dùng cho per-row fields
  (`algorithm`, `algorithm_family`, `noise_policy_used`, `n_segments`,
  `noise_count`, `noise_ratio`).
- **`exclusion_reasons`** (NEW per P1-3): manifests bị loại khỏi
  `groups` vì key không match với bất kỳ manifest nào khác trong
  multi-manifest call. Dùng cho key fields (`dataset_id`,
  `preprocessed_id`, `ml_dataset_sha256`, `feature_set_sha256`).

**Quy tắc (deterministic; không optional flag, không competing behavior):**

- **Single-manifest call** (1 path): emit 1 `ComparisonGroup`
  singleton với `note = "singleton — no comparison possible"`; không
  có per-row diff; `exclusion_reasons = []`.
- **Multi-manifest call, ≥1 shared key (≥2 manifests share key đó)**:
  emit chỉ các group có ≥2 members; các manifest còn lại (key chỉ
  match với chính nó) được route sang `exclusion_reasons` thay vì
  được emit như singleton group.
- **All-incompatible call** (multi-manifest, không có shared key
  nào): emit `groups = []`; populate `exclusion_reasons` cho MỌI
  manifest; mỗi entry có `no_retained_group = true` (không có group
  nào để anchor).
- **Mixed call** (≥1 multi-member group + ≥1 excluded manifest):
  retain mọi multi-member compatible group; report mọi excluded
  manifest qua `exclusion_reasons`; **không** chọn anchor group
  tuỳ ý. `differing_key_field_names` cho mỗi excluded manifest
  list các key field có giá trị unique vs MỌI retained group
  (anchor-free).
- **Same-key + different per-row field**: 1 group với 1+
  `incompatibility_reasons` (per-row fields); không ảnh hưởng bởi
  rule trên.
- **Duplicate input handling**: paths trùng (cùng `segmentation_id`)
  dedupe trước khi partition; first occurrence wins (R-DEV-06-27).

**Output (NEW top-level fields per R-DEV-06-27):**

```json
{
  "schema_version": "1.0.0",
  "compared_at_utc": "...",
  "groups": [...],            // chỉ multi-member (hoặc singleton call)
  "incompatibility_reasons": [...],   // per-row diffs trong cùng group
  "exclusion_reasons": [
    {
      "excluded_segmentation_id": "seg_...",
      "excluded_key": {
        "dataset_id": "...",
        "preprocessed_id": "...",
        "ml_dataset_sha256": "...",
        "feature_set_sha256": "..."
      },
      "reason_code": "excluded_no_shared_key",
      "differing_key_field_names": ["dataset_id"],
      "no_retained_group": true | false
    }
  ],
  "total_input_count": 3,
  "total_compared_count": 2,
  "total_excluded_count": 1,
  "disclaimer": "no ranking, recommendation, or winner annotation is emitted; descriptive comparison only"
}
```

**Invariants (added in P1-3 resolution):**

- R-DEV-06-26: `incompatibility_reasons` và `exclusion_reasons` là
  hai field riêng biệt; key-field diffs KHÔNG xuất hiện trong
  `incompatibility_reasons`; per-row diffs KHÔNG xuất hiện trong
  `exclusion_reasons`.
- R-DEV-06-27: `total_input_count == total_compared_count +
  total_excluded_count` (luôn luôn đúng; verified bằng 5 test case
  ở 4 input shape).
- R-DEV-06-24 (carried from Phase 1.5): key chỉ chứa 4 field
  đã liệt kê; `preprocessing_config_sha256` không bao giờ trong
  key.

**Determinism:** input order được giữ (group order, exclusion order);
output JSON có thể reproduce với cùng input + config.

---

## 9. Storage schema, provenance, determinism, safety

### 9.1. Storage layout (đã verify qua DEV-04 / DEV-05 patterns)

```
<storage_root>/datasets/<ds_id>/preprocessed/<pp_id>/clustering/<cl_id>/
    segmentation/<seg_id>/
        segmentation_manifest.json
        segment_sizes.csv
        segment_sizes_long.csv
        segment_profiles.csv
        segment_profiles.json
        segment_characteristics.json
        <seg_id>.log
```

- `<storage_root>` resolved từ `configs/dev02_dataset_management.yaml`
  (shared với DEV-02/03/04/05); KHÔNG có CLI override `--storage-root`.
- `segmentation_id` derived từ 8 canonical fields (xem §4.3).
- Atomic write pattern: staging dir → `os.rename` → final dir (mirror
  DEV-04 / DEV-05).

### 9.2. Determinism (per AGENTS.md §2.7)

- `segmentation_id` content-addressed: same input + same config →
  same id.
- `feature_set_sha256` derived từ sorted feature list (deterministic).
- `config_sha256` derived từ raw config YAML text.
- Profile statistics dùng `pandas.describe()` (deterministic for given
  input).
- **Idempotency:** `find_existing_segmentation(seg_id)` re-uses
  existing manifest if collision detected (mirror DEV-05).
- **Force-rerun:** CLI flag `--force-rerun`; backup old run + atomic
  publish.

### 9.3. Provenance chain (đầy đủ)

`segmentation_manifest.json` chứa (mirror DEV-05 `EvaluationManifest`):

- `clustering_id` (canonical pointer to DEV-04)
- `preprocessed_id` (canonical pointer to DEV-03)
- `dataset_id` (canonical pointer to DEV-02)
- `ml_dataset_sha256` (from DEV-03)
- `feature_set_sha256` (derived)
- `preprocessing_config_sha256` (from DEV-03)
- `algorithm` + `algorithm_family` (from DEV-04)
- `noise_policy_used` (from DEV-05 evaluation OR config default)
- `environment` block (python, platform, libraries)
- `research_safety` block (always false)

### 9.4. Research-safety invariants (R-DEV-06-NN) — NEW for DEV-06

| # | Invariant | Verification |
|---|---|---|
| R-DEV-06-01 | `research_safety.automatically_promoted_to_research = False` always | `TestResearchSafetyBlock` |
| R-DEV-06-02 | `research_safety.appeared_in_research_evidence = False` always | `TestResearchSafetyBlock` |
| R-DEV-06-03 | `research_safety.scope = "PROFILED_PROTOTYPE"` always (1-value enum) | `TestResearchSafetyBlock` |
| R-DEV-06-04 | No write to `data/raw/**`, `data/interim/**`, `data/external/**` | `TestPathContainment` (mirror R-EVAL-04) |
| R-DEV-06-05 | No write to `reports/**` | `TestPathContainment` (mirror R-EVAL-05) |
| R-DEV-06-06 | Writes only into `segmentation/<seg_id>/` subtree | `TestPathContainment` (mirror R-EVAL-06) |
| R-DEV-06-07 | No write to DEV-02..05 staging / backup / failed-tracking dirs | `TestPathContainment` (mirror R-EVAL-07) |
| R-DEV-06-08 | No "best/winner/optimal/ranking/composite_score/recommended/high-value/loyal/champion/churn" outside disclaimer | `TestCheckNoBannedSubstrings` (extend R-EVAL-08 with extra business terms) |
| R-DEV-06-09 | Never reads `final_clustering_dataset.parquet` (research evidence) | `TestNoFe06Reference` (mirror R-EVAL-09) |
| R-DEV-06-10 | DEV-03 ML Dataset parquet bytes unchanged before vs after run | `TestUpstreamImmutability` (mirror R-EVAL-10) |
| R-DEV-06-11 | DEV-04 cluster_labels / clustering_manifest SHA unchanged | `TestUpstreamImmutability` (mirror R-EVAL-11) |
| R-DEV-06-12 | DEV-05 evaluation_manifest SHA unchanged (nếu consumed) | `TestUpstreamImmutability` (mirror R-EVAL-12) |
| R-DEV-06-13 | `statistics_set` restricted to closed set (no ARI/AMI/PCA/silhouette — those live in research core) | `TestStatisticsSetClosed` (mirror R-EVAL-12 pattern) |
| R-DEV-06-14 | No test against real FE-06 data | `TestNoFe06Reference` (mirror R-EVAL-13) |
| R-DEV-06-15 | Import blocklist: forbidden imports target research-core only. Blocked patterns: `customer_segmentation.evaluation.` (research core, NOT `customer_segmentation.prototype.evaluation.`), `customer_segmentation.profiling.*` (research core, EPIC-09 nếu có), `customer_segmentation.feature_engineering.*` (research core, FE-01..06), `customer_segmentation.preprocessing.` (research core, NOT prototype.preprocessing) | `TestImportBlocklist` (mirror R-EVAL-15; regex with negative lookbehind for `.prototype.`) |
| R-DEV-06-16 | Manifest / CSV / JSON consistency (same n_segments, same segment_ids, same is_noise flags) | `TestManifestCsvConsistency` (mirror R-EVAL-16) |
| R-DEV-06-17 | Atomic publish (temp file + rename) | `TestAtomicPublish` (mirror R-EVAL-17) |
| R-DEV-06-18 | Segment naming NOT emitted (no "Champions", "Loyal", "At-Risk" auto-naming) | `TestNoBusinessNaming` (NEW for DEV-06) |
| R-DEV-06-19 | Characteristic IDs descriptive only (no business claim) | `TestCharacteristicDescriptiveOnly` (NEW for DEV-06) |
| R-DEV-06-20 | Per-segment profile references feature set trong clustering_manifest.feature_set (no extra features) | `TestFeatureSetClosure` (NEW for DEV-06) |

> R-DEV-06-21..25 (Phase 1.5: percentage denominators, non-DBSCAN
> noise, post-preprocessing warning, 4-field key, top-K consistency)
> are documented in §20.2. R-DEV-06-26..27 (P1-3 resolution:
> compare reason concepts separate; summary counts exact) are
> documented in §20.2a.

### 9.5. Static checks

- **Import blocklist** (`tests/test_dev06_import_blocklist.py`): 5 tests;
  scan source cho forbidden imports. Blocklist targets research-core only;
  `customer_segmentation.prototype.*` subpackages (including
  `prototype.evaluation`) are allowed for read-only consumption:
  - `customer_segmentation.evaluation.` (research core; NOT
    `customer_segmentation.prototype.evaluation.`) — research-core
    evaluation module, EPIC-08/09 owned.
  - `customer_segmentation.profiling.*` (research core, EPIC-09 nếu có).
  - `customer_segmentation.feature_engineering.*` (research core, FE-01..06).
  - `customer_segmentation.preprocessing.` (research core; NOT
    `customer_segmentation.prototype.preprocessing.`).
  - `customer_segmentation.transformation.*` (research core).
  - `matplotlib`, `seaborn`, `plotly` (visualization, EPIC-10 owned).
  - `sklearn.cluster.*` (re-implement clustering — chỉ dùng qua
    `customer_segmentation.clustering.*` DEV-04 contract).
  - Regex form: `(?<!prototype\.)customer_segmentation\.evaluation\.` để
    tránh false-positive match.

- **AST scan** for forbidden function calls: `os.remove`, `shutil.rmtree`,
  `Path.unlink` ngoài staging → final rename context (mirror R-DEV-04-14).

---

## 10. Implementation phases theo dependency order

(Phase 2 — CHƯA thực hiện trong Phase 1 này. Plan ghi để human reviewer
ước lượng effort.)

| Phase | Sub-phase | Component | Test focus |
|---|---|---|---|
| **2A** | Scope enums | `scope.py` (ProfiledScope, SegmentationStage, NOISE_POLICIES, STATISTICS_SET) | Enum invariant tests |
| **2A** | Storage | `storage.py` (derive_segmentation_id, find_existing_segmentation, path resolution) | Storage + idempotency tests |
| **2A** | Config | `config_loader.py` + `configs/dev06_segmentation.yaml` | YAML loader + dataclass tests |
| **2B** | Manifest | `manifest.py` (SegmentationManifest schema + atomic I/O) | Round-trip + atomic write |
| **2C** | Profile | `profile.py` (compute sizes, percentages, feature profiles) | Numerical + categorical + edge cases |
| **2C** | Characteristics | `characteristics.py` (rule engine, default rules from §7.4) | Rule engine + descriptive invariant |
| **2D** | Compare | `compare.py` (CompatibilityKey, compare_segmentations) | Compatibility + no-ranking |
| **2E** | Display | `display.py` (format tables, banned-substring check) | Display + R-DEV-06-08 |
| **2F** | Validation | `validation.py` (input validation report) | Stage B tests |
| **2G** | Logging | `logging_config.py` (PerStageLogger) | Logging façade tests |
| **2H** | Pipeline | `pipeline.py` (Stage A→H driver) | End-to-end with synthetic ML Dataset |
| **2I** | CLI | `scripts/dev06_run_segmentation.py` | CLI argparser + sub-command tests |
| **2J** | Safety | All R-DEV-06-NN tests in `test_dev06_research_safety.py` | Research safety invariants |
| **2K** | Import blocklist | `test_dev06_import_blocklist.py` | Static AST scan |
| **2L** | Runtime deps | `test_dev06_runtime_dependencies.py` | No new libs |

**Ước lượng test count (mirror DEV-05 = 214 tests, DEV-04 = 158 tests):**
~180-220 tests. Cụ thể: ~30 storage/scope, ~40 manifest, ~30 profile, ~20
characteristics, ~20 compare, ~20 display, ~25 research-safety, ~10 import
blocklist, ~5 runtime deps, ~10 CLI, ~15 pipeline integration.

---

## 11. Acceptance criteria mapping

| AC | Description | Test / verification | Phase 2 file |
|---|---|---|---|
| **AC-1** | Display segments. | `test_dev06_display.py::TestFormatSegmentsTable` (5 tests) + `test_dev06_cli.py::TestListSubCommand` (2 tests) | `display.py`, `scripts/dev06_run_segmentation.py` |
| **AC-2** | Display size. | `test_dev06_display.py::TestFormatSizesTable` (4 tests) + `test_dev06_cli.py::TestSizesSubCommand` (2 tests) | `display.py`, `scripts/dev06_run_segmentation.py` |
| **AC-3** | Display characteristics. | `test_dev06_display.py::TestFormatCharacteristicsTable` (5 tests) + `test_dev06_cli.py::TestCharacteristicsSubCommand` (2 tests) + `TestCharacteristicDescriptiveOnly` (R-DEV-06-19) | `display.py`, `characteristics.py`, `scripts/dev06_run_segmentation.py` |
| **AC-4** | Provide profiles. | `test_dev06_profile.py::TestComputeFeatureProfiles` (15 tests) + `TestFormatProfilesTable` (3 tests) + `TestProfileCsvSchema` (3 tests) + `TestFeatureSetClosure` (R-DEV-06-20) | `profile.py`, `display.py` |
| **AC-5** | Provide comparison. | `test_dev06_compare.py::TestCompareSegmentations` (8 tests) + `TestNoBannedSubstrings` (R-DEV-06-08) + `TestCompatibilityPartition` (3 tests) + `test_dev06_cli.py::TestCompareSubCommand` (2 tests) | `compare.py`, `display.py`, `scripts/dev06_run_segmentation.py` |

**Static checks:**

- `test_dev06_research_safety.py` — 20 tests covering R-DEV-06-01..20.
- `test_dev06_import_blocklist.py` — 5 tests (forbidden imports).
- `test_dev06_runtime_dependencies.py` — 3 tests (no new libs).

**Manual / deferred checks (per AGENTS.md §2.8):**

- Synthetic data run (Phase 2); no real dataset.
- Lint (`ruff check .`); format (`black --check .`).
- Full regression DEV-02..06.

---

## 12. Test matrix

### 12.1. Unit tests (per component)

| File | Tests (~) | Coverage |
|---|---|---|
| `test_dev06_scope.py` | 22 | Enum invariants, frozenset symmetry, NOISE_POLICIES closed set, STATISTICS_SET closed set |
| `test_dev06_storage.py` | 38 | `segmentation_id` derivation, regex, path containment, find_existing, collision |
| `test_dev06_config.py` | 28 | YAML parsing, defaults, error paths, dataclass invariants |
| `test_dev06_manifest.py` | 41 | Round-trip, atomic write, density_based noise_count, scope enforcement |
| `test_dev06_profile.py` | 30 | Numerical stats correctness, categorical top-k, missing values, edge cases, defensive copies |
| `test_dev06_characteristics.py` | 20 | Rule engine, default rules, descriptive invariant (R-DEV-06-19) |
| `test_dev06_compare.py` | 14 | Compatibility partition, no-ranking guarantee, provenance |
| `test_dev06_display.py` | 22 | Format tables, R-DEV-06-08 banned-substring scan, business-terms scan |
| `test_dev06_research_safety.py` | 20 | R-DEV-06-01..20 invariants |
| `test_dev06_import_blocklist.py` | 5 | Forbidden imports |
| `test_dev06_runtime_dependencies.py` | 3 | Declared deps only |
| `test_dev06_cli.py` | 10 | CLI argparser, sub-commands |
| `test_dev06_pipeline.py` | 15 | End-to-end with synthetic ML Dataset |

**Tổng ước lượng:** ~268 tests.

### 12.2. Edge case tests (chuẩn bị Phase 2)

| Test ID | Scenario | Expected |
|---|---|---|
| `test_segmentation_all_noise_dbscan` | DBSCAN all rows → `ClusterLabel = -1` | `n_segments = 0`; `noise_count = n_samples_input`; profile empty; manifest emitted with `n_clusters_input=0` |
| `test_segmentation_single_cluster` | K-Means K=1 | `n_segments = 1`; profile + characteristics computed for segment 0 |
| `test_segmentation_dbscan_default_exclude` | DBSCAN with `noise_policy="exclude"` (default) | `n_segments = n_clusters_realized`; noise not in `segment_sizes.csv`; noise in `segment_sizes_long.csv` with `is_noise=true` |
| `test_segmentation_dbscan_include_override` | DBSCAN with `noise_policy="include"` | `n_segments = n_clusters_realized + 1`; noise segment in `segment_sizes.csv` with `is_noise=true` |
| `test_segmentation_kmeans_basic` | K-Means K=4 | `n_segments = 4`; profile + characteristics computed for all 4 |
| `test_segmentation_agglomerative_basic` | Agglomerative K=3 | `n_segments = 3`; profile + characteristics |
| `test_segmentation_gmm_basic` | GMM K=4 | `n_segments = 4`; optional `Probability_*` columns in cluster_labels NOT used for profile (Phase 2) |
| `test_segmentation_fuzzy_cmeans_basic` | Fuzzy C-Means K=3 | `n_segments = 3`; optional `Membership_*` columns NOT used for profile (Phase 2) |
| `test_segmentation_percentage_rounding` | Synthetic sizes [1, 2, 3, 4] | Sum to 1.0000 (4 decimal rounding); explicit per-row `percentage_base` |
| `test_segmentation_compare_compatible` | 2 manifests cùng group key | 1 group; size_distribution side-by-side; 0 incompatibility reasons |
| `test_segmentation_compare_incompatible_dataset` | 2 manifests khác `dataset_id` | 0 groups; 1 incompatibility_reason for `dataset_id` |
| `test_segmentation_compare_incompatible_noise_policy` | 2 manifests cùng group key, khác `noise_policy_used` | 1 group; 1 incompatibility_reason for `noise_policy_used` (per-row field, not group key) |
| `test_segmentation_singleton_group` | 1 manifest only | 1 group with 1 member; note "singleton" |
| `test_segmentation_input_alignment_fail` | `L1.n_samples != L2.shape[0]` | Validation FAIL; `Dev06PipelineError` raised; no manifest written |
| `test_segmentation_ml_dataset_missing` | L4 không tồn tại | Validation FAIL; `Dev06PipelineError`; no manifest written |
| `test_segmentation_clustering_manifest_missing` | L1 không tồn tại | Validation FAIL; `Dev06PipelineError`; no manifest written |
| `test_segmentation_no_business_naming` | Grep DEV-06 source cho "Champion", "Loyal", "At-Risk", "high-value" | 0 matches outside disclaimer / test data |
| `test_segmentation_no_ranking_in_compare` | Generate `comparison_report.json` cho 2 manifests | 0 matches cho "best", "winner", "ranking", "composite" |
| `test_segmentation_atomic_publish` | Crash mid-write | Staging dir cleaned; previous run preserved (no partial manifest) |
| `test_segmentation_idempotency` | Run 2 lần cùng input + config | Same `segmentation_id`; 2nd run re-uses existing (no duplicate) |

### 12.3. Synthetic fixtures (no real data)

Phase 2 sẽ tạo fixtures trong `tests/fixtures/dev06/` (synthetic):

- `synthetic_ml_dataset.parquet`: 100 rows × 4 numerical + 1 categorical
  features + CustomerID (1..100). Dùng cho unit tests.
- `synthetic_clustering_manifest.json`: mirror DEV-04 schema, n_samples=100,
  feature_set=[4 numerical + 1 categorical], algorithm=kmeans,
  n_clusters=4, clustering_id="cl_synthetic_...".
- `synthetic_cluster_labels.parquet`: 100 rows × {CustomerID, ClusterLabel,
  IsNoise} with K-Means-style labels.
- `synthetic_evaluation_manifest.json`: optional, mirror DEV-05 schema.

**Quan trọng:** KHÔNG sử dụng `data/raw/primary/Online Retail.xlsx`
hoặc `data/processed/**` trong tests (R-DEV-06-14).

---

## 13. Risks và mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R-1 | DEV-06 output bị hiểu nhầm là "segment naming" / "business claim" | High — vi phạm AGENTS.md §3 "Profiling" | R-DEV-06-08 + R-DEV-06-18 + R-DEV-06-19 enforce; banlist tăng cường với "Champion", "Loyal", "high-value", "at-risk", "churn", "marketing" |
| R-2 | Feature type phát hiện sai (e.g. ZIP code bị coi là numerical) | Medium — profile statistics meaningless | Card-50 check (≥ 50 unique object → `text_or_id` → skip with warning); defensive: ghi warning vào log |
| R-3 | DEV-06 deviated sang EPIC-09 scope (distinctiveness scoring, behavioral consistency) | High — scope expansion | Import blocklist R-DEV-06-15; explicit non-goal §1.2; static check for forbidden method names (`compute_distinctiveness`, `score_interpretability`) |
| R-4 | `percentage_base` interpretation sai (OQ-SEG-DENOM-01) | Medium — analyst confusion | Default record cả 2 percentages trong `segment_sizes_long.csv` (với `percentage_base` column) cho transparency; CLI flag override |
| R-5 | Noise policy applied khác DEV-05 (do user chọn `--noise-policy include` ở DEV-05, default ở DEV-06) | Medium — comparison invalid | Record `noise_policy_used` trong `segmentation_manifest.json`; emit `incompatibility_reason` khi compare với manifest khác `noise_policy_used` |
| R-6 | DEV-06 trở thành "implicit ranking" qua size + characteristics summary | Low — analyst tự interpret | Disclaimer bắt buộc trong mọi display; không compute composite; banlist includes "ranking" |
| R-7 | DEV-06 output bị silently promote (e.g. docx export cho marketing team) | High — protocol violation | R-DEV-06-01..03 + R-DEV-06-15 + R-DEV-06-18 enforce; README note "PROTOTYPE ONLY" |
| R-8 | Schema drift giữa DEV-04 `ClusteringManifest` v1.0.0 (không có `feature_set_sha256`) và DEV-06 requirement | Low — DEV-06 computes `feature_set_sha256` itself | DEV-06 derives from L1.feature_set, không depend on field có sẵn |
| R-9 | DEV-06 đọc `final_clustering_dataset.parquet` (research evidence) | High — protocol violation | R-DEV-06-09 + R-DEV-06-14 enforce; import blocklist cấm `customer_segmentation.feature_engineering.*` |
| R-10 | `cluster_labels_*.parquet` có `Probability_*` / `Membership_*` columns (GMM/FCM) bị dùng cho profile | Medium — out-of-scope statistic | Profile KHÔNG đọc `Probability_*` / `Membership_*`; chỉ đọc `CustomerID`, `ClusterLabel`, `IsNoise`; defensive check |

---

## 14. Open questions / decisions cần human approval

> Theo AGENTS.md §2.10, §6: methodology-relevant decisions cần human
> approval; không tự settle.
>
> **Status semantics (per Phase 1.5 review, updated 2026-10-10):**
> - `PROPOSED — AWAITING HUMAN APPROVAL`: mặc định cho mọi OQ; Phase 2
>   KHÔNG được bắt đầu cho đến khi human owner gửi explicit approval token.
> - `DECIDED — OWNER-AUTHORIZED`: human owner đã ghi nhận quyết định
>   trong task brief §3; rationale + constraints documented in §14.2.
> - `REJECTED`: chỉ khi human owner explicit reject.
> - `DEFERRED`: postponed sang phase sau; documented nhưng không resolve.

> **Phase 1.5 update (2026-10-10):** All 10 OQs below are now
> `DECIDED — OWNER-AUTHORIZED` per task brief §3. Detailed rationale,
> behavioral requirements, and per-decision constraints are documented
> in §14.2 (after this table). Phase 2 may begin after human owner sends
> explicit `APPROVE PHASE 2` token.

| ID | Question | Options | **Proposal status** | Owner |
|---|---|---|---|---|
| OQ-SEG-DENOM-01 | `percentage_base` mặc định nào cho `segment_percentage`? | A: `n_samples_input`; B: `n_samples_used_for_compute` (after noise policy) | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.1):** Primary = `n_samples_input`; secondary = `percentage_of_non_noise` (denominator = `n_samples_used_for_compute`, null if 0); both percentages rounded 2 dp; reconcile to ≈ 100% within rounding; see §14.2.1. | Human owner |
| OQ-SEG-NOISE-01 | Noise display strategy: noise có xuất hiện trong segment list? | A: noise excluded; B: noise included với `is_noise=true`; C: noise summary ở cuối report | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.2):** Preserve `ClusterLabel = -1`; `is_noise` flag in output; noise included in `percentage_input` denominator, excluded from `percentage_of_non_noise`; non-DBSCAN → noise fields = null (not invented); see §14.2.2. | Human owner |
| OQ-SEG-CHAR-01 | Default rule set cho characteristic derivation (§7.4) — dùng luôn 6 rules đề xuất hay chỉ 1-2 rules? | A: all 6 rules; B: only `mean_high_<feature>` + `mean_low_<feature>`; C: no default rules (caller must specify) | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.3):** Reduced set of 4 rules — retain `mean_high_<feature>`, `mean_low_<feature>`, `median_above_dataset_median_<feature>`, `top_category_<feature>_<value>`; remove `category_diversity_low_<feature>` + `missing_share_high_<feature>` (profile stats, not characteristics); see §14.2.3. | Human owner / mentor |
| OQ-SEG-PROFILE-01 | Profile có bao gồm DEV-03 `feature_set` mở rộng (nếu có extended features từ FE-02..06 mà chưa được thêm vào `preprocessing.feature_set`)? | A: chỉ dùng `L1.feature_set`; B: dùng full `ml_dataset_*.parquet` columns (excluding CustomerID) | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.4):** Default = `L1.feature_set`; preserve feature order; values are post-preprocessing (scaled/transformed), NOT original — explicit warning in output; per-feature type detection (numerical / boolean / categorical / text_or_id / datetime); see §14.2.4. | Human owner |
| OQ-SEG-INHERIT-01 | DEV-06 có bắt buộc `evaluation_id` (DEV-05 manifest) để tồn tại? | A: required; B: optional (default to ADR-0006 "exclude") | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.5):** Optional. DEV-06 operates on DEV-04 alone; L5 (DEV-05 manifest) cross-checked for compatibility + provenance if provided; never fabricated; see §14.2.5. | Human owner |
| OQ-SEG-LAYOUT-01 | Output dir: `clustering/<cl_id>/segmentation/<seg_id>/` hay `clustering/<cl_id>/profiling/<seg_id>/`? | A: `segmentation/...`; B: `profiling/...` | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.6):** `segmentation/` subdir; path containment; atomic publish; idempotency; no modification of DEV-04/05 storage; see §14.2.6. | Human owner |
| OQ-SEG-COMPARE-01 | Compare có cho phép across `algorithm_family`? | A: chỉ same `algorithm_family`; B: any; emit incompatibility reason | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.7):** 4-field compatibility key (dataset_id, preprocessed_id, ml_dataset_sha256, feature_set_sha256) — NO `preprocessing_config_sha256` (avoid DEV-05 placeholder defect); `algorithm_family` is per-row provenance, not in key; reject comparison when key is empty; see §14.2.7. | Human owner |
| OQ-SEG-NAMESPACE-01 | Config file location: `configs/dev06_segmentation.yaml`? | A: `configs/dev06_segmentation.yaml`; B: `configs/segmentation.yaml` (follows dev05/dev04 pattern with `dev0N_` prefix) | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.8):** `configs/dev06_segmentation.yaml`; schema documented in §14.2.8; file NOT created in planning phase. | Human owner |
| OQ-SEG-DISPLAY-01 | Default top-K cho categorical profile? | A: 3; B: 5; C: 10 | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.9):** K=10 (config-overridable); tie-break `count DESC, category_name ASC`; `other_count` for omitted categories; full distribution reconstructable; see §14.2.9. | Human owner |
| OQ-SEG-DEPENDENCY-01 | Có cần library mới không (vd. `tabulate` cho table display)? | A: chỉ stdlib + pandas/numpy; B: thêm `tabulate` | **`DECIDED — OWNER-AUTHORIZED` (Phase 1.5, brief §3.10):** No new dependencies. Reuse `pandas`, `numpy`, `pyarrow`, `pyyaml` + stdlib (`textwrap`, `csv`, `json`, `pathlib`, `hashlib`); no `tabulate`; see §14.2.10. | Human owner |

**Quyết định KHÔNG mở (đã closed theo existing contracts — unchanged):**

- DEV-06 là prototype layer (per ADR-0005 + AGENTS.md §1).
- DEV-06 không tự đặt tên business-y (per AGENTS.md §3 "Profiling").
- DEV-06 không ranking (per AGENTS.md §2.5, §2.6).
- DEV-06 noise policy default = `"exclude"` (per ADR-0006).
- DEV-06 5 algorithms hỗ trợ: kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans (per ADR-0003).
- DEV-06 KHÔNG thuộc EPIC-09 (per ranh giới CP-01..05 §1.3).
- DEV-06 KHÔNG đọc `final_clustering_dataset.parquet` (per R-DEV-06-09, mirror R-EVAL-09).
- DEV-06 KHÔNG visualization (per AGENTS.md §3; mirror R-EVAL-15).

### 14.2. Owner-authorized decisions — detailed rationale and constraints

> Each OQ below records the decision ratified by the human owner in
> task brief §3 (2026-10-10), with the rationale, behavioral
> requirements, and any new invariants (R-DEV-06-NN) that the decision
> introduces.

#### 14.2.1. OQ-SEG-DENOM-01 — Percentage denominator

**Decision:** Use the full input sample count as the primary percentage
denominator.

**Rationale:** Analyst-friendly answer to "what fraction of all customers
does this segment represent?"; avoids the "doubling" artefact when noise
ratio is high (e.g. 50% noise would double non-noise segment percentages
under a `n_samples_used_for_compute` denominator).

**Behavioral requirements (per brief §3.1):**

- `percentage_input = segment_count / n_samples_input * 100`.
- Also report `percentage_of_non_noise` when that denominator is valid
  and greater than zero (i.e. `n_samples_used_for_compute > 0`).
- Name both percentage fields clearly and document their denominators.
- Report raw counts alongside percentages.
- Avoid division by zero; define the output for empty input explicitly.
- Document rounding (default 2 dp; configurable
  `dev06_segmentation.display.percentage_decimals`) and deterministic
  output.
- Percentages across all input segments, including noise when present,
  reconcile to approximately 100% within rounding tolerance.
- Percentages among non-noise clusters reconcile to approximately 100%
  when non-noise samples exist.
- Do not use the DEV-05 metric noise policy as an implicit substitute
  for DEV-06 percentage semantics (DEV-06 defines its own `noise_policy_used`
  field per §6.4).

**Concrete CSV schema (final):**

```csv
segment_id,count,percentage_input,percentage_of_non_noise,is_noise,percentage_rounding_decimals
0,1180,62.43,64.39,false,2
1,512,27.07,27.93,false,2
2,201,10.62,10.96,false,2
-1,2010,47.91,,true,2
```

**New invariant R-DEV-06-21:** Both percentages MUST use distinct,
explicit denominator names. Test `test_dev06_percentages_distinct_denominators`:
`(percentage_input / 100) * n_samples_input == count` AND
`(percentage_of_non_noise / 100) * n_samples_used_for_compute == count`
within rounding tolerance (≤ 1 ulp of last decimal place).

#### 14.2.2. OQ-SEG-NOISE-01 — Noise display strategy

**Decision:** Preserve and display DBSCAN noise as an explicit special
group.

**Rationale:** Full transparency; never silently reclassify noise as a
"real" segment; allow analyst to reason about DBSCAN behavior.

**Behavioral requirements (per brief §3.2):**

- Preserve `ClusterLabel = -1` verbatim (no relabel).
- Expose `is_noise: bool` in every segment-level output row.
- Include noise row in `percentage_input` denominator; exclude from
  `percentage_of_non_noise` denominator.
- Apply noise-specific fields (`noise_count`, `noise_ratio`,
  `n_clusters_input`) only when the actual algorithm contract supports
  noise. Use the verified `algorithm_family == "density_based"` check
  (DBSCAN only) — do NOT infer noise support from arbitrary label value.
- For algorithms that do not support noise: `noise_count = null`,
  `noise_ratio = null`, `n_clusters_input = n_segments`,
  `noise_policy_used = "n/a"` (closed enum, mirror ADR-0006).
- Do not mutate upstream labels or clustering artifacts.
- Validate `ClusterLabel` and `IsNoise` consistency:
  `IsNoise == (ClusterLabel == -1)`. Inconsistency → Validation FAIL.
- Handle all-noise and empty-input cases deterministically (see §6.5).

**New invariant R-DEV-06-22:** Noise fields are gated by
`algorithm_family == "density_based"`. Non-DBSCAN runs emit
`noise_count = null` (NOT 0). Test
`test_dev06_non_dbscan_noise_fields_null` (mirror test_dev05 pattern).

#### 14.2.3. OQ-SEG-CHAR-01 — Customer-characteristic rules

**Decision:** Use a reduced set of four deterministic descriptive rules.

**Rationale:** Two of the originally proposed six rules
(`category_diversity_low_<feature>`, `missing_share_high_<feature>`) are
profile-quality / statistical indicators, not customer-characteristic
labels. They are already captured in §7.2/§7.3 profile statistics
(`unique_count`, `missing_count`, `missing_ratio`). Retaining them in
the characteristic rule set would conflate two distinct output layers.

**Behavioral requirements (per brief §3.3):**

- The four retained rules (with names and definitions from current
  plan's §7.4 — verified in source):
  1. `mean_high_<feature>` — Segment mean of `<feature>` > dataset mean
     + `N` * dataset std. (Default `N = 1.0`, config
     `dev06_segmentation.characteristic_rules.z_threshold`.)
  2. `mean_low_<feature>` — Segment mean of `<feature>` < dataset mean
     - `N` * dataset std.
  3. `median_above_dataset_median_<feature>` — Segment median > dataset
     median.
  4. `top_category_<feature>_<value>` — Top-1 category of `<feature>` in
     segment is `<value>` (per OQ-SEG-DISPLAY-01 top-K + alphabetical
     tie-break).
- Each generated characteristic MUST have traceable supporting statistics
  (`derived_stats` field in `segment_characteristics.json`).
- Do not generate business labels ("VIP", "loyal", "high-value", "at-risk",
  "champion", "churn", "marketing", "target"). R-DEV-06-19 reinforces.
- Do not make causal claims or imply business value.
- Mentor review (if required by repository governance) is a separate
  gate; does not block DEV-06 Phase 2 per AGENTS.md §2.10
  (`TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED`).

**§7.4 update (final, REVISED):** See §7.4 in this plan for the four-rule
table with definitions; the two removed rules are listed with rationale
for their removal.

#### 14.2.4. OQ-SEG-PROFILE-01 — Feature profile scope

**Decision:** Use `L1.feature_set` as the default profile feature set.

**Rationale:** The clustering was performed on exactly `L1.feature_set`;
profiling the same set preserves alignment with the cluster-label
provenance chain. Profiling arbitrary additional columns would silently
expand the scope beyond the approved clustering contract.

**Behavioral requirements (per brief §3.4):**

- Validate every requested feature exists in `L1.feature_set` (R-DEV-06-20).
- Preserve feature order deterministically (same order as `L1.feature_set`).
- Do not silently profile arbitrary dataset columns.
- Use the approved input path (L4 from `L3.ml_dataset_block.artifact_path`).
- If only scaled/preprocessed features are available (the case in
  DEV-06's default flow), label profiles accordingly and emit explicit
  warning: `"Feature profile uses scaled/transformed values; not directly
  interpretable in original business units (per DEV-03 preprocessing)."`
- Do NOT access `data/processed/final_clustering_dataset.parquet` (R-DEV-06-09).
- Do NOT assume original-scale data exists.
- Per-feature type detection (final, expanded):
  - `int64`, `float64`, `int32`, `float32` → `numerical`
  - `bool` → `boolean` (treat as 0/1 for stats; record `is_boolean = true`)
  - `category`, `object` with `nunique <= 50` → `categorical`
  - `object` with `nunique > 50` → `text_or_id` → **skip** with warning
  - `datetime64`, `timedelta64` → `datetime` → **skip** with warning
- Manifest records `preprocessing_applied: {transformation, scaling}`
  (read from `PreprocessedManifest.preprocessing_block`).
- Do not change preprocessing behavior or upstream contracts.

**New invariant R-DEV-06-23:** Profile disclaimer about post-preprocessing
values is MANDATORY in every output file's first-line comment (CSV header
comment) and in `segmentation_manifest.json` `preprocessing_warning` field.

#### 14.2.5. OQ-SEG-INHERIT-01 — Evaluation ID dependency

**Decision:** Make `evaluation_id` optional.

**Rationale:** DEV-06 is a downstream profile consumer; it should not
require DEV-05 to have run. Per AGENTS.md §2.2 phase isolation, each
phase depends on prior phases but should not block on optional
downstream artifacts.

**Behavioral requirements (per brief §3.5):**

- DEV-06 must be able to consume valid clustering output (L1 + L2 + L3 +
  L4) without requiring L5.
- If a valid evaluation manifest (L5) is provided, validate:
  1. `schema_version == "1.0.0"`.
  2. `clustering_id == L1.clustering_id`.
  3. `ml_dataset_sha256` (L5) == `L1.ml_dataset_sha256`.
  4. Use L5's `noise_policy_used` as DEV-06 default.
  5. Record `input_evaluation_manifest` path + `evaluation_id` in
     `segmentation_manifest.json`.
- If L5 is not provided: `evaluation_id = null`; `noise_policy_used`
  defaults to `"exclude"` (DBSCAN) or `"n/a"` (non-DBSCAN) per ADR-0006.
- Never fabricate an `evaluation_id` or write a reference to a
  non-existent L5 file.
- Preserve the distinction between clustering provenance
  (canonical: `clustering_id`) and evaluation provenance
  (optional: `evaluation_id`).

#### 14.2.6. OQ-SEG-LAYOUT-01 — Output directory

**Decision:** Use the `segmentation/` output subdirectory.

**Rationale:** Matches the Jira task title "Customer Segment Module";
avoids clash with EPIC-09's "profiling" subdir (which would conflate
CP-01..05 research work with DEV-06 prototype output).

**Behavioral requirements (per brief §3.6):**

- Output path:
  `<storage_root>/datasets/<ds_id>/preprocessed/<pp_id>/clustering/<cl_id>/segmentation/<seg_id>/`
- `segmentation_id` regex: `^seg_[0-9a-f]{24}$` (mirror DEV-04/05
  `cl_` / `ev_` pattern).
- Path containment validated via
  `Path.resolve() + relative_to(storage_root)`.
- Atomic publish: `staging_dir → os.rename → final_dir` (mirror DEV-05).
- Idempotency: `find_existing_segmentation(seg_id)` re-uses existing
  manifest on collision.
- `--force-rerun` CLI flag for backup + atomic re-publish.
- Do not modify DEV-04 or DEV-05 storage behavior.

#### 14.2.7. OQ-SEG-COMPARE-01 — Segment comparison (revised per P1-3 resolution, 2026-10-10)

**Decision:** Compare only compatible experiments using explicit
compatibility checks and provenance. Two reason concepts are kept
separate: per-row diffs within a shared group, and exclusion of
manifests whose key has no sharing partner.

**Rationale:** The DEV-05 `CompatibilityKey` includes
`preprocessing_config_sha256`, but `clustering_manifest.json` v1.0.0
does NOT contain this field. Reusing that field mechanically would
inherit the DEV-05 placeholder defect (see §19.6) and force DEV-06 to
use a fabricated hash. Therefore, DEV-06 uses a narrower key (4 fields
that ARE present in `clustering_manifest.json`).

**Behavioral requirements (per brief §3.7, P1-3 resolution):**

- DEV-06 `CompatibilityKey` fields (4):
  1. `dataset_id`
  2. `preprocessed_id`
  3. `ml_dataset_sha256` (from `L1.ml_dataset_sha256` — present in
     `ClusteringManifest` v1.0.0; verified).
  4. `feature_set_sha256` (DEV-06 derives from
     `L1.feature_set sorted → SHA256`).
- `preprocessing_config_sha256` is NOT in the key; it is recorded as
  provenance in `segmentation_manifest.json` (read from
  `PreprocessedManifest.config_hash`). The provenance is metadata, not
  part of the compatibility comparison.
- Per-row provenance fields (recorded but not in key): `algorithm`,
  `algorithm_family`, `noise_policy_used`, `n_segments`, `noise_count`,
  `noise_ratio`.
- **Incompatibility behavior** (revised; deterministic, single
  contract — no optional flag):
  - **Single-manifest call** (1 path) → emit 1 singleton group
    với `note = "singleton — no comparison possible"`. Đây là
    case duy nhất còn emit singleton group.
  - **Multi-manifest call**:
    - Same key, different per-row field → retain multi-member group;
      emit `incompatibility_reason` (vào `incompatibility_reasons`)
      cho mỗi differing per-row field.
    - Different key, key có partner (≥2 manifest share key) → group
      đó được retain; những manifest khác key (không có partner)
      được route sang `exclusion_reasons`.
    - All-incompatible (no shared key) → emit `groups = []`;
      populate `exclusion_reasons` cho MỌI manifest, mỗi entry
      có `no_retained_group = true`.
    - Mixed call → retain multi-member groups + populate
      `exclusion_reasons` cho excluded manifests; **không** chọn
      anchor group tuỳ ý; `differing_key_field_names` list các key
      field unique vs MỌI retained group.
- **Two reason concepts, separated** (R-DEV-06-26):
  - `incompatibility_reasons`: per-row diffs **trong** cùng group
    (R-DEV-06-26 enforced — key-field diffs KHÔNG BAO GIỜ xuất
    hiện ở đây).
  - `exclusion_reasons`: key-field exclusion. Mỗi entry có:
    - `excluded_segmentation_id`
    - `excluded_key` (full 4-field key của excluded manifest)
    - `reason_code` (stable constant `"excluded_no_shared_key"`)
    - `differing_key_field_names` (key fields unique vs retained)
    - `no_retained_group` (True iff all-incompatible)
- **Summary metadata** (R-DEV-06-27): top-level
  `total_input_count`, `total_compared_count`, `total_excluded_count`.
  Invariant: `total_input_count == total_compared_count +
  total_excluded_count`. Duplicate paths (same `segmentation_id`)
  dedupe trước partition; first occurrence wins.
- Do not rank algorithms / segments / declare winners / infer superiority.
- Equal feature names alone do NOT prove experiments are comparable
  (they must share the same `feature_set_sha256`).

**New invariants (added in P1-3 resolution):**

- R-DEV-06-24 (carried): `CompatibilityKey` MUST NOT include
  `preprocessing_config_sha256`. Test
  `test_dev06_compare_key_uses_only_manifest_fields`:
  `set(compatibility_key_fields) ⊆
  {"dataset_id", "preprocessed_id", "ml_dataset_sha256", "feature_set_sha256"}`.
- R-DEV-06-26 (NEW): `incompatibility_reasons` and
  `exclusion_reasons` are separate fields; key-field diffs NEVER
  appear in `incompatibility_reasons`; per-row diffs NEVER appear
  in `exclusion_reasons`. Test:
  `test_compare_reason_concepts_separate` + 5 sub-tests.
- R-DEV-06-27 (NEW): `total_input_count == total_compared_count +
  total_excluded_count` for every call. Test:
  `test_compare_summary_counts_exact` with 4 input shapes
  (single / all-compatible / all-incompatible / mixed).

**Resolution path for the original §8.3 / §14.2.7 conflict (P1-3):**
plan §8.3 originally said "All-incompatible → emit 0 groups +
incompatibility_reasons populated"; implementation at the time
emitted singleton groups per key. The Owner-approved resolution
(2026-10-10) adopts the plan's intent (0 groups + reasons) and
extends it with the new `exclusion_reasons` field to keep the
two reason concepts distinct. Implementation now matches plan;
tests pin the contract. See
`docs/system/DEV-06_remediation_report.md` §3.9 for audit trail.

#### 14.2.8. OQ-SEG-NAMESPACE-01 — Configuration filename

**Decision:** Use `configs/dev06_segmentation.yaml`.

**Rationale:** Consistent with `configs/dev0[2..5]_*.yaml` naming pattern.

**Behavioral requirements (per brief §3.8):**

- File path: `configs/dev06_segmentation.yaml` (DO NOT CREATE in planning
  phase).
- Document the intended schema in the plan only (see below).

**Intended configuration schema (final, planned for Phase 2):**

```yaml
dev06_segmentation:
  noise_policy:
    default: "exclude"      # prototype default per ADR-0006 (DBSCAN only)
  statistics:
    numerical: [mean, median, std, q1, q3, min, max]
    categorical_topk: 10     # per OQ-SEG-DISPLAY-01
    categorical_uniqueness_threshold: 50  # object with >50 unique → text_or_id
  characteristic_rules:
    enabled:
      - "mean_high_<feature>"
      - "mean_low_<feature>"
      - "median_above_dataset_median_<feature>"
      - "top_category_<feature>_<value>"
    z_threshold: 1.0
  display:
    percentage_decimals: 2
    missing_value_placeholder: "--"
    csv_missing_value: ""
    disclaimer_text: "no ranking, recommendation, or winner annotation is emitted; descriptive comparison only; values are post-preprocessing"
  storage:
    output_dir_relative: "segmentation"
    emit_profiles_csv: true
    emit_profiles_json: true
    emit_characteristics_json: true
    emit_sizes_long_csv: true
  logging:
    level: "INFO"
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_dir_relative: "data/prototype/datasets"
    emit_to_console: true
  research_safety:
    readonly_paths:
      - "data/raw/primary"
      - "data/raw/backup"
      - "data/processed"
      - "reports"
    never_promote_to_research: true
    segmentation_scope: "PROFILED_PROTOTYPE"
  validation:
    min_samples: 2
    min_features: 1
    require_no_nan: false
    exclude_customer_id_from_features: true
  compare:
    emit_singleton_group: true
    show_provenance_per_row: true
    disclaimer_text: "no ranking, recommendation, or winner annotation is emitted; descriptive comparison only"
```

#### 14.2.9. OQ-SEG-DISPLAY-01 — Categorical profile top-K

**Decision:** Use a configurable default K = 10.

**Rationale:** K=10 provides more detail than K=3 (which is too coarse
for high-cardinality features like Country with 38 unique values) while
remaining within typical terminal display width. Config-overridable for
specific use cases.

**Behavioral requirements (per brief §3.9):**

- `STATISTICS_TOPK` default = 10 (config-overridable).
- Tie-breaking: `count DESC, category_name ASC` (deterministic;
  alphabetical secondary sort).
- Preserve true category counts and denominator: every category's
  count is accessible via `topk_counts` (for top-K) or implicitly via
  `other_count` (for omitted) + `unique_count` (total).
- Report `other_count`: sum of counts of categories NOT in top-K.
- Top-K is a display representation, NOT a complete distribution.
  `unique_count` + `other_count` enable reconstruction.
- Do not silently discard categories from persisted source data; the
  raw `cluster_labels_<exp_id>.parquet` is unchanged.
- Behavior for fewer than K categories: `topk_categories` contains all
  available categories; `other_count = 0`;
  `topk_categories.length == unique_count`.
- Behavior for zero valid observations: all fields = null per
  R-DEV-06-08 (no-fake-default).
- No new dependencies (R-DEV-06-15 + OQ-SEG-DEPENDENCY-01).

**New invariant R-DEV-06-25 (NEW):** `other_count` MUST be non-negative
integer; `topk_counts.sum() + other_count == total_count - missing_count`
(where `total_count` is segment size). Test
`test_dev06_categorical_topk_other_count_consistent`.

#### 14.2.10. OQ-SEG-DEPENDENCY-01 — New dependencies

**Decision:** Do not add new dependencies for DEV-06 by default.

**Rationale:** Existing dependencies (pandas, numpy, pyarrow, pyyaml,
scikit-learn) are sufficient for descriptive statistics + CSV/JSON I/O.
Stdlib (`textwrap`, `csv`, `json`, `pathlib`, `hashlib`) covers terminal
table formatting and content addressing.

**Behavioral requirements (per brief §3.10):**

- Reuse existing dependencies only.
- If a new dependency appears necessary in the future, record the
  technical limitation and defer the decision for separate human
  approval + ADR.
- Do not modify `pyproject.toml`; do not install packages; do not
  silently widen dependency constraints.

---

## 15. Files dự kiến tạo/sửa (Phase 2 — KHÔNG thực hiện trong Phase 1)

### 15.1. Source code (mới trong prototype layer)

```
src/customer_segmentation/prototype/segmentation/
├── __init__.py                    (public API re-exports)
├── scope.py                       (enums + frozen constants)
├── storage.py                     (content-addressed id + path resolution)
├── config_loader.py               (YAML loader → SegmentationConfig dataclass)
├── manifest.py                    (SegmentationManifest schema + atomic I/O)
├── profile.py                     (segment sizes + percentages + feature profiles)
├── characteristics.py             (rule engine + default rules)
├── compare.py                     (CompatibilityKey + compare_segmentations)
├── display.py                     (format tables + banned-substring check)
├── logging_config.py              (PerStageLogger façade)
├── pipeline.py                    (Stage A→H orchestrator)
└── validation.py                  (Stage B input validation report)
```

### 15.2. CLI script

```
scripts/dev06_run_segmentation.py   (argparse + profile/list/sizes/profiles/characteristics/compare sub-commands)
```

### 15.3. Config

```
configs/dev06_segmentation.yaml   (default config; mirror dev05_evaluation.yaml structure)
```

### 15.4. Test files (13 files, ~268 tests)

```
tests/test_dev06_scope.py
tests/test_dev06_config.py
tests/test_dev06_storage.py
tests/test_dev06_manifest.py
tests/test_dev06_profile.py
tests/test_dev06_characteristics.py
tests/test_dev06_compare.py
tests/test_dev06_display.py
tests/test_dev06_research_safety.py
tests/test_dev06_import_blocklist.py
tests/test_dev06_runtime_dependencies.py
tests/test_dev06_cli.py
tests/test_dev06_pipeline.py
tests/fixtures/dev06/   (synthetic ML dataset + clustering manifest + cluster labels)
```

### 15.5. Files KHÔNG sửa

- `AGENTS.md`
- Bất kỳ file nào trong `docs/decisions/0001..0006/`
- `docs/system/DEV-0[1..5]_*.md`, `docs/system/SYS-0[1..6]_*.md`
- `configs/dev0[2..5]_*.yaml`
- `src/customer_segmentation/{clustering,dataset_management,evaluation,feature_engineering,preprocessing,transformation}/**`
- `src/customer_segmentation/prototype/{clustering,dataset_management,evaluation,feature_generation,preprocessing}/**`
- `scripts/dev0[2..5]_*.py`
- `tests/test_dev0[2..5]_*.py`, `tests/fixtures/dev0[2..5]/`
- `data/**`, `reports/**`, `pyproject.toml`

---

## 16. Verification commands dự kiến (Phase 2)

```bash
# 1. Synthetic data integration test (no real dataset)
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py profile \
    --dataset-id ds_synthetic \
    --preprocessed-id pp_synthetic \
    --clustering-id cl_synthetic \
    --config configs/dev06_segmentation.yaml
# Expected: writes <storage_root>/.../clustering/cl_synthetic/segmentation/seg_<...>/
#           with segmentation_manifest.json + 4 CSVs/JSONs + log

# 2. Display sub-commands
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py list \
    --segmentation-manifest <path-to-segmentation_manifest.json>
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py sizes \
    --segmentation-manifest <path>
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py profiles \
    --segmentation-manifest <path> --segment-id 0
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py characteristics \
    --segmentation-manifest <path>

# 3. Compare sub-command
PYTHONPATH=src python3 scripts/dev06_run_segmentation.py compare \
    --segmentation-manifest <path1> <path2>
# Expected: emit comparison_report.json + print compatibility table

# 4. Lint + format
ruff check src/customer_segmentation/prototype/segmentation/ \
          scripts/dev06_run_segmentation.py \
          tests/test_dev06_*.py
black --check src/customer_segmentation/prototype/segmentation/ \
              scripts/dev06_run_segmentation.py \
              tests/test_dev06_*.py

# 5. DEV-06 tests only
PYTHONPATH=src python3 -m pytest tests/test_dev06_*.py -v
# Expected: ~268 passed, 0 failed, 0 skipped

# 6. Full regression DEV-02..06
PYTHONPATH=src python3 -m pytest tests/test_dev02_*.py tests/test_dev03_*.py \
    tests/test_dev04_*.py tests/test_dev05_*.py tests/test_dev06_*.py
# Expected: ~950 passed (682 cumulative DEV-02..05 per DEV-05 completion summary + 268 DEV-06), 1 pre-existing skipped (DEV-03 C7)
```

**Quan trọng Phase 1:** KHÔNG chạy bất kỳ command nào trong section này.
Phase 1 chỉ inspect file + viết plan này.

---

## 17. Explicit stop gate trước implementation

> AGENTS.md §6, §2.10, §2.11: stop, surface issue clearly, wait for
> human direction.

Sau khi plan này được viết, **DỪNG**.

Không tự ý:

- Bắt đầu implement bất kỳ file nào trong §15.
- Chạy bất kỳ command nào trong §16.
- Tạo directory `src/customer_segmentation/prototype/segmentation/`.
- Tạo file `configs/dev06_segmentation.yaml`.
- Tạo file `scripts/dev06_run_segmentation.py`.
- Tạo bất kỳ file test nào dưới `tests/test_dev06_*.py` hoặc
  `tests/fixtures/dev06/`.
- Modify bất kỳ file tracked nào.
- Git operations: add, commit, push, branch, PR, merge.

**Chờ human owner review plan này và gửi explicit approval token.**

Approval token theo convention của project:

- `APPROVE PHASE 2` → cho phép implement tất cả file trong §15.1–§15.3
  + chạy tests với synthetic data.
- `APPROVE WITH NOTES — <note>` → cho phép implement với specific
  overrides.
- `REVISE PLAN — <feedback>` → cần update plan trước khi implement.
- `HOLD` → dừng; chờ thêm direction.

Sau approval, Phase 2 mới bắt đầu.

---

## 18. Plan status & self-check

### 18.1. Plan self-check

- [x] Task scope defined (Jira 6 trục + 5 AC).
- [x] Non-goals explicit (15 mục theo AGENTS.md).
- [x] Source documents referenced với section (AGENTS.md, ADR-0003/4/5/6,
      DEV-04/05 plans + completion summaries + final review, EPIC-09 plan).
- [x] Existing contracts verified qua source inspection (`clustering_manifest.py`,
      `artifacts.py`, `preprocessing/manifest.py`, `evaluation/manifest.py`).
- [x] Input/output contracts concrete (L1..L5 + manifest schema v1.0.0).
- [x] Storage layout dựa trên DEV-04/05 pattern.
- [x] Functional requirements cho 6 trục Jira (§5, §7).
- [x] Segment / noise / percentage semantics (§6) — open questions recorded
      trong §14.
- [x] Feature profile + characteristic rules (§7) — open question on
      default rules recorded.
- [x] Comparison semantics (§8) — compatibility + no-ranking.
- [x] Provenance + determinism + safety (§9) — R-DEV-06-01..20.
- [x] Implementation phases (§10).
- [x] Acceptance criteria mapping (§11).
- [x] Test matrix (§12).
- [x] Risks + mitigations (§13).
- [x] Open questions cần human approval (§14) — 10 OQs, owners assigned.
- [x] Files expected (§15) — explicit list.
- [x] Verification commands (§16) — synthetic data only.
- [x] Explicit stop gate (§17) — approval token required.

### 18.2. Plan status

`PLAN READY FOR PHASE 2 APPROVAL` (per Phase 1.5 update 2026-10-10).
All 10 OQs `DECIDED — OWNER-AUTHORIZED` (§14). Cross-decision
consistency verified (§20). Phase 2 implementation may begin only
after human owner sends explicit `APPROVE PHASE 2` token (per §17,
§19.7).

### 18.3. Required contracts (verified by source inspection)

- DEV-02 storage contract: VERIFIED (`configs/dev02_dataset_management.yaml`,
  `prototype.dataset_management.*`).
- DEV-03 ML Dataset + PreprocessedManifest v1.0.0: VERIFIED
  (`prototype.preprocessing.manifest.py: PREPROCESSED_MANIFEST_SCHEMA_VERSION = "1.0.0"`).
- DEV-04 ClusteringManifest v1.0.0 + cluster_labels_*.parquet schema:
  VERIFIED (`prototype.clustering.manifest.py: CLUSTERING_MANIFEST_SCHEMA_VERSION = "1.0.0"`,
  `clustering.artifacts.py:42..95`).
- DEV-05 EvaluationManifest v1.0.0 (optional input): VERIFIED
  (`prototype.evaluation.manifest.py: EVALUATION_MANIFEST_SCHEMA_VERSION = "1.0.0"`).
- ADR-0005 architecture: VERIFIED (Option A file-based; no backend).
- ADR-0006 noise policy: VERIFIED (default = "exclude" for prototype layer).
- ADR-0003 algorithm scope: VERIFIED (5 algorithms; K-Medoids OUT).

### 18.4. Hard stop

Per AGENTS.md §2.11: no Git operations.
Per AGENTS.md §2.1, §2.7: no invented data, results, references.
Per AGENTS.md §2.10: no `RESEARCH_APPROVED` claim.
Per AGENTS.md §6: no implementation until human approval.

**END OF PLAN.**

---

## 20. Cross-Decision Consistency Review (Phase 1.5)

> Section này verify 12 cross-decision consistency checks per task brief
> §4. Sau khi tất cả 10 OQs được ghi nhận là `DECIDED — OWNER-AUTHORIZED`,
> cần đảm bảo các quyết định không mâu thuẫn với verified contracts hoặc
> với nhau.

### 20.1. Consistency checks (per task brief §4)

| # | Check | Result | Reference |
|---|---|---|---|
| 1 | Full-input percentages và non-noise percentages dùng denominators riêng biệt, rõ ràng | ✅ PASS — `percentage_input` (denominator `n_samples_input`) + `percentage_of_non_noise` (denominator `n_samples_used_for_compute`); R-DEV-06-21 enforces | §14.2.1 |
| 2 | DBSCAN noise identifiable, không confused với normal segment | ✅ PASS — `is_noise` flag; `ClusterLabel = -1` preserved; noise vẫn trong `segment_sizes_long.csv` nhưng loại khỏi `segment_sizes.csv`; R-DEV-06-22 enforces | §14.2.2 |
| 3 | Non-noise percentages có defined behavior cho all-noise input | ✅ PASS — All-noise case: `n_segments = 0`, `segment_sizes.csv` empty, `segment_sizes_long.csv` có 1 row noise-only; `percentage_of_non_noise = null` (denominator = 0); manifest records `noise_count = n_samples_input`, `noise_ratio = 1.0` | §6.5 + §14.2.2 |
| 4 | Noise-specific fields KHÔNG fabricated cho algorithms không support noise | ✅ PASS — `algorithm_family == "density_based"` gate; non-DBSCAN → `noise_count = null`, `noise_ratio = null`, `n_clusters_input = n_segments`, `noise_policy_used = "n/a"`; R-DEV-06-22 enforces | §14.2.2 |
| 5 | Characteristic rules consume statistics defined by feature-profile contract | ✅ PASS — 4 rules (`mean_high_<feature>`, `mean_low_<feature>`, `median_above_dataset_median_<feature>`, `top_category_<feature>_<value>`) chỉ dùng `mean`, `median`, top-1 category — tất cả đều có trong §7.2/§7.3 feature-profile statistics | §7.4 + §14.2.3 |
| 6 | `L1.feature_set` traceable to approved data source + aligned với customer labels | ✅ PASS — L1 = `clustering_manifest.feature_set` (verified field in v1.0.0); L4 = ML Dataset from `L3.ml_dataset_block.artifact_path`; CustomerID alignment qua §4.1 validation rule 8 | §4.1 + §14.2.4 |
| 7 | Optional evaluation provenance KHÔNG trở thành hidden prerequisite | ✅ PASS — L5 (DEV-05 manifest) explicitly optional; DEV-06 hoạt động độc lập với DEV-04 outputs; `evaluation_id = null` khi L5 không có | §14.2.5 |
| 8 | Comparison compatibility KHÔNG rely on missing manifest fields hoặc placeholder hashes | ✅ PASS — DEV-06 `CompatibilityKey` (4 fields) deliberately narrower than DEV-05's (5+1 fields); `preprocessing_config_sha256` (DEV-05 placeholder) NOT included; `ml_dataset_sha256` đọc từ `clustering_manifest` (verified field); R-DEV-06-24 enforces | §14.2.7 + §19.6 |
| 9 | Output paths nằm trong prototype hierarchy | ✅ PASS — `<storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/<cl>/segmentation/<seg>/`; path containment enforced; R-DEV-06-04..07 mirror DEV-05 R-EVAL-04..07 | §14.2.6 |
| 10 | Plan KHÔNG claim DEV-06 outputs là research evidence | ✅ PASS — `research_safety.automatically_promoted_to_research = false` always; `appeared_in_research_evidence = false` always; `scope = "PROFILED_PROTOTYPE"`; R-DEV-06-01..03; `TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED` per AGENTS.md §2.10 | §9.4 + §1.2 |
| 11 | No scope leaked into EPIC-09 | ✅ PASS — Distinctiveness, Interpretability, Behavioral consistency, Business relevance explicitly listed as non-goals (§1.2); import blocklist forbids `customer_segmentation.profiling.*` (research core, EPIC-09 nếu có); R-DEV-06-15 | §1.2 + §9.4 |
| 12 | Every Jira AC maps to concrete planned behavior + synthetic-fixture test | ✅ PASS — AC-1..5 mapped to specific test files in §11; synthetic fixtures plan ở §12.3; all 12 edge-case tests in §12.2 | §11 + §12 |

### 20.2. New invariants introduced by Phase 1.5 decisions (R-DEV-06-21..25)

| # | Invariant | Decision source | Test |
|---|---|---|---|
| R-DEV-06-21 | Both percentages MUST use distinct, explicit denominator names; reconciliation test | OQ-SEG-DENOM-01 | `test_dev06_percentages_distinct_denominators` |
| R-DEV-06-22 | Noise fields gated by `algorithm_family == "density_based"`; non-DBSCAN → `noise_count = null` | OQ-SEG-NOISE-01 | `test_dev06_non_dbscan_noise_fields_null` |
| R-DEV-06-23 | Post-preprocessing warning MANDATORY in every output file + manifest | OQ-SEG-PROFILE-01 | `test_dev06_preprocessing_warning_present` |
| R-DEV-06-24 | `CompatibilityKey` MUST NOT include `preprocessing_config_sha256` (avoid DEV-05 placeholder) | OQ-SEG-COMPARE-01 | `test_dev06_compare_key_uses_only_manifest_fields` |
| R-DEV-06-25 | `other_count >= 0`; `topk_counts.sum() + other_count == total_count - missing_count` | OQ-SEG-DISPLAY-01 | `test_dev06_categorical_topk_other_count_consistent` |

These invariants are added to §9.4 (R-DEV-06-01..25) — see
§20.3 for the integrated table reference.

### 20.2a. New invariants introduced by P1-3 resolution (R-DEV-06-26..27)

| # | Invariant | Decision source | Test |
|---|---|---|---|
| R-DEV-06-26 | `incompatibility_reasons` and `exclusion_reasons` are separate fields; key-field diffs NEVER appear in `incompatibility_reasons`; per-row diffs NEVER appear in `exclusion_reasons` | P1-3 resolution (2026-10-10) | `TestCompareReasonConceptsSeparate` (4 tests) |
| R-DEV-06-27 | `total_input_count == total_compared_count + total_excluded_count` for every compare call; duplicate paths (same `segmentation_id`) dedupe before partition; first occurrence wins | P1-3 resolution (2026-10-10) | `TestCompareSummaryCountsExact` (4 tests) + `TestSummaryCounts.test_invariant_total_input_equals_compared_plus_excluded` |

These invariants are added to §9.4 (R-DEV-06-01..27) — see §20.3
for the integrated table reference.

### 20.3. Integration into R-DEV-06 invariant table (§9.4)

The full invariant list is now R-DEV-06-01..27 (20 original + 5 from
Phase 1.5 + 2 from P1-3 resolution). Implementation note: when Phase 2
begins, the `test_dev06_research_safety.py` file should include test
methods for R-DEV-06-21..27 in addition to the original 20 invariants.

### 20.4. Consistency verdict

**All 12 cross-decision consistency checks PASS.** No contradictions
detected between owner-authorized decisions and verified contracts.
The plan is internally consistent and contract-compliant.

### 20.5. Pre-existing DEV-05 issue (per task brief §5)

**Confirmed via direct source inspection** during Phase 1.5:

- `src/customer_segmentation/prototype/evaluation/pipeline.py:363`:
  ```python
  preprocessing_config_sha = str(
      clustering_manifest_data.get("preprocessing_config_sha256", "f" * 64)
  )
  ```
  This is a fallback to placeholder `"f" * 64` when the field is absent
  from `clustering_manifest.json` (which is always — `ClusteringManifest`
  v1.0.0 does not have this field).

**Impact on DEV-06:** DEV-06's `CompatibilityKey` (4 fields) deliberately
excludes `preprocessing_config_sha256` to avoid inheriting this defect.
The `preprocessing_config_sha256` is recorded in `segmentation_manifest.json`
as provenance (read from `PreprocessedManifest.config_hash`), but NOT
used in compatibility comparison.

**Documented as separate pre-existing issue** in §19.6 (not a DEV-06
implementation requirement). Recommend ADR for DEV-05 remediation in
future phase.

### 20.6. Phase 1.5 final status

`PLAN READY FOR PHASE 2 APPROVAL`

- All 10 OQs DECIDED.
- All 12 cross-decision consistency checks PASS.
- Pre-existing DEV-05 issue confirmed + documented; not blocking DEV-06.
- New invariants R-DEV-06-21..25 introduced; integrated into R-DEV-06
  list.
- §18.2 plan status updated to `PLAN READY FOR PHASE 2 APPROVAL`.
- §19.7 Phase 2 gates updated (OQ condition satisfied).

**Implementation may begin ONLY after human owner sends explicit
`APPROVE PHASE 2` token.**

---

## 19. Plan Review Notes (Phase 1.5 / OQ Resolution Review)

> Phần này được thêm sau Phase 1 plan review. **KHÔNG thay đổi Phase 2
> implementation; chỉ clarify / correct Phase 1 contract assertions.**

### 19.1. Review scope

Phase 1 plan đã được review lại với focus:
- 10 OQs trong §14 (proposed defaults, owner, impact).
- 4 high-risk areas (R-1, R-3, R-7, R-9).
- CustomerID / RowIndex alignment.
- ClusterLabel và IsNoise consistency.
- Empty clusters và all-noise data.
- Missing values và feature type detection.
- Input schema / version validation.
- Deterministic output và provenance.
- Safe output paths và upstream immutability.
- Ranh giới technical implementation vs research approval.

### 19.2. Contract verifications (additional spot-checks beyond §3.1)

| Contract | Verified by | Status |
|---|---|---|
| `AlgorithmFamily` enum values | `src/customer_segmentation/clustering/result.py:70..81` — `HARD="hard"`, `DENSITY_BASED="density_based"`, `MODEL_BASED="model_based"`, `FUZZY="fuzzy"`, `OTHER="other"` | ✅ Verified |
| `cluster_labels_*.parquet` CustomerID default vs RowIndex fallback | `src/customer_segmentation/clustering/artifacts.py:42..95` — default có CustomerID; RowIndex chỉ khi `customer_metadata_df is None` | ✅ Verified |
| `ml_dataset_*.parquet` CustomerID presence | `src/customer_segmentation/prototype/clustering/pipeline.py:296..317` — detect `"CustomerID"/"customer_id"/"Customer ID"`; file vẫn giữ CustomerID (split chỉ trong pipeline) | ✅ Verified |
| `ClusteringManifest` không có `preprocessing_config_sha256` | grep `prototype/clustering/manifest.py` — không tìm thấy field | ✅ Verified |
| DEV-05 pipeline dùng fallback placeholder cho preprocessing_config_sha256 | `src/customer_segmentation/prototype/evaluation/pipeline.py:363` — `clustering_manifest_data.get("preprocessing_config_sha256", "f" * 64)` | ✅ Verified (DEV-05 có defect, DEV-06 tránh bằng cách đọc trực tiếp từ `PreprocessedManifest.config_hash`) |
| `EvaluationManifest` có `ml_dataset_path` field | `src/customer_segmentation/prototype/evaluation/manifest.py:233` — `ml_dataset_path: str` | ✅ Verified (L5 có thể cross-check L4 path) |
| DEV-05 `CompatibilityKey` 5 fields + metric_set | `src/customer_segmentation/prototype/evaluation/compare.py:45..62` | ✅ Verified (DEV-06 tương tự nhưng drop `metric_set` vì DEV-06 không có metrics) |
| `segment_sizes_long.csv` rounding convention | DEV-05 metrics_long.csv dùng 4 decimal (per plan §5.5); DEV-06 inherit | ✅ Consistent |
| `noise_policy` config format (default `"exclude"`) | `configs/dev05_evaluation.yaml:noise_policy.default: "exclude"` | ✅ Verified (DEV-06 config mirror) |

### 19.3. Plan refinements made (Phase 1.5 review)

| Section | Change | Rationale |
|---|---|---|
| §3.1 | Thêm note: ml_dataset có thể có CustomerID; non-DBSCAN algorithms không có noise | Clarify ambiguity discovered qua source inspection |
| §3.1 | Thêm note: `ClusteringManifest` KHÔNG có `preprocessing_config_sha256`; L3 (PreprocessedManifest) bắt buộc để lấy canonical value | Avoid DEV-05's fallback placeholder defect |
| §4.1 | Update L4 description: "Columns: CustomerID (optional) + feature_set columns" | Clarify CustomerID presence |
| §4.1 | Update validation rule 8: handle CustomerID (preferred) vs RowIndex (fallback) | Cover both alignment modes |
| §4.1 | Add validation rule 9: non-DBSCAN ClusterLabel.min() >= 0 | Non-DBSCAN semantics |
| §4.1 | Add validation rule 10: L5 cross-check clustering_id + ml_dataset_sha256 | Optional L5 validation |
| §6.3 | OQ-SEG-DENOM-01 default proposal: A (`n_samples_input`) thay vì B | Recommend analyst-friendly; record cả 2 percentages |
| §6.4 | OQ-SEG-NOISE-01: add algorithm-family gating (DBSCAN only); `noise_policy_used="n/a"` cho non-DBSCAN | Discover: chỉ DBSCAN mới có noise |
| §7.3 | OQ-SEG-DISPLAY-01: top-K default 10 (thay vì 3); add tie-breaking rule + `other_count` field | Per brief recommendation; deterministic |
| §9.4 R-DEV-06-15 | Clarify import blocklist targets research-core only; regex với negative lookbehind cho `.prototype.` | Tránh false-positive; allow prototype.evaluation read-only |
| §9.5 | Update import blocklist patterns tương ứng | Same as above |
| §14 | Mark 10 OQs as `PROPOSED — AWAITING HUMAN APPROVAL` với recommendation; add status semantics block | Per brief instruction: không tự settle |
| §16 | Fix test count math: 682 (DEV-02..05) + 268 (DEV-06) = 950 (was incorrectly 965) | Math correction |

### 19.4. Recommendations summary (per OQ)

| OQ | Recommendation | Strength |
|---|---|---|
| OQ-SEG-DENOM-01 | **A** (n_samples_input as primary; both percentages recorded) | Strong — analyst-friendly, no silent doubling |
| OQ-SEG-NOISE-01 | **B** (full transparency, is_noise flag; non-DBSCAN = null) | Strong — safest, no silent reclassification |
| OQ-SEG-CHAR-01 | **Reduced set (4 rules)** — drop `category_diversity_low` + `missing_share_high` (they're profile stats, not characteristics) | Medium — semantic clarification needed |
| OQ-SEG-PROFILE-01 | **A** (L1.feature_set only); add explicit warning that values are post-preprocessing (scaled/transformed), NOT original | Strong — R-DEV-06-20 enforces; original values need new ADR |
| OQ-SEG-INHERIT-01 | **B** (optional); L5 cross-check via `read_evaluation_manifest` từ `prototype.evaluation` (research-core forbidden) | Strong — no circular dependency |
| OQ-SEG-LAYOUT-01 | **A** (`segmentation/`) | Strong — matches Jira title; `profiling/` reserved for EPIC-09 |
| OQ-SEG-COMPARE-01 | **A reduced to 4-field key** — narrow DEV-05's 5-field key by dropping `preprocessing_config_sha256` (avoid placeholder defect); `algorithm_family` as per-row provenance (not in key) | Strong — descriptive comparison still useful, no fabricated hash |
| OQ-SEG-NAMESPACE-01 | **A** (`dev06_segmentation.yaml`) | Strong — consistent with dev02..05 pattern |
| OQ-SEG-DISPLAY-01 | **K=10** (config-overridable; tie-break alphabetical; `other_count` for omitted) | Medium — depends on human preference |
| OQ-SEG-DEPENDENCY-01 | **A** (no new deps) | Strong — stdlib + pandas/numpy sufficient |

### 19.5. High-risk area verification

| Risk | Mitigation enforceability | Verified? |
|---|---|---|
| R-1 (segment naming / business claim) | R-DEV-06-08 + 18 + 19: banned-substring scan + characteristic_id format check + static grep for "Champion/Loyal/high-value/at-risk/churn" | ✅ Enforceable via import blocklist (R-DEV-06-15), static AST scan (R-DEV-06-15), output metadata |
| R-3 (EPIC-09 scope expansion) | R-DEV-06-15: forbidden method names (`compute_distinctiveness`, `score_interpretability`, `behavioral_consistency`); import blocklist; explicit non-goal §1.2 | ✅ Enforceable via AST scan + import blocklist |
| R-7 (silent promotion) | R-DEV-06-01..03: research_safety block always false; + R-DEV-06-15 + 18 | ✅ Enforceable via dataclass invariant test |
| R-9 (FE-06 read) | R-DEV-06-09: forbidden file path regex; + R-DEV-06-14: no real-data test; + R-DEV-06-15: forbidden import | ✅ Enforceable via static AST + path regex |

### 19.6. Pre-existing defects discovered (NOT DEV-06 scope, but worth noting)

| Defect | Location | Impact | Recommendation |
|---|---|---|---|
| `ClusteringManifest` missing `preprocessing_config_sha256` | `prototype/clustering/manifest.py` (v1.0.0) | DEV-05 pipeline (evaluation/pipeline.py:363) uses placeholder `"f" * 64` as fallback | Log as separate finding; do NOT fix in DEV-06 scope (would violate AGENTS.md §2.2 phase isolation). DEV-06 reads from PreprocessedManifest instead. |
| DEV-05 fallback for missing `preprocessing_config_sha256` | `prototype/evaluation/pipeline.py:363` — `clustering_manifest_data.get("preprocessing_config_sha256", "f" * 64)` (CONFIRMED via direct source inspection during Phase 1.5) | Comparison key may be incorrect for some DEV-04 runs. DEV-06's `CompatibilityKey` is INTENTIONALLY narrower (4 fields) to avoid inheriting this defect. | DEV-06 AVOIDS the placeholder behavior (drops the field from the compatibility key); recommend ADR for DEV-05 remediation in a future phase. Documented as separate pre-existing issue, not a DEV-06 implementation requirement. |

### 19.7. Phase 2 implementation gates (per Phase 1.5 finalization)

Phase 2 KHÔNG được bắt đầu cho đến khi:

1. Human owner gửi explicit approval token `APPROVE PHASE 2` (per §17).
2. Tất cả 10 OQs trong §14 đã `DECIDED — OWNER-AUTHORIZED` (✅ done
   in Phase 1.5 per task brief §3).
3. (Nếu characteristic rules approved) Mentor review theo
   `docs/research/review/MENTOR_REVIEW_FORM_EXP01_EXP05.md` (mentor-owned
   process, không thuộc DEV-06 scope; vẫn là separate gate sau khi
   Phase 2 implementation xong, không block Phase 2 start).

### 19.8. Review status (Phase 1.5)

`PLAN DECIDED — READY FOR PHASE 2 APPROVAL`

Tất cả 10 OQs `DECIDED — OWNER-AUTHORIZED` (per task brief §3, 2026-10-10).
13 clarifications trong §19.3. Recommendations §19.4 cross-referenced với
§14.2 detailed decisions. Pre-existing defect §19.6 confirmed. Phase 2 gate
ở §17 / §19.7. Cross-decision consistency review ở §20.

---
