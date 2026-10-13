# DEV-04 — Prototype Clustering Execution

> **Mã task:** DEV-04
> **Tên:** Prototype Clustering Execution (Jira scope: chọn Algorithm / cấu hình Parameters / run Experiment / sinh Cluster Labels / lưu Experiment / lưu Result)
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config, no ADR, no SYS edit, no Git op). Phase 2 (implementation) yêu cầu human approval gate.
> **Ngày:** 2026-10-09
> **Phạm vi:** Cung cấp **prototype-layer** capability để chạy clustering
> experiments trên ML Dataset do DEV-03 sinh ra (per-user, per-dataset), dùng
> ML-01 framework + 5 algorithm adapters đã có (K-Means, Agglomerative,
> DBSCAN, GMM, Fuzzy C-Means). Output = cluster labels parquet + experiment
> log JSON + algorithm-specific output (soft probabilities / membership) +
> prototype manifest, ghi vào
> `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/`
> (per-clustering_id subdirectory; xem §6.3 để biết lý do).
> **Does NOT** sửa ML-01 framework, không implement algorithm mới, không
> tự evaluate / rank / chọn "best", không promote prototype output thành
> research evidence, không mở rộng scope sang EPIC-07/08/09.
> **Architecture:** Option A (ADR-0005) — offline, single-machine, file-based.
> No backend, no API, no database, no worker, no queue.
> **Kế thừa:** DEV-02 contract (`docs/system/DEV-02_dataset_management.md`)
> cho input, DEV-03 manifest schema (`docs/system/DEV-03_preprocessing.md`
> §10.4 + `prototype.preprocessing.manifest.PreprocessedManifest`) cho
> content addressing. DEV-04 consume các public APIs của research core
> (`customer_segmentation.clustering.*`).

---

## 1. Mục tiêu và Jira traceability

### 1.1. Mục tiêu

DEV-04 cung cấp prototype-layer clustering execution cho downstream
prototype DEVs (DEV-05 → DEV-09) cần operate trên user-supplied dataset
đã qua DEV-02 import + DEV-03 preprocessing. Cụ thể:

| # | Jira scope item | DEV-04 deliverable |
|---|---|---|
| 1 | Chọn Algorithm | `algorithm` field trong config + CLI flag; dispatch qua `AlgorithmRegistry` (ML-01) |
| 2 | Cấu hình Parameters | Per-algorithm hyperparameters trong `configs/dev04_clustering.yaml`; CLI override |
| 3 | Run Experiment | `ExperimentRunner.run()` (ML-01) được wrap + dispatch từ prototype CLI |
| 4 | Sinh Cluster Labels | `cluster_labels_{experiment_id}.parquet` (CustomerID + ClusterLabel + IsNoise + Probability_k / Membership_k nếu có) |
| 5 | Lưu Experiment | `experiment_log_{experiment_id}.json` (full `ExperimentResult` payload) |
| 6 | Lưu Result | `clustering_manifest.json` (DEV-04-level manifest) + algorithm_output parquet (nếu applicable) |

Jira scope: `Choose Algorithm / Configure Parameters / Run Experiment /
Produce Cluster Labels / Save Experiment / Save Result`. Acceptance Criteria:
algorithm chọn được, configure được, chạy được, có Cluster Labels, lưu
Experiment được, lưu Result được. DEV-04 chỉ cover 6 AC này; **không**
tính metrics, không ranking, không "best/optimal/recommended".

### 1.2. Phân biệt với EPIC-06 / ML-02 → ML-06

| Concern | EPIC-06 (ML-01 → ML-06) | DEV-04 (prototype) |
|---|---|---|
| Owner | Research core (`customer_segmentation.clustering.*`) | Prototype layer (`customer_segmentation.prototype.clustering.*`) |
| Input | `data/processed/final_clustering_dataset.parquet` (FE-06) | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_*.parquet` (DEV-03) |
| CustomerID | `data/processed/customer_metadata.parquet` (FE-06) | Same DEV-03 ML Dataset's CustomerID column (nếu DEV-03 default — drop trước khi vào matrix; CustomerID ở lại trong metadata write back) |
| Output | `data/processed/clustering_experiments/` + `reports/ml0X/` (RESEARCH) | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/` (PROTOTYPE) |
| Evidence | Research evidence (185 runs, EXP-01..05) | Prototype evidence (per-user, per-dataset; NOT research) |
| Metrics | Computed (silhouette, DBI, CH, WCSS) per EXP-01..05 | **NOT** computed in DEV-04 scope (out of scope; AGENTS.md §3) |
| "Best" claim | Forbidden (AGENTS.md §2.5) | Forbidden (AGENTS.md §2.5) |
| Promotion gate | Mentor + ADR (research methodology change) | **NOT** promoted; `research_safety.automatically_promoted_to_research = false` always |

### 1.3. Phân biệt với EPIC-07 / EPIC-08 / EPIC-09

| Task | Scope | DEV-04 overlap |
|---|---|---|
| EPIC-07 (controlled sweep: k_range, eps_range, ...) | Sweep hyperparameters across many runs | **Out of scope**. DEV-04 runs ONE experiment at a time per CLI invocation. Sweeping is the caller's responsibility (e.g. shell loop or future prototype layer). |
| EPIC-08 (evaluation: silhouette, DBI, CH, stability) | Compute evaluation metrics on cluster outputs | **Out of scope**. DEV-04 does NOT call `metrics.py` (per AGENTS.md §3 "Clustering" row: "Reporting internal metrics without stability and runtime; ignoring silhouette for density-based clusters" → in research core EPIC-08. Prototype DEVs may later add metric computation, but not in DEV-04). |
| EPIC-09 (segment profiling: naming, characterization) | Profile clusters, name segments | **Out of scope**. DEV-04 does NOT name segments ("Champions", "Loyal", ...). |
| CP-01..05 (cluster profiling stages) | Same EPIC-09; out of scope here | Out of scope. |

---

## 2. Nguồn tài liệu đã đọc

> Tất cả paths dưới đây là relative-to-repo-root. Mỗi phát biểu trong plan
> trích từ doc X phải đính kèm section reference. Plan **không** dùng
> statement nào không có nguồn (AGENTS.md §2.1, §2.7).

| Tài liệu | Vai trò cho DEV-04 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules (binding) | Toàn bộ |
| `docs/decisions/0003-algorithm-scope.md` (ADR-0003) | 5 algorithms only; K-Medoids OUT OF SCOPE | Toàn bộ |
| `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) | Architecture contract (Option A) | Toàn bộ |
| `docs/system/DEV-01_project_setup.md` | Verification + architecture boundary pattern | Toàn bộ |
| `docs/system/DEV-02_dataset_management.md` | Downstream contract, manifest schema, coupling rules | Toàn bộ (skim) |
| `docs/system/DEV-03_preprocessing.md` | Plan của DEV-03 (output contract cho DEV-04) | Toàn bộ (skim) |
| `docs/system/DEV-03_completion_summary.md` | DEV-03 implementation status (TECHNICALLY_IMPLEMENTED) | Toàn bộ |
| `docs/research/ML01_Clustering_Experiment_Framework.md` | ML-01 framework contract (research) | Toàn bộ |
| `docs/research/ML02_KMeans.md` .. `ML06_Fuzzy_CMeans.md` | Per-algorithm adapter scope | Skim (header + Scope sections) |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | Algorithm / registry contract | Skim (header) |
| `configs/clustering.yaml` | ML-01 framework config (single source of truth) | Toàn bộ |
| `src/customer_segmentation/clustering/__init__.py` | ML-01 public API | Toàn bộ |
| `src/customer_segmentation/clustering/base.py` | `BaseClusterAlgorithm` abstract base | Toàn bộ |
| `src/customer_segmentation/clustering/registry.py` | `AlgorithmRegistry` | Toàn bộ |
| `src/customer_segmentation/clustering/result.py` | `ClusterResult`, `ExperimentResult`, `MetricsResult`, `AlgorithmFamily`, `ExperimentStatus` | Toàn bộ |
| `src/customer_segmentation/clustering/runner.py` | `ExperimentRunner`, `ExperimentSpec`, `resolve_random_seed`, `capture_library_versions`, `capture_platform_info` | Toàn bộ |
| `src/customer_segmentation/clustering/artifacts.py` | `write_cluster_labels`, `write_algorithm_output`, `write_experiment_artifacts` | Toàn bộ |
| `src/customer_segmentation/clustering/validation.py` | `validate_clustering_matrix`, `validate_customer_alignment`, `ValidationCheck`, `ValidationReport`, `IdentifierLeakageError`, `ClusteringInputError` | Toàn bộ |
| `src/customer_segmentation/clustering/config.py` | `FrameworkConfig` (typed dataclass), `load_framework_config`, `compute_text_sha256` | Toàn bộ |
| `src/customer_segmentation/clustering/logging_utils.py` | `get_logger`, `setup_file_logging`, `write_experiment_log`, `now_utc_iso` | Toàn bộ |
| `src/customer_segmentation/clustering/kmeans.py` | `KMeansAdapter` (ML-02) | Toàn bộ |
| `src/customer_segmentation/clustering/agglomerative.py` | `AgglomerativeAdapter` (ML-03) | Toàn bộ (skim signature + scope) |
| `src/customer_segmentation/clustering/dbscan.py` | `DBSCANAdapter` (ML-04) | Toàn bộ |
| `src/customer_segmentation/clustering/gmm.py` | `GMMAdapter` (ML-05) | Toàn bộ |
| `src/customer_segmentation/clustering/fuzzy_cmeans.py` | `FuzzyCMeansAdapter` (ML-06) | Toàn bộ (skim signature + scope) |
| `src/customer_segmentation/clustering/kmedoids.py` | `fit_kmedoids` (OUT OF SCOPE per ADR-0003, `NotImplementedError`) | Toàn bộ |
| `scripts/run_ml02_kmeans.py` .. `run_ml06_fuzzy_cmeans.py` | Existing orchestrators (pattern to mirror) | Toàn bộ (skim) |
| `tests/test_ml01_framework.py` | ML-01 framework test surface | Header + class list (skim) |
| `tests/test_ml02_kmeans.py` .. `test_ml06_fuzzy.py` | Per-adapter test surface | Header + class list (skim) |
| `src/customer_segmentation/prototype/preprocessing/__init__.py` | DEV-03 public API | Toàn bộ |
| `src/customer_segmentation/prototype/preprocessing/manifest.py` | `PreprocessedManifest` schema (DEV-04 reference) | Skim (skeleton) |
| `src/customer_segmentation/prototype/preprocessing/pipeline.py` | DEV-03 pipeline driver (pattern) | Toàn bộ (skim) |
| `src/customer_segmentation/dataset_management/__init__.py` | DEV-02 public API | Toàn bộ |
| `data/prototype/datasets/ds_*/manifest.json` | Sample DEV-02 manifests (2 files exist) | Toàn bộ |
| `data/processed/final_clustering_dataset.parquet` | FE-06 final matrix (14 features × 4371 customers) | Schema verified (read-only) |
| `data/processed/customer_metadata.parquet` | FE-06 customer metadata (CustomerID × 4371 unique) | Schema verified (read-only) |
| `data/processed/clustering_experiments/experiment_log_*.json` | Sample ML-04 experiment log (real format) | Toàn bộ (1 sample) |

> **NOT read in depth** (out of plan scope): `notebooks/**`,
> `reports/fe0*/**`, `reports/exp0*/**`, `reports/evaluation/**`,
> `docs/research/review/**`, `docs/research/algorithm_theory_v3_exports/**`,
> `src/customer_segmentation/clustering/{baseline,cluster_number,
> hyperparameter_search,metrics,preprocessing_feature_sensitivity,stability}.py`
> (research evaluation layers — out of DEV-04 scope), `docs/data_dictionary/**`,
> `docs/methodology/**`, `docs/system/SYS-01..06` (skim header only; full read
> unnecessary for clustering execution).

---

## 3. Hiện trạng source code / module / config / test

### 3.1. Source code đã tồn tại (research core, READ-ONLY đối với DEV-04)

```
src/customer_segmentation/clustering/             (RESEARCH CORE — toàn bộ READ-ONLY; reused by DEV-04)
├── __init__.py                                   (public API: registry, base, config, result, runner, validation, logging)
├── base.py                                       (BaseClusterAlgorithm, ClusterAlgorithmError)
├── registry.py                                   (AlgorithmRegistry, AlgorithmRegistryError)
├── result.py                                     (AlgorithmFamily, ClusterResult, MetricsResult, ExperimentResult,
                                                   ExperimentStatus, ClusterResultEncoder, cluster_result_to_dict)
├── runner.py                                     (ExperimentRunner, ExperimentSpec, RunnerError,
                                                   resolve_random_seed, capture_library_versions, capture_platform_info)
├── artifacts.py                                  (write_cluster_labels, write_algorithm_output,
                                                   write_experiment_artifacts)
├── validation.py                                 (validate_clustering_matrix, validate_customer_alignment,
                                                   ValidationCheck, ValidationReport, IdentifierLeakageError,
                                                   ClusteringInputError)
├── config.py                                     (FrameworkConfig, ExperimentConfig, InputConfig, ValidationConfig,
                                                   OutputConfig, LoggingConfig, MetadataConfig, RandomSeedConfig,
                                                   load_framework_config, framework_config_to_dict, compute_text_sha256)
├── logging_utils.py                              (get_logger, setup_file_logging, write_experiment_log, now_utc_iso)
├── kmeans.py                                     (KMeansAdapter — ML-02; registered as "kmeans"; HARD family)
├── agglomerative.py                              (AgglomerativeAdapter — ML-03; registered as "agglomerative"; HARD family)
├── dbscan.py                                     (DBSCANAdapter — ML-04; registered as "dbscan"; DENSITY_BASED family)
├── gmm.py                                        (GMMAdapter — ML-05; registered as "gmm"; MODEL_BASED family)
├── fuzzy_cmeans.py                               (FuzzyCMeansAdapter — ML-06; registered as "fuzzy_cmeans"; FUZZY family)
├── kmedoids.py                                   (OUT OF SCOPE per ADR-0003; NotImplementedError placeholder)
├── baseline.py                                   (BaselineRunner — EXP-01 orchestrator; not used by DEV-04)
├── cluster_number.py                             (EPIC-07 sweep; not used by DEV-04)
├── hyperparameter_search.py                      (EPIC-07 sweep; not used by DEV-04)
├── preprocessing_feature_sensitivity.py          (EXP-04 sweep; not used by DEV-04)
├── stability.py                                  (EPIC-08 stability; not used by DEV-04)
└── metrics.py                                    (EPIC-08 metrics; not used by DEV-04)
```

### 3.2. Configs hiện có

```
configs/
├── aggregation.yaml, clustering.yaml, dataset.yaml, eva03_stability_evaluation.yaml,
├── exp01..05_*.yaml, experiment.yaml, feature_engineering.yaml, features.yaml,
├── outlier.yaml, preprocessing.yaml, transformation.yaml
├── dev02_dataset_management.yaml                 (DEV-02 config — precedent for DEV-04 config)
└── dev03_preprocessing.yaml                      (DEV-03 config — sibling precedent for DEV-04)
```

### 3.3. Scripts hiện có

```
scripts/
├── run_fe01..fe06_*.py                           (FE-* research orchestrators — NOT to be modified)
├── run_exp01..exp05_*.py                         (EXP-* orchestrators — NOT to be modified)
├── run_ml02..ml06_*.py                           (ML-02..ML-06 orchestrators — pattern to mirror)
├── run_eva0X.py, run_cp0X.py                     (Evaluation + cluster profiling — out of scope)
├── build_*.py, generate_*.py, audit_dataset.py   (Other research scripts)
└── dev02_import_dataset.py                       (DEV-02 CLI — pattern to mirror)
    dev03_preprocess_dataset.py                   (DEV-03 CLI — pattern to mirror; NEW CLI for DEV-04)
```

### 3.4. Tests hiện có

```
tests/
├── test_*.py (research core tests — pre-existing, NOT to be modified)
├── test_dev02_*.py (12 files — pattern to mirror for DEV-04)
├── test_dev03_*.py (15 files — pattern to mirror for DEV-04)
├── test_ml01_framework.py                        (ML-01 framework test surface — NOT to be modified by DEV-04)
├── test_ml02_kmeans.py                           (ML-02 K-Means adapter — NOT modified)
├── test_ml03_agglomerative.py                    (ML-03 Agglomerative adapter — NOT modified)
├── test_ml04_dbscan.py                           (ML-04 DBSCAN adapter — NOT modified)
├── test_ml05_gmm.py                              (ML-05 GMM adapter — NOT modified)
├── test_ml06_baseline.py                         (ML-06 baseline — NOT modified)
└── test_ml06_fuzzy.py                            (ML-06 Fuzzy C-Means adapter — NOT modified)
```

### 3.5. Trạng thái module / configuration

| Item | Status (research core) | Source | Implication cho DEV-04 |
|---|---|---|---|
| ML-01 framework (`registry`, `runner`, `result`, `validation`, `artifacts`, `logging_utils`, `config`) | `TECHNICALLY_IMPLEMENTED` (per `clustering.yaml::framework.metadata.stage_status`) | `configs/clustering.yaml::framework.metadata`; `tests/test_ml01_framework.py` (existing 1468 tests) | DEV-04 WRAPS these modules verbatim; không modify. |
| K-Means adapter (ML-02) | `TECHNICALLY_IMPLEMENTED`; `working_n_clusters=4` is `WORKING_ASSUMPTION` | `configs/clustering.yaml::algorithms.kmeans` | DEV-04 calls `KMeansAdapter` via `AlgorithmRegistry.get("kmeans")`; per-experiment hyperparameters via `ExperimentSpec.hyperparameters` |
| Agglomerative adapter (ML-03) | `TECHNICALLY_IMPLEMENTED`; `working_n_clusters=4`, `working_linkage="ward"`, `working_metric="euclidean"` are `WORKING_ASSUMPTION` | `configs/clustering.yaml::algorithms.agglomerative` | Same pattern; `n_clusters`, `linkage`, `metric` configurable via `ExperimentSpec.hyperparameters` |
| DBSCAN adapter (ML-04) | `TECHNICALLY_IMPLEMENTED`; `working_eps=0.5`, `working_min_samples=5`, `working_metric="euclidean"` are `WORKING_ASSUMPTION`; noise label = -1 preserved | `configs/clustering.yaml::algorithms.dbscan` | Same pattern; `eps`, `min_samples`, `metric` configurable |
| GMM adapter (ML-05) | `TECHNICALLY_IMPLEMENTED`; `working_n_components=4`, `working_covariance_type="full"`, `working_init_params="kmeans"` are `WORKING_ASSUMPTION`; soft_probabilities preserved | `configs/clustering.yaml::algorithms.gmm` | Same pattern; `n_components`, `covariance_type`, `init_params`, `random_state` configurable |
| Fuzzy C-Means adapter (ML-06) | `TECHNICALLY_IMPLEMENTED`; `working_n_clusters=4`, `working_fuzziness=2.0`, `working_max_iter=300`, `working_error=1e-4` are `WORKING_ASSUMPTION`; soft_membership preserved | `configs/clustering.yaml::algorithms.fuzzy_cmeans` | Same pattern; `n_clusters` (c), `m` (fuzziness), `max_iter`, `error`, `random_state` configurable |
| K-Medoids | `OUT OF SCOPE` per ADR-0003 (`NotImplementedError`) | `kmedoids.py`; `configs/clustering.yaml::algorithms.kmedoids.enabled = false` | DEV-04 MUST NOT use K-Medoids. `AlgorithmRegistry` does NOT register kmedoids. If user passes `--algorithm kmedoids`, DEV-04 raises `AlgorithmRegistryError` (from `AlgorithmRegistry.get()`). |
| 5 algorithms registered | `['agglomerative', 'dbscan', 'fuzzy_cmeans', 'gmm', 'kmeans']` | `AlgorithmRegistry.list_registered()` (5 entries) | DEV-04 supported algorithm list = 5 names above. No extension. |
| `ExperimentRunner.run(matrix_df, customer_metadata_df, *, input_sha256, input_path, metadata_path, output_dir)` signature | `TECHNICALLY_IMPLEMENTED` | `runner.py:155-179` | DEV-04 MUST pass `matrix_df` (numeric, no CustomerID), `customer_metadata_df` (carrying CustomerID), and `output_dir` (prototype dir, not research dir) |
| Artifact writers (`write_cluster_labels`, `write_algorithm_output`, `write_experiment_artifacts`) | `TECHNICALLY_IMPLEMENTED` | `artifacts.py` | DEV-04 reuses these writers via `ExperimentRunner.run(output_dir=...)` — runner internally calls `write_experiment_artifacts`. No need to import artifact writers directly. |
| `FrameworkConfig` (typed dataclass) | `TECHNICALLY_IMPLEMENTED` | `config.py` | DEV-04 reuses `load_framework_config()` to load ML-01 framework config; ALLOWS custom config file via CLI flag (per the existing `FrameworkConfig(explicit=...)` pattern in `run_ml02_kmeans.py`). However, `FrameworkConfig.input.{final_clustering_dataset_path, customer_metadata_path}` is hard-coded as research paths. **CRITICAL for DEV-04**: see §6.3. |
| Random seed policy | `framework.random_seed.default = 42`; per-algorithm override supported | `config.py::RandomSeedConfig`; `runner.py::resolve_random_seed` | DEV-04 supports per-experiment `seed_override` via `ExperimentSpec.seed_override`; algorithm-specific override via YAML `per_algorithm_override` |
| Logging (`get_logger`, `setup_file_logging`, `write_experiment_log`) | `TECHNICALLY_IMPLEMENTED` | `logging_utils.py` | DEV-04 reuses the `customer_segmentation.clustering` logger; experiment log JSON written by `ExperimentRunner` (delegated to `write_experiment_log`). |
| Storage paths (`framework.input.final_clustering_dataset_path` = `./data/processed/final_clustering_dataset.parquet`; `framework.output.artifacts_dir` = `./data/processed/clustering_experiments`; `framework.output.report_dir` = `./reports/ml01`) | `TECHNICALLY_IMPLEMENTED` but **HARDCODED to research paths** in `clustering.yaml` | `clustering.yaml::framework.input.output` | **CRITICAL GAP**: `ExperimentRunner` reads `self.cfg.input.final_clustering_dataset_path` and `self.cfg.input.customer_metadata_path` for **logging/audit metadata only** (not for actual I/O — the runner takes `matrix_df` + `customer_metadata_df` as arguments). So the runner's I/O is NOT bound to the YAML paths. However, the `input_path`/`metadata_path` recorded in the experiment log come from the **caller** (DEV-04 must pass them as kwargs to `runner.run()`). |
| Algorithm family semantics (HARD, DENSITY_BASED, MODEL_BASED, FUZZY) | `TECHNICALLY_IMPLEMENTED` in `result.py::AlgorithmFamily` | `result.py:46-55` | DEV-04 preserves each family semantics: DBSCAN keeps noise label -1; GMM keeps soft_probabilities; FCM keeps soft_membership. Adapter contract already enforces this; DEV-04 just dispatches. |
| Metrics computation | **NOT** in ML-01 framework (`MetricsResult` is placeholder) | `result.py::MetricsResult` (all fields default to `None`) | DEV-04 does NOT compute any metrics (out of scope; per AGENTS.md §3 "Clustering" + user request §4.D). The `metrics` field in `ExperimentResult` will be empty (None values). |
| `FrameworkConfig.output.{cluster_labels_filename, experiment_log_filename, algorithm_output_filename}` templates | `cluster_labels_filename: "cluster_labels_{experiment_id}.parquet"`; `experiment_log_filename: "experiment_log_{experiment_id}.json"`; `algorithm_output_filename: "algorithm_output_{experiment_id}.parquet"` | `clustering.yaml::framework.output` | DEV-04 reuses these templates. Experiment ID is per-DV04-run (built from algorithm + hyperparameters, mirror `run_ml02_kmeans.py::_build_experiment_id`). |

### 3.6. Output location analysis (CRITICAL for §4 research safety)

The **research core** writes artifacts to:
- `data/processed/clustering_experiments/cluster_labels_{experiment_id}.parquet`
- `data/processed/clustering_experiments/experiment_log_{experiment_id}.json`
- `data/processed/clustering_experiments/algorithm_output_{experiment_id}.parquet` (only when soft probabilities/membership present)
- `data/processed/customer_metadata.parquet` — **READ-ONLY** for the runner (never modified)
- `data/processed/final_clustering_dataset.parquet` — **READ-ONLY** for the runner (never modified)

The **prototype layer** (DEV-04) MUST write to a separate location:
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/cluster_labels_{experiment_id}.parquet`
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/experiment_log_{experiment_id}.json`
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/algorithm_output_{experiment_id}.parquet` (conditional)
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/clustering_manifest.json` (DEV-04 manifest)

The `ExperimentRunner.run(output_dir=...)` parameter takes a `Path` and writes there. So **no modification to ML-01 is needed** to point to prototype paths — DEV-04 simply passes the prototype directory as `output_dir` when calling `runner.run()`. This is the **cleanest** research-safety isolation: the runner is parameterised over the output directory; research paths are the framework default but not hard-coded in the runner.

> **Verified by code inspection** (`src/customer_segmentation/clustering/runner.py:155-179, 240-250, 380-410`): the runner's I/O is fully parameterised:
> - `matrix_df` and `customer_metadata_df` are caller-supplied (read into memory by the caller; runner does NOT read from disk)
> - `output_dir` is caller-supplied (runner does NOT default to a hard-coded research path)
> - `input_path`, `metadata_path`, `input_sha256` are caller-supplied (recorded as metadata only; not used for I/O)
>
> This is the contract AGENTS.md §2.3 ("Dataset đầu vào của một phase phải được READ-ONLY nếu plan yêu cầu. ... Không được mutate silently") implicitly relies on.

### 3.7. Preprocessed manifest schema reference (from DEV-03)

`PreprocessedManifest` (`src/customer_segmentation/prototype/preprocessing/manifest.py`) has a `ml_dataset_block` field with `row_count`, `column_count`, `columns`, `sha256`. DEV-04 will reference this in the DEV-04 manifest for the source ML Dataset pointer (mirror DEV-03 pattern: `preprocessed_id` + `preprocessed_sha256`).

---

## 4. Phạm vi (in-scope / out-of-scope)

### 4.1. In-scope (Jira scope + 6 AC)

| # | In-scope item | Reference |
|---|---|---|
| 1 | Choose algorithm (1 of 5: kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans) | `AlgorithmRegistry.list_registered()` |
| 2 | Configure per-algorithm hyperparameters + random seed | `ExperimentSpec.hyperparameters`, `seed_override` |
| 3 | Run a single experiment end-to-end (validate → fit → log) | `ExperimentRunner.run()` |
| 4 | Produce cluster labels parquet (CustomerID + ClusterLabel + IsNoise + extras) | `write_cluster_labels` (called by `ExperimentRunner`) |
| 5 | Save experiment log JSON (full `ExperimentResult`) | `write_experiment_log` (called by `ExperimentRunner`) |
| 6 | Save result (algorithm_output parquet for soft algorithms + DEV-04 manifest JSON) | `write_algorithm_output` + DEV-04 `clustering_manifest.json` |

### 4.2. Out-of-scope (explicit)

| # | Out-of-scope item | Reason |
|---|---|---|
| 1 | Implementing K-Medoids | ADR-0003: OUT OF SCOPE. `kmedoids.py` is a placeholder. |
| 2 | Implementing K-Means / Agglomerative / DBSCAN / GMM / FCM | ML-02..ML-06 already `TECHNICALLY_IMPLEMENTED`; wrap-and-call only. |
| 3 | Modifying ML-01 framework (`registry`, `runner`, `result`, `artifacts`, `validation`, `config`, `logging_utils`) | Research core READ-ONLY per AGENTS.md §2.2. Phase isolation. |
| 4 | Modifying `configs/clustering.yaml` | Research config; prototype has its own `configs/dev04_clustering.yaml`. |
| 5 | Modifying `scripts/run_ml0X_*.py` | Research orchestrators. |
| 6 | Computing evaluation metrics (silhouette, DBI, CH, WCSS) | AGENTS.md §3 "Clustering" forbids in non-evaluation stages; metrics are EPIC-08 scope. |
| 7 | Ranking algorithms, picking "best / optimal / recommended" | AGENTS.md §2.5, §2.6 forbidden. |
| 8 | Stability / runtime analysis | EPIC-08 scope. |
| 9 | Hyperparameter sweep (k_range, eps_range, ...) | EPIC-07 scope. DEV-04 runs ONE experiment per CLI invocation. |
| 10 | Segment profiling / naming ("Champions", "Loyal", ...) | EPIC-09 / CP-01..05 scope. |
| 11 | Visualization | EPIC-09 scope. |
| 12 | Modifying research artefacts (data/processed, data/raw, reports/, customer_metadata.parquet, final_clustering_dataset.parquet) | AGENTS.md §2.3, §2.12. |
| 13 | Modifying DEV-02 / DEV-03 outputs (data/prototype/datasets/<dataset_id>/manifest.json, preprocessed/manifest.json) | Downstream packages READ-ONLY. |
| 14 | Adding new third-party dependencies | All required libs (numpy, pandas, scipy, scikit-learn, pyarrow, PyYAML) already in `pyproject.toml::dependencies`. |
| 15 | Backend / API / database / worker / queue | ADR-0005 Option A. |
| 16 | New top-level config files in `configs/` other than `configs/dev04_clustering.yaml` | Single new file. |
| 17 | Modifying `tests/test_ml0X_*.py` | Research tests READ-ONLY. |
| 18 | Git operations (commit, push, PR, merge) | AGENTS.md §2.11. |
| 19 | Promoting `WORKING_ASSUMPTION` to `RESEARCH_APPROVED_FINAL` | AGENTS.md §2.10. |
| 20 | Resolving DOC-CTD-01 (FE-06 C7 status conflict) | Methodology blocker; out of DEV-04 scope. |

### 4.3. Inherited from DEV-02 / DEV-03 (not DEV-04 to resolve)

- **DOC-CTD-01** (`METHODOLOGY_LOCK_STATUS.md` ↔ `SYS-04` DS-03 = FE-06 C7 conflict) — out of scope; DEV-04 mirrors FE-06 / `clustering.yaml` as-is.
- **SYS-06 §S-02 wording conflict** (UI "no upload" vs CLI upload) — out of scope; HTML prototype is mock-data only.
- **`scripts/run_pipeline.py` is `NotImplementedError`** — out of scope (DEV-01 §4.1 disposition).
- **Pre-existing lint findings in research core** — out of scope (DEV-01 §7.1.1 disposition).

---

## 5. Architecture và data flow

### 5.1. Architecture (per ADR-0005 Option A)

| Concern | Contract |
|---|---|
| Operator interface | Python CLI / `scripts/dev04_run_clustering.py` |
| ML orchestration | `scripts/dev04_run_clustering.py` → `customer_segmentation.prototype.clustering.pipeline` → `customer_segmentation.clustering.ExperimentRunner` (direct call; no HTTP service, no worker process) |
| Persistence | Filesystem + Parquet (`data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/`) + JSON manifests |
| Prototype frontend | `docs/system/ui-prototype/index.html` (mock data; design/UX review only; unchanged) |
| Backend / API / database / worker / queue | **N/A** — intentionally not implemented (per ADR-0005 Option A) |

### 5.2. Data flow

```
                DEV-02 (completed)
                     │
                     ▼
data/prototype/datasets/<dataset_id>/
  ├── <original_filename>
  └── manifest.json
                     │
                     │ (DEV-03 read via DEV-02 public API)
                     ▼
                DEV-03 (completed)
                     │
                     ▼
data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/
  ├── ml_dataset_<ts>_<hex>.parquet         (CustomerID + 14 candidate features)
  ├── preprocessed_<ts>_<hex>.parquet       (cleaned transaction-level; optional)
  ├── preprocessed_manifest.json             (PreprocessedManifest)
  └── <preprocessed_id>.log

                     │
                     │ (DEV-04 reads via DEV-03 public API
                     │  customer_segmentation.prototype.preprocessing.manifest)
                     ▼
                DEV-04 (this plan)
                     │
                     │  - DEV-04 consumes: ml_dataset_*.parquet (CustomerID + 14 features)
                     │  - Splits: customer_metadata_df = CustomerID-only
                     │            matrix_df = 14 features (NO CustomerID)
                     │  - ExperimentRunner.run(matrix_df, customer_metadata_df,
                     │                          output_dir=staging_dir)  ← see §6.7.4
                     │  - Runner writes to staging_dir:
                     │      cluster_labels_{experiment_id}.parquet
                     │      experiment_log_{experiment_id}.json
                     │      algorithm_output_{experiment_id}.parquet (conditional)
                     │  - DEV-04 then writes:
                     │      clustering_manifest.json (atomic; in staging)
                     │      <clustering_id>.log (per-stage; in staging)
                     │  - On success: atomic rename staging_dir → final
                     │  - On failure: unlink staging_dir; restore backup
                     ▼
data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/
  ├── <clustering_id_1>/
  │   ├── cluster_labels_<experiment_id_1>.parquet
  │   ├── experiment_log_<experiment_id_1>.json
  │   ├── algorithm_output_<experiment_id_1>.parquet   (only if soft output)
  │   ├── clustering_manifest.json                     (DEV-04 manifest)
  │   └── <clustering_id_1>.log
  ├── <clustering_id_2>/                                (khác config, cùng preprocessed_id)
  │   ├── cluster_labels_<experiment_id_2>.parquet
  │   ├── experiment_log_<experiment_id_2>.json
  │   ├── algorithm_output_<experiment_id_2>.parquet
  │   ├── clustering_manifest.json
  │   └── <clustering_id_2>.log
  └── _staging_<run_uuid>/                              (transient; chỉ tồn tại khi run đang chạy)
```

**Tại sao mỗi `clustering_id` có subdirectory riêng** (xem §6.3 và §6.7.1):

- Một thư mục cố định `clustering_manifest.json` không thể lưu nhiều
  config cùng tồn tại (mỗi lần ghi sẽ overwrite manifest cũ).
- Hai cấu hình khác nhau (`--n-clusters=3` vs `--n-clusters=5`) cho
  cùng `preprocessed_id` sẽ có 2 `clustering_id` khác nhau → 2 bộ
  artifact ở 2 subdirectory song song. `--force-rerun` cho cùng
  `clustering_id` sẽ được route về staging/publish (xem §6.7.4) để
  đảm bảo kết quả cũ còn nguyên cho đến khi publish thành công.
- `experiment_id` do user đặt (CLI `--experiment-id`) chỉ cần unique
  trong subdirectory; hai config khác nhau (clustering_id khác nhau)
  có thể dùng cùng `experiment_id` mà không xung đột vì chúng ở 2
  thư mục khác nhau.

**Why this isolation works**: the `ExperimentRunner` (ML-01) is parameterised over `output_dir` and `matrix_df` / `customer_metadata_df`. The framework's YAML `framework.input.{final_clustering_dataset_path, customer_metadata_path}` and `framework.output.{artifacts_dir, report_dir}` are **NOT consulted by the runner at I/O time** — they're only used for default config validation. The caller (`ExperimentRunner.__init__` and `.run()`) decides where to read from and write to. DEV-04 passes a staging subdirectory (NOT the final per-clustering_id directory) to keep the ML-01 I/O surface unchanged; DEV-04 then handles atomic publish.

### 5.3. Sequence (single DEV-04 run)

```
┌─ Stage 0: preflight (CLI args + config load) ──────────┐
│  - resolve --dataset-id, --preprocessed-id, --algorithm,│
│    --hyperparameters, --seed, --experiment-id          │
│  - load configs/dev04_clustering.yaml (DEV-04 config)  │
│  - load configs/clustering.yaml (ML-01 framework cfg)  │
└─────────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage 1: lookup preprocessed dataset (DEV-03 input) ──┐
│  - read preprocessed_manifest.json under                │
│    data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/│
│  - verify preprocessed_scope == "PREPROCESSED_PROTOTYPE"│
│  - verify ml_dataset_block present; locate ml_dataset_*.parquet│
│  - load ml_dataset parquet → ml_dataset_df              │
│  - log: stage_1.start / stage_1.input.rows / ...        │
│  → on FAIL: abort with error; no write                  │
└─────────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage 2: split ML Dataset → matrix + metadata ────────┐
│  - customer_key = "CustomerID"                          │
│  - matrix_df = ml_dataset_df.drop(columns=[customer_key])│
│  - customer_metadata_df = ml_dataset_df[[customer_key]] │
│  - log: stage_2.matrix.shape / metadata.shape           │
│  → on FAIL: abort                                       │
└─────────────────────────────────────────────────────────┘
                            ↓ (only on PASS)
┌─ Stage 3: build ExperimentSpec + ExperimentRunner ─────┐
│  - experiment_id = "{algorithm}-<hyperparameter-hash>"  │
│  - hyperparameters from CLI/config                      │
│  - seed_override from CLI/config                        │
│  - compute clustering_id (xem §6.4.1)                   │
│  - call find_existing_clustering (xem §6.7.1):          │
│      - manifest valid + payload khớp + not              │
│        --force-rerun → early-return existing            │
│      - manifest valid + payload khớp + --force-rerun    │
│        → continue (staging/publish)                     │
│      - no match → continue (new run)                    │
│      - **R2**: manifest corrupt + not --force-rerun →   │
│        fail-closed CLI exit non-zero                    │
│      - **R2**: manifest corrupt + --force-rerun →       │
│        move final_dir → _backup_<uuid>_corrupt/         │
│        (atomic rename); continue (new run); cleanup     │
│        retain _backup_*_corrupt/                        │
│  - **R2 #6**: Dev04CollisionError KHÔNG BAO GIỜ catch   │
│    bởi recovery path                                    │
│  - if continuing, prepare staging subdirectory:         │
│      staging_dir = base/clustering/_staging_<run_uuid>/ │
│  - if --force-rerun + old subdirectory exists, snapshot │
│    old to backup_dir (atomic rename on POSIX)           │
│  - ExperimentRunner(framework_cfg, spec,                │
│                     config_source=path,                │
│                     config_text=yaml_text)             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─ Stage 4: runner.run() (writes vào staging_dir) ───────┐
│  - validates matrix (no CustomerID, no NaN, no Inf)     │
│  - validates metadata alignment                        │
│  - resolves algorithm from registry                    │
│  - resolves seed (per algorithm + override)            │
│  - adapter.fit(matrix_df.to_numpy()) → ClusterResult   │
│  - writes cluster_labels + experiment_log +            │
│    algorithm_output (if soft) under staging_dir        │
│    (ML-01 output_dir param)                            │
│  - returns ExperimentResult (status=SUCCESS or FAILED)  │
│  → on FAILED: chỉ ghi experiment_log vào staging;     │
│    KHÔNG ghi cluster_labels, KHÔNG ghi algorithm_output │
│    (runner gate save_labels=False). Stage 5 abort;     │
│    **R1+R2 EXCEPTION PATH** (the 4 steps below MUST   │
│    run in this exact order; do not interleave):         │
│      Step 1 (R1): _preserve_failed_log move            │
│        experiment_log*.json từ staging →               │
│        _failed_<clustering_id>_<run_uuid>/             │
│        (RETAINED cho audit, KHÔNG BAO GIỜ unlink).     │
│        Nếu preserve itself fail (OSError, permission,  │
│        disk full): log + KHÔNG raise (primary exc must  │
│        propagate); log left in staging_dir if possible.│
│        **`_preserve_failed_log` return                 │
│        `PreservationStatus` ∈ {"ok", "partial",        │
│        "no_log", "failed"}`; exception handler set     │
│        `state.unpreserved_log_in_staging=True` nếu     │
│        status ∈ {"partial","failed"} VÀ re-scan        │
│        xác nhận còn `experiment_log_*.json` trong       │
│        staging (defence-in-depth: tránh false +ve).    │
│      Step 2 (R2): if a normal --force-rerun backup     │
│        exists (state.backup_dir set, NOT corrupt       │
│        recovery), attempt to restore recoverable       │
│        SUCCESS: os.rename(backup_dir, final_dir) atomic.│
│        If restore fails: log + leave backup_dir in     │
│        place (KHÔNG silently destroy recoverable art.).│
│        corrupt-recovery backup (suffix `_corrupt`) is   │
│        NOT restored here — retained for diagnosis.     │
│      Step 3: re-raise the original run/publish         │
│        exception (primary exception). Any secondary     │
│        failure from Step 1 or Step 2 is logged but NOT  │
│        raised (replacing primary would hide cause).     │
│      Step 4: outer cleanup pass (R3) runs in `finally` │
│        and does NOT delete the retained _failed_*/ dir  │
│        or the only recoverable backup_dir (publish_     │
│        succeeded=False → backup retained).              │
│        **F1 invariant**: nếu Step 1 set                │
│        `state.unpreserved_log_in_staging=True` (i.e.    │
│        preserve fail/partial VÀ còn log trong staging),│
│        cleanup pass MUST NOT unlink staging_dir (retain│
│        cho manual recovery); chỉ xóa nếu status = "ok" │
│        hoặc "no_log" (no log = no orphan to preserve). │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─ Stage 5: write DEV-04 manifest (vào staging_dir) ─────┐
│  - clustering_id = "cl_<sha256(canonical_effective_config)[:24]>"  │
│    (canonical JSON object 7 trường logic, xem §6.4.1;  │
│    preprocessed_id, algorithm, hyperparameters sorted+  │
│    JSON-canonical, seed_policy, seed, config_sha256,    │
│    ml_dataset_sha256)                                    │
│  - fields: full DEV-04 manifest schema (xem §6.4)       │
│    - schema_version, scope                               │
│    - clustering_id                                       │
│    - preprocessed_id, ml_dataset_sha256  (CANONICAL     │
│      1/7 + 7/7; field names = canonical payload keys)   │
│    - algorithm, algorithm_version, algorithm_family     │
│    - experiment_id                                       │
│    - experiment_log_path, cluster_labels_path,           │
│      algorithm_output_path (nullable)                    │
│    - hyperparameters (verbatim from ExperimentResult,   │
│      effective after CLI merge)                          │
│    - random_seed_requested (audit; runtime),             │
│      seed_policy (canonical 4/7, xem §6.4.2),            │
│      seed (canonical 5/7 — int cho stochastic, null cho   │
│      deterministic)                                       │
│    - n_clusters, n_samples, feature_set, feature_count  │
│    - input_identity (matrix + customer_metadata SHA)    │
│    - config_source, config_sha256 (sha256 of dev04 yaml)│
│    - environment (python / platform / libraries)        │
│    - created_utc, last_seen_utc, log_file               │
│    - research_safety:                                    │
│        automatically_promoted_to_research: false        │
│        appeared_in_research_evidence: false             │
│        scope: "CLUSTERED_PROTOTYPE"                      │
│        read_only_paths_unmodified: [4 paths]             │
│  - atomic write: temp file + rename (xem §6.2.2),       │
│    trong staging_dir                                     │
│  - verify all artifacts in staging (size, schema)        │
│  → on FAIL (Stage 5): **R1** _preserve_failed_log run;  │
│    staging unlinked (sau preserve); backup restored;    │
│    CLI exit non-zero                                     │
│  → on PASS (Stage 5): chuyển sang Stage 5b               │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─ Stage 5b: atomic publish (staging → final) ───────────┐
│  - final_dir = base/clustering/<clustering_id>/         │
│  - on POSIX: os.rename(staging_dir, final_dir)          │
│    là single atomic operation; thay thế hoàn toàn       │
│    hoặc không gì cả                                     │
│  - nếu final_dir đã tồn tại (--force-rerun): backup đã  │
│    được move đi ở Stage 3; rename vẫn atomic và thay    │
│    thế old final_dir                                     │
│  → on success: cleanup backup_dir (nếu có, R3 + R2      │
│    retain _backup_*_corrupt/)                            │
│  → on failure (rename exception): restore backup;       │
│    cleanup staging (không thể xảy ra trên POSIX khi    │
│    cùmột filesystem; documented for safety)            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─ Stage 6: log per-stage (vào final_dir) ────────────────┐
│  - <clustering_id>.log: per-stage entries trong final  │
│  - shared with research log format                      │
│  - log level configurable via YAML (INFO default)       │
│  - on FAIL: per-stage log được preserve trong staging  │
│    trước khi unlink (debug only); final_dir không bị  │
│    touch                                                │
└─────────────────────────────────────────────────────────┘

**Top-level try/finally wrapper (R3)**: Toàn bộ Stage 0 → Stage 6 (và
publish ở Stage 5b) được wrap trong 1 `try/finally:` block duy nhất.
Cleanup pass (xem §6.7.4 pseudocode `_cleanup_pass`) chạy trong
`finally:` để đảm bảo (a) unlink staging_dir nếu còn; (b) unlink
backup_dir NẾU publish_succeeded=True AND KHÔNG phải corrupt recovery
backup; (c) retain `_failed_*/` cho audit (R1); (d) retain
`_backup_*_corrupt/` cho audit (R2); (e) KHÔNG touch other runs' dirs;
(f) KHÔNG hide primary exception nếu cleanup cũng fail. **Distinguish
Python exception cleanup from crash recovery**: cleanup chỉ chạy khi
Python có control; crash (segfault/OOM/power loss) recovery thuộc về
next invocation's `recover_orphan_backups`.
```

### 5.4. Coupling rules

#### 5.4.1. `customer_segmentation.prototype.clustering` MAY import from:

- `customer_segmentation.clustering.*` (RESEARCH CORE — READ-ONLY; wrap-and-call)
  - `clustering.ExperimentRunner`, `ExperimentSpec`
  - `clustering.AlgorithmRegistry` (read-only lookup)
  - `clustering.FrameworkConfig`, `load_framework_config`, `compute_text_sha256`
  - `clustering.{ClusterResult, ExperimentResult, ExperimentStatus, MetricsResult, AlgorithmFamily}`
  - `clustering.{validate_clustering_matrix, validate_customer_alignment}` (re-exposure; runner calls them internally)
  - `clustering.logging_utils.{get_logger, now_utc_iso}`
- `customer_segmentation.prototype.preprocessing.{manifest, list, scope}` (READ-ONLY; DEV-04 consumes DEV-03 manifest + ML Dataset path)
- `customer_segmentation.dataset_management.{scope, storage, manifest, validation, list}` (READ-ONLY; for ID pattern reuse)
- `customer_segmentation.transformation.versioning` (READ-ONLY; reuse `compute_file_sha256`, `compute_df_sha256`)
- `customer_segmentation.config.loader` (READ-ONLY; pattern reuse for frozenset + typed-error)
- stdlib + `pandas` + `pyarrow` + `PyYAML` (already in `pyproject.toml::dependencies`)

#### 5.4.2. `customer_segmentation.prototype.clustering` MUST NOT import from:

- `customer_segmentation.clustering.{baseline, cluster_number, hyperparameter_search, metrics, stability, preprocessing_feature_sensitivity}` (EPIC-07/08 evaluation; out of DEV-04 scope)
- `customer_segmentation.transformation.{pipeline, scaling}` (FE-06 C7-bound; not relevant to clustering execution)
- `customer_segmentation.evaluation`, `.profiling`, `.outlier_analysis`, `.visualization` (downstream stages; out of scope)
- Any backend / API / database / queue library (per ADR-0005)
- Any new third-party dependency (per AGENTS.md §5 + DEV-01 §5)

#### 5.4.3. Cả hai đảm bảo:

- Một chiều: DEV-04 READS từ research core; research core NEVER imports DEV-04 (mirror DEV-03 §5.2.3).
- `research_safety.automatically_promoted_to_research = false` trong mọi manifest DEV-04 sinh ra.
- `clustering_manifest.scope = "CLUSTERED_PROTOTYPE"` (NOT `RESEARCH`).

---

## 6. Input/output contracts

### 6.1. Input contract

**Caller** (CLI hoặc downstream prototype DEV) cung cấp:

| Argument | Type | Required | Source | Default |
|---|---|---|---|---|
| `--dataset-id` | str | YES | DEV-02 manifest | (none) |
| `--preprocessed-id` | str | YES | DEV-03 manifest | (none) |
| `--algorithm` | str | YES (or via YAML) | `AlgorithmRegistry.list_registered()` ⊆ {`kmeans`, `agglomerative`, `dbscan`, `gmm`, `fuzzy_cmeans`} | (none) |
| `--n-clusters` / `--n-components` / `--eps` / `--min-samples` / `--fuzziness` / `--linkage` / `--metric` / `--covariance-type` / `--init-params` / `--max-iter` / `--n-init` | int / float / str | NO (per-algorithm; from YAML) | `configs/dev04_clustering.yaml::algorithms.<name>.*` | algorithm-specific |
| `--seed` | int | NO | `configs/dev04_clustering.yaml::random_seed.default` hoặc `per_algorithm_override.<algo>` hoặc `--seed` (override) | YAML default |
| `--experiment-id` | str | NO | Built from `algorithm + hyperparameters` (mirror `run_ml02_kmeans.py::_build_experiment_id`) | auto |
| `--config` | Path | NO | `configs/dev04_clustering.yaml` (default) | auto-discovery |
| `--framework-config` | Path | NO | `configs/clustering.yaml` (ML-01 framework config) | auto-discovery |

**Consumed by DEV-04**:

- ML Dataset: `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_<ts>_<hex>.parquet`
  - Schema (from DEV-03 default): 14 candidate features + CustomerID column (FE-05 default; per `docs/system/DEV-03_preprocessing.md` §5.4.2 + `feature_engineering.yaml`).
  - CustomerID is split off into `customer_metadata_df` BEFORE `ExperimentRunner.run()`.
  - All other columns are the feature matrix.
  - **DEV-04 MUST NOT assume FE-06 schema verbatim** — the input is a prototype ML Dataset from DEV-03, which may have a different feature set (e.g. user can disable RFM, change feature subset). DEV-04 just drops CustomerID and uses the rest.
  - If the ML Dataset has fewer than 2 rows or 1 column, the validation will fail with a clear error (handled by `validate_clustering_matrix`).
- DEV-03 manifest: `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json`
  - For provenance pointer (`source_dataset_id`, `source_dataset_sha256`).
  - For content addressing (`preprocessed_sha256` = `ml_dataset_block.sha256`).
  - For environment snapshot (inherited from DEV-03 environment block).

### 6.2. Output contract

**Written by DEV-04** dưới
`data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/`
(mỗi `clustering_id` có subdirectory riêng — xem §6.3 và §6.7.1):

| File | Writer | Atomic? | Schema |
|---|---|---|---|
| `cluster_labels_<experiment_id>.parquet` | `write_cluster_labels()` (ML-01; `customer_segmentation.clustering.artifacts.write_cluster_labels`) | **Không atomic** (xem §6.2.1) | `CustomerID` + `ClusterLabel` (int64) + `IsNoise` (bool) + optional `Probability_k` (GMM) hoặc `Membership_k` (FCM) |
| `experiment_log_<experiment_id>.json` | `write_experiment_log()` (ML-01; `customer_segmentation.clustering.logging_utils.write_experiment_log`) | **Không atomic** (xem §6.2.1) | Full `ExperimentResult.to_dict()` (algorithm, hyperparameters, seed, n_clusters, cluster_labels shape, metrics=None, error=None/exception, platform, library_versions, scope_boundaries, pending_review_notes, assumptions, config_source, config_sha256) |
| `algorithm_output_<experiment_id>.parquet` (conditional) | `write_algorithm_output()` (ML-01) | **Không atomic** | CustomerID + `Probability_k` (GMM, n_components columns) hoặc `Membership_k` (FCM, c columns). ONLY written if `cluster_result.soft_probabilities is not None OR cluster_result.soft_membership is not None`. |
| `clustering_manifest.json` | DEV-04 manifest writer (`prototype/clustering/manifest.py::write_clustering_manifest`) | **Atomic (temp + rename)** — bắt buộc (xem §6.2.1) | DEV-04-specific manifest schema (see §6.4) |
| `<clustering_id>.log` | DEV-04 per-stage log writer (`prototype/clustering/logging_config.py`) | **Atomic (temp + rename)** của mỗi entry line, hoặc single file handle flush-then-rotate (xem §6.2.2) | Per-stage entries: timestamp, level, stage name, message, key metrics |

**Tại sao mỗi `clustering_id` là 1 subdirectory** (xem §6.3, §6.7.1):

- Cho phép nhiều config (cùng `preprocessed_id`, khác `--n-clusters`,
  `--eps`, v.v.) **cùng tồn tại song song** dưới các `clustering_id`
  khác nhau mà không bị ghi đè.
- Mỗi lần ghi chỉ thuộc về 1 `clustering_id`; khác subdirectory = khác
  config = khác nhóm artifact. Khi user đổi `--n-clusters` từ 3 → 5,
  clustering_id mới → subdirectory mới → 2 bộ artifact cùng tồn tại.
- Khi user dùng `--force-rerun` cho cùng `clustering_id`, staging
  + atomic publish policy (xem §6.7.4) đảm bảo kết quả cũ còn nguyên
  cho đến khi publish thành công.
- Custom `--experiment-id` chỉ cần unique trong subdirectory; hai
  config khác nhau (clustering_id khác nhau) có thể dùng cùng
  experiment_id mà không xung đột.

#### 6.2.1. Atomicity analysis (verified by code inspection)

**Phát hiện từ code inspection** (Phase 1, không sửa code):

- `customer_segmentation.clustering.artifacts.write_cluster_labels` gọi
  `df.to_parquet(output_path, index=False)` trực tiếp — KHÔNG có
  temp-file + rename. `pyarrow`'s default `to_parquet` **không đảm
  bảo atomic write** trên POSIX; nếu process crash giữa write, file
  có thể ở trạng thái partial (header ghi xong nhưng data chưa xong,
  hoặc footer thiếu). Tương tự `write_algorithm_output`.
- `customer_segmentation.clustering.logging_utils.write_experiment_log`
  mở file với `open("w", encoding="utf-8")` rồi `json.dump(...)` —
  KHÔNG atomic. Crash giữa dump để lại partial JSON.

**Đây là giới hạn của research core (READ-ONLY cho DEV-04 theo
AGENTS.md §2.2)**, không thể sửa trong DEV-04 scope. **Mitigation**:

- DEV-04 phải sử dụng **idempotency mechanism** (§6.7) để khi một
  partial cluster_labels_*.parquet tồn tại nhưng manifest chưa có,
  retry sẽ overwrite cluster_labels (to_parquet truncate) rồi tạo
  manifest atomic.
- DEV-04 KHÔNG quyết định "cluster_labels partial đã hợp lệ" — phải
  có manifest atomic-write đi kèm mới coi như completed.
- **Thứ tự ghi của ML-01 trong `write_experiment_artifacts`** (xác
  minh bằng code inspection `src/customer_segmentation/clustering/
  artifacts.py:223-260`): (a) `cluster_labels_*.parquet` được ghi
  trước (nếu `save_labels=True` và `cluster_result is not None`),
  sau đó (b) `experiment_log_*.json` luôn được ghi, cuối cùng
  (c) `algorithm_output_*.parquet` được ghi có điều kiện. Vì vậy
  trong trường hợp SUCCESS, **cluster_labels luôn xuất hiện trước
  experiment_log trên filesystem**; trong trường hợp FAILED,
  `save_labels=False` nên chỉ `experiment_log_*.json` được ghi
  (audit-only). Nếu crash xảy ra sau cluster_labels nhưng trước
  experiment_log, manifest sẽ không có (vì manifest là gate), và
  retry sẽ overwrite cluster_labels cũ + experiment_log cũ.

#### 6.2.2. DEV-04 writers — atomic write bắt buộc

**`clustering_manifest.json`**: DEV-04 PHẢI dùng pattern temp-file +
rename (mirror `customer_segmentation.dataset_management.manifest.write_manifest`
và `customer_segmentation.prototype.preprocessing.manifest.write_preprocessed_manifest`).
Pseudocode:

```python
def write_clustering_manifest(manifest: ClusteringManifest, path: Path) -> None:
    """Atomic write: temp file in same dir, rename on success."""
    path = Path(path)
    if not path.parent.exists():
        raise Dev04ManifestError(f"Parent directory does not exist: {path.parent}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(manifest_to_dict(manifest), fh,
                      ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(path)  # atomic on POSIX (rename(2))
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise
```

**`<clustering_id>.log`**: DEV-04 phải dùng một trong hai cách:

(a) **Per-entry atomic**: mỗi log entry ghi vào temp file rồi rename
append vào file chính. Chậm hơn nhưng đảm bảo 100% atomicity.

(b) **Single FileHandler + flush**: dùng `logging.FileHandler(path, mode="w")`
với formatter, và `handler.flush()` sau mỗi entry. KHÔNG đảm bảo
100% atomicity ở mức OS-syscall nhưng đủ tốt cho prototype scale.

DEV-04 chọn **(b)** để cân bằng performance và safety: prototype
scale (1 user, 1 process) không cần per-entry atomic.

**Test yêu cầu** (cho atomic writers):

- `test_dev04_manifest.py::test_manifest_atomic_write_no_partial_on_crash` —
  monkey-patch `tmp.replace` để raise; assert manifest path KHÔNG tồn
  tại và tmp path KHÔNG còn trỏ (cleaned up).
- `test_dev04_manifest.py::test_manifest_atomic_write_temp_cleanup` —
  trigger exception trong serialization; assert `*.tmp` được unlink.
- `test_dev04_logging.py::test_log_file_flush_on_entry` — verify
  `handler.flush()` được gọi sau mỗi log entry (hoặc mỗi stage
  transition).

### 6.3. Output path resolution

DEV-04 **không** tự định nghĩa `storage_root`. Storage root luôn được load
từ **`configs/dev02_dataset_management.yaml::dataset_management.storage_root`**
(đã được DEV-02 §6.2 / §9.5 đóng cam cứng: "CLI không có `--dest-root`,
YAML không có override cho storage_root"). DEV-03 cũng reuse cùng
root qua `resolve_storage_root_for_dataset(...)` (xem
`customer_segmentation/prototype/preprocessing/storage.py::resolve_storage_root_for_dataset`).
DEV-04 tuân thủ **đúng cùng quy ước** với DEV-02/03.

**Layout tổng quát** (xem §5.2 data flow):

```
storage_root/
└── datasets/
    └── <dataset_id>/
        └── preprocessed/
            └── <preprocessed_id>/
                └── clustering/                           # DEV-04 base
                    ├── <clustering_id>/                  # per-run final dir (one per content-addressed id)
                    │   ├── cluster_labels_<experiment_id>.parquet
                    │   ├── experiment_log_<experiment_id>.json
                    │   ├── algorithm_output_<experiment_id>.parquet  (conditional)
                    │   ├── clustering_manifest.json
                    │   └── <clustering_id>.log
                    ├── _staging_<run_uuid>/               # transient, current run only
                    │                                       # contents: cluster_labels_<exp>.parquet,
                    │                                       #            experiment_log_<exp>.json,
                    │                                       #            [algorithm_output_<exp>.parquet],
                    │                                       #            clustering_manifest.json (atomic write),
                    │                                       #            <clustering_id>.log
                    ├── _backup_<run_uuid>/                # normal --force-rerun backup của final_dir cũ
                    │                                       # (chứa 1 inner subdir: <clustering_id>/;
                    │   tạo bằng `os.rename(final_dir, backup_dir)` nên
                    │   inner subdir = chính final_dir cũ)
                    │                                       # Cleanup pass unlink sau success; retain
                    │                                       # nếu publish_succeeded=False (next-run recovery).
                    ├── _backup_<run_uuid>_corrupt/        # R2: --force-rerun backup của corrupt manifest
                    │                                       # Cleanup pass LUÔN retain (audit/diagnosis).
                    └── _failed_<clustering_id>_<run_uuid>/  # R1: FAILED run log tracking
                                                            # (chứa experiment_log_<exp>.json +
                                                            #  _preservation_audit.txt; LUÔN retain)
```

**Backup directory layout** (refined cho consistency với §6.7.4
pseudocode):

- `_backup_<run_uuid>/` được tạo bằng `os.rename(final_dir,
  backup_dir)` ở Stage 3 của pseudocode (§6.7.4). Sau rename, nội
  dung của `_backup_<run_uuid>/` chính là nội dung của final_dir cũ,
  tức **một inner subdir `<clustering_id>/` chứa đầy đủ 5 file**
  (cluster_labels, experiment_log, [algorithm_output],
  clustering_manifest, `<clustering_id>.log`).
- `_backup_<run_uuid>_corrupt/` (R2): tương tự layout với backup
  bình thường (1 inner subdir `<clustering_id>/`), nhưng với suffix
  `_corrupt` để cleanup_pass phân biệt và LUÔN retain. KHÔNG dùng
  để recovery — chỉ để diagnosis. Nếu next run gặp recovery pass,
  backup_dir với suffix `_corrupt` KHÔNG được restore (chỉ
  `_backup_<uuid>` không suffix mới được recover).
- `_failed_<clustering_id>_<run_uuid>/` (R1): chứa
  `experiment_log_<exp>.json` (move từ staging trước khi unlink) và
  `_preservation_audit.txt` (audit record khi preserve). KHÔNG có
  inner subdir; flat layout. Cleanup pass LUÔN retain.
- `recover_orphan_backups()` (§6.7.4) quét `base_dir/_backup_*` (bao
  gồm cả `_backup_<uuid>_corrupt` NHƯNG bỏ qua chúng) và với mỗi
  backup_dir hợp lệ (đúng 1 inner subdir matching regex
  `^cl_[0-9a-f]{24}$`, KHÔNG có suffix `_corrupt`):
  - nếu `base_dir/<clustering_id>/` CHƯA tồn tại → atomic restore
    (`os.rename(backup_dir/<clustering_id>, base_dir/<clustering_id>)`)
  - nếu `base_dir/<clustering_id>/` ĐÃ tồn tại → skip (idempotent
    no-op; main pipeline sẽ xử lý qua orphan-final flow nếu cần).
- Mỗi `_backup_<run_uuid>/` chỉ được xử lý bởi recovery của
  process có `_RUN_UUID` ≠ `run_uuid` (xem `_RUN_UUID` filter).
- KHÔNG có `_backup_<run_uuid>/<clustering_id>/<clustering_id>/`
  (double nesting); chỉ single level.

**Helper functions** (mirror `dataset_management.storage` pattern):

```python
def prototype_clustering_base_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
) -> Path:
    """Return base dir chứa tất cả clustering runs của 1 preprocessed_id.

    Path = <root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/
    """
    root = Path(storage_root).resolve()
    candidate = (
        root
        / "datasets"                   # mirror DEV-02 datasets/ container
        / dataset_id
        / "preprocessed"
        / preprocessed_id
        / "clustering"
    ).resolve()
    candidate.relative_to(root)        # raises ValueError if outside
    return candidate


def prototype_clustering_run_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
) -> Path:
    """Return final dir cho 1 clustering_id (sau khi publish).

    Path = base_dir / <clustering_id>/
    """
    base = prototype_clustering_base_dir(storage_root, dataset_id, preprocessed_id)
    candidate = (base / clustering_id).resolve()
    # Containment: must be under storage_root (clustering_id phải pass
    # validate_clustering_id_format trước — prefix 'cl_', 24 hex).
    storage_root_resolved = Path(storage_root).resolve()
    candidate.relative_to(storage_root_resolved)  # raises ValueError
    return candidate
```

**Quy ước cứng**:

1. **Single source of truth**: `storage_root` đọc từ
   `configs/dev02_dataset_management.yaml` qua
   `customer_segmentation.dataset_management.storage.resolve_storage_root(...)`.
2. **No CLI override**: CLI của DEV-04 **không** có `--storage-root` /
   `--dest-root` / tương đương (mirror DEV-02 §3.5 và DEV-03).
3. **No YAML override**: `configs/dev04_clustering.yaml` **không** có
   key `storage.storage_root`. (Trước đây plan nháp từng liệt kê key
   này như optional; quyết định cuối cùng là **bỏ** để khớp với
   DEV-02/03 contract và tránh phá vỡ single source of truth.)
4. **Path containment validation**:
   - `prototype_clustering_base_dir`: pass `Path.resolve()` + thử
     `relative_to(storage_root.resolve())`. Nếu path nằm ngoài
     storage_root → `Dev04StoragePathError` (raised before write).
   - `prototype_clustering_run_dir`: thêm check `clustering_id` phải
     match regex `^cl_[0-9a-f]{24}$` trước khi dùng làm tên thư
     mục; nếu không match → `Dev04StoragePathError` (chống path
     traversal qua input).
   - Staging/backup dirs phải match `^_(staging|backup)_<hex|tokens>/$`
     để cleanup pass có thể identify.
5. **Per-clustering_id subdirectory** (xem §6.7.1 + §6.7.4): mỗi
   `clustering_id` là 1 subdirectory cuối; nhiều config cùng tồn tại
   song song. `--force-rerun` an toàn nhờ staging/atomic publish.
6. **Test yêu cầu**: `test_dev04_storage.py::test_path_containment_*`
   (3 cases: relative parent traversal, absolute path via dataset_id,
   symlink outside storage_root — mỗi case phải raise
   `Dev04StoragePathError`); thêm `test_clustering_id_format_*` (3
   cases: valid `cl_<24hex>`, invalid prefix, invalid hex length).

The CLI prepares a staging subdirectory
`prototype_clustering_base_dir(...) / f"_staging_{run_uuid}"` and passes
that to `ExperimentRunner.run(output_dir=staging_dir)`. After Stage 5
succeeds, DEV-04 atomic-renames staging → final
(`os.rename(staging_dir, final_dir)`). See §6.7.4 for full staging/
publish flow. ML-01 runner thực hiện I/O tương đối với `staging_dir`;
nếu bất kỳ artifact nào ML-01 cố ghi ra ngoài `staging_dir` (không xảy
ra trong code hiện tại nhưng là đề phòng) → research-safety test sẽ
phát hiện (vì path ngoài `staging_dir` chắc chắn cũng ngoài
storage_root).

### 6.4. DEV-04 manifest schema (`clustering_manifest.json`)

**Quy tắc thiết kế schema**: **7 trường canonical dùng cho
`clustering_id` derivation và collision detection phải có cùng tên
và cùng representation** với các key trong manifest. Manifest là
**superset** chứa canonical payload 7 trường cộng thêm các field
runtime / artifact-paths / provenance. `_extract_canonical_payload_from_manifest`
chỉ là phép **dict subset selection** — KHÔNG có phép chuyển đổi
hai chiều nào (xem §6.7.1).

| Field | Type | Source | Purpose |
|---|---|---|---|
| `schema_version` | str | hard-coded `"1.0.0"` | Schema identity |
| `clustering_id` | str | `cl_<sha256(canonical_payload_7)[:24]>` (xem §6.4.1) | Content-addressed identity (mirror DEV-02/03 pattern) |
| `scope` | str | hard-coded `"CLUSTERED_PROTOTYPE"` | Always prototype scope |
| `preprocessed_id` | str | from DEV-03 manifest | **CANONICAL FIELD 1/7** — same name in canonical payload |
| `ml_dataset_sha256` | str | from DEV-03 `ml_dataset_block.sha256` | **CANONICAL FIELD 7/7** — same name in canonical payload |
| `algorithm` | str | from CLI / config | **CANONICAL FIELD 2/7** — one of 5 |
| `algorithm_version` | str | from `ExperimentResult.algorithm_version` | E.g. `sklearn_1.5` |
| `algorithm_family` | str | from `AlgorithmFamily` (HARD, DENSITY_BASED, MODEL_BASED, FUZZY) | Per family semantics |
| `experiment_id` | str | from CLI / auto-generated | Stable per-experiment ID |
| `hyperparameters` | dict | from `ExperimentResult.hyperparameters` (effective, sau CLI overrides), canonical-normalized | **CANONICAL FIELD 3/7** — exact subset equality với canonical payload |
| `seed_policy` | str | `"stochastic"` \| `"deterministic"` (derived từ algorithm qua `supports_random_state()`, xem §6.4.2) | **CANONICAL FIELD 4/7** — exact subset equality |
| `seed` | int or null | Effective seed (int nếu `seed_policy="stochastic"`, **luôn `null` nếu `seed_policy="deterministic"`** dù user có truyền `--seed`) | **CANONICAL FIELD 5/7** — exact subset equality |
| `config_sha256` | str | SHA-256 bytes của `configs/dev04_clustering.yaml` | **CANONICAL FIELD 6/7** — exact subset equality |
| `experiment_log_path` | str | relative path | Audit trail |
| `cluster_labels_path` | str | relative path | Cluster labels parquet |
| `algorithm_output_path` | str or null | relative path or null | Only for GMM/FCM soft algorithms |
| `log_file` | str | relative path | Per-run log |
| `n_clusters` | int or null | from `ExperimentResult.n_clusters` | Convenience |
| `n_samples` | int | from `ExperimentResult.n_samples` | Customer count |
| `feature_set` | list[str] | from `ExperimentResult.feature_set` | Column names used |
| `feature_count` | int | from `ExperimentResult.feature_count` | `len(feature_set)` |
| `input_identity` | dict | from `ExperimentResult.{dataset_sha256, input_path, metadata_path}` | Identity of source ML Dataset |
| `environment` | dict | from `ExperimentResult.{platform, library_versions}` | Reproducibility |
| `created_utc` | str (ISO-8601 UTC) | runtime | Idempotency lookup |
| `last_seen_utc` | str (ISO-8601 UTC) | runtime | Idempotency lookup |
| `research_safety.automatically_promoted_to_research` | bool | hard-coded `false` | NEVER promoted |
| `research_safety.appeared_in_research_evidence` | bool | hard-coded `false` | NEVER research evidence |
| `research_safety.scope` | str | hard-coded `"CLUSTERED_PROTOTYPE"` | Always prototype |
| `research_safety.read_only_paths_unmodified` | list[str] | hard-coded `[4 paths]` | Defence-in-depth |

**Canonical payload 7 fields** (định nghĩa chính thức, dùng cho cả
`derive_clustering_id` lẫn collision detection):

```python
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "preprocessed_id",     # str
    "algorithm",           # str (1 of 5)
    "hyperparameters",      # dict (normalized)
    "seed_policy",         # "stochastic" | "deterministic"
    "seed",                # int | None
    "config_sha256",       # str
    "ml_dataset_sha256",   # str
)
```

Manifest **PHẢI** chứa đủ 7 key trên với đúng tên. Khi viết manifest,
DEV-04 copy trực tiếp các giá trị canonical (đã được normalize) vào
đúng key. KHÔNG đổi tên, KHÔNG viết hoa khác (`Source_Preprocessed_Id`),
KHÔNG thêm prefix (`source_preprocessed_id`). Đây là contract nghiêm
ngặt để `_extract_canonical_payload_from_manifest` chỉ cần dict subset.

**Stable vs Runtime fields** (mirror DEV-03 §10.4 pattern):

- **Stable** (equal across runs of same input + same effective config — tức cùng 7 trường canonical): `clustering_id`, **7 canonical fields**, `algorithm_version`, `algorithm_family`, `experiment_id`, `n_clusters`, `n_samples`, `feature_set`, `feature_count`, `input_identity`, `schema_version`, `scope`, `research_safety.*`, artifact paths.
- **Runtime** (may differ): `created_utc`, `last_seen_utc`, `environment`.

**Quan trọng — không nhầm representation** (mirror `seed_policy`
canonical whitelist ở §6.4.2):

- Manifest KHÔNG có field `effective_seed_policy` (đã đổi thành
  `seed_policy` với giá trị canonical `"stochastic"` /
  `"deterministic"`; xem §6.4.2).
- Manifest KHÔNG có field tên `random_seed` (request) riêng — đây
  là audit runtime field; nếu user cần audit request, xem
  `experiment_log_<experiment_id>.json` (do ML-01
  `ExperimentResult.to_dict()` ghi) chứ KHÔNG copy sang manifest.
- Manifest KHÔNG có field tên `random_seed_used` (legacy) — manifest
  dùng field canonical `seed` (int cho stochastic algorithms, `null`
  cho deterministic). `ExperimentResult.random_seed_used` vẫn
  được ghi ở `experiment_log_<experiment_id>.json` (ML-01 output).
- Manifest KHÔNG có field tên `source_preprocessed_id` /
  `source_preprocessed_sha256` (legacy) — manifest dùng canonical
  `preprocessed_id` / `ml_dataset_sha256` (canonical keys 1/7 +
  7/7) để round-trip identity-preserving subset selection.

#### 6.4.1. `clustering_id` canonical derivation

`clustering_id` phải phản ánh **cấu hình hiệu lực thực tế** mà runner
nhận được (effective configuration after CLI overrides + seed
resolution), không chỉ raw YAML. **Công thức canonical** dùng một
**JSON object duy nhất** chứa 7 trường logic — KHÔNG ghép chuỗi bằng
ký tự xuống dòng, KHÔNG dùng multi-line string concatenation (vì phụ
thuộc platform, locale, OS). Phương pháp: serialize payload thành
JSON string canonical rồi hash byte UTF-8 của JSON đó.

**Serialization contract** (áp dụng cho CẢ payload lẫn nested values
trong payload, đảm bảo byte-level canonical tuyệt đối):

```python
import json
payload_bytes = json.dumps(
    payload,
    sort_keys=True,            # canonical key ordering (cho cả payload lẫn nested dict)
    ensure_ascii=False,        # giữ UTF-8 bytes (compact hơn \uXXXX-escape)
    separators=(",", ":"),      # bỏ mọi whitespace, đảm bảo byte-level canonical
    allow_nan=False,           # cấm NaN/Infinity (raise ValueError nếu xuất hiện)
).encode("utf-8")
```

**Quy tắc bắt buộc**:

1. `sort_keys=True` — đảm bảo key ordering canonical ở mọi cấp
   (payload và nested dict). KHÔNG dựa vào Python `dict` insertion
   order hoặc YAML key order.
2. `allow_nan=False` — Python `json.dumps` mặc định cho phép
   `NaN`/`Infinity` (non-standard JSON); DEV-04 **cấm** vì phụ thuộc
   platform-specific IEEE-754 representation. Nếu hyperparameter
   chứa NaN/Inf → raise `Dev04ConfigError` (không dùng `json.dumps`
   mặc định).
3. `separators=(",", ":")` — bỏ spaces; đảm bảo 2 payload semantic
   equivalent → cùng byte string.
5. `ensure_ascii=False` — giữ UTF-8 (compact hơn escape form);
   KHÔNG dùng `\uXXXX` mặc định.
6. Scalar normalization: mọi value trong `hyperparameters` được ép
   qua `json.loads(json.dumps(v, allow_nan=False))` trước khi đưa
   vào payload — chuẩn hoá `None` → `null`, `bool` → `true`/`false`,
   `int`/`float` chính xác đến giá trị.

7 trường logic (object keys):

```python
payload_obj = {
    "preprocessed_id":   <str>,                      # từ CLI/DEV-03 manifest
    "algorithm":         <str>,                      # 1 of 5: kmeans/agglomerative/dbscan/gmm/fuzzy_cmeans
    "hyperparameters":    <canonical dict>,            # dict sau CLI merge + sort_keys + scalar normalization
    "seed_policy":       "stochastic" | "deterministic",  # derived from algorithm (xem §6.4.2)
    "seed":              <int> | None,                # giá trị seed mà runner resolve được (None cho deterministic)
    "config_sha256":     <str>,                       # SHA-256 bytes của configs/dev04_clustering.yaml
    "ml_dataset_sha256": <str>,                       # từ DEV-03 manifest.ml_dataset_block.sha256
}
```

**Hằng số**:

- `CLUSTERING_ID_PREFIX = "cl_"` (mirror `ds_`, `pp_`).
- `CLUSTERING_ID_HEX_LEN = 24` (96 bits; mirror `DATASET_ID_HEX_LEN`,
  `PREPROCESSED_ID_HEX_LEN`).
- `DETERMINISTIC_ALGORITHMS = frozenset({"agglomerative", "dbscan"})`
  — tag cho `seed_policy`.

**Pseudocode đầy đủ**:

```python
import hashlib
import json
from typing import Any

CLUSTERING_ID_PREFIX = "cl_"
CLUSTERING_ID_HEX_LEN = 24
# Algorithm cố định deterministic (supports_random_state() == False).
DETERMINISTIC_ALGORITHMS = frozenset({"agglomerative", "dbscan"})


def derive_clustering_id(
    *,
    preprocessed_id: str,
    algorithm: str,
    hyperparameters: dict[str, Any],   # effective, sau CLI merge YAML
    effective_seed: int | None,        # giá trị seed mà runner resolve được
                                       # cho algorithm này (None nếu algorithm
                                       # không support random_state)
    ml_dataset_sha256: str,            # từ DEV-03 manifest.ml_dataset_block.sha256
    config_sha256: str,                # SHA-256 bytes của `configs/dev04_clustering.yaml`
) -> str:
    """Return 'cl_' + first 24 hex chars of SHA-256 of effective config.

    Canonical payload là một JSON object 7 trường logic (xem schema ở
    trên). Serialization: json.dumps với sort_keys=True,
    ensure_ascii=False, separators=(",", ":"), allow_nan=False. Hash
    là SHA-256(UTF-8 bytes của JSON string)[:24 hex]. Đây là single
    source of truth cho clustering_id — KHÔNG có representation nào
    khác (text lines, tuple, etc.).
    """
    # 1. Canonical hoá hyperparameters: sort key, ép value qua
    #    json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))
    #    để chuẩn hoá scalar (None → null, bool → true/false,
    #    int/float chính xác). Lưu ý: `json.dumps` chấp nhận đúng 5
    #    tham số sau — `ensure_ascii`, `allow_nan`, `sort_keys`,
    #    `separators`, `indent`. Mọi tên khác (vd. `allow_ncii`) raise
    #    `TypeError`. Toàn bộ pseudocode ở §6.4.1 đã được kiểm tra
    #    bằng cách thực thi trực tiếp trong `test_dev04_storage.py::
    #    test_clustering_id_pseudocode_runs_without_typeerror` (xem
    #    AC-10 #61c).
    hp_canonical_obj = {
        k: json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))
        for k, v in sorted(hyperparameters.items(), key=lambda kv: kv[0])
    }
    # 2. Seed policy: tách khỏi seed value để hai run với seed khác
    #    nhau nhưng cùng deterministic algorithm vẫn ra CÙNG id.
    seed_policy = (
        "deterministic" if algorithm in DETERMINISTIC_ALGORITHMS else "stochastic"
    )
    # 3. Payload = 7 trường logic trong 1 JSON object (single source).
    payload_obj = {
        "preprocessed_id": preprocessed_id,
        "algorithm": algorithm,
        "hyperparameters": hp_canonical_obj,
        "seed_policy": seed_policy,
        "seed": effective_seed,           # None cho deterministic
        "config_sha256": config_sha256,
        "ml_dataset_sha256": ml_dataset_sha256,
    }
    # 4. Canonical byte-level serialization (xem contract ở trên).
    payload_bytes = json.dumps(
        payload_obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return CLUSTERING_ID_PREFIX + digest[:CLUSTERING_ID_HEX_LEN]
```

**Constants**:

- `CLUSTERING_ID_PREFIX = "cl_"` (mirror `ds_`, `pp_`).
- `CLUSTERING_ID_HEX_LEN = 24` (96 bits; mirror `DATASET_ID_HEX_LEN`,
  `PREPROCESSED_ID_HEX_LEN`). Collision probability cho vài trăm
  run/dataset là không đáng kể (xem §6.7.2).
- `DETERMINISTIC_ALGORITHMS = frozenset({"agglomerative", "dbscan"})`
  — tag cho seed_policy trong canonical payload.

**Đặc tính đảm bảo**:

1. **Determinism**: cùng `payload` bytes (algorithm + hyperparameters
   canonical + seed + ml_dataset + config) → cùng `clustering_id`.
2. **Sensitivity**: bất kỳ thay đổi nào trong (algorithm, một hyperparameter,
   seed marker, ML Dataset SHA, YAML config SHA) → `clustering_id` đổi.
3. **CLI-overrides visibility**: CLI flag đổi một hyperparameter →
   `hyperparameters_canonical` đổi → `clustering_id` đổi (đúng semantics).
4. **Seed-respect cho deterministic**: hai run với `--seed 1` và
   `--seed 2` cho Agglomerative vẫn ra **cùng** `clustering_id` vì
   `seed_policy=deterministic` + `seed=null` (runner ép về None); đúng
   vì cluster labels thực sự không đổi.
5. **Reproducibility for stochastic**: hai run với `--seed 42` cho
   K-Means ra **cùng** `clustering_id` và cùng nội dung cluster_labels
   (verified bằng `test_dev04_artifacts.py::test_reproducibility_kmeans`).

**Test cases bắt buộc** (cho `test_dev04_storage.py::test_clustering_id_*`):

- Different algorithm (same rest) → different `clustering_id`.
- Different `n_clusters` (same rest) → different `clustering_id`.
- Different CLI override (e.g. `--tol 1e-5` vs YAML `--tol 1e-4`) →
  different `clustering_id`.
- Different `config_sha256` (YAML file byte change) → different
  `clustering_id`.
- Different `ml_dataset_sha256` (DEV-03 re-preprocess) → different
  `clustering_id`.
- Stochastic algorithm, different seed → different `clustering_id`.
- Deterministic algorithm, different seed (CLI vs YAML) → SAME
  `clustering_id` (because `seed_policy=deterministic`, `seed=null`).
- Null values (`fuzziness` is None, `metric` is None when default
  unused) — serialised as `null` (canonical).

#### 6.4.2. `seed_policy` semantics (mirror ML-01 `supports_random_state()`)

`seed_policy` là **trường canonical field 4/7** — giá trị phải khớp
đúng giá trị dùng trong `derive_clustering_id` (§6.4.1) và trong
`_extract_canonical_payload_from_manifest` (§6.7.1). Hai giá trị hợp
lệ duy nhất (canonical, byte-level):

| Algorithm | `supports_random_state()` | `seed_policy` (canonical) | `seed` (canonical) |
|---|---|---|---|
| `kmeans` | True | `"stochastic"` | int (từ `resolve_random_seed`) |
| `gmm` | True | `"stochastic"` | int |
| `fuzzy_cmeans` | True | `"stochastic"` | int |
| `agglomerative` | False | `"deterministic"` | `null` (runner ép `seed_to_pass=None`) |
| `dbscan` | False | `"deterministic"` | `null` |

Hai điểm bắt buộc cho canonical JSON serialization (§6.4.1):

1. `seed_policy` chỉ nhận đúng 2 giá trị `"stochastic"` hoặc
   `"deterministic"`. KHÔNG dùng `"stochastic_resolved"` /
   `"deterministic_ignored"` / giá trị trung gian — đã được thay
   thế để khớp canonical payload. Bất kỳ deviation nào (e.g. user
   muốn audit riêng "stochastic_resolved") phải lưu ở field
   runtime (vd. `seed_resolution_log`) chứ KHÔNG đưa vào canonical
   payload (vì sẽ đổi `clustering_id`).
2. `seed` là **effective seed mà runner resolve được** (int nếu
   `seed_policy="stochastic"`, **luôn `null` nếu
   `seed_policy="deterministic"`** dù user có truyền `--seed` qua
   CLI). `ExperimentResult.random_seed` (request từ CLI / YAML)
   vẫn được ghi ở runtime field `random_seed_requested` (audit-only,
   KHÔNG nằm trong canonical payload); `random_seed_used` (giá trị
   thực sự đi vào adapter) cũng là audit-only — nguồn sự thật về
   "seed đã thực sự được dùng" — nhưng KHÔNG nằm trong canonical
   payload vì nó luôn bằng `seed` cho stochastic algorithms và
   luôn `null` cho deterministic (trùng `seed`).

**`DETERMINISTIC_ALGORITHMS` frozenset** (mirror ML-01 ground truth):

```python
# Định nghĩa tại `prototype/clustering/storage.py`; mirror
# `customer_segmentation.clustering.{agglomerative,dbscan}.supports_random_state()`.
DETERMINISTIC_ALGORITHMS: frozenset[str] = frozenset({"agglomerative", "dbscan"})
```

Hằng số này **phải** được dùng trong `_build_canonical_payload`
(§6.7.1) và `derive_clustering_id` (§6.4.1) — KHÔNG hard-code
comparison trong pipeline driver. Nếu ML-01 sau này đánh dấu thêm
1 algorithm là deterministic, DEV-04 chỉ cần import lại (hoặc
rebuild) frozenset (xem AC-10 #61b — test `test_clustering_id_deterministic_algorithms_set`).

**Tại sao phải chuẩn hoá này**: nếu `seed_policy` giữa
`_build_canonical_payload` (dùng `"stochastic"`/`"deterministic"`)
và `_extract_canonical_payload_from_manifest` (đọc từ manifest)
không khớp, `_canonical_payload_equal` (§6.7.1) sẽ fail mọi lần
và `find_existing_clustering` raise `Dev04CollisionError` sai
— biến idempotency hit hợp lệ thành collision false positive.
Đây là P1 finding round-2 đã được sửa trong plan này.

### 6.5. Validation contract (delegated to ML-01)

DEV-04 does NOT re-implement validation. It calls `ExperimentRunner.run()` which internally calls:

- `validate_clustering_matrix(matrix_df, ...)` — checks:
  - dataset non-empty
  - all numeric
  - no NaN
  - no Inf
  - no constant features
  - min_samples >= 2
  - min_features >= 1
  - **NO identifier leakage** (`CustomerID`, `InvoiceNo`, `InvoiceDate`, `StockCode`, `Description`, `Country` MUST NOT be in matrix; raises `IdentifierLeakageError`)
- `validate_customer_alignment(customer_metadata_df, matrix_df, ...)` — checks:
  - metadata row count == matrix row count
  - `CustomerID` column present
  - `CustomerID` unique
  - `CustomerID` no NaN

If validation fails, the runner returns `ExperimentResult` with `status = FAILED` and an error block. The DEV-04 wrapper translates this to:
- write `experiment_log_<experiment_id>.json` (with `status: FAILED` + error block) — written by ML-01 into `staging_dir`. **KHÔNG** written ở `final_dir` (vì run FAIL).
- write per-run `<clustering_id>.log` (with FAILURE entries) — written by DEV-04 per-stage log emission; written to staging_dir; KHÔNG BAO GIỜ ở final_dir.
- **DO NOT** write `cluster_labels_*.parquet`, `algorithm_output_*.parquet`, or `clustering_manifest.json` (per DEV-03 pattern: no partial artefact on FAIL).

**R1 — FAILED experiment log retention + R2 backup restore (post-cleanup) — explicit 4-step ordering**:

Sau khi run FAIL (Stage 4 / Stage 5 exception), trước khi unlink
`staging_dir`, exception-handler của main pipeline phải chạy đúng
4 bước theo thứ tự dưới đây (load-bearing contract; do not
interleave; do not skip). Tham chiếu: §5.3 sequence diagram
(Stage 4-FAIL branch), §6.7.4 pseudocode (Stage 4/5 except
block), §8.1 (flow step 16), §16.2 (R-15 + R-16 mitigations).

1. **Step 1 (R1): Preserve FAILED log.** `_preserve_failed_log`
   (helper trong §6.7.4) move `experiment_log_*.json` từ staging
   sang `_failed_<clustering_id>_<run_uuid>/`. Nếu staging chứa
   nhiều `experiment_log_*.json` (parametrised runs), tất cả được
   move; `_preservation_audit.txt` sidecar ghi `preserved_logs=<N>`.
   - Nếu `experiment_log_*.json` không tồn tại trong staging
     (vd. crash trước Stage 4): KHÔNG tạo `_failed_*/` dir; không
     có gì để preserve. Cleanup pass sẽ rmdir nếu dir rỗng (do
     mkdir failed hoặc nothing to preserve).
   - Nếu `_preserve_failed_log` itself fail (vd. permission error,
     disk full khi mkdir): log warning, retain
     `experiment_log_*.json` trong staging_dir nếu có thể
     (orphaned ở đó cho manual recovery). KHÔNG BAO GIỜ
     silent-fail. KHÔNG raise (primary exception must continue
     to propagate ở Step 3).

2. **Step 2 (R2 normal backup restore):** Nếu
   `state.backup_dir` được set bởi normal `--force-rerun` path
   (i.e. `state.backup_dir_from_corrupt_manifest == False`),
   attempt to restore recoverable SUCCESS: `os.rename(backup_dir,
   final_dir)` (atomic). Mục đích: trả `final_dir` về trạng thái
   trước run (idempotent về mặt artifact visibility cho
   downstream).
   - **KHÔNG restore** nếu `state.backup_dir_from_corrupt_manifest
     == True` (suffix `_corrupt` retained cho audit; không phải
     valid SUCCESS để restore).
   - Nếu restore fail (OSError, permission, ...): log error,
     leave `backup_dir` ở nguyên vị trí. cleanup_pass sẽ retain
     nó (publish_succeeded=False path) cho `recover_orphan_backups`
     ở next run hoặc manual recovery. KHÔNG BAO GIỜ silent-
     destroy recoverable artifact.

3. **Step 3: Re-raise primary exception.** Mọi secondary failure
   từ Step 1 hoặc Step 2 đã được log ở Step 1 / Step 2. Re-raise
   `stage4_5_exc` (hoặc `stage5b_exc` cho Stage 5b publish
   failure) để CLI exit non-zero với error message gốc. KHÔNG
   replace primary exception bằng secondary failure (sẽ che giấu
   root cause).

4. **Step 4: Outer cleanup pass (R3).** `finally:` của `run_dev04`
   invoke `_cleanup_pass(state)`. cleanup pass KHÔNG BAO GIỜ
   delete:
   - `_failed_*/` (Step 1 output) — R1 invariant
   - `backup_dir` nếu `publish_succeeded=False` (Step 2 fail
     path) — R2 retain invariant
   - `_backup_*_corrupt/` nếu R2 corrupt recovery xảy ra trước
     đó — R2 audit invariant
   - **`staging_dir` nếu `state.unpreserved_log_in_staging == True`**
     — **R1 retention invariant (F1 fix)**: nếu Step 1 (R1)
     preservation thất bại (một phần hoặc toàn bộ) và
     `experiment_log_*.json` vẫn còn trong staging_dir (orphan),
     cleanup pass PHẢI coi staging_dir là "retained for manual
     recovery" và KHÔNG ĐƯỢC `shutil.rmtree(staging_dir)`. Xem
     rule #7 bên dưới cho invariant đầy đủ.

**Quy tắc bắt buộc cho FAILED handling**:

1. **FAILED run KHÔNG publish** `cluster_labels_*.parquet`,
   `clustering_manifest.json`, hoặc `algorithm_output_*.parquet`
   (per AC-5 #24-26 — no partial artefact).
2. **FAILED run PRESERVE** `experiment_log_*.json` ở FAILED tracking
   directory (`_failed_<clustering_id>_<run_uuid>/`). Cleanup pass
   KHÔNG BAO GIỜ unlink `_failed_*/`. Đây là AC-5 #24 contract
   (log written for BOTH SUCCESS and FAILED outcomes).
3. Nếu ML-01 không ghi log nào (vd. crash trước Stage 4), không có
   `_failed_*/` được tạo — không có gì để preserve.
4. Nếu `_preserve_failed_log` itself fails (vd. permission error,
   disk full khi mkdir): log warning, retain `experiment_log_*.json`
   trong staging_dir nếu có thể (orphaned nơi đó cho manual
   recovery). KHÔNG BAO GIỜ silent-fail. KHÔNG raise. Primary
   exception ở Step 3 sẽ propagate. Cleanup pass sẽ log
   preservation failure trong audit trail.
5. `final_dir` KHÔNG BAO GIỜ bị touch cho FAILED run TRỪ KHI
   normal --force-rerun backup restore (Step 2) thành công. Nếu
   `--force-rerun`, backup_dir được restore về final_dir SAU khi
   `_preserve_failed_log` chạy (Step 1 trước, Step 2 sau).
6. CLI exit non-zero cho FAILED run (per AC-3 #15 + AC-5 #26).
   Exit code phân biệt stage (Stage 4 = 4, Stage 5 = 5, validation
   = 6, corrupt recovery fail = 7, manifest corrupt = 8, …) — xem
   `scripts/dev04_run_clustering.py` implementation.

7. **F1 invariant — staging retention khi preservation thất bại
   (cleanup MUST NOT delete staging chứa unpreserved FAILED log)**:
   - **Điều kiện trigger**: Step 1 (R1) `_preserve_failed_log` chạy
     nhưng KHÔNG thể move được TẤT CẢ `experiment_log_*.json` từ
     staging sang `_failed_*/`. Nguyên nhân: (a) `mkdir
     _failed_*/` fail (permission, disk full, EEXIST); (b) một số
     `shutil.move(...)` call fail (giữa chừng; vd. permission
     denied trên target, race với user khác); (c) ML-01 ghi
     `experiment_log_*.json` SAU khi `_preserve_failed_log` đã
     chạy xong (impossible với current ML-01 contract nhưng plan
     bao quát cho future-proofing).
   - **Detection**: `_preserve_failed_log` return một
     `PreservationStatus` (4 giá trị canonical: `"ok"` (move tất
     cả thành công), `"partial"` (một số move thành công, một số
     fail), `"no_log"` (không có log trong staging, không có gì để
     preserve), `"failed"` (mkdir failed trước khi move bất kỳ
     log nào)). Exception handler ở `run_dev04` (§6.7.4
     pseudocode) set `state.unpreserved_log_in_staging = True`
     khi `PreservationStatus ∈ {"partial", "failed"}` VÀ re-scan
     staging_dir xác nhận còn `experiment_log_*.json` thực sự
     (defence-in-depth: tránh false positive do race).
   - **Cleanup pass behavior (R3)**: `_cleanup_pass` PHẢI kiểm tra
     `state.unpreserved_log_in_staging` TRƯỚC KHI unlink
     staging_dir. Nếu `True`, KHÔNG được `shutil.rmtree(staging_dir)`;
     log warning rằng staging_dir được retain cho manual
     recovery; primary exception vẫn propagate bình thường. Staging
     dir sẽ được pick up bởi `recover_orphan_backups` ở next
     invocation (nếu uuid đổi) hoặc bởi manual user intervention.
   - **Idempotency guarantee**: nếu `recover_orphan_backups` ở
     next run thấy `_staging_<run_uuid>/` còn sót (orphan), nó
     KHÔNG restore staging_dir thành final_dir (vì staging không
     phải final); nó log warning và skip. User tự dọn hoặc dùng
     `scripts/dev04_cleanup_orphans.py` (out of DEV-04 scope) để
     dọn staging_dir cũ sau khi đã recover log manually.
   - **Tránh silent destruction**: invariant này ngăn chặn tình
     huống `_preserve_failed_log` fail → log orphaned trong
     staging → `_cleanup_pass` unlink staging → log bị xóa vĩnh
     viễn → AC-5 #24 audit trail bị mất. Đây là F1 finding —
     bổ sung chính xác khoảng trống giữa "preserve fail leaves
     log in staging" (đã có trong plan trước) và "cleanup unlinks
     staging unconditionally" (chưa được gate).
   - **Cross-section consistency**: invariant này phải explicit
     trong §5.3 sequence diagram (Stage 4-FAIL branch), §6.5
     R1+R2 contract (rule #7 + Step 4 bullet mới), §6.7.3
     retry semantics (failure window F14 mới), §6.7.4
     pseudocode (`_CleanupState` mới field
     `unpreserved_log_in_staging` + `_cleanup_pass` check +
     `_preserve_failed_log` return value), §8.1 execution flow
     (step 16 Step 1 + Step 4 bullets), §8.4 reprocessing safety
     (new bullet F1 invariant), §10 acceptance criteria (new
     AC-5 #24e + new AC-12 #73h), §11.1a (new R1 tests
     `test_staging_retained_when_preservation_partial` +
     `test_staging_retained_when_preservation_failed` + new R3
     test `test_cleanup_pass_skips_staging_when_unpreserved_log`),
     §16.1 (acknowledgement), §16.2 (R-15 mitigation update +
     new R-15a entry for F1 invariant).

### 6.6. Research safety contract

**Hard rule** (per AGENTS.md §2.3, §2.12, §3 "Clustering"):

- DEV-04 NEVER mutates:
  - `data/raw/primary/**`
  - `data/raw/backup/**`
  - `data/processed/**` (FE-06 outputs)
  - `reports/**` (research reports)
  - `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's)
  - `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json` (DEV-03's)
  - `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_*.parquet` (DEV-03's)

- DEV-04 WRITES only to:
  - `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/` (NEW directory; git-ignored via `data/prototype/**` rule in `.gitignore`)

- Research-safety test: pre/post snapshot SHA-256 + mtime of `data/raw/primary`, `data/raw/backup`, `data/processed`, `reports/`, DEV-02's manifest, DEV-03's manifest + ml_dataset → all unchanged.

### 6.7. Idempotency, collision, retry và staging/publish semantics

Phần này mô tả rõ 4 hành vi cần thiết để DEV-04 đảm bảo: (a) chạy
lại không bị hiểu nhầm artifact cũ là mới, (b) không ghi đè âm thầm
kết quả của config khác, (c) chạy lại sau lỗi trung gian vẫn cho ra
trạng thái nhất quán, (d) `--force-rerun` không làm hỏng kết quả
SUCCESS cũ.

#### 6.7.1. Idempotency

**Per-clustering_id subdirectory** (xem §5.2, §6.3): mỗi
`clustering_id` có 1 subdirectory riêng tại
`<base>/clustering/<clustering_id>/`. Điều này **tự nhiên giải quyết**
vấn đề "nhiều config cùng tồn tại" mà không cần filename trick, đồng
thời **loại bỏ hoàn toàn khả năng ghi đè manifest** giữa hai config
khác nhau:

- Hai config khác nhau (`--n-clusters=3` vs `--n-clusters=5`) → 2
  `clustering_id` khác nhau (xem §6.4.1 canonical derivation) → 2
  subdirectory song song, mỗi subdirectory chứa 1 manifest riêng.
- Khi tìm manifest, `find_existing_clustering` được truyền
  `clustering_id` làm key — chỉ truy vấn đúng 1 path
  `<base>/clustering/<clustering_id>/clustering_manifest.json`. KHÔNG
  quét sibling, KHÔNG quét đệ quy, KHÔNG fallback sang path cố định.
- Vì vậy KHÔNG tồn tại đường dẫn manifest "cố định" nào ở level
  clustering/; mỗi `clustering_id` ánh xạ 1-1 sang 1 manifest path.
  Manifest của clustering_id A không bao giờ bị ghi đè bởi run của
  clustering_id B.
- Cùng config (cùng `clustering_id`) → idempotent skip nếu manifest
  đã tồn tại; hoặc staging+publish nếu `--force-rerun`.
- Custom `--experiment-id` chỉ cần unique **trong subdirectory của 1
  `clustering_id`**. Hai `clustering_id` khác nhau có thể dùng cùng
  `experiment_id` mà không xung đột (vì file ở 2 thư mục khác nhau).
  **Tuy nhiên**, nếu hai lần chạy CÙNG `clustering_id` nhưng KHÁC
  `--experiment-id` → subdirectory giống nhau → file trong đó có thể
  bị overwrite (vì tên file chứa `experiment_id`). DEV-04 chủ động
  **refuse** trường hợp này bằng cách: nếu manifest đã tồn tại với
  `experiment_id` khác, CLI exit non-zero với error
  `experiment_id conflict: existing=<X>, requested=<Y>` trừ khi user
  truyền `--force-rerun` (xem §6.7.4 cho staging/publish an toàn).
  Verified bằng
  `test_dev04_pipeline.py::test_experiment_id_conflict_detected`.

**Lookup function** (analogous to DEV-02's `find_existing_dataset`,
nhưng scope theo subdirectory, **và verify canonical payload khớp
với effective config hiện tại** để phát hiện collision):

```python
def find_existing_clustering(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    *,
    # Effective config hiện tại (từ CLI + YAML merge sau resolve).
    algorithm: str,
    hyperparameters: dict[str, Any],
    effective_seed: int | None,
    ml_dataset_sha256: str,
    config_sha256: str,
) -> Path | None:
    """Return clustering_manifest.json path nếu đã tồn tại VÀ canonical
    payload của nó khớp với effective config hiện tại, else None.

    Ba trạng thái quan trọng phân biệt rõ (xem §6.7 + AC-12 #66a):
    - **(a) Idempotent hit** — manifest tồn tại, canonical payload hợp
      lệ VÀ khớp effective config hiện tại → return Path. Caller
      (CLI / pipeline) sẽ early-return / skip re-fit.
    - **(b) Collision / tamper** — `clustering_id` trùng nhưng
      canonical payload HỢP LỆ ở cả 2 phía nhưng KHÁC NHAU (collision
      96-bit cực hiếm, hoặc manifest bị tamper ngoài DEV-04) → raise
      ``Dev04CollisionError``. Caller KHÔNG được coi là idempotent
      hit, KHÔNG được chạy lại, KHÔNG được overwrite.
    - **(c) Manifest corrupt** — manifest tồn tại nhưng KHÔNG dùng
      được (JSON corrupt, thiếu 1 trong 7 canonical key, sai kiểu,
      ``seed_policy`` không ∈ canonical whitelist, ...) → raise
      ``Dev04ManifestCorrupt``. Caller phải fail-closed (CLI exit
      non-zero với error rõ ràng); CHỈ được phép tiếp tục với
      ``--force-rerun`` (sẽ move final → backup rồi publish lại).

    Scope hẹp: chỉ kiểm tra
    ``<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/clustering_manifest.json``.
    KHÔNG quét đệ quy (defence-in-depth; tránh traversal qua symlink
    hoặc path khác).

    Raises
    ------
    Dev04CollisionError
        Trạng thái (b) — manifest hợp lệ nhưng payload khác.
    Dev04ManifestCorrupt
        Trạng thái (c) — manifest không dùng được.
    """
    # 1. Validate clustering_id format trước (chống path traversal).
    if not _CLUSTERING_ID_RE.match(clustering_id):
        return None

    run_dir = prototype_clustering_run_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id
    )
    manifest_path = run_dir / "clustering_manifest.json"
    if not manifest_path.exists():
        return None

    # 2. Load manifest JSON. OSError (file unreadable) hoặc
    #    JSONDecodeError (corrupt JSON) → corrupt manifest → raise
    #    Dev04ManifestCorrupt (fail-closed). KHÔNG return None (vì
    #    plan yêu cầu manifest corrupt không được xem như valid
    #    idempotent hit — §6.7.1 phân biệt rõ với (c) missing
    #    manifest bên dưới ở line `if not manifest_path.exists()`).
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None  # race: file vanished between exists() and open()
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev04ManifestCorrupt(
            f"manifest at {manifest_path!s} is unreadable or corrupt JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise Dev04ManifestCorrupt(
            f"manifest at {manifest_path!s} must be a JSON object; "
            f"got {type(data).__name__}."
        )

    # 3. Manifest tự tham chiếu đúng clustering_id?
    #    Mismatch = tamper (file bị rename / edit ngoài DEV-04).
    #    → Dev04ManifestCorrupt (fail-closed).
    if data.get("clustering_id") != clustering_id:
        raise Dev04ManifestCorrupt(
            f"manifest clustering_id field {data.get('clustering_id')!r} "
            f"!= directory name {clustering_id!r}; manifest is "
            f"inconsistent with its path (possible tamper or rename). "
            f"Refusing to interpret."
        )

    # 4. CANONICAL PAYLOAD COMPARISON — phát hiện collision.
    #    Bước này cần canonical payload hợp lệ ở CẢ HAI phía:
    #    - expected: từ effective config hiện tại (CLI merge).
    #    - stored: trích từ manifest, validate đầy đủ ở
    #      _extract_canonical_payload_from_manifest (raises
    #      Dev04ManifestCorrupt nếu thiếu key, sai kiểu, ...).
    expected_payload = _build_canonical_payload(
        preprocessed_id=preprocessed_id,
        algorithm=algorithm,
        hyperparameters=hyperparameters,
        effective_seed=effective_seed,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
    )
    try:
        stored_payload = _extract_canonical_payload_from_manifest(data)
    except Dev04ManifestCorrupt:
        # Re-raise với context path (không bịt traceback gốc).
        raise

    if not _canonical_payload_equal(expected_payload, stored_payload):
        # Collision hoặc tamper: clustering_id trùng nhưng canonical
        # payload hợp lệ ở cả 2 phía nhưng khác → KHÔNG idempotent
        # skip, KHÔNG overwrite, KHÔNG chạy lại.
        raise Dev04CollisionError(
            f"clustering_id collision or manifest tamper detected: "
            f"clustering_id={clustering_id}, "
            f"expected_payload={expected_payload}, "
            f"stored_payload={stored_payload}. "
            f"Refusing to proceed; investigate manually. "
            f"If this is a benign collision (probability ~6.3e-18 at "
            f"1e6 IDs; see §6.7.2), bump CLUSTERING_ID_HEX_LEN. "
            f"If manifest was tampered, restore from backup."
        )

    return manifest_path
```

**Hai helper quan trọng**:

```python
def _build_canonical_payload(
    *, preprocessed_id, algorithm, hyperparameters,
    effective_seed, ml_dataset_sha256, config_sha256,
) -> dict[str, Any]:
    """Trả về canonical payload object 7 trường logic (xem §6.4.1).

    Contract byte-level cứng:
    - ``seed_policy`` ∈ {"stochastic", "deterministic"} (canonical;
      mirror §6.4.2; KHÔNG dùng "stochastic_resolved" /
      "deterministic_ignored" — đã deprecated).
    - Hyperparameters chuẩn hoá deterministic: mỗi value được ép qua
      ``json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))``
      trước khi đưa vào payload; outer keys được sort bằng
      ``sorted(...)`` (lexicographic, key=str); nested dicts được sort
      recursive bởi lần ``json.dumps(..., sort_keys=True)`` ở bước 4
      (§6.4.1). NaN/Infinity raise ValueError tại bước scalar
      normalization (xem AC-10 #61a — `test_clustering_id_canonical_json_*`).
    - KHÔNG có field ngoài 7 trường canonical.
    """
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev04ConfigError("preprocessed_id must be non-empty str.")
    if algorithm not in DETERMINISTIC_ALGORITHMS and algorithm not in STOCHASTIC_ALGORITHMS:
        raise Dev04ConfigError(
            f"algorithm {algorithm!r} is not in registry whitelist; "
            "refuse to derive clustering_id for an unknown algorithm."
        )
    if not isinstance(ml_dataset_sha256, str) or not ml_dataset_sha256:
        raise Dev04ConfigError("ml_dataset_sha256 must be non-empty str.")
    if not isinstance(config_sha256, str) or not config_sha256:
        raise Dev04ConfigError("config_sha256 must be non-empty str.")
    if effective_seed is not None and not isinstance(effective_seed, int):
        raise Dev04ConfigError(
            f"effective_seed must be int or None; got {type(effective_seed).__name__}."
        )

    hp_canonical = {
        k: json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))
        for k, v in sorted(hyperparameters.items(), key=lambda kv: kv[0])
    }
    seed_policy = (
        "deterministic" if algorithm in DETERMINISTIC_ALGORITHMS
        else "stochastic"
    )
    return {
        "preprocessed_id":   preprocessed_id,
        "algorithm":         algorithm,
        "hyperparameters":    hp_canonical,
        "seed_policy":       seed_policy,
        "seed":              effective_seed,
        "config_sha256":     config_sha256,
        "ml_dataset_sha256": ml_dataset_sha256,
    }


# STOCHASTIC_ALGORITHMS = frozenset({"kmeans", "gmm", "fuzzy_cmeans"})
# — defined in prototype/clustering/storage.py; mirror the
# `customer_segmentation.clustering.{kmeans,gmm,fuzzy_cmeans}.supports_random_state() == True` ground truth.
# Used only to validate algorithm whitelist in _build_canonical_payload.


# Schema version (round, single source of truth) — must mirror §6.4 schema table.
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "preprocessed_id",
    "algorithm",
    "hyperparameters",
    "seed_policy",
    "seed",
    "config_sha256",
    "ml_dataset_sha256",
)
# Required types for round-trip validation.
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "preprocessed_id":   str,
    "algorithm":         str,
    "hyperparameters":   dict,
    "seed_policy":       str,             # must be "stochastic" or "deterministic"
    "seed":              (int, type(None)),
    "config_sha256":     str,
    "ml_dataset_sha256": str,
}


class Dev04ManifestCorrupt(ValueError):
    """Raised khi manifest tồn tại nhưng KHÔNG đọc được canonical payload
    một cách đáng tin cậy.

    Phân biệt với Dev04CollisionError: ``Dev04ManifestCorrupt`` = manifest
    không dùng được (thiếu field, sai kiểu, JSON corrupt); caller KHÔNG
    được coi như idempotent hit và KHÔNG được coi như collision. Caller
    nên abort run với error rõ ràng hoặc --force-rerun để ghi đè.
    """


def _extract_canonical_payload_from_manifest(
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Trích 7 trường canonical từ stored manifest.

    **Subset identity-preserving selection** — KHÔNG có phép chuyển đổi
    hai chiều, KHÔNG rename key. Manifest được viết với đúng 7 key
    canonical (xem §6.4 schema table + `_build_canonical_payload` ở
    trên); hàm này chỉ là dict subset selection trên cùng 7 key.

    Raises
    ------
    Dev04ManifestCorrupt
        Nếu manifest thiếu 1 trong 7 key canonical, hoặc giá trị của
        1 key không khớp type kỳ vọng, hoặc ``seed_policy`` không ∈
        {"stochastic", "deterministic"}, hoặc ``seed`` không phải int
        hoặc None, hoặc ``hyperparameters`` không phải dict. Caller
        KHÔNG được coi là idempotent hit; KHÔNG raise Dev04CollisionError
        (collision chỉ xảy ra khi canonical payload HỢP LỆ ở cả 2 phía
        nhưng KHÁC NHAU — xem ``_canonical_payload_equal``).
    """
    if not isinstance(manifest_data, dict):
        raise Dev04ManifestCorrupt(
            f"manifest must be a JSON object; got {type(manifest_data).__name__}."
        )
    for key in CANONICAL_PAYLOAD_KEYS:
        if key not in manifest_data:
            raise Dev04ManifestCorrupt(
                f"manifest is missing required canonical key {key!r}; "
                f"available keys: {sorted(manifest_data.keys())}."
            )
    # Type check (defence-in-depth: caller có thể đã sửa manifest).
    for key, expected in _CANONICAL_PAYLOAD_TYPES.items():
        value = manifest_data[key]
        if not isinstance(value, expected):
            raise Dev04ManifestCorrupt(
                f"manifest field {key!r} has wrong type "
                f"{type(value).__name__}; expected {expected}."
            )
    # seed_policy whitelist (canonical 2-value enum).
    sp = manifest_data["seed_policy"]
    if sp not in ("stochastic", "deterministic"):
        raise Dev04ManifestCorrupt(
            f"manifest seed_policy={sp!r} is not in canonical whitelist "
            f"('stochastic', 'deterministic'); refuse to round-trip."
        )
    # Determinism invariant: deterministic algorithm MUST have seed=null.
    if sp == "deterministic" and manifest_data["seed"] is not None:
        raise Dev04ManifestCorrupt(
            f"manifest has seed_policy='deterministic' but seed="
            f"{manifest_data['seed']!r} (must be null); "
            "manifest is internally inconsistent."
        )
    return {
        "preprocessed_id":   manifest_data["preprocessed_id"],
        "algorithm":         manifest_data["algorithm"],
        "hyperparameters":    manifest_data["hyperparameters"],
        "seed_policy":       sp,
        "seed":              manifest_data["seed"],
        "config_sha256":     manifest_data["config_sha256"],
        "ml_dataset_sha256": manifest_data["ml_dataset_sha256"],
    }


def _canonical_payload_equal(
    expected: dict[str, Any], stored: dict[str, Any],
) -> bool:
    """So sánh 2 canonical payload bằng cách serialize cả hai qua JSON
    canonical rồi so sánh bytes. Tránh so sánh dict trực tiếp (dễ
    miss nested difference).

    Raises
    ------
    ValueError
        Nếu canonical payload chứa NaN / Infinity (Python ``json.dumps``
        mặc định chấp nhận, nhưng canonical serialization với
        ``allow_nan=False`` raise). Đây là lỗi input, không phải
        collision. Caller phải xử lý như ``Dev04ManifestCorrupt`` hoặc
        ``Dev04ConfigError`` tuỳ payload nào lỗi.
    """
    expected_bytes = json.dumps(
        expected, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    stored_bytes = json.dumps(
        stored, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return expected_bytes == stored_bytes
```

**Tại sao cần bước 4 (canonical payload comparison)**:

- 96-bit hash collision có xác suất cực nhỏ (~ 10⁻¹⁸ ở 10⁶ lượt — xem
  §6.7.2), nhưng KHÔNG phải zero. Nếu xảy ra, `clustering_id` của hai
  effective config khác nhau sẽ trùng → nếu chỉ so sánh `clustering_id`,
  manifest của run A có thể bị CLI coi như "đã có" cho run B và
  early-return mà không nhận ra khác biệt.
- Manifest cũng có thể bị tamper (file edit ngoài DEV-04) → nội dung
  không khớp config ban đầu. Phát hiện qua payload comparison.
- Phát hiện này là **defense-in-depth**, không thay thế birthday
  bound; nó đảm bảo ngay cả khi collision xảy ra, hệ thống KHÔNG
  silently return sai manifest.

**Quy tắc idempotency** (cập nhật cho phù hợp với collision +
manifest-corruption detection):

1. Cùng `(preprocessed_id, algorithm, hyperparameters, seed,
   seed_policy, ml_dataset_sha256, config_sha256)`
   → cùng `clustering_id` → nếu
   `<base>/clustering/<clustering_id>/clustering_manifest.json` đã
   tồn tại VÀ canonical payload khớp → **DEV-04 mặc định KHÔNG chạy
   lại** (early return từ CLI với exit code 0 và đường dẫn manifest).
   Người dùng phải truyền `--force-rerun` để bypass (xem §6.7.4 cho
   staging policy an toàn).
2. Cùng `preprocessed_id`, config khác (e.g. user đổi `--n-clusters`):
   → `clustering_id` khác → subdirectory khác → KHÔNG đụng đến kết
   quả cũ. Hai bộ artifact cùng tồn tại song song dưới 2
   subdirectory.
3. **`clustering_id` trùng nhưng canonical payload khác**
   (collision cực hiếm hoặc tamper) → `find_existing_clustering`
   raise `Dev04CollisionError` → CLI exit non-zero với error message
   rõ ràng. KHÔNG coi là idempotent skip, KHÔNG chạy lại, KHÔNG
   overwrite. **`Dev04CollisionError` KHÔNG BAO GIỜ được catch bởi
   recovery path** (R2 #6) — collision là honest trial vs legitimate
   classification; user phải investigate manually. Khác với
   `Dev04ManifestCorrupt` (R2) là "manifest không đọc được" → có
   safe recovery path với `--force-rerun`.
4. **Manifest tồn tại nhưng KHÔNG dùng được** (JSON corrupt, thiếu
   canonical key, sai type, `seed_policy` legacy, ...) →
   `find_existing_clustering` raise `Dev04ManifestCorrupt`.
   - **Default behavior (fail-closed, KHÔNG `--force-rerun`)**:
     CLI exit non-zero. KHÔNG auto-recover từ backup; KHÔNG coi là
     idempotent skip; KHÔNG treat như valid hit. Plan R2 explicitly
     forbids silent reinterpretation.
   - **Với `--force-rerun`** (R2 safe recovery): corrupt final
     được move sang `_backup_<run_uuid>_corrupt/` (atomic rename);
     fresh run proceeds với staging mới + publish atomic + cleanup
     retain corrupt backup cho audit. Nếu rename corrupt final →
     backup FAIL: stop với `Dev04StoragePathError` (R2 #5). Plan
     KHÔNG BAO GIỜ cho phép path này bypass collision detection cho
     valid manifest khác canonical payload (R2 #6), KHÔNG cho phép
     overwrite valid existing SUCCESS trước khi staging artifacts
     hoàn chỉnh (R2 #7). Corrupt manifest backup retained cho
     audit; startup recovery pass KHÔNG restore từ `_backup_*_corrupt/`
     (suffix marker = skip).
   - User KHÔNG truyền `--force-rerun`: phải xử lý thủ công
     (inspect corrupt manifest, xóa thủ công final_dir + manifest,
     hoặc dùng `--force-rerun`).

**Tại sao early-return mặc định**: tránh re-fit một cách tốn kém và
tránh nhầm lẫn kết quả. Phù hợp với AGENTS.md §2.7
(reproducibility — đã có kết quả reproducible thì không cần chạy lại).

**Tại sao corrupt manifest là fail-closed theo mặc định**: nếu
manifest corrupt, KHÔNG có cách nào phân biệt "manifest bị tamper"
vs "process crash mid-write" — cả hai đều leave uninterpretable
state. Auto-treating như "không có manifest, fresh run" sẽ silently
overwrite previous state mà không có cách audit. Phải có explicit
user confirmation (`--force-rerun`). Phù hợp với AGENTS.md §2.7 +
§2.1 (no silent overwrite, no invented data integrity).

**Test yêu cầu** (mở rộng cho round-2 P1 fix + R1/R2/R3):

- `test_dev04_storage.py::test_find_existing_clustering_*` (match
  valid + canonical payload khớp → return path; path missing →
  None; corrupt JSON → Dev04ManifestCorrupt; manifest clustering_id
  mismatch → Dev04ManifestCorrupt; 7-key missing/wrong-type →
  Dev04ManifestCorrupt).
- `test_dev04_storage.py::test_find_existing_clustering_collision_detected` —
  **CRITICAL cho collision detection**: pre-create manifest với
  `clustering_id=X` nhưng canonical payload lưu trữ KHÁC với effective
  config hiện tại (giả lập collision hoặc tamper); gọi
  `find_existing_clustering(...)` với effective config mới; verify
  nó raise `Dev04CollisionError` chứ KHÔNG return path (KHÔNG được
  coi là idempotent skip); verify error message chứa
  `expected_payload` + `stored_payload` cho diagnosis.
- `test_dev04_storage.py::test_find_existing_clustering_manifest_corrupt_*`
  (5 cases: corrupt JSON; missing `seed_policy`; wrong type `seed`;
  `seed_policy="foo"`; deterministic + seed=42) — verify mỗi case
  raise `Dev04ManifestCorrupt` với thông điệp rõ ràng, KHÔNG trả
  Path, KHÔNG raise `Dev04CollisionError`.
- `test_dev04_storage.py::test_extract_canonical_payload_subset_identity`
  — verify manifest có đủ 7 key canonical + nhiều field runtime;
  `_extract_canonical_payload_from_manifest` trả về đúng 7 key với
  values giống manifest (subset selection, KHÔNG rename).
- `test_dev04_storage.py::test_clustering_id_pseudocode_runs_without_typeerror`
  — **CRITICAL cho P1 fix**: thực thi pseudocode của
  `_build_canonical_payload` và `derive_clustering_id` (xem §6.4.1)
  trực tiếp trong test với inputs thực (hyperparameters có nested
  dict, NaN/Infinity, UTF-8 strings); assert KHÔNG có `TypeError`
  nào (đặc biệt là do tham số không hợp lệ như `allow_ncii`); assert
  output bytes ổn định across Python sessions.
- `test_dev04_storage.py::test_clustering_id_format_*` (3 cases:
  valid `cl_<24hex>`, invalid prefix `xx_<...>`, length sai — return
  None / raise tương ứng).
- `test_dev04_storage.py::test_seed_policy_canonical_whitelist`
  (parametrised over 5 algorithms; verify `seed_policy` ∈
  {"stochastic", "deterministic"}; mapping kmeans/gmm/fuzzy_cmeans
  → "stochastic", agglomerative/dbscan → "deterministic").
- `test_dev04_manifest.py::test_idempotent_skip_default` (gọi CLI 2
  lần với cùng effective config; lần 2 không fit lại, trả về
  manifest có sẵn + exit code 0).
- `test_dev04_pipeline.py::test_force_rerun_safety` (xem §6.7.4
  test requirements; dùng staging để chứng minh kết quả cũ còn
  nguyên khi crash trước publish).
- `test_dev04_pipeline.py::test_different_config_coexists` (chạy 2
  config khác nhau trong cùng preprocessed_id → 2 subdirectory, 2
  manifest, 2 bộ artifact; KHÔNG đụng đến nhau).

#### 6.7.2. Collision

**Không gian hash**: `clustering_id` = `cl_` + 24 ký tự hex đầu của
SHA-256, tức **96 bit entropy**, `N = 2^96 ≈ 7.92 × 10²⁸` giá trị
có thể.

**Công thức birthday bound** (xấp xỉ chuẩn cho `k << √N`):

```
P(at least one collision trong k clusterings)
  ≈ k² / (2N)
  = k² / 2^97
```

Trong đó `k` = tổng số `clustering_id` đã được derive.

**Bảng xác suất va chạm** (kết quả tính từ công thức trên, không
phải giá trị gần đúng heuristic):

| Số clusterings (k) | P(at least one collision) |
|---|---|
| 1 000            | 6.31 × 10⁻²⁴ |
| 10 000           | 6.31 × 10⁻²² |
| 1 000 000        | 6.31 × 10⁻¹⁸ |
| 1 000 000 000    | 6.31 × 10⁻¹² |

**Đọc bảng**: xác suất va chạm vẫn là **con số hữu hạn** ở mọi quy
mô, KHÔNG BAO GIỜ bằng 0. Trong phạm vi prototype (vài trăm đến vài
nghìn lượt chạy per dataset), xác suất va chạm ~ 10⁻²⁴ đến 10⁻²² —
cực kỳ nhỏ nhưng **không phải zero**. Plan này ghi nhận đây là rủi ro
dư rất nhỏ, không phải cam kết "không thể xảy ra". Nếu collision xảy
ra (xác suất cỡ 10⁻²⁰ ở vài nghìn lượt), `find_existing_clustering`
(xem §6.7.1) sẽ trả về Path của manifest cũ với `clustering_id` trùng
→ caller sẽ thấy early-return trên nội dung khác (silent overwrite
nếu caller không kiểm tra lại nội dung manifest).

**Phòng hờ** (không phải handler bắt buộc, chỉ là defense-in-depth):

- Smoke test `test_dev04_storage.py::test_clustering_id_uniqueness`
  chạy 1000 `derive_clustering_id` với inputs ngẫu nhiên và assert
  không có collision trong batch (verification phương pháp).
- Documented behavior: nếu collision xảy ra ở production scale, fix
  bằng cách tăng `CLUSTERING_ID_HEX_LEN` lên 32 (128 bits, xác suất
  ~ 10⁻²⁰ cho 10⁹ lượt) — cần ADR mới, hiện tại 24 hex đã đủ cho
  DEV-04 scope.

**Tại sao 24 hex là đủ cho DEV-04**: ước lượng số `clustering_id`
trong toàn bộ prototype (1 năm vận hành, 5 user, mỗi user vài
nghìn runs) ~ 10⁵–10⁶. Theo bảng trên, **P(at least one collision) =
6.31×10⁻¹⁸ ở 10⁶ lượt** (chính xác theo công thức `k²/2N`, không
phải range xấp xỉ) — vẫn đủ nhỏ để bỏ qua trong thực tế (xác suất
còn nhỏ hơn nhiều so với xác suất hardware failure). Tăng lên 32 hex
chỉ cần khi vượt quá 10⁹ lượt tích lũy (toàn bộ prototype + research
qua nhiều năm).

**Quan trọng — KHÔNG dựa vào xác suất cực nhỏ để bỏ qua detection
hoàn toàn**: xem §6.7.1 — `find_existing_clustering` PHẢI so sánh
canonical payload của manifest đã tồn tại với effective config hiện
tại; nếu khác (kể cả khi `clustering_id` trùng do collision cực hiếm),
CLI phải raise collision error chứ KHÔNG được coi là idempotent skip.
Detection này là defense-in-depth, bổ sung cho xác suất cực nhỏ của
collision.

#### 6.7.3. Retry semantics (với staging/publish — xem §6.7.4)

Mọi write diễn ra trong **staging subdirectory** của current run, KHÔNG
phải final directory. Retry sau partial failure hoàn toàn an toàn vì
final directory của các run khác không bị touch.

**Quy tắc retry** (sau partial failure — tất cả tác động trong staging
của current run):

| Tình huống | Hành vi |
|---|---|
| Lần 1 FAIL tại validation (matrix NaN) → runner ghi `experiment_log_*.json` trong **staging** với `status: FAILED`; zero file khác trong staging. Retry Lần 2 với input đã sửa → vì `ml_dataset_sha256` đổi → `clustering_id` đổi → subdirectory mới → fresh run. | OK, an toàn |
| Lần 1 FAIL tại algorithm fit (exception) → `experiment_log_*.json` trong staging ghi `status: FAILED`; cluster_labels KHÔNG được ghi (`save_labels=False` cho FAILED); final subdirectory KHÔNG bị touch. Retry Lần 2 với cùng config → cùng `clustering_id` → staging mới (run_uuid mới); final cũ còn nguyên (nếu SUCCESS lần 1) hoặc trống (nếu lần 1 là run đầu). | OK, an toàn |
| Lần 1: cluster_labels_*.parquet đã được ghi vào staging; trước khi Stage 5 (manifest write) → process crash. Staging chứa cluster_labels nhưng KHÔNG có manifest (vì manifest atomic write chưa commit); final subdirectory KHÔNG bị touch. Retry → idempotency lookup thấy final KHÔNG có manifest → fresh run với staging mới. Staging cũ (orphaned) sẽ được cleanup pass unlink (xem §6.7.4). | OK, an toàn — final subdirectory không bị touch lần nào |
| Lần 1 SUCCESS → tất cả artifact ở final subdirectory. Retry Lần 2 với cùng input + cùng config → idempotency lookup THẤY manifest → CLI exit 0 không chạy lại. | OK, mong đợi |
| Lần 1 SUCCESS với config A. Lần 2 SUCCESS với config B (khác `--n-clusters`) → `clustering_id` khác → 2 subdirectory song song; 2 bộ artifact cùng tồn tại. **KHÔNG** overwrite. | OK, theo contract §6.7.1 |
| Lần 1 SUCCESS với config A. Lần 2 FAIL với config B → staging mới cho config B; cluster_labels B KHÔNG được ghi; subdirectory A không bị touch. | OK, an toàn |
| Process crash trong `to_parquet()` của cluster_labels (trong staging) → partial file trong staging. Final subdirectory KHÔNG bị touch. Cleanup pass unlink staging. Retry → fresh run. | OK, an toàn — final không bị touch lần nào |

**Chính sách orphan** (xem §6.7.4 để biết cơ chế chính xác):

**DEV-04 KHÔNG cam kết "không có orphan tuyệt đối"**. Có 3 orphan
risk được chấp nhận explicit (theo đúng nguyên tắc AGENTS.md §2.7
"reproducibility" + §6 "escalation" — không tự ý tạo cơ chế mới
ngoài scope):

(a) Staging subdirectory (`_staging_<run_uuid>/`) có partial files khi
process crash trước publish.

(b) Backup subdirectory (`_backup_<run_uuid>/`) tồn tại tạm thời khi
`--force-rerun` với old result và crash trước khi restore hoặc unlink
xong.

(c) Final subdirectory `<clustering_id>/` bị "trống" (no manifest) khi
process crash **đúng khoảnh khắc** giữa `os.rename(staging, final)`
và việc atomic flush của final dir hoàn tất — trên cùng filesystem
POSIX điều này không thể xảy ra (single syscall), nhưng nếu có
(NFS, crash VM giữa syscall), final có thể tồn tại dạng "no manifest"
(tức tên dir mới đã có nhưng contents không coherent).

**Quy tắc cleanup pass** (xem §6.7.4 pseudocode để biết cơ chế chính
xác):

- Cleanup pass cuối run (chạy trong `finally:` của `run_dev04`) chỉ
  unlink **staging/backup dirs của current run** (xác định bằng
  `_RUN_UUID` set 1 lần khi process start). KHÔNG BAO GIỜ xóa file
  của run khác (kể cả finalized subdirectory khác `clustering_id`).
- Cleanup pass **chỉ chạm vào dirs match `^_(staging|backup)_<uuid>$/` của current process**. Mọi file khác (kể cả file của process khác
  đang viết, finalized subdirectories của run khác, ML-01 output dirs)
  KHÔNG bị touch.
- Cleanup pass (R3): chạy trong `finally:` của `run_dev04` — không
  chỉ success path. Backup_dir chỉ được unlink NẾU
  `publish_succeeded=True` AND `backup_dir_from_corrupt_manifest=False`.
  Corrupt backup và failed_tracking_dir LUÔN retain cho audit (R1/R2).
- KHÔNG cam kết cleanup chạy sau abrupt crash (segfault, OOM, power
  loss); chỉ crash recovery trên next invocation
  (`recover_orphan_backups`). Plan distinguish Python exception
  cleanup from crash recovery explicitly.

**Quy tắc FAILED retention** (R1):

- Một run FAIL (validation NaN, algorithm exception, manifest write
  fail, exception in runner.run) KHÔNG publish cluster_labels /
  clustering_manifest. Đây là đúng contract AC-5 #24-26 (FAILED log
  bắt buộc, không partial cluster_labels / manifest).
- Trước khi unlink staging_dir, `_preserve_failed_log` (helper
  function trong §6.7.4) move `experiment_log_*.json` từ staging
  sang `_failed_<clustering_id>_<run_uuid>/`. Nếu ML-01 không ghi
  log nào (vd. crash trước Stage 4), `_preserve_failed_log` không
  tạo failed_tracking_dir — không có gì để preserve.
- `_failed_*/` LUÔN retain trên disk cho audit (R1 invariant).
  Cleanup pass KHÔNG BAO GIỜ unlink failed_tracking_dir (kể cả khi
  `publish_succeeded=True` không áp dụng — failed_tracking_dir là
  side artifact).
- **F1 invariant (cleanup pass MUST NOT unlink staging chứa
  unpreserved FAILED log)**: nếu `_preserve_failed_log` trả về
  `PreservationStatus ∈ {"partial", "failed"}` (move không thành
  công hết) VÀ re-scan staging_dir xác nhận còn
  `experiment_log_*.json`, exception handler set
  `state.unpreserved_log_in_staging = True`. Cleanup pass
  (`_cleanup_pass` trong §6.7.4) PHẢI skip `shutil.rmtree(staging_dir)`
  trong trường hợp này; staging_dir được retain cho manual
  recovery. Xem §6.5 rule #7 cho invariant đầy đủ và §6.7.4
  failure window F14 cho failure mode.
- User có thể dọn thủ công sau khi review audit log.

**Quy tắc recovery** (khi gặp orphan ở lần chạy sau):

| Orphan loại | Recovery |
|---|---|
| (a) Staging cũ còn sót từ crash trước | Cleanup pass lần chạy mới KHÔNG động vào (vì `_RUN_UUID` khác). Nếu user muốn dọn, dùng script riêng `scripts/dev04_cleanup_orphans.py` (out of DEV-04 scope; chỉ unlink dirs có TTL > 7 ngày). Trong DEV-04 scope: staging dirs KHÔNG BAO GIỜ bị cleanup cross-process. |
| (b) Backup cũ còn sót từ `--force-rerun` crash trước | Tương tự (a); KHÔNG tự ý dọn. Backup được coi là "safety net" — nếu không có run tiếp theo, nó vẫn còn đó cho đến khi user dọn thủ công. |
| (b') Corrupt backup cũ `_backup_<uuid>_corrupt/` còn sót | `recover_orphan_backups` SKIP directories với suffix `_corrupt` (R2 marker) — KHÔNG restore từ corrupt backup. Corrupt backup retained cho diagnosis; user tự dọn. |
| (c) Final `<clustering_id>/` no-manifest | Lần chạy tiếp theo với cùng `clustering_id`: idempotency lookup thấy final KHÔNG có manifest → fresh run với staging mới. Final cũ (no-manifest) được move sang backup_dir (atomic rename) → staging_dir mới → publish atomic → backup_dir unlink. |
| (d) `_failed_<clustering_id>_<run_uuid>/` cũ còn sót | KHÔNG cleanup tự động — R1 invariant retain. User tự dọn thủ công nếu muốn. |

**Final subdirectory chỉ được touch bằng MỘT `os.rename` nguyên tử**
(Stage 5b publish) — sau rename, mọi file trong final subdirectory là
coherent (cùng publish event). Trước rename, final subdirectory hoàn
toàn untouched.

**Không cam kết** "cleanup pass đảm bảo không orphan trên disk". Cam
kết thực sự:

- Cleanup pass **CHỈ** unlink staging/backup dirs của current run
  (theo R3 rules ở §6.7.4).
- Cleanup pass retain `_backup_*_corrupt/` (R2) và `_failed_*/` (R1)
  bất chấp publish_succeeded.
- Nếu process crash, cleanup pass KHÔNG chạy → staging/backup/failed
  dirs của run đó có thể còn trên disk. Lần chạy sau với `_RUN_UUID`
  khác KHÔNG động vào (recovery pass chỉ handle normal `_backup_*`
  KHÔNG suffix).
- Recovery từ orphan (a)/(b)/(b')/(c)/(d) đều có cơ chế rõ ràng (xem
  bảng trên).

**Test bắt buộc cho orphan policy**:

- `test_dev04_pipeline.py::test_crash_before_publish_preserves_old_success` —
  chạy run A SUCCESS; mô phỏng crash giữa Stage 4 (manifest chưa
  publish) bằng monkey-patch `os.rename` raise trước commit; verify
  final_dir của A còn nguyên (SHA-256 manifest + cluster_labels
  không đổi), staging_dir có thể còn sót (orphan loại (a) — KHÔNG
  test sẽ fail nếu expect cleanup ngay lập tức).
- `test_dev04_storage.py::test_cleanup_pass_only_removes_own_run` —
  pre-create `_staging_<other_run_uuid>/` và `_backup_<other_run_uuid>/`
  giả lập; chạy run hiện tại với `_RUN_UUID` khác; verify 2 dirs giả
  vẫn còn.
- `test_dev04_pipeline.py::test_orphan_final_no_manifest_recovery` —
  pre-create final subdirectory của `clustering_id` X với contents
  rỗng (no manifest, no parquet); gọi CLI với clustering_id X; verify
  CLI move final cũ → backup, tạo staging mới, publish atomic; backup
  unlink.
- `test_dev04_pipeline.py::test_staging_and_backup_cleanup_after_success` —
  chạy `--force-rerun` SUCCESS; verify cả staging_dir lẫn backup_dir
  đều được unlink (cleanup pass hoạt động bình thường ở happy path).

#### 6.7.4. Staging và atomic publish policy

Mục tiêu: **mọi write của một run phải được cô lập trong staging
subdirectory của run đó** cho đến khi final subdirectory được
publish bằng một `os.rename` nguyên tử. Khi đó:

- Nếu run SUCCESS: final subdirectory chứa tất cả artifact coherent
  (cùng publish event).
- Nếu run FAIL bất kỳ lúc nào: final subdirectory hoàn toàn không
  bị touch; chỉ staging subdirectory bị ảnh hưởng; cleanup pass cuối
  run unlink staging.
- Nếu process crash trước publish: chỉ staging bị partial; final
  subdirectory của run này (nếu có từ lần chạy trước) còn nguyên.
- Cleanup pass **CHỈ unlink staging/backup dirs của current run**
  (xác định bằng `run_uuid`); KHÔNG BAO GIỜ xóa file khác.

**Cửa sổ lỗi nguy hiểm — `final → backup` rename thành công nhưng
process bị kill trước publish**: nếu `--force-rerun` đã rename
`final_dir` cũ sang `backup_dir` nhưng process chết trước khi
`os.rename(staging, final)` được gọi, trạng thái đĩa là:
- `final_dir` (= `base_dir/<clustering_id>/`): KHÔNG tồn tại.
- `backup_dir` (= `base_dir/_backup_<old_run_uuid>/`): chứa
  `backup_dir/<clustering_id>/` với toàn bộ artifact cũ.
- `staging_dir` (= `base_dir/_staging_<old_run_uuid>/`): có thể
  tồn tại với partial files (orphan loại (a)) hoặc đã được unlink
  bởi cleanup của run cũ (nếu cleanup chạy trước khi crash).

Đây là cửa sổ lỗi mà `test_force_rerun_safety` cũ chưa bao phủ
(vì nó monkey-patch `os.rename` raise TRƯỚC commit; cửa sổ này là
`os.rename(final, backup)` đã thành công, `os.rename(staging, final)`
chưa bao giờ chạy). Cần **startup recovery pass** (xem pseudocode
dưới) và test mô phỏng crash đúng trong cửa sổ này (xem
`test_crash_after_backup_before_publish_restored_on_next_run`).

**Bảng failure windows cho `--force-rerun` an toàn** — mỗi failure
window được liệt kê cùng trạng thái đĩa trước/sau, hành vi của
lần chạy kế tiếp, và artifact nào được bảo toàn (mapping với các
AC cụ thể trong §10 AC-12):

| # | Failure window | Disk state ngay sau crash | Hành vi của lần chạy kế tiếp | Artifact bảo toàn |
|---|---|---|---|---|
| F1 | Crash **trước** khi `final → backup` rename chạy | `final_dir` cũ còn nguyên (md5 = A); `backup_dir` không tồn tại; `staging_dir` không tồn tại | Main pipeline: idempotency check thấy valid manifest → **idempotent skip** (không touch disk). Nếu `--force-rerun`: chạy bình thường (Stage 3 backup, 4 fit, 5 publish). | Old SUCCESS (A) còn nguyên |
| F2 | Crash **sau** `final → backup` rename **nhưng trước** `staging_dir.mkdir()` | `final_dir` KHÔNG tồn tại; `backup_dir/_backup_<uuid>/<clustering_id>/` chứa A; `staging_dir` không tồn tại | Startup recovery pass: thấy `backup_dir` (uuid ≠ current), final missing → atomic restore `backup_dir/<clustering_id>` → `final_dir`; idempotency skip (A). | Old SUCCESS (A) được restore nguyên vẹn |
| F3 | Crash **sau** `staging_dir.mkdir()` **nhưng trước** Stage 4 (`runner.run()` hoàn tất) | `final_dir` KHÔNG tồn tại; `backup_dir` chứa A; `staging_dir` tồn tại nhưng trống hoặc partial (`save_labels=False` vì chưa tới Stage 5) | Startup recovery pass: restore backup → final (A). Main pipeline: idempotency skip (A). Cleanup pass của current run unlink `staging_dir` partial. | Old SUCCESS (A) được restore; staging partial bị cleanup |
| F4 | `os.rename(staging_dir, final_dir)` **thất bại** (exception, e.g. disk full, NFS hiccup) | `final_dir` KHÔNG tồn tại; `backup_dir` chứa A; `staging_dir` có thể còn (chưa được move) hoặc đã được rename đến 1 nửa (POSIX rename là atomic — full success hoặc không gì; trên cùng FS). | Except handler trong pseudocode restore `backup_dir` → `final_dir` (atomic), cleanup `staging_dir`. Nếu process chết giữa except handler: startup recovery sẽ pick up `backup_dir` lần sau. | Old SUCCESS (A) được restore |
| F5 | Crash **ngay sau** `os.rename(staging, final)` thành công **nhưng trước** cleanup backup | `final_dir` chứa NEW result; `backup_dir` vẫn còn với A (orphaned); `staging_dir` đã trở thành `final_dir`. | Main pipeline: cleanup `backup_dir` (rmtree). Nếu chết trước cleanup: `backup_dir` orphaned — user có thể dọn thủ công (DEV-04 KHÔNG tự động cross-process cleanup). | NEW result published; old A trong backup_dir (user tự dọn) |
| F6 | Crash hoặc exception **trong startup recovery** | `final_dir` có thể đã được restore 1 phần (atomic rename = nguyên tử, hoặc KHÔNG gì xảy ra); `backup_dir` có thể đã được move | Recovery wrap in try/except: nếu exception xảy ra, log warning và KHÔNG abort main pipeline. Main pipeline chạy bình thường với `final_dir` ở trạng thái hiện tại (có thể missing → re-fit sẽ trigger backup từ orphan final flow). | Cố gắng giữ max(A, NEW) |
| F7 | `final_dir` tồn tại nhưng manifest **corrupt** | `final_dir/<clustering_id>/` chứa partial hoặc full artifact + corrupt manifest JSON | Default: `find_existing_clustering` raises `Dev04ManifestCorrupt` → fail-closed CLI exit non-zero. **KHÔNG** auto-restore backup. User phải `--force-rerun` (sẽ move corrupt final → `_backup_<uuid>_corrupt` rồi re-fit). Với `--force-rerun`: corrupt final rename sang `_backup_<uuid>_corrupt/`; new run proceed với staging mới; cleanup retain `_backup_<uuid>_corrupt/` cho audit. Nếu rename corrupt final → backup fail: stop với `Dev04StoragePathError`. | Default: KHÔNG touch; fail-closed để user quyết định. Với `--force-rerun`: corrupt backup retained; new SUCCESS published khi re-fit. |
| F7a | `final_dir` tồn tại, manifest **missing** (no manifest at all — orphan final no-manifest) | `final_dir/<clustering_id>/` chứa artifact (cluster_labels, experiment_log, ...) nhưng KHÔNG có `clustering_manifest.json` | `find_existing_clustering` returns `None` (line `if not manifest_path.exists(): return None`). Force-rerun path: `final_dir` exists → rename sang `normal_backup_dir` (`_backup_<uuid>`); staging mới + publish atomic + cleanup retain until success → `backup_dir` unlinked. (Same flow as orphan recovery; cùng path.) | Old artifact moved sang backup; new SUCCESS published khi re-fit. |
| F7b | `final_dir` tồn tại, manifest **partially corrupt** (e.g. JSON parse OK but missing 1 canonical key, wrong type) | `final_dir/<clustering_id>/` chứa artifact + manifest JSON hợp lệ cú pháp nhưng thiếu 1 trong 7 canonical key, hoặc `seed_policy` không ∈ canonical whitelist | Same as F7: `_extract_canonical_payload_from_manifest` raise `Dev04ManifestCorrupt`. Default fail-closed; `--force-rerun` → corrupt recovery. | Same as F7. |
| F8 | Backup **malformed** (multiple inner subdirs hoặc no inner subdir) | `backup_dir/_backup_<uuid>/` không match contract | Recovery pass SKIP (fail-closed for malformed); main pipeline chạy bình thường; user tự dọn thủ công | KHÔNG touch malformed backup; final_dir state giữ nguyên |
| F9 | **Multiple** backup_dirs từ các run trước, cùng clustering_id | `backup_dir/_backup_<uuid_1>/<clustering_id>/` + `backup_dir/_backup_<uuid_2>/<clustering_id>/` | Recovery pass: iterate. uuid_1 được restore (final_dir missing → restore). uuid_2 thấy final_dir đã tồn tại (just-restored from uuid_1) → SKIP. uuid_2 backup_dir orphaned. | A được restore; uuid_2 backup_dir tự dọn sau |
| F10 | Backup chứa inner subdir có tên không match `^cl_[0-9a-f]{24}$` | `backup_dir/_backup_<uuid>/some_random_dir/` | Recovery pass: regex check fails → SKIP malformed backup. User tự dọn. | KHÔNG touch malformed backup |
| F11 | **FAILED** run — Stage 4 / Stage 5 fail (matrix validation NaN, algorithm exception, manifest write fail) | `staging_dir` chứa partial artifact (có thể có `experiment_log_*.json` từ ML-01 cho `save_labels=False` path); `final_dir` untouched (hoặc backup nếu `--force-rerun`); `failed_tracking_dir` được tạo nếu `experiment_log_*.json` tồn tại trong staging | Main pipeline: `_preserve_failed_log` move `experiment_log_*.json` từ staging → `_failed_<clustering_id>_<run_uuid>/`; restore backup nếu có; CLI exit non-zero. **KHÔNG** publish manifest / cluster_labels. Cleanup pass (R3) retain `_failed_*/` cho audit. | `experiment_log_*.json` PRESERVED ở `_failed_*/` cho audit; final_dir state unchanged (hoặc backup restored) |
| F12 | **R2 corrupt recovery backup** retained on disk sau success | `_backup_<run_uuid>_corrupt/` tồn tại chứa corrupt manifest cũ | Cleanup pass LUÔN retain `_backup_*_corrupt/` (R2 invariant). User tự dọn thủ công sau khi diagnose. **KHÔNG** auto-delete. | Corrupt manifest backup retained cho audit |
| F13 | Cleanup pass itself raises exception | `state` structure corrupted | Cleanup wrap in try/except: log warning; **KHÔNG** re-raise; primary exception (if any) is preserved. Python `finally:` semantics: cleanup exception logged but discarded in unwind. | Cleanup exception logged; primary exception (if any) propagates |
| F14 | **R1 preservation fail + cleanup unlinks staging** (F1 invariant gap) | `staging_dir` chứa `experiment_log_*.json` chưa được move; `_failed_*/` không tồn tại hoặc rỗng (mkdir fail); cleanup pass DEFAULT (KHÔNG có F1 invariant) sẽ `shutil.rmtree(staging_dir)` → log bị xóa vĩnh viễn | Default (current pre-F1 plan): AC-5 #24 audit trail bị mất silently. **With F1 invariant (§6.5 rule #7)**: `_preserve_failed_log` return `PreservationStatus ∈ {"partial", "failed"}`; exception handler set `state.unpreserved_log_in_staging=True` sau re-scan; cleanup pass KHÔNG unlink staging_dir (retain cho manual recovery); primary exception vẫn propagate. | With F1 invariant: experiment_log_*.json PRESERVED trong staging_dir (orphan) cho manual recovery; next invocation's `recover_orphan_backups` không restore staging nhưng log warning; user tự dọn sau khi recover manually. |

**Cleanup pass scope** (R3 — top-level `finally:` của `run_dev04`):

- Cleanup pass chạy ở `finally:` của `run_dev04` (cuối mỗi run) —
  KHÔNG chỉ trong success path. Runs cả khi primary exception raised
  (Python `finally:` semantics).
- Cleanup pass CHỉ xét các entry trong `base_dir` thuộc về current
  process: `_staging_<run_uuid>`, `_backup_<run_uuid>`,
  `_backup_<run_uuid>_corrupt`, `_failed_<clustering_id>_<run_uuid>`.
  Các entry với run_uuid khác (process khác) → KHÔNG BAO GIỜ touch.
- Với mỗi match (UUID filter):
    - `_staging_<run_uuid>/` còn tồn tại → unlink bằng
      `shutil.rmtree` (idempotent với `ignore_errors=True`).
    - `_backup_<run_uuid>/` còn tồn tại → unlink NẾU
      `publish_succeeded=True` AND `backup_dir_from_corrupt_manifest=False`;
      NGƯỢC LẠI retain (R2 corrupt backup retain for diagnosis;
      publish failed retain for next-run recovery).
    - `_backup_<run_uuid>_corrupt/` → LUÔN retain (R2).
    - `_failed_<clustering_id>_<run_uuid>/` → LUÔN retain (R1).
- KHÔNG BAO GIỜ recurse vào `<clustering_id>/` subdirs của base_dir
  để xoá file (chỉ touch top-level staging/backup/failed dirs của
  current run).
- Final subdirs (`<clustering_id>/`) KHÔNG match `_staging_*` /
  `_backup_*` / `_failed_*` → KHÔNG BAO GIỜ bị cleanup pass touch.
- Cleanup pass wrap trong try/except: nếu cleanup raise, log warning
  và KHÔNG re-raise (primary exception, nếu có, được preserve).
- **Distinguish Python exception cleanup from crash recovery**: cleanup
  pass chỉ chạy khi Python có control (cuối run, normal return hoặc
  exception được raise). Nếu process bị kill ngang (segfault, OOM,
  power loss, machine crash), cleanup KHÔNG chạy → orphan dirs sẽ
  được handle bởi startup recovery ở NEXT run
  (`recover_orphan_backups`). Plan KHÔNG cam kết cleanup chạy sau
  abrupt crash.

**Startup recovery position** — tại sao chạy TRƯỚC ID derivation
và lookup, không phải sau:

- Sau recovery pass, `final_dir` (nếu đã được restore từ backup) sẽ
  có manifest hợp lệ → idempotency lookup thấy match → early-return
  (mặc định) hoặc tiếp tục force-rerun (nếu user yêu cầu).
- Nếu chạy recovery SAU lookup, lookup sẽ thấy `final_dir` missing
  (vì backup chưa được restore) → silently re-fit (overwrite logic
  đúng nhưng tốn công trong khi A còn nguyên trong backup).
- Recovery pass wrap trong try/except (`contextlib.suppress`) để nếu
  OSError xảy ra, log warning và KHÔNG abort main pipeline.

**Defence-in-depth cho malformed backup**:

- Backup_dir với multiple inner subdirs → KHÔNG recover (vì
  không xác định được "đúng" subdir nào; tránh heuristic sai).
- Backup_dir với no inner subdirs → KHÔNG recover.
- Backup_dir với inner subdir không match regex → KHÔNG recover
  (regex `^cl_[0-9a-f]{24}$` đảm bảo chỉ nhận valid clustering_id).
- Tất cả các malformed case → leave-on-disk (user tự dọn).

**Không có heuristic "auto-cleanup"**: DEV-04 KHÔNG tự xoá malformed
backup_dir / orphan final / orphan staging khi không xác định được
ownership an toàn. Mọi cleanup phải xác định được UUID của current
run (qua `_RUN_UUID` set 1 lần khi process start). Cleanup cross-
process (vd. dọn orphan từ process khác) là ngoài DEV-04 scope.

**Startup recovery pass** (chạy 1 lần khi process start, TRƯỚC mọi
staging/publish của current run):

```python
def recover_orphan_backups(base_dir: Path, current_run_uuid: str) -> int:
    """Restore final_dir từ orphan backup_dir của run trước (nếu có).

    Quét base_dir/_backup_<uuid>/ với uuid != current_run_uuid.
    Với mỗi backup_dir hợp lệ (đúng 1 inner subdir matching regex
    ^cl_[0-9a-f]{24}$/):
      - Nếu final_dir (= base_dir/<clustering_id>/) KHÔNG tồn tại
      - → os.rename(backup_dir/<clustering_id>, final_dir)  # atomic
      - → entry.rmdir() (nếu backup_dir giờ trống; KHÔNG touch
        nếu vẫn còn file)
      - → log: "RECOVERED: <clustering_id> from orphan backup"

    KHÔNG động vào:
      - backup_dir của current_run (sẽ được handle bởi main pipeline).
      - staging_dir (orphan loại a; KHÔNG auto-recover; cleanup pass
        hiện tại sẽ unlink nếu match uuid).
      - final_dir nếu đã tồn tại (manifest hợp lệ → idempotent skip;
        manifest corrupt → Dev04ManifestCorrupt ở find_existing_clustering;
        không có manifest → main pipeline move sang backup rồi re-fit).
      - malformed backup_dir (multiple/no inner subdirs, inner subdir
        không match regex): SKIP — không raise, không auto-fix; leave
        on disk cho user dọn thủ công.

    Returns: số orphan backup đã được recover.

    Exceptions: KHÔNG raise ra ngoài. Toàn bộ function wrap trong
    try/except + log; recovery errors KHÔNG abort main pipeline
    (chỉ log warning). Lý do: nếu recovery raise, lần chạy hiện tại
    sẽ crash ngay từ đầu — không có tác dụng gì ngoài việc chặn
    user khỏi tiếp tục làm việc. Orphan từ run trước KHÔNG được
    coi là blocker cho run hiện tại.
    """
    import contextlib
    import logging
    log = logging.getLogger("customer_segmentation.prototype.clustering")
    recovered = 0
    skipped_malformed = 0
    skipped_existing = 0
    skipped_corrupt = 0  # R2: skip _backup_*_corrupt directories.
    errors: list[str] = []
    try:
        for entry in base_dir.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if not name.startswith(_BACKUP_PREFIX):
                continue
            # Bỏ qua backup_dir của current run (main pipeline xử lý).
            # R2: bỏ qua _backup_<uuid>_corrupt directories — these are
            # preserved for diagnosis, NOT for recovery. Main pipeline
            # never produces corrupt backups; recovery pass should not
            # accidentally restore a corrupt manifest as the latest SUCCESS.
            if name.endswith(_CORRUPT_BACKUP_SUFFIX):
                skipped_corrupt += 1
                log.debug(
                    "DEV-04 recovery: backup_dir %s has %s suffix "
                    "(R2 marker); skipping recovery.",
                    entry, _CORRUPT_BACKUP_SUFFIX,
                )
                continue
            run_uuid = name[len(_BACKUP_PREFIX):]
            if run_uuid == current_run_uuid:
                continue
            # Quét nội dung backup_dir — phải có đúng 1 <clustering_id>/.
            try:
                subdirs = [p for p in entry.iterdir() if p.is_dir()]
            except OSError as exc:
                errors.append(f"iterdir failed on {entry!s}: {exc!s}")
                continue
            if len(subdirs) != 1:
                skipped_malformed += 1
                log.warning(
                    "DEV-04 recovery: backup_dir %s has %d inner subdirs "
                    "(expected 1); leaving on disk for manual cleanup.",
                    entry, len(subdirs),
                )
                continue  # malformed; để nguyên cho user xử lý
            inner = subdirs[0]
            m = _CLUSTERING_ID_RE.match(inner.name)
            if not m:
                skipped_malformed += 1
                log.warning(
                    "DEV-04 recovery: backup_dir %s inner subdir %r "
                    "does not match clustering_id regex; leaving on disk "
                    "for manual cleanup.",
                    entry, inner.name,
                )
                continue
            recovered_clustering_id = inner.name
            final_dir = base_dir / recovered_clustering_id
            # Path containment defence-in-depth: final_dir phải nằm
            # trong base_dir. (base_dir đã được resolve ở caller.)
            try:
                final_dir.resolve().relative_to(base_dir.resolve())
            except ValueError:
                errors.append(
                    f"refusing to restore {final_dir!s}: outside base_dir"
                )
                continue
            if final_dir.exists():
                skipped_existing += 1
                log.debug(
                    "DEV-04 recovery: final_dir %s already exists; "
                    "skipping restore (main pipeline will handle via "
                    "idempotent lookup / orphan flow).",
                    final_dir,
                )
                continue
            # Atomic restore: backup_dir/<clustering_id> → base_dir/<clustering_id>.
            try:
                os.rename(inner, final_dir)
            except OSError as exc:
                errors.append(
                    f"rename {inner!s} -> {final_dir!s} failed: {exc!s}"
                )
                continue
            # Backup_dir giờ trống → unlink (KHÔNG động nếu vẫn còn file).
            with contextlib.suppress(OSError):
                entry.rmdir()
            log.info(
                "DEV-04 recovery: restored %s from orphan backup %s.",
                final_dir, entry,
            )
            recovered += 1
    except Exception as exc:
        # Defensive: KHÔNG BAO GIỜ raise ra ngoài. Log + continue.
        log.exception("DEV-04 recovery: unexpected error; continuing.")
        errors.append(f"unexpected error: {exc!s}")
    if errors:
        log.warning(
            "DEV-04 recovery: %d error(s) encountered: %s",
            len(errors), errors,
        )
    log.debug(
        "DEV-04 recovery summary: recovered=%d, skipped_malformed=%d, "
        "skipped_existing=%d, skipped_corrupt=%d, errors=%d",
        recovered, skipped_malformed, skipped_existing,
        skipped_corrupt, len(errors),
    )
    return recovered
```

**Bảng quyết định cho `recover_orphan_backups`** (explicit decision
matrix — mỗi state mapping tới hành vi cụ thể):

| State | Quan sát | Hành vi | Ghi log |
|---|---|---|---|
| S1 | `backup_dir` không match `_backup_*` regex | Skip (không phải backup) | (none) |
| S2 | `backup_dir` UUID = `current_run_uuid` | Skip (current run xử lý) | (none) |
| S3 | `backup_dir` không iterdir được (OSError) | Skip + log warning | "iterdir failed" |
| S4 | `backup_dir` có 0 inner subdirs | Skip malformed + log warning | "expected 1, got 0" |
| S5 | `backup_dir` có ≥2 inner subdirs | Skip malformed + log warning | "expected 1, got N" |
| S6 | `backup_dir` có 1 inner subdir nhưng tên KHÔNG match `^cl_[0-9a-f]{24}$` | Skip malformed + log warning | "inner subdir does not match regex" |
| S7 | `backup_dir` có 1 inner subdir matching regex, `final_dir.exists() == True` | Skip + log debug | "final_dir already exists" |
| S8 | `backup_dir` có 1 inner subdir matching regex, `final_dir` missing, `final_dir.resolve()` ngoài `base_dir` | Skip + log warning | "refusing to restore: outside base_dir" |
| S9 | `backup_dir` có 1 inner subdir matching regex, `final_dir` missing, `os.rename` raise OSError | Skip + log warning | "rename failed" |
| S10 | `backup_dir` có 1 inner subdir matching regex, `final_dir` missing, `os.rename` thành công, `entry.rmdir()` OK | Restore + log info | "restored X from orphan backup" |
| S11 | `backup_dir` có 1 inner subdir matching regex, `final_dir` missing, `os.rename` thành công, `entry.rmdir()` raise OSError (backup_dir không trống) | Restore successful, backup_dir KHÔNG được unlink (không rỗng) — leave on disk | "restored X; backup_dir not empty, leaving for manual cleanup" |
| S12 | Recovery gặp unexpected exception | Wrap in try/except; log; KHÔNG raise | "unexpected error; continuing" |

**Pseudocode đầy đủ** (reference, implementation ở
`prototype/clustering/pipeline.py::run`):

```python
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# Set 1 lần khi process start. Dùng để cleanup pass identify dirs
# của current run; KHÔNG touch dirs của process khác.
_RUN_UUID: str = uuid.uuid4().hex
_STAGING_PREFIX = "_staging_"
_BACKUP_PREFIX = "_backup_"
_FAILED_PREFIX = "_failed_"        # R1: FAILED run log tracking directory.
_CORRUPT_BACKUP_SUFFIX = "_corrupt"  # R2: corrupt manifest backup marker.

# Regex dùng cho find_existing_clustering + cleanup identification.
import re
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")
_STAGING_OR_BACKUP_OR_FAILED_RE = re.compile(
    r"^_(staging|backup|failed)_[A-Za-z0-9_-]+$"
)


@dataclass
class _CleanupState:
    """State passed to top-level cleanup pass (R3).

    F1 invariant: `unpreserved_log_in_staging` (bool, default False)
    tracks whether `_preserve_failed_log` reported partial or full
    failure AND a re-scan confirmed `experiment_log_*.json` still
    exists in staging_dir. When True, `_cleanup_pass` MUST NOT
    unlink `staging_dir` (retained for manual recovery). See §6.5
    rule #7, §6.7.3 failure window F14, §6.7.4 F1 invariant.
    """
    base_dir: Path
    current_run_uuid: str
    staging_dir: Path | None = None
    backup_dir: Path | None = None
    backup_dir_from_corrupt_manifest: bool = False  # R2: retain if true.
    failed_tracking_dir: Path | None = None           # R1: retain for audit.
    publish_succeeded: bool = False                  # Gate backup deletion.
    manifest_path: Path | None = None
    final_dir: Path | None = None
    unpreserved_log_in_staging: bool = False         # F1: gate staging unlink.


# Canonical return values for `_preserve_failed_log`. F1 invariant uses
# these to drive `state.unpreserved_log_in_staging` in the exception
# handler. All 4 values are stable contracts (Phase 2 implementation
# must use these exact strings for log parsing and test assertions).
PreservationStatus = Literal["ok", "partial", "no_log", "failed"]
# - "ok": all experiment_log_*.json in staging moved successfully to
#   _failed_*/; audit sidecar written; staging_dir has no remaining
#   log files.
# - "partial": some experiment_log_*.json moved, some failed
#   (OSError mid-loop, race, permission); audit sidecar records
#   `preserved_logs=<N>` with N < total; staging_dir still has
#   orphan logs.
# - "no_log": no experiment_log_*.json in staging at the time
#   `_preserve_failed_log` ran (e.g., crash before Stage 4 wrote
#   anything); nothing to preserve; no _failed_*/ created.
# - "failed": mkdir _failed_*/ failed before any move ran (e.g.,
#   permission denied, EEXIST, disk full at base_dir); all logs
#   remain in staging_dir (orphan).


def _preserve_failed_log(
    staging_dir: Path,
    failed_tracking_dir: Path,
    run_uuid: str,
) -> PreservationStatus:
    """R1: Move FAILED experiment_log_*.json from staging to a dedicated
    tracking directory before staging is unlinked. Return a
    `PreservationStatus` (F1 invariant contract).

    Failure of this move operation itself is logged but does not raise:
    cleanup pass will report it, and the run will exit with the original
    exception. The FAILED log MUST be preserved or the audit trail for
    AC-5 #24 will be lost.

    Return values (F1 invariant contract; exact strings):
      - "ok": all `experiment_log_*.json` in staging moved successfully.
      - "partial": some moved, some failed (mid-loop OSError, etc.);
        staging_dir still has orphan logs.
      - "no_log": no `experiment_log_*.json` in staging; nothing to
        preserve; no `_failed_*/` created.
      - "failed": mkdir `_failed_*/` failed before any move ran; all
        logs remain in staging_dir.

    Caller (exception handler in `run_dev04`) is responsible for:
      (a) Re-scanning staging_dir after this function returns to
          confirm whether `experiment_log_*.json` files remain
          (defence-in-depth: races, late writes by ML-01, etc.).
      (b) Setting `state.unpreserved_log_in_staging = True` when
          return value ∈ {"partial", "failed"} AND re-scan confirms
          orphan logs exist.
      (c) Re-raising the primary exception (this function does NOT
          raise under any circumstance — it is a best-effort helper).

    See §6.5 rule #7, §6.7.3 failure window F14, §6.7.4 F1 invariant
    for the cleanup pass contract that depends on this return value.
    """
    import contextlib
    import logging
    log = logging.getLogger("customer_segmentation.prototype.clustering")

    if not staging_dir.exists():
        return "no_log"

    # Discover FAILED experiment log(s) written by ML-01 inside staging.
    failed_logs = sorted(staging_dir.glob("experiment_log_*.json"))
    if not failed_logs:
        # No log to preserve (e.g., crash before runner.run wrote anything).
        # Nothing to do; the failed_tracking_dir will be cleaned up later
        # because it's empty (rmdir).
        return "no_log"

    try:
        failed_tracking_dir.mkdir(parents=True, exist_ok=False)
    except (FileExistsError, OSError) as exc:
        log.error(
            "DEV-04: cannot create FAILED tracking dir %s for run_uuid=%s: %s. "
            "FAILED log will remain in staging_dir (orphaned).",
            failed_tracking_dir, run_uuid, exc,
        )
        return "failed"

    preserved_count = 0
    for log_file in failed_logs:
        try:
            target = failed_tracking_dir / log_file.name
            shutil.move(str(log_file), str(target))
            preserved_count += 1
        except OSError as exc:
            log.error(
                "DEV-04: failed to move FAILED log %s -> %s: %s",
                log_file, failed_tracking_dir / log_file.name, exc,
            )

    # Audit record: small sidecar file documenting the preservation.
    try:
        audit_path = failed_tracking_dir / "_preservation_audit.txt"
        audit_path.write_text(
            f"preserved_at_utc={_now_utc_iso()}\n"
            f"source_staging={staging_dir.name}\n"
            f"run_uuid={run_uuid}\n"
            f"reason=runner reported non-SUCCESS or unhandled exception\n"
            f"preserved_logs={preserved_count}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning(
            "DEV-04: could not write FAILED audit record at %s: %s",
            failed_tracking_dir / "_preservation_audit.txt", exc,
        )

    # F1 invariant return: distinguish "all preserved" vs "partial".
    if preserved_count == len(failed_logs):
        return "ok"
    return "partial"


def _cleanup_pass(state: _CleanupState) -> None:
    """R3: Top-level cleanup pass scoped to current run's `_RUN_UUID`.

    Cleanup must:
      * Be scoped to current `_RUN_UUID` (never touch other runs).
      * NOT remove a backup that contains the only recoverable SUCCESS.
      * NOT remove retained FAILED logs (R1).
      * NOT remove another run's staging / backup / log directory.
      * Preserve ambiguous or malformed filesystem states for manual
        diagnosis (e.g. failed_tracking_dir with sub-tree irregularities).
      * Log cleanup failures clearly.

    This function MUST NOT raise. It is called from a top-level
    `finally:` block in `run_dev04`. If cleanup itself fails, the
    exception is caught and logged by the caller; the primary exception
    (if any) is NOT hidden.

    Distinguish Python exception cleanup from crash recovery:
      * This function runs only when Python has control (finally block).
      * If process crashed (segfault, OOM, power loss), this function
        does NOT run; orphan staging/backup/failed dirs are recovered
        on the NEXT invocation via `recover_orphan_backups` (startup
        recovery). See §6.7.4 "Cửa sổ lỗi nguy hiểm" failure windows.
    """
    import contextlib
    import logging
    log = logging.getLogger("customer_segmentation.prototype.clustering")

    base_dir = state.base_dir
    run_uuid = state.current_run_uuid

    # 1. Unlink staging_dir of current run if it still exists.
    #    R3 invariant: only dirs matching current `_RUN_UUID` are touched.
    #    F1 invariant: if `state.unpreserved_log_in_staging == True`
    #    (i.e., `_preserve_failed_log` returned "partial" or "failed"
    #    AND re-scan confirmed orphan logs in staging), DO NOT
    #    unlink staging_dir — it contains the only remaining copy of
    #    an unpreserved FAILED log. Retain for manual recovery. See
    #    §6.5 rule #7, §6.7.3 failure window F14.
    if state.staging_dir is not None and state.staging_dir.exists():
        if state.unpreserved_log_in_staging:
            log.warning(
                "DEV-04 cleanup (F1 invariant): staging_dir %s contains "
                "unpreserved FAILED log(s); RETAINING for manual recovery. "
                "Do not unlink until orphan logs are recovered. "
                "User may inspect, copy logs out, then run "
                "scripts/dev04_cleanup_orphans.py (out of DEV-04 scope) "
                "to remove the staging_dir.",
                state.staging_dir,
            )
        elif run_uuid in state.staging_dir.name:
            try:
                shutil.rmtree(state.staging_dir)
                log.debug(
                    "DEV-04 cleanup: unlinked staging_dir %s",
                    state.staging_dir,
                )
            except OSError as exc:
                log.warning(
                    "DEV-04 cleanup: failed to unlink staging_dir %s: %s. "
                    "Leaving for manual cleanup.",
                    state.staging_dir, exc,
                )
        else:
            log.warning(
                "DEV-04 cleanup: staging_dir %s does not contain "
                "current run_uuid %s; refusing to unlink.",
                state.staging_dir, run_uuid,
            )

    # 2. Unlink backup_dir of current run only if:
    #      (a) publish succeeded (so backup is no longer the only SUCCESS);
    #      (b) backup is NOT from a corrupt manifest (R2: corrupt backups
    #          are retained for audit/diagnosis).
    #    If publish failed OR backup is corrupt, retain backup_dir so
    #    startup recovery on next invocation can restore from it.
    if state.backup_dir is not None and state.backup_dir.exists():
        if not state.publish_succeeded:
            log.info(
                "DEV-04 cleanup: publish did not succeed; retaining "
                "backup_dir %s for manual recovery on next invocation.",
                state.backup_dir,
            )
        elif state.backup_dir_from_corrupt_manifest:
            # R2: corrupt-manifest backup is preserved for diagnosis.
            log.info(
                "DEV-04 cleanup: backup_dir %s originated from a corrupt "
                "manifest; retaining for diagnosis. User may remove "
                "manually after review.",
                state.backup_dir,
            )
        else:
            # Normal --force-rerun success: backup_dir can be deleted.
            if run_uuid in state.backup_dir.name:
                try:
                    shutil.rmtree(state.backup_dir)
                    log.debug(
                        "DEV-04 cleanup: unlinked backup_dir %s",
                        state.backup_dir,
                    )
                except OSError as exc:
                    log.warning(
                        "DEV-04 cleanup: failed to unlink backup_dir %s: %s",
                        state.backup_dir, exc,
                    )
            else:
                log.warning(
                    "DEV-04 cleanup: backup_dir %s does not contain "
                    "current run_uuid %s; refusing to unlink.",
                    state.backup_dir, run_uuid,
                )

    # 3. failed_tracking_dir: RETAIN for audit. NEVER unlink.
    #    R1: FAILED logs must remain on disk for inspection.
    #    User can manually remove if they no longer need them.
    if state.failed_tracking_dir is not None and state.failed_tracking_dir.exists():
        log.info(
            "DEV-04 cleanup: retaining FAILED tracking dir %s for audit. "
            "User may remove manually after review.",
            state.failed_tracking_dir,
        )


def run_dev04(
    *, storage_root, dataset_id, preprocessed_id,
    algorithm, hyperparameters, effective_seed,
    force_rerun: bool = False,
    requested_experiment_id: str | None = None,
    ml_dataset_sha256: str,
    config_sha256: str,
    matrix_df=None,          # type: ignore[assignment]
    customer_metadata_df=None,  # type: ignore[assignment]
    runner=None,             # ML-01 ExperimentRunner instance
) -> Path:
    """Return path to clustering_manifest.json (existing hoặc mới publish).

    R3: The whole body is wrapped in a top-level `try/finally:` block.
    The `finally:` block invokes `_cleanup_pass(state)` which is
    scoped to `_RUN_UUID` and preserves documents (R1) / corrupt
    backups (R2).
    """

    import contextlib
    import logging
    log = logging.getLogger("customer_segmentation.prototype.clustering")

    base_dir = prototype_clustering_base_dir(
        storage_root, dataset_id, preprocessed_id
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    state = _CleanupState(
        base_dir=base_dir,
        current_run_uuid=_RUN_UUID,
    )

    try:
        # 0. STARTUP RECOVERY PASS — xử lý orphan backup từ run trước bị
        #    crash sau khi rename final→backup nhưng trước publish. PHẢI
        #    chạy trước khi main pipeline, vì nếu KHÔNG chạy, idempotency
        #    lookup ở bước 2 có thể thấy final KHÔNG tồn tại (do bị move
        #    sang backup) và silently chạy lại (overwrite logic đúng nhưng
        #    sẽ tốn công re-fit trong khi kết quả cũ vẫn còn nguyên trong
        #    backup).
        #    Recovery wrap in try/except: nếu recovery raise (vd. OSError
        #    bất thường trong iterdir), log + continue — KHÔNG abort main
        #    pipeline. Recovery errors KHÔNG bao giờ là blocker cho run
        #    hiện tại (orphan từ run trước không nên ngăn user làm việc).
        try:
            recovered = recover_orphan_backups(base_dir, current_run_uuid=_RUN_UUID)
            if recovered > 0:
                log.info(
                    "DEV-04 startup recovery: restored %d orphan backup(s) "
                    "from previous crashed run(s).", recovered
                )
        except Exception:
            log.exception(
                "DEV-04 startup recovery: unexpected error; continuing "
                "main pipeline without recovery."
            )
            recovered = 0

        # 1. Compute clustering_id (xem §6.4.1) — cần hyperparameters
        #    effective (sau CLI merge) + seed resolved.
        clustering_id = derive_clustering_id(
            preprocessed_id=preprocessed_id,
            algorithm=algorithm,
            hyperparameters=hyperparameters,
            effective_seed=effective_seed,
            ml_dataset_sha256=ml_dataset_sha256,
            config_sha256=config_sha256,
        )
        state.final_dir = final_dir = prototype_clustering_run_dir(
            storage_root, dataset_id, preprocessed_id, clustering_id
        )

        # 2. Idempotency: nếu đã có manifest hợp lệ (canonical payload
        #    khớp) và không force → skip.
        #
        #    R2 NOTE: `find_existing_clustering` raises Dev04CollisionError
        #    (manifest valid + payload khác) hoặc Dev04ManifestCorrupt
        #    (manifest invalid). Without --force-rerun, both errors
        #    propagate up (fail-closed). With --force-rerun, only
        #    Dev04ManifestCorrupt is caught below and converted into a
        #    safe recovery flow (move corrupt final -> backup, then
        #    proceed). Dev04CollisionError is NEVER caught here — that
        #    exception signals honest trial and classification; the user
        #    must investigate.
        try:
            existing = find_existing_clustering(
                storage_root, dataset_id, preprocessed_id, clustering_id,
                algorithm=algorithm,
                hyperparameters=hyperparameters,
                effective_seed=effective_seed,
                ml_dataset_sha256=ml_dataset_sha256,
                config_sha256=config_sha256,
            )
        except Dev04ManifestCorrupt as exc:
            # R2: corrupt manifest. Default behavior is fail-closed.
            # With --force-rerun, preserve corrupt final in a uniquely
            # identified backup location before proceeding with a fresh
            # staging + publish cycle.
            if not force_rerun:
                log.error(
                    "DEV-04: final_dir %s contains an unreadable or corrupt "
                    "manifest. Refusing to interpret as a valid run. "
                    "Pass --force-rerun to move the corrupt final to a "
                    "backup location and proceed with a fresh run.",
                    final_dir,
                )
                raise

            # R2: --force-rerun with corrupt manifest recovery.
            # Move corrupt final -> backup. Use suffix `_corrupt` to
            # distinguish from a normal force-rerun backup; cleanup
            # retains corrupt backups (R2 #5 / cleanup_pass branch 2).
            corrupt_backup_dir = base_dir / (
                f"{_BACKUP_PREFIX}{_RUN_UUID}{_CORRUPT_BACKUP_SUFFIX}"
            )
            try:
                os.rename(final_dir, corrupt_backup_dir)
            except OSError as rename_exc:
                # R2 #5: backup failed; stop with a clear error and
                # preserve all potentially recoverable artifacts.
                # Do NOT proceed with a fresh run.
                log.error(
                    "DEV-04: --force-rerun with corrupt manifest detected, "
                    "but moving final_dir %s to backup %s failed: %s. "
                    "Refusing to proceed; investigate manually.",
                    final_dir, corrupt_backup_dir, rename_exc,
                )
                raise Dev04StoragePathError(
                    f"Cannot move corrupt final_dir {final_dir!s} to "
                    f"backup {corrupt_backup_dir!s}: {rename_exc!s}. "
                    "Refusing to proceed; investigate manually."
                ) from rename_exc

            log.warning(
                "DEV-04: --force-rerun moved corrupt final_dir %s to "
                "backup %s for diagnosis; proceeding with a fresh run.",
                final_dir, corrupt_backup_dir,
            )
            state.backup_dir = corrupt_backup_dir
            state.backup_dir_from_corrupt_manifest = True
            # existing is None; fall through to staging prep.

        if existing is not None and not force_rerun:
            # 2a. EXPERIMENT_ID CONFLICT CHECK — đã phát hiện manifest
            #     idempotent hit; kiểm tra thêm experiment_id (nếu user
            #     đã truyền --experiment-id khác với manifest.experiment_id).
            #     Nếu khác → refuse (CLI exit non-zero với error
            #     "experiment_id conflict: existing=<X>, requested=<Y>")
            #     trừ khi --force-rerun đã được set.
            #     Lưu ý: user có thể KHÔNG truyền --experiment-id (CLI
            #     auto-derive từ algorithm + hyperparameters, mirror
            #     run_ml02_kmeans._build_experiment_id); trong trường hợp
            #     đó requested_experiment_id = auto_derived_experiment_id
            #     (xem §7.2.4).
            if requested_experiment_id is not None:
                existing_manifest = read_manifest_metadata(existing)
                existing_experiment_id = existing_manifest.get("experiment_id")
                if (
                    existing_experiment_id is not None
                    and existing_experiment_id != requested_experiment_id
                ):
                    raise Dev04ExperimentIdConflictError(
                        f"experiment_id conflict: existing="
                        f"{existing_experiment_id!r}, requested="
                        f"{requested_experiment_id!r}. Use --force-rerun to "
                        f"overwrite (will move final -> backup, then publish "
                        f"new artifact set with requested_experiment_id)."
                    )
            state.manifest_path = existing
            return existing   # CLI exit 0 với đường dẫn manifest cũ

        # 2b. Nếu --force-rerun + idempotent hit: KHÔNG early-return ở
        #     đây. Tiếp tục xuống Stage 3 (chuẩn bị staging + backup
        #     cũ). Khi --force-rerun được set, requested_experiment_id
        #     được dùng xuyên suốt cho cluster_labels_*, experiment_log_*,
        #     algorithm_output_*, clustering_manifest.experiment_id, log
        #     entries. ID nào trong manifest mới = ID user yêu cầu; ID
        #     trong manifest cũ = nằm trong backup_dir (bảo toàn).
        #     Cũng áp dụng cho R2 corrupt recovery (backup_dir đã được
        #     set ở trên với _corrupt suffix).

        # 3. Chuẩn bị staging và (nếu cần) backup.
        state.staging_dir = staging_dir = base_dir / f"{_STAGING_PREFIX}{_RUN_UUID}"

        # R2 #6/#7: nếu final_dir còn tồn tại (force-rerun path đã xóa
        # corrupt final ở block trên; idempotent path có existing is not
        # None và đã early-return; đây chỉ là force-rerun path bình
        # thường với valid manifest), atomically rename final_dir cũ
        # sang backup_dir. Stage 5b atomic publish (staging -> final) đảm
        # bảo KHÔNG có khoảng trống nào giữa backup và publish — chỉ
        # cần backup tồn tại nếu publish fail (F2/F4 window).
        if final_dir.exists():
            # R2 #6: collision detection KHÔNG bị bypass.
            # R2 #7: valid existing SUCCESS KHÔNG bị overwrite trước khi
            #         staging artifacts hoàn chỉnh + validated.
            normal_backup_dir = base_dir / f"{_BACKUP_PREFIX}{_RUN_UUID}"
            try:
                os.rename(final_dir, normal_backup_dir)
            except OSError as rename_exc:
                log.error(
                    "DEV-04: --force-rerun failed to snapshot final_dir "
                    "%s to backup %s: %s. Refusing to proceed.",
                    final_dir, normal_backup_dir, rename_exc,
                )
                raise Dev04StoragePathError(
                    f"Cannot snapshot final_dir {final_dir!s} to backup "
                    f"{normal_backup_dir!s}: {rename_exc!s}. Refusing to "
                    "proceed; user must investigate."
                ) from rename_exc
            # Only set state.backup_dir if not already set by corrupt recovery.
            if state.backup_dir is None:
                state.backup_dir = normal_backup_dir
                # backup_dir_from_corrupt_manifest remains False (normal).

        try:
            staging_dir.mkdir(parents=True, exist_ok=False)
        except (FileExistsError, OSError) as exc:
            log.error(
                "DEV-04: cannot create staging_dir %s: %s",
                staging_dir, exc,
            )
            raise

        # 4. Chạy experiment vào staging_dir (Stage 4 = runner.run).
        #    ML-01 chỉ thấy staging_dir, KHÔNG biết final_dir tồn tại.
        try:
            result = runner.run(
                matrix_df, customer_metadata_df,
                output_dir=staging_dir,
                # ... other kwargs as per §6.1
            )
            if result.status != "SUCCESS":
                raise Dev04RunError(
                    f"Algorithm fit failed: {result.error}"
                )
            # Stage 5: write clustering_manifest vào staging (atomic).
            manifest = build_clustering_manifest(
                result=result,
                clustering_id=clustering_id,
                preprocessed_id=preprocessed_id,
                ml_dataset_sha256=ml_dataset_sha256,
                config_sha256=config_sha256,
                # ... other fields per §6.4
            )
            write_clustering_manifest(
                manifest, staging_dir / "clustering_manifest.json"
            )
            # Verify tất cả artifact trong staging trước publish.
            verify_staging_artifacts(staging_dir, expected_manifest=manifest)
        except Exception as stage4_5_exc:
            # R1 + R2: Stage 4 / Stage 5 exception path.
            # The ordering below is load-bearing and is the single
            # source of truth for the failure window F11 (and F5);
            # see §5.3 sequence diagram Stage 4-FAIL branch, §6.5
            # R1 contract, and §6.7.3 retry semantics for cross-
            # references. The four steps MUST happen in this exact
            # order; do not interleave log statements, do not catch
            # _preserve_failed_log errors to mask the primary
            # exception, do not move the restore-backup step before
            # the preserve step.
            log.error(
                "DEV-04: Stage 4 / Stage 5 failed: %s",
                stage4_5_exc,
            )

            # Step 1 (R1): preserve any experiment_log_*.json from the
            # current staging directory into _failed_<clustering_id>_<run_uuid>/.
            # This MUST run before any staging unlink or backup
            # restoration; _preserve_failed_log reads from staging_dir
            # and writes to failed_tracking_dir. If preservation itself
            # fails (OSError, permission denied, disk full), the
            # failure is logged but NOT raised — the primary exception
            # stage4_5_exc must continue to propagate (per §6.5 R1
            # rule 4). The experiment_log is left in staging_dir if
            # possible (orphaned for manual recovery) so the audit
            # trail is not silently destroyed. failed_tracking_dir
            # will be retained by the outer cleanup_pass (R1 invariant)
            # and is NEVER unlinked.
            #
            # F1 invariant: `_preserve_failed_log` returns a
            # `PreservationStatus` (canonical 4-value enum). After
            # the call, we re-scan staging_dir to confirm whether any
            # `experiment_log_*.json` actually remain (defence-in-
            # depth: handle races, late writes, etc.). If the
            # PreservationStatus is "partial" or "failed" AND the
            # re-scan finds orphan logs, set
            # `state.unpreserved_log_in_staging = True` so that
            # `_cleanup_pass` (Step 4) does NOT unlink staging_dir.
            # This is the F1 invariant contract documented in §6.5
            # rule #7 and §6.7.3 failure window F14.
            state.failed_tracking_dir = (
                base_dir / f"{_FAILED_PREFIX}{clustering_id}_{_RUN_UUID}"
            )
            preservation_status = _preserve_failed_log(
                staging_dir=staging_dir,
                failed_tracking_dir=state.failed_tracking_dir,
                run_uuid=_RUN_UUID,
            )
            if preservation_status in ("partial", "failed"):
                # Re-scan to confirm orphan logs exist (defence-in-
                # depth; handles cases where the helper logged an
                # error but a subsequent shutil.move may have
                # completed mid-loop, or where race conditions
                # between ML-01 writes and our glob may differ).
                try:
                    remaining_logs = sorted(
                        staging_dir.glob("experiment_log_*.json")
                    )
                except OSError:
                    # If re-scan itself fails (e.g., staging_dir
                    # vanished between preservation and re-scan),
                    # err on the side of retention: assume orphan
                    # exists and set the flag.
                    remaining_logs = ["<rescan-failed>"]
                if remaining_logs:
                    state.unpreserved_log_in_staging = True
                    log.warning(
                        "DEV-04 (F1 invariant): _preserve_failed_log "
                        "returned %r and %d experiment_log_*.json "
                        "remain in staging_dir %s. Setting "
                        "state.unpreserved_log_in_staging=True so "
                        "_cleanup_pass (Step 4) retains staging_dir "
                        "for manual recovery. See §6.5 rule #7.",
                        preservation_status, len(remaining_logs),
                        staging_dir,
                    )

            # Step 2 (R2): if a normal backup exists from a valid-
            # manifest --force-rerun (state.backup_dir is set, NOT
            # from corrupt recovery which has its own suffix),
            # attempt to restore the recoverable SUCCESS to final_dir.
            # This is the recovery policy documented in §6.7.3 and
            # §6.7.4. The restore is best-effort: if it fails
            # (OSError, permission denied), the failure is logged
            # but the primary exception is still preserved (Step 3
            # always re-raises stage4_5_exc). The backup_dir is
            # intentionally left in place on restore failure so the
            # recoverable artifact is never silently destroyed —
            # cleanup_pass will retain it (publish_succeeded=False
            # path), and a subsequent run's recover_orphan_backups
            # can complete the restore.
            #
            # IMPORTANT: only restore for state.backup_dir set by
            # the NORMAL --force-rerun path. R2 corrupt-recovery
            # backup (state.backup_dir_from_corrupt_manifest=True)
            # is NOT restored here — the corrupt manifest is not a
            # valid SUCCESS to restore, and the suffix `_corrupt`
            # is intentionally retained for diagnosis (R2 #5).
            if (
                state.backup_dir is not None
                and state.backup_dir.exists()
                and not state.backup_dir_from_corrupt_manifest
            ):
                try:
                    os.rename(state.backup_dir, final_dir)
                except OSError as restore_exc:
                    log.error(
                        "DEV-04: failed to restore backup_dir %s -> final_dir "
                        "%s after Stage 4/5 failure: %s. backup_dir is left "
                        "in place for manual recovery (recover_orphan_backups "
                        "on next invocation can complete the restore).",
                        state.backup_dir, final_dir, restore_exc,
                    )

            # Step 3: re-raise the original run/publish exception.
            # The original stage4_5_exc is the primary exception;
            # it must propagate up so the CLI exits non-zero with a
            # clear error message. Any secondary failure from Step 1
            # or Step 2 is recorded in the logs (above) and audit
            # sidecar (_preservation_audit.txt) but is NOT raised —
            # replacing the primary exception with a secondary one
            # would hide the actual cause of the run failure.
            raise

        # 5. Stage 5b: atomic publish (staging → final). Đây là 1
        #    `os.rename` duy nhất — trên cùng filesystem là atomic.
        try:
            os.rename(staging_dir, final_dir)   # atomic on POSIX
            # staging_dir no longer exists; it is now final_dir.
            state.staging_dir = None
            state.publish_succeeded = True
            state.manifest_path = final_dir / "clustering_manifest.json"
        except Exception as stage5b_exc:
            # R3 invariant: a publish failure triggers the same R1 +
            # R2 recovery path as a Stage 4/5 failure. The four-step
            # ordering from the Stage 4/5 except block above applies
            # here verbatim, with stage5b_exc as the primary
            # exception. To avoid duplicating the four-step logic,
            # we re-raise into the same handler by NOT catching
            # here — but we DO want to mark publish_succeeded=False
            # so cleanup_pass retains the backup. The outer
            # `try/finally:` of run_dev04 (R3) will route through
            # _cleanup_pass, which inspects state.publish_succeeded.
            log.error(
                "DEV-04: atomic publish failed: %s. backup_dir will "
                "be retained by cleanup_pass (publish_succeeded=False).",
                stage5b_exc,
            )
            # state.publish_succeeded remains False (default).
            # state.backup_dir is already set from the normal
            # --force-rerun flow above; _cleanup_pass will retain
            # it because publish_succeeded=False.
            raise

        # 6. Cleanup backup (normal case --force-rerun success) is done
        #    by _cleanup_pass below in the finally block; we set the
        #    flag here so cleanup_pass knows it is safe to unlink.
        #    Corrupt backups (R2) are retained unconditionally.

        state.manifest_path = final_dir / "clustering_manifest.json"
        return state.manifest_path

    finally:
        # R3: TOP-LEVEL CLEANUP PASS.
        # Runs after normal completion OR after an unhandled exception.
        # Does NOT run after process crash (segfault, OOM, power loss) —
        # those scenarios rely on startup recovery on the NEXT run
        # (§6.7.4 "Cửa sổ lỗi nguy hiểm" + `recover_orphan_backups`).
        #
        # cleanup_pass MUST NOT raise; if it does, log and swallow so the
        # primary exception is preserved (R3 contract: cleanup failure
        # does NOT hide the primary exception).
        try:
            _cleanup_pass(state)
        except Exception as cleanup_exc:
            log.exception(
                "DEV-04 cleanup pass raised an exception (this is a bug "
                "in the cleanup logic, not in the algorithm run): %s. "
                "Primary exception (if any) is preserved.",
                cleanup_exc,
            )
            # Do NOT re-raise here — primary exception (if any) is being
            # unwound and would be shadowed. If no primary exception
            # (i.e., we are unwinding a normal return), Python will
            # discard this exception since we are in `finally:`. The
            # log entry is the only signal.
```

**Atomicity guarantee** — phạm vi được đảm bảo thực sự:

- `os.rename(src, dst)` trên cùng filesystem (POSIX) là một syscall
  `rename(2)` nguyên tử; kernel đảm bảo destination tồn tại với tên
  mới OR giữ nguyên tên cũ, KHÔNG trạng thái trung gian. **Chỉ áp
  dụng cho 1 syscall rename đơn lẻ** — KHÔNG đảm bảo atomicity cho
  chuỗi nhiều rename (`final → backup` rồi `staging → final`) coi
  như 1 transaction.
- Một run chỉ có DUY NHẤT một `os.rename` từ staging → final; đó
  là publish event duy nhất. Trước rename: final_dir cũ còn nguyên
  (nếu có). Sau rename: final_dir mới thay thế hoàn toàn.
- Backup_dir cũng là `os.rename`, nên khi `--force-rerun` chuẩn bị
  final_dir mới, final_dir cũ vẫn còn nguyên (ở backup) cho đến khi
  rename cuối cùng (staging → final) thành công.
- **`cluster_labels_*.parquet` / `algorithm_output_*.parquet` /
  `experiment_log_*.json` writers** (ML-01, READ-ONLY đối với DEV-04)
  **KHÔNG atomic** theo POSIX (xem §6.2.1 verified by code
  inspection): `df.to_parquet()` và `json.dump()` mở file ghi trực
  tiếp, có thể để lại partial file nếu crash giữa write. Mitigation:
  những file này được ghi trong staging_dir; staging KHÔNG được
  promote thành final trừ khi Stage 5b `os.rename` thành công
  (full atomic publish). Nếu crash trước publish, staging_dir có
  thể có partial files; final_dir hoàn toàn untouched → không có
  partial state nào được "publish" ra ngoài.
- **`clustering_manifest.json`** DEV-04 writer **atomic** (temp +
  rename — mirror `dataset_management.manifest.write_manifest`).
  Manifest atomic write đảm bảo nếu Stage 5 fail (e.g. exception
  trong serialization), KHÔNG có manifest partial ở final hoặc
  staging; chỉ có `*.tmp` được cleanup trong except block.

**Failure-window cumulative guarantee** — qua tất cả 10 failure
windows ở bảng trên (§6.7.4 "Cửa sổ lỗi nguy hiểm"):

- Old SUCCESS result (A) bảo toàn trong các window F1, F2, F3, F4, F5
  (idempotent skip hoặc restore từ backup hoặc keep nguyên ở final).
- New result (NEW) chỉ được "publish" sau khi `os.rename(staging,
  final)` thành công.
- Manifest không bao giờ tồn tại ở final nếu cluster_labels hoặc
  experiment_log chưa được write đầy đủ trong staging (vì
  manifest write xảy ra sau runner.run, và publish chỉ xảy ra
  sau manifest write thành công).
- Orphan backup / staging dirs KHÔNG BAO GIỜ bị cleanup cross-
  process; chỉ current `_RUN_UUID` được cleanup.

**Cross-run safety**:

- Mỗi run có `_RUN_UUID` riêng (set khi process start); staging_dir
  và backup_dir của run này chứa `_RUN_UUID` → cleanup pass chỉ
  unlink staging/backup dirs có `_RUN_UUID` của current process.
- Staging/backup dirs của process khác (khác `_RUN_UUID`) KHÔNG bị
  touch. Đây là pattern an toàn cho concurrent runs (mặc dù DEV-04
  scope là 1 user, 1 process; pattern vẫn hữu ích cho future
  parallel runs).
- Final subdirectories (không match `_staging_*` / `_backup_*`) KHÔNG
  BAO GIỜ bị touch bởi cleanup pass.

**Test bắt buộc** (xem §10 AC-12, AC-13 cho danh sách đầy đủ):

- `test_dev04_pipeline.py::test_crash_before_publish_preserves_old_success` —
  **CRITICAL cho P1 issue "--force-rerun không làm hỏng kết quả
  SUCCESS cũ"**. Chạy run A SUCCESS (snapshot SHA-256 manifest +
  cluster_labels). Sau đó chạy `--force-rerun` với cùng `clustering_id`
  + monkey-patch `os.rename(staging, final)` raise exception trước
  commit; verify (a) final_dir của A còn nguyên (manifest SHA không
  đổi, cluster_labels SHA không đổi); (b) backup_dir chứa bản
  backup từ final cũ; (c) staging_dir có thể bị cleanup hoặc còn
  sót (orphan loại (a) — không assert phải cleanup). KHÔNG test sẽ
  fail nếu expect cleanup ngay lập tức.
- `test_dev04_pipeline.py::test_crash_after_backup_before_publish_restored_on_next_run`
  — **CRITICAL cho P1 fix "backup recovery"**: mô phỏng crash trong
  cửa sổ `final → backup` rename thành công nhưng `staging → final`
  chưa chạy. Test sequence:
    (a) Chạy run A SUCCESS (snapshot SHA-256 manifest + cluster_labels).
    (b) Chạy `--force-rerun` + monkey-patch `os.rename(staging, final)`
        raise exception SAU khi `final → backup` rename đã chạy
        (dùng side_effect list: [success, raise] để pass rename
        đầu, fail rename sau).
    (c) Verify trạng thái đĩa: `final_dir` KHÔNG tồn tại;
        `backup_dir/_backup_<uuid>/<clustering_id>/` chứa toàn bộ
        artifact cũ.
    (d) Gọi CLI lại (KHÔNG `--force-rerun`; chỉ same config) — startup
        recovery pass sẽ restore `backup_dir/<clustering_id>/` →
        `final_dir` atomic trước khi main pipeline chạy.
    (e) Verify sau khi CLI exit 0 (idempotent skip): `final_dir`
        tồn tại với manifest SHA + cluster_labels SHA KHÔNG ĐỔI
        so với snapshot ở (a); `backup_dir` đã được cleanup.
- `test_dev04_pipeline.py::test_recover_orphan_backups_no_op_when_final_exists`
  — backup_dir cũ có `<clustering_id>/` nhưng `final_dir` cũng đã
  tồn tại (manifest hợp lệ — e.g. đã được restore thủ công trước);
  recovery pass KHÔNG động vào (skip).
- `test_dev04_pipeline.py::test_force_rerun_safety` — chạy run A
  SUCCESS; mô phỏng crash giữa Stage 4 và Stage 5b (monkey-patch
  `os.rename` raise trước khi commit); verify final_dir của A còn
  nguyên (SHA-256 manifest không đổi, cluster_labels không bị
  partial), staging_dir được cleanup.
- `test_dev04_storage.py::test_staging_isolation` — chạy run A;
  ngay sau khi Stage 4 xong (manifest chưa publish), check rằng
  final_dir vẫn là bản cũ (nếu có) hoặc không tồn tại.
- `test_dev04_storage.py::test_cleanup_pass_only_removes_own_run` —
  pre-create một `_staging_<other_run_uuid>/` dir giả lập của process
  khác; chạy run hiện tại; verify dir giả lập vẫn còn.
- `test_dev04_storage.py::test_atomic_publish_whole_directory` —
  chạy run full; verify rằng final_dir chứa đủ 4-5 files
  (cluster_labels, experiment_log, [algorithm_output], manifest,
  log) cùng lúc (mtime gần nhau), không có partial state.
- `test_dev04_pipeline.py::test_staging_and_backup_cleanup_after_success`
  — chạy `--force-rerun` SUCCESS; verify cả staging_dir lẫn
  backup_dir đều được unlink.
- `test_dev04_pipeline.py::test_orphan_final_no_manifest_recovery` —
  pre-create final subdirectory của `clustering_id` X với contents
  rỗng (no manifest, no parquet); gọi CLI với clustering_id X; verify
  CLI move final cũ → backup, tạo staging mới, publish atomic;
  backup unlink.
- `test_dev04_pipeline.py::test_experiment_id_conflict_detected` —
  pre-create final subdirectory với manifest có `experiment_id=A1`;
  gọi CLI với cùng clustering_id nhưng `--experiment-id=A2`; verify
  CLI exit non-zero với error `experiment_id conflict: existing=A1,
  requested=A2`; gọi CLI lại với `--experiment-id=A2 --force-rerun`;
  verify SUCCESS (override qua staging/atomic publish).

**Tóm tắt** (gộp §6.7.1 + §6.7.3 + §6.7.4):

- Same input + same effective config → idempotent skip (unless
  `--force-rerun`).
- Different config → khác `clustering_id` → khác subdirectory →
  artifact co-exist song song, không bao giờ overwrite.
- Mọi write của 1 run cô lập trong staging; final chỉ được touch
  bằng 1 `os.rename` nguyên tử.
- Cleanup pass chỉ xóa staging/backup dirs của run hiện tại.
- `--force-rerun` an toàn: backup_dir giữ final cũ nguyên vẹn cho
  đến khi publish thành công; nếu crash trước publish, backup_dir
  restore về final_dir (atomic rename) hoặc được giữ lại để user
  phục hồi thủ công.
- Custom `--experiment-id` khác với manifest đã tồn tại → CLI exit
  non-zero (refuse), trừ khi `--force-rerun`.

---

## 7. Algorithm registry và parameter configuration

### 7.1. Algorithm registry (read-only)

DEV-04 dispatches algorithms via `AlgorithmRegistry` (ML-01). The registry already contains 5 entries:

| Algorithm name | Family | Adapter | `supports_random_state()` |
|---|---|---|---|
| `kmeans` | HARD | `KMeansAdapter` (ML-02) | `True` |
| `agglomerative` | HARD | `AgglomerativeAdapter` (ML-03) | `False` (deterministic) |
| `dbscan` | DENSITY_BASED | `DBSCANAdapter` (ML-04) | `False` (deterministic) |
| `gmm` | MODEL_BASED | `GMMAdapter` (ML-05) | `True` |
| `fuzzy_cmeans` | FUZZY | `FuzzyCMeansAdapter` (ML-06) | `True` |

DEV-04 MUST NOT add, remove, or re-register any algorithm. K-Medoids is **OUT OF SCOPE** per ADR-0003 and is NOT in the registry; if user passes `--algorithm kmedoids`, `AlgorithmRegistry.get("kmedoids")` raises `AlgorithmRegistryError` which propagates up as a runner error (DEV-04 translates to FAILED status + clear error message).

### 7.2. Parameter configuration

#### 7.2.1. Per-algorithm hyperparameters (in `configs/dev04_clustering.yaml`)

```yaml
dev04_clustering:
  algorithms:
    kmeans:
      enabled: true
      n_clusters: 4
      init: "k-means++"
      n_init: 10
      max_iter: 300
      tol: 1.0e-4
    agglomerative:
      enabled: true
      n_clusters: 4
      linkage: "ward"
      metric: "euclidean"
      compute_distances: true
    dbscan:
      enabled: true
      eps: 0.5
      min_samples: 5
      metric: "euclidean"
    gmm:
      enabled: true
      n_components: 4
      covariance_type: "full"
      init_params: "kmeans"
      tol: 1.0e-3
      reg_covar: 1.0e-6
      max_iter: 100
      n_init: 1
    fuzzy_cmeans:
      enabled: true
      n_clusters: 4
      fuzziness: 2.0
      max_iter: 300
      error: 1.0e-4
```

#### 7.2.2. CLI overrides (optional)

CLI flags override YAML values:
- `--n-clusters <int>` → K-Means `n_clusters`, Agglomerative `n_clusters`, FCM `n_clusters`
- `--n-components <int>` → GMM `n_components`
- `--init {k-means++,random}` → K-Means `init`
- `--n-init <int>` → K-Means `n_init`
- `--max-iter <int>` → K-Means / GMM / FCM `max_iter`
- `--tol <float>` → K-Means / GMM `tol`
- `--linkage {ward,complete,average,single}` → Agglomerative `linkage`
- `--metric {euclidean,manhattan,cityblock,cosine,chebyshev,l1,l2}` → Agglomerative / DBSCAN `metric`
- `--compute-distances {true,false}` → Agglomerative `compute_distances`
- `--eps <float>` → DBSCAN `eps`
- `--min-samples <int>` → DBSCAN `min_samples`
- `--covariance-type {full,tied,diag,spherical}` → GMM `covariance_type`
- `--init-params {kmeans,random}` → GMM `init_params`
- `--reg-covar <float>` → GMM `reg_covar`
- `--fuzziness <float>` → FCM `fuzziness` (m; must be > 1)
- `--error <float>` → FCM `error` (convergence threshold)

CLI override is **optional** (YAML is single source of truth; mirror DEV-02 / DEV-03 pattern).

#### 7.2.3. Random seed

3-level resolution (mirror ML-01 `resolve_random_seed`):

1. CLI `--seed <int>` (per-experiment override) → highest priority
2. YAML `framework.random_seed.per_algorithm_override.<algo>` (per-algorithm override)
3. YAML `framework.random_seed.default` (framework default) → lowest priority

If algorithm does NOT consume `random_state` (Agglomerative, DBSCAN), the runner sets `seed_to_pass = None` regardless of YAML/CLI seed (truthful, per `supports_random_state() == False`).

#### 7.2.4. Experiment ID

Built from `algorithm + hyperparameters` (mirror `run_ml02_kmeans.py::_build_experiment_id`):

```
<algo>-k<n>-<init>-ninit<n>-maxiter<n>-seed<cfg|int>
```

Example: `dev04-kmeans-k4-kmeansplusplus-ninit10-maxiter300-seedcfg`.

Alternative: user can pass `--experiment-id <custom>` to override.

### 7.3. Configuration files

- `configs/dev04_clustering.yaml` (NEW) — DEV-04 config (lưu ý: KHÔNG
  có key `storage.storage_root`; storage root lấy từ DEV-02 config
  theo §6.3):
  - `dev04_clustering.algorithms.<name>.*` — per-algorithm hyperparameters
  - `dev04_clustering.random_seed.{default, per_algorithm_override}` — seed policy
  - `dev04_clustering.logging.{level, log_dir_relative, format, emit_to_console}` — logging policy
  - `dev04_clustering.storage.{output_dir_relative, emit_algorithm_output}` — output policy (relative to storage_root, NOT override of root)
  - `dev04_clustering.research_safety.{readonly_paths, never_promote_to_research}` — defence-in-depth
  - `dev04_clustering.validation.{min_samples, min_features, require_no_nan, require_no_inf, require_all_numeric, exclude_customer_id_from_features}` — delegate to ML-01 (these mirror `FrameworkConfig.validation.*` from `clustering.yaml`)
- `configs/clustering.yaml` (READ-ONLY; ML-01 framework config) — re-used for the framework `FrameworkConfig` (validation, output filename templates, logging level, platform metadata). The `framework.input.*` and `framework.output.artifacts_dir` fields are NOT used by DEV-04 (DEV-04 overrides with its own paths); the rest of the framework config IS used (validation policy, output filename templates, log format, library_versions snapshot).
- `configs/dev02_dataset_management.yaml` (READ-ONLY; loaded bởi DEV-02, nhưng DEV-04 cũng dùng qua `customer_segmentation.dataset_management.storage.resolve_storage_root` để resolve `storage_root`).

---

## 8. Experiment execution, result persistence và logging

### 8.1. Experiment execution

Single experiment per CLI invocation. The flow (mirror §5.3 sequence):
**mọi file được ghi vào staging_dir trước, chỉ atomic-publish sang
final_dir ở cuối run** (xem §6.7.4). **Toàn bộ flow được wrap trong
top-level `try/finally:` block** (R3); cleanup pass chạy ở `finally:`
(xem `_cleanup_pass` §6.7.4 pseudocode).

1. CLI parse: `--dataset-id`, `--preprocessed-id`, `--algorithm`, hyperparameters, `--seed`, `--experiment-id`, `--force-rerun`, `--config`, `--framework-config`.
2. Load `configs/dev04_clustering.yaml` (DEV-04 config).
3. Load `configs/clustering.yaml` (ML-01 framework config) via `load_framework_config()`.
4. Read `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json` (verify `preprocessed_scope == PREPROCESSED_PROTOTYPE`).
5. Locate ML Dataset parquet under the same directory.
6. Load ML Dataset → split into `matrix_df` (drop CustomerID) + `customer_metadata_df` (CustomerID only).
7. Compute matrix + customer_metadata SHA-256 (for `input_identity`).
8. **Compute `clustering_id`** (canonical, xem §6.4.1) từ effective hyperparameters + seed resolved + ml_dataset_sha256 + config_sha256.
9. **Idempotency check** (§6.7.1): `find_existing_clustering(clustering_id)`.
    - Manifest valid + canonical payload khớp + KHÔNG `--force-rerun` → CLI exit 0 với đường dẫn manifest cũ.
    - Manifest valid + canonical payload khớp + `--force-rerun` → tiếp tục Stage 10 (staging/publish).
    - Manifest missing → tiếp tục Stage 10 (new run).
    - **R2**: Manifest corrupt + KHÔNG `--force-rerun` → CLI exit non-zero (fail-closed).
    - **R2**: Manifest corrupt + `--force-rerun` → atomic rename `final_dir` → `_backup_<uuid>_corrupt/`; tiếp tục Stage 10.
    - Manifest valid + canonical payload KHÁC (collision) → CLI exit non-zero với `Dev04CollisionError` (R2 #6 — KHÔNG BAO GIỜ catch bởi recovery path).
10. **Prepare staging_dir + (nếu cần) backup_dir** (§6.7.4): nếu `final_dir` đã tồn tại (force-rerun path hoặc R2 corrupt recovery), `os.rename(final_dir, backup_dir)` (atomic; với R2 thêm suffix `_corrupt`). Tạo `staging_dir` mới.
11. Build `ExperimentSpec(experiment_id, algorithm, hyperparameters, seed_override)`.
12. Build `ExperimentRunner(framework_cfg, spec, config_source=path, config_text=yaml_text)`.
13. Call `runner.run(matrix_df, customer_metadata_df, input_sha256=..., input_path=..., metadata_path=..., output_dir=staging_dir)`. ML-01 chỉ thấy staging_dir.
14. Receive `ExperimentResult`. Inspect `status` (SUCCESS / FAILED).
15. Nếu SUCCESS: build DEV-04 `clustering_manifest.json` atomic write vào `staging_dir`; verify tất cả artifact; `os.rename(staging_dir, final_dir)` (atomic publish); cleanup pass (R3) unlink backup_dir nếu `publish_succeeded=True` AND KHÔNG phải corrupt recovery backup.
16. Nếu FAILED: **4-step exception path** (R1 + R2 explicit ordering; xem §6.5 + §6.7.4 pseudocode cho chi tiết từng bước):
    1. **Step 1 (R1):** `_preserve_failed_log` move `experiment_log_*.json` từ staging → `_failed_<clustering_id>_<run_uuid>/` (RETAINED cho audit, KHÔNG BAO GIỜ unlink); audit sidecar `_preservation_audit.txt` ghi cùng. KHÔNG publish `cluster_labels_*.parquet` / `algorithm_output_*.parquet` / `clustering_manifest.json`. Nếu preserve fail: log warning, leave log in staging nếu có thể, KHÔNG raise. **`_preserve_failed_log` return `PreservationStatus` ∈ {"ok", "partial", "no_log", "failed"}`**; nếu status ∈ {"partial", "failed"} VÀ re-scan staging_dir xác nhận còn `experiment_log_*.json`, exception handler set `state.unpreserved_log_in_staging = True` (F1 invariant).
    2. **Step 2 (R2):** Nếu `state.backup_dir` được set bởi normal `--force-rerun` (KHÔNG phải corrupt recovery), attempt `os.rename(backup_dir, final_dir)` (atomic) để restore recoverable SUCCESS. corrupt-recovery backup KHÔNG restore. Nếu restore fail: log error, leave backup_dir in place cho `recover_orphan_backups` / manual recovery.
    3. **Step 3:** Re-raise original exception (primary). KHÔNG raise secondary failure từ Step 1 / Step 2.
    4. **Step 4:** Cleanup pass (R3) chạy trong `finally:` của `run_dev04()`; retain `_failed_*/` (R1), retain backup_dir (R2 publish_succeeded=False path), retain `_backup_*_corrupt/` (R2 audit), **và NẾU `state.unpreserved_log_in_staging == True` (F1 invariant) thì KHÔNG unlink `staging_dir`** (retain cho manual recovery vì chứa unpreserved FAILED log). KHÔNG touch other runs' dirs. KHÔNG hide primary exception. CLI exit non-zero.
17. **R3** Cleanup pass chạy trong `finally:` của `run_dev04()`: scoped theo `_RUN_UUID`; retain `_failed_*/` (R1), retain `_backup_*_corrupt/` (R2); KHÔNG touch other runs' dirs; KHÔNG hide primary exception nếu cleanup cũng fail. Plan KHÔNG cam kết cleanup chạy sau abrupt crash — đó là `recover_orphan_backups` territory (next invocation).
18. Build `<clustering_id>.log` (per-stage entries; nằm trong final_dir nếu SUCCESS, trong staging trước unlink nếu FAILED — debug only).

### 8.2. Result persistence

| Outcome | Files written (cuối run, sau publish) |
|---|---|
| SUCCESS | Tất cả 4-5 file ở `<base>/clustering/<clustering_id>/`: `cluster_labels_<experiment_id>.parquet` (ML-01; non-atomic) + `experiment_log_<experiment_id>.json` (ML-01; non-atomic) + (conditional) `algorithm_output_<experiment_id>.parquet` (ML-01; non-atomic) + `clustering_manifest.json` (DEV-04; **atomic**) + `<clustering_id>.log` (DEV-04; FileHandler + flush). Tất cả publish cùng lúc bằng 1 `os.rename` ở §6.7.4 Stage 5b. |
| FAILED (validation or algorithm) | (R1) **`experiment_log_<experiment_id>.json` PRESERVED ở `<base>/clustering/_failed_<clustering_id>_<run_uuid>/`** (move từ staging trước unlink). Audit sidecar `_preservation_audit.txt` ghi cùng. KHÔNG có `cluster_labels_*.parquet`, `algorithm_output_*.parquet`, `clustering_manifest.json`, hoặc `<clustering_id>.log` ở final. Staging_dir cleaned up sau khi move log. Backup_dir restore nếu có `--force-rerun` (old final unchanged). CLI exit non-zero. `_failed_*/` retained cho audit (R1). |
| Idempotent skip (default re-run) | CLI exit 0; existing manifest_path trả về; KHÔNG tạo staging. |
| `--force-rerun` SUCCESS (normal path) | old final_dir move sang `_backup_<run_uuid>/` (atomic rename); staging_dir mới; publish atomic; cleanup pass unlink `backup_dir` (R3 + `publish_succeeded=True`). Old final chỉ bị overwrite bởi publish event. |
| `--force-rerun` với corrupt manifest (R2) | (R2) corrupt final move sang `_backup_<run_uuid>_corrupt/` (atomic rename; retention cho audit); staging_dir mới; publish atomic; cleanup pass retain `backup_dir` (R2 invariant + R3 `backup_dir_from_corrupt_manifest=True`). New SUCCESS published ở final_dir. Corrupt backup retained cho manual review. |

**R3 top-level cleanup invariant**: cleanup pass chạy trong `finally:`
của `run_dev04` (KHÔNG chỉ success path). Cleanup unlink:
- `_staging_<run_uuid>/` nếu còn.
- `_backup_<run_uuid>/` nếu `publish_succeeded=True` AND
  `backup_dir_from_corrupt_manifest=False`.
- KHÔNG BAO GIỜ unlink `_backup_<run_uuid>_corrupt/` (R2 retain).
- KHÔNG BAO GIỜ unlink `_failed_<clustering_id>_<run_uuid>/` (R1 retain).

**Atomic write status (verified by Phase 1 code inspection)**:

- **`cluster_labels_*.parquet`** + **`algorithm_output_*.parquet`** — viết bởi ML-01 `write_cluster_labels` / `write_algorithm_output` (`customer_segmentation.clustering.artifacts`); dùng `df.to_parquet(output_path, index=False)` trực tiếp — **không atomic** theo POSIX. ML-01 là research core (READ-ONLY đối với DEV-04); không thể sửa trong DEV-04 scope.
- **`experiment_log_*.json`** — viết bởi ML-01 `write_experiment_log` (`customer_segmentation.clustering.logging_utils`); dùng `open("w")` + `json.dump()` — **không atomic**. Cùng lý do trên.
- **`clustering_manifest.json`** — DEV-04 PHẢI atomic write (temp + rename) vào staging; mirror `dataset_management.manifest.write_manifest` / `prototype.preprocessing.manifest.write_preprocessed_manifest`. Xem §6.2.1.
- **`<clustering_id>.log`** — DEV-04 dùng `logging.FileHandler` + explicit `flush()` sau mỗi stage transition. Không 100% atomic ở mức OS-syscall nhưng đủ cho prototype scale.
- **`os.rename(staging_dir, final_dir)`** (§6.7.4 Stage 5b) — atomic ở mứp syscall (`rename(2)` trên POSIX, cùng filesystem). Đây là publish event duy nhất; sau rename, mọi file trong final_dir là coherent (cùng publish). Đây là lý do `cluster_labels_*.parquet` non-atomic ở ML-01 vẫn an toàn: nếu parquet partial ở staging, Stage 5b chưa xảy ra → final chưa bị touch.

**Cross-run safety**: cleanup pass (R3) chỉ unlink staging/backup/failed
dirs của current run (xác định bằng `run_uuid`); KHÔNG BAO GIỜ xóa
file khác (xem §6.7.4 cleanup_pass pseudocode). Staging/backup/failed
dirs của process khác (khác `run_uuid`) KHÔNG bị touch. KHÔNG đụng
đến `_backup_<run_uuid>_corrupt/` của current run (R2 retain invariant).

### 8.3. Logging

Per-stage log file `<clustering_id>.log` (under
`data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/`
cho SUCCESS; dưới staging trước unlink cho FAILED) với Python
`logging` module:

- Format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`
- Level: configurable via YAML (default INFO)
- Per-stage entries:
  - `stage_0.start / stage_0.complete` — CLI parse + config load
  - `stage_1.start / stage_1.complete` — DEV-03 lookup
  - `stage_2.start / stage_2.complete` — matrix/metadata split
  - `stage_3.start / stage_3.complete` — build ExperimentSpec + Runner + staging prep
  - `stage_4.start / stage_4.complete (or FAILED)` — runner.run() (algorithm fit into staging_dir)
  - `stage_5.start / stage_5.complete (or FAILED)` — write clustering_manifest (atomic, in staging)
  - `stage_5b.start / stage_5b.complete` — atomic publish (`os.rename` staging → final)
  - `stage_6.start / stage_6.complete` — finalize log
- Each entry includes: timestamp, stage name, level, key metrics (row counts, columns, durations, algorithm, seed, n_clusters).
- FAILURE entries include stack trace.
- The experiment log JSON (`experiment_log_<experiment_id>.json`) is a SEPARATE artifact written by the ML-01 framework's `write_experiment_log()` (full `ExperimentResult` payload). The per-stage `<clustering_id>.log` is the DEV-04 wrapper's per-stage log.

### 8.4. Reprocessing safety

Cross-reference §6.7 (idempotency + collision + retry + staging/publish)
cho toàn bộ semantics. Tóm tắt:

- Re-running DEV-04 với cùng `(preprocessed_id, algorithm,
  hyperparameters, seed_policy + seed, ml_dataset_sha256,
  config_sha256)` → cùng `clustering_id` → CLI early-return với
  manifest hiện có (không re-fit). Truyền `--force-rerun` để bypass
  (xem §6.7.4 cho staging/atomic publish an toàn).
- Same `clustering_id` với outcome khác nhau (e.g. SUCCESS trước, FAIL
  sau khi sửa data nhưng `ml_dataset_sha256` đổi → `clustering_id` đổi
  → không xung đột).
- Different config (khác `--n-clusters`, etc.) → `clustering_id` khác
  → khác subdirectory → 2 bộ artifact co-exist song song; KHÔNG
  overwrite.
- Failed run KHÔNG để partial state ở final_dir (vì mọi write trong
  staging; final chỉ được touch bằng 1 `os.rename` nguyên tử).
  **R1**: `experiment_log_*.json` được PRESERVE ở
  `_failed_<clustering_id>_<run_uuid>/` cho audit (xem §6.5 + §6.7.3
  + §6.7.4 cho 4-step exception path ordering).
- `--force-rerun` an toàn: backup_dir giữ final cũ nguyên cho đến
  khi publish atomic thành công; nếu crash trước publish, final cũ
  restore từ backup. **R2**: nếu manifest corrupt, `--force-rerun`
  move corrupt final → `_backup_<run_uuid>_corrupt/` (retained cho
  audit); fresh run proceed. Default behavior (không `--force-rerun`)
  với manifest corrupt: fail-closed CLI exit non-zero.
- **R3**: Toàn bộ run wrapped trong top-level `try/finally:` (§6.7.4
  pseudocode); cleanup pass scoped theo `_RUN_UUID` chạy trong
  `finally:` (R3 invariants: retain `_failed_*/` (R1), retain
  `_backup_*_corrupt/` (R2), KHÔNG touch other runs' dirs, KHÔNG
  hide primary exception). Plan KHÔNG cam kết cleanup chạy sau
  abrupt crash.
- **F1 invariant (cleanup MUST NOT delete staging chứa unpreserved
  FAILED log)**: nếu `_preserve_failed_log` trả về
  `PreservationStatus ∈ {"partial", "failed"}` (move không thành
  công hết) VÀ re-scan staging_dir xác nhận còn
  `experiment_log_*.json`, exception handler set
  `state.unpreserved_log_in_staging = True`. Cleanup pass
  (`_cleanup_pass` trong §6.7.4) PHẢI skip `shutil.rmtree(staging_dir)`
  trong trường hợp này; staging_dir được retain cho manual
  recovery. Xem §6.5 rule #7, §6.7.3 failure window F14, và
  AC-5 #24e + AC-12 #73h trong §10.

Phần này trước đây (plan nháp) chỉ có 2 dòng rất sơ lược; nay đã
được nâng cấp thành §6.7 đầy đủ với lookup function, collision math,
và retry policy table.

---

## 9. Prototype / research storage isolation

### 9.1. Hard rule — never write to research artefacts

DEV-04 **must not** write, mutate, delete, or rename anything under:

- `data/raw/primary/**`
- `data/raw/backup/**`
- `data/processed/**` (FE-06 outputs: `final_clustering_dataset.parquet`, `customer_metadata.parquet`, `clustering_experiments/`, etc.)
- `reports/**` (FE-01..06, EXP-01..05, EVA-01..03, CP-01..05 evidence; `reports/ml01/`, `reports/ml02/`, ..., `reports/ml06/`)
- `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's)
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json` (DEV-03's)
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_*.parquet` (DEV-03's ML Dataset)
- `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_*.parquet` (DEV-03's intermediate cleaned)

**Enforcement**:

- **Storage root constraint**: the only writable location is `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/`. The storage root is fixed in config (no CLI override; mirror DEV-02 §3.5 disposition).
- **Import-blocklist test** asserts that `prototype.clustering` does NOT import from any research module that has side effects on research paths. It MAY import from `customer_segmentation.clustering.*` (READ-ONLY use; the framework is read-only for I/O as documented in §3.6).
- **Research-safety test** snapshots the 4 research paths + DEV-02 manifest + DEV-03 manifest + DEV-03 ML Dataset SHA-256 + mtime before and after, asserts unchanged.

### 9.2. Read-side access policy

DEV-04 inherits the DEV-02 / DEV-03 read-isolation model: the user must have read access to:

- DEV-03 ML Dataset parquet (read by DEV-04 to load `matrix_df` + `customer_metadata_df`)
- DEV-03 preprocessed_manifest.json (read for provenance pointer)
- DEV-02 manifest.json (read for dataset identity)
- Research core modules (`customer_segmentation.clustering.*`) (read for orchestration)

DEV-04 does NOT have direct access to `data/raw/primary/`, `data/processed/`, or `reports/`. The DEV-03 ML Dataset is the only input. This is a **strict boundary**: DEV-04 cannot bypass DEV-03 to read raw or research data.

### 9.3. Source-path portability

The DEV-04 manifest inherits the DEV-02 / DEV-03 manifest source-path policy: `preprocessed_id` là portable (content-addressed; canonical key 1/7); `input_identity.input_path` và `input_identity.metadata_path` được ghi absolute paths (mirror ML-01 pattern; audit only). **Trong per-clustering_id subdirectory layout, các đường dẫn artifact trong manifest là relative** (vd. `cluster_labels_<experiment_id>.parquet`, không có leading `clustering/<clustering_id>/`); việc resolve thành absolute path thuộc về caller (DEV-05+ hoặc user). Điều này giữ manifest portable nếu user di chuyển prototype sub-tree (vd. copy sang dataset khác, archive).

### 9.4. Git-ignore

`data/prototype/**` is already git-ignored (per `.gitignore` line covering `data/prototype/**`, inherited from DEV-02 §7.3 fix). DEV-04 writes into the same `data/prototype/datasets/...` sub-tree, nên staging dirs (`_staging_*`), backup dirs (`_backup_*`) và final subdirs (`<clustering_id>/`) đều tự động git-ignored. Không cần thay đổi `.gitignore`.

### 9.5. Promotion to research evidence (forbidden)

Per AGENTS.md §2.10 + ADR-0005: DEV-04 output is **NEVER** promoted to research evidence. The manifest's `research_safety` block hard-codes:

- `automatically_promoted_to_research: false`
- `appeared_in_research_evidence: false`
- `scope: "CLUSTERED_PROTOTYPE"`

Promotion is owned by mentor + ADR (per AGENTS.md §2.10). If a future phase wants to use a prototype clustering result as research evidence, a new ADR + reproducibility check is required (this is OUT OF DEV-04 scope).

---

## 10. Acceptance Criteria mapping

Jira AC: 6 items. DEV-04 expands them into **95 verifiable criteria**
(xem bảng tổng kết ở cuối §10; baseline 76 từ plan ban đầu + 19
mới cho canonical JSON spec, atomic publish, staging/publish,
per-clustering_id subdirectory, path containment, collision
detection, manifest corruption, recovery, experiment_id conflict,
seed_policy canonical whitelist, extract subset identity).

### AC-1: Có thể chọn Algorithm (Jira AC #1)

| # | Criterion | Verification |
|---|---|---|
| 1 | `python -c "from customer_segmentation.prototype.clustering import run_clustering_experiment"` exits 0. | Smoke import. |
| 2 | `AlgorithmRegistry.list_registered()` returns 5 names: `[agglomerative, dbscan, fuzzy_cmeans, gmm, kmeans]` (K-Medoids NOT included per ADR-0003). | `tests/test_dev04_registry.py::test_algorithm_registry_5_names`. |
| 3 | All 5 algorithms can be selected via `--algorithm <name>` CLI flag. | `tests/test_dev04_pipeline.py::test_each_algorithm_dispatch`. |
| 4 | `--algorithm kmedoids` → `AlgorithmRegistryError` (K-Medoids OUT OF SCOPE per ADR-0003). | `tests/test_dev04_pipeline.py::test_kmedoids_rejected`. |
| 5 | `--algorithm unknown_xyz` → `AlgorithmRegistryError` (registry refuses unknown). | `tests/test_dev04_pipeline.py::test_unknown_algorithm_rejected`. |

### AC-2: Có thể cấu hình (Parameters) (Jira AC #2)

| # | Criterion | Verification |
|---|---|---|
| 6 | `configs/dev04_clustering.yaml` exists; has blocks: `dev04_clustering.{algorithms.<5_names>, random_seed, logging, storage, research_safety, validation}`. | `test_dev04_config.py::test_yaml_schema_blocks_present`. |
| 7 | Each algorithm's working hyperparameters are surfaced in the YAML (mirror `configs/clustering.yaml::algorithms.*`). | `test_dev04_config.py::test_per_algorithm_hyperparameters_present`. |
| 8 | CLI flag `--n-clusters <int>` overrides YAML for K-Means / Agglomerative / FCM. | `test_dev04_pipeline.py::test_cli_override_n_clusters`. |
| 9 | CLI flag `--seed <int>` overrides YAML for K-Means / GMM / FCM (algorithms with `supports_random_state() == True`). | `test_dev04_pipeline.py::test_cli_override_seed`. |
| 10 | CLI flag `--seed` is **ignored** for Agglomerative / DBSCAN (deterministic; truthful per `supports_random_state() == False`). | `test_dev04_pipeline.py::test_seed_ignored_for_deterministic`. |
| 11 | Random seed resolution: 3-level (CLI > per-algo YAML > framework default) per `resolve_random_seed`. | `test_dev04_pipeline.py::test_seed_resolution_three_level`. |

### AC-3: Chạy được (Jira AC #3)

| # | Criterion | Verification |
|---|---|---|
| 12 | End-to-end happy path: DEV-02 import → DEV-03 preprocess → DEV-04 cluster (K-Means, k=4, seed=42) → all 4-5 artefact files written. | `test_dev04_pipeline.py::test_end_to_end_kmeans_happy_path`. |
| 13 | End-to-end happy path: same for Agglomerative / DBSCAN / GMM / FCM. | `test_dev04_pipeline.py::test_end_to_end_each_algorithm` (parametrised). |
| 14 | Validation failures abort BEFORE `adapter.fit()` (no partial artefact). | `test_dev04_pipeline.py::test_validation_failure_aborts_before_fit`. |
| 15 | Algorithm fit failures → `status: FAILED` in experiment_log; NO `cluster_labels`, NO `algorithm_output`, NO `clustering_manifest.json`. | `test_dev04_pipeline.py::test_algorithm_failure_no_partial_artefact`. |
| 16 | CustomerID NEVER appears in the matrix passed to `ExperimentRunner.run()`. | `test_dev04_pipeline.py::test_customer_id_dropped_from_matrix` (verify `matrix_df.columns` does NOT include CustomerID; verify `customer_metadata_df.columns == ['CustomerID']`). |
| 17 | `validate_clustering_matrix` (ML-01) is invoked by the runner and its results are recorded in the experiment log. | `test_dev04_pipeline.py::test_matrix_validation_invoked`. |

### AC-4: Có Cluster Labels (Jira AC #4)

| # | Criterion | Verification |
|---|---|---|
| 18 | `cluster_labels_<experiment_id>.parquet` is written under prototype clustering dir on SUCCESS. | `test_dev04_artifacts.py::test_cluster_labels_written`. |
| 19 | Schema: `CustomerID` + `ClusterLabel` (int64) + `IsNoise` (bool); GMM adds `Probability_k`; FCM adds `Membership_k`. | `test_dev04_artifacts.py::test_cluster_labels_schema_per_algorithm` (parametrised). |
| 20 | DBSCAN noise label `-1` is preserved verbatim. | `test_dev04_artifacts.py::test_dbscan_noise_label_preserved`. |
| 21 | GMM soft probabilities preserved as `Probability_0`..`Probability_{K-1}` columns. | `test_dev04_artifacts.py::test_gmm_soft_probabilities_columns`. |
| 22 | FCM soft membership preserved as `Membership_0`..`Membership_{c-1}` columns. | `test_dev04_artifacts.py::test_fcm_soft_membership_columns`. |
| 23 | `algorithm_output_<experiment_id>.parquet` written only for GMM / FCM (not K-Means / Agglomerative / DBSCAN). | `test_dev04_artifacts.py::test_algorithm_output_conditional`. |

### AC-5: Lưu Experiment (Jira AC #5)

| # | Criterion | Verification |
|---|---|---|
| 24 | `experiment_log_<experiment_id>.json` is written under prototype clustering dir for BOTH SUCCESS and FAILED outcomes. | `test_dev04_artifacts.py::test_experiment_log_written_always`. |
| 24a | **R1**: On FAILED outcome, `experiment_log_<experiment_id>.json` is MOVED to `_failed_<clustering_id>_<run_uuid>/` (NOT deleted). The directory is retained for audit. The audit sidecar `_preservation_audit.txt` is written with `preserved_at_utc`, `source_staging`, `run_uuid`, `reason`. | `test_dev04_artifacts.py::test_failed_log_retained_in_tracking_dir`. |
| 24b | **R1**: `_preserve_failed_log` creates `_failed_*/` only if `experiment_log_*.json` exists in staging. If ML-01 wrote no log (e.g., crash before Stage 4), no tracking dir is created. | `test_dev04_artifacts.py::test_failed_tracking_dir_only_if_log_exists`. |
| 24c | **R1**: Cleanup pass (R3) NEVER unlinks `_failed_*/` even after a successful subsequent run; the FAILED log persists across processes for audit. | `test_dev04_storage.py::test_cleanup_pass_retains_failed_tracking_dir`. |
| 24d | **R1**: If `_preserve_failed_log` itself fails (e.g., permission error, disk full), the failure is logged but does not raise; `experiment_log_*.json` is retained in staging_dir if possible (orphaned) for manual recovery. | `test_dev04_artifacts.py::test_failed_preservation_failure_does_not_raise`. |
| 24e | **F1 invariant (R1 retention under preservation failure)**: nếu `_preserve_failed_log` trả về `PreservationStatus ∈ {"partial", "failed"}` VÀ re-scan staging_dir xác nhận còn `experiment_log_*.json`, exception handler set `state.unpreserved_log_in_staging = True`; cleanup pass (`_cleanup_pass` trong §6.7.4) PHẢI skip `shutil.rmtree(staging_dir)` (retain cho manual recovery). Quy tắc này ngăn chặn AC-5 #24 audit trail bị mất silently do cleanup unlink staging chứa unpreserved FAILED log. | `test_dev04_storage.py::test_staging_retained_when_preservation_partial` + `test_dev04_storage.py::test_staging_retained_when_preservation_failed` (parametrised over PreservationStatus = "partial" / "failed"). |
| 25 | On SUCCESS, log includes: `algorithm`, `algorithm_version`, `algorithm_family`, `hyperparameters`, `random_seed`, `random_seed_used`, `n_clusters`, `cluster_labels_shape`, `cluster_labels_dtype`, `feature_set`, `feature_count`, `n_samples`, `execution_time`, `timestamp`, `platform`, `library_versions`, `scope_boundaries`, `pending_review_notes`, `assumptions`, `config_source`, `config_sha256`, `dataset_sha256`, `input_path`, `metadata_path`. | `test_dev04_artifacts.py::test_experiment_log_schema`. |
| 26 | On FAILED, log includes: `status: FAILED`, `error: {type, message, traceback, matrix_validation, alignment_validation}`. | `test_dev04_artifacts.py::test_failed_log_schema`. |
| 27 | `experiment_id` in the log matches the `cluster_labels_*` filename. | `test_dev04_artifacts.py::test_experiment_id_consistency`. |
| 28 | `config_sha256` is computed from `configs/dev04_clustering.yaml` at run time. | `test_dev04_artifacts.py::test_config_sha256_recorded`. |

### AC-6: Lưu Result (Jira AC #6)

| # | Criterion | Verification |
|---|---|---|
| 29 | `clustering_manifest.json` is written under prototype clustering dir on SUCCESS (only). | `test_dev04_manifest.py::test_manifest_written_on_success`. |
| 30 | Manifest schema complete (per §6.4): all required fields present, stable vs runtime classification correct. | `test_dev04_manifest.py::test_manifest_schema_complete`. |
| 31 | `clustering_id = "cl_<24-hex>"` content-addressed từ canonical JSON object 7 trường logic: `preprocessed_id`, `algorithm`, `hyperparameters` (sorted, value canonical), `seed_policy`, `seed`, `config_sha256`, `ml_dataset_sha256`. Hash = SHA-256 của UTF-8 bytes của `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)` (xem §6.4.1). | `test_dev04_storage.py::test_clustering_id_derivation` (canonical spec per §6.4.1; detailed cases AC-10 #53-#61b). |
| 32 | Re-clustering idempotent: same `(preprocessed_id, algorithm, hyperparameters, seed_policy, seed, config_sha256, ml_dataset_sha256)` → same `clustering_id`. | `test_dev04_storage.py::test_recluster_idempotent` (broad input coverage) + AC-12 #69 (`test_idempotent_skip_default` — full CLI level). |
| 33 | `research_safety.automatically_promoted_to_research = false` always. | `test_dev04_manifest.py::test_no_automatic_research_promotion`. |
| 34 | `research_safety.scope = "CLUSTERED_PROTOTYPE"` always. | `test_dev04_manifest.py::test_scope_always_clustered_prototype`. |
| 35 | Pre/post SHA-256 of `data/raw/primary`, `data/raw/backup`, `data/processed`, `reports/`, DEV-02 manifest, DEV-03 manifest + ML Dataset → all unchanged. | `test_dev04_research_safety.py::test_research_artifacts_unmodified` + `test_dev02_manifest_unmodified` + `test_dev03_manifest_unmodified` + `test_dev03_ml_dataset_unmodified`. |

### AC-7: Logging (Jira AC #3 supporting, per-stage emission)

| # | Criterion | Verification |
|---|---|---|
| 36 | Per-stage log file `<clustering_id>.log` written under prototype clustering dir. | `test_dev04_logging.py::test_log_file_written`. |
| 37 | Each stage (0→6) emits at least one log entry. | `test_dev04_logging.py::test_log_per_stage_emission`. |
| 38 | Log level configurable via YAML (DEBUG/INFO/WARNING/ERROR); level filter applied. | `test_dev04_logging.py::test_log_level_configurable`. |
| 39 | Failures emit ERROR-level log with stack trace; log file preserved on failure. | `test_dev04_logging.py::test_failure_log_preserved`. |

### AC-8: Defence-in-depth (mirror DEV-02 / DEV-03, not Jira AC but required)

| # | Criterion | Verification |
|---|---|---|
| 40 | Forbidden imports absent (no `fastapi`, `flask`, `sqlalchemy`, `redis`, `celery`, `rq`, etc.). | `tests/test_dev04_import_blocklist.py`. |
| 41 | No new third-party dependency added. | `tests/test_dev04_runtime_dependencies.py`. |
| 42 | Existing test suite not regressed (pre/post pass-fail map). | full `pytest`; per AGENTS.md §2.8, no regression. |
| 43 | Lint clean for DEV-04 additions only (pre-existing findings = N/A). | `ruff check src/customer_segmentation/prototype/clustering/ scripts/dev04_run_clustering.py configs/dev04_clustering.yaml tests/test_dev04_*.py` |
| 44 | Format clean for DEV-04 additions only. | `black --check <same paths>`. |
| 45 | Documentation complete (`docs/system/DEV-04_clustering_execution.md` written — this plan). | File exists. |

### AC-9: Research-safety (CRITICAL, per user §4.D)

| # | Criterion | Verification |
|---|---|---|
| 46 | `data/processed/clustering_experiments/` is NEVER written by DEV-04 (only by research orchestrators). | `test_dev04_research_safety.py::test_research_clustering_experiments_dir_unmodified`. |
| 47 | `data/processed/customer_metadata.parquet` SHA-256 unchanged. | `test_dev04_research_safety.py::test_customer_metadata_unchanged`. |
| 48 | `data/processed/final_clustering_dataset.parquet` SHA-256 unchanged. | `test_dev04_research_safety.py::test_final_clustering_dataset_unchanged`. |
| 49 | `reports/ml01/`..`reports/ml06/` SHA-256 unchanged. | `test_dev04_research_safety.py::test_research_reports_unchanged`. |
| 50 | `data/prototype/datasets/<dataset_id>/manifest.json` (DEV-02's) SHA-256 unchanged. | `test_dev04_research_safety.py::test_dev02_manifest_unchanged`. |
| 51 | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json` (DEV-03's) SHA-256 unchanged. | `test_dev04_research_safety.py::test_dev03_manifest_unchanged`. |
| 52 | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_*.parquet` (DEV-03's) SHA-256 unchanged. | `test_dev04_research_safety.py::test_dev03_ml_dataset_unchanged`. |

### AC-10: `clustering_id` canonical derivation (per §6.4.1)

| # | Criterion | Verification |
|---|---|---|
| 53 | `derive_clustering_id` deterministic: cùng inputs → cùng `clustering_id`. | `test_dev04_storage.py::test_clustering_id_deterministic`. |
| 54 | Different algorithm → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_differs_by_algorithm`. |
| 55 | Different single hyperparameter (e.g. `--n-clusters`) → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_differs_by_hyperparameter`. |
| 56 | Different CLI override (e.g. `--tol 1e-5` vs YAML `--tol 1e-4`) → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_sensitive_to_cli_override`. |
| 57 | Different `config_sha256` (YAML byte change) → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_differs_by_config_hash`. |
| 58 | Different `ml_dataset_sha256` (DEV-03 re-preprocess) → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_differs_by_ml_dataset_hash`. |
| 59 | Stochastic algorithm (kmeans/gmm/fuzzy_cmeans), different seed → different `clustering_id`. | `test_dev04_storage.py::test_clustering_id_seed_sensitivity_stochastic`. |
| 60 | Deterministic algorithm (agglomerative/dbscan), different seed (CLI vs YAML) → SAME `clustering_id` (vì `seed_policy=deterministic` + `seed=null`). | `test_dev04_storage.py::test_clustering_id_seed_invariant_deterministic`. |
| 61 | 1000 random `derive_clustering_id` calls produce 1000 distinct IDs (collision smoke). | `test_dev04_storage.py::test_clustering_id_uniqueness`. |
| 61a | Canonical payload là JSON object với 7 trường logic (`preprocessed_id`, `algorithm`, `hyperparameters` sorted + nested sort, `seed_policy` ∈ {"stochastic", "deterministic"}, `seed` int or null, `config_sha256`, `ml_dataset_sha256`); hash byte UTF-8 của JSON (`sort_keys=True`, `ensure_ascii=False`, `separators=(",", ":")`, `allow_nan=False`). | `test_dev04_storage.py::test_clustering_id_canonical_json_*` (4 cases: empty hyperparameters; hyperparameters với nested dict; NaN/Infinity raises; same input across Python sessions → same id). |
| 61b | `DETERMINISTIC_ALGORITHMS = frozenset({"agglomerative", "dbscan"})` được dùng để tag `seed_policy`; thay đổi set này → đổi clustering_id (vì payload đổi). | `test_dev04_storage.py::test_clustering_id_deterministic_algorithms_set`. |
| 61c | **CRITICAL cho P1 fix `allow_ncii` typo**: thực thi pseudocode của `_build_canonical_payload` và `derive_clustering_id` (xem §6.4.1) trực tiếp trong test với inputs thực (hyperparameters có nested dict, NaN/Infinity, UTF-8 strings); assert KHÔNG có `TypeError` nào (đặc biệt là do tham số không hợp lệ như `allow_ncii`); assert output bytes ổn định across Python sessions. | `test_dev04_storage.py::test_clustering_id_pseudocode_runs_without_typeerror`. |
| 61d | `seed_policy` chỉ nhận 2 giá trị canonical `"stochastic"` / `"deterministic"` (mirror ML-01 `supports_random_state()`); KHÔNG dùng `"stochastic_resolved"` / `"deterministic_ignored"` / giá trị legacy. `_build_canonical_payload` produce giá trị canonical. | `test_dev04_storage.py::test_seed_policy_canonical_whitelist` (parametrised over 5 algorithms; verify output `seed_policy` ∈ {"stochastic", "deterministic"}; verify mapping: kmeans/gmm/fuzzy_cmeans → "stochastic", agglomerative/dbscan → "deterministic"). |

### AC-11: Atomic write guarantees (per §6.2.1, §6.2.2)

| # | Criterion | Verification |
|---|---|---|
| 62 | `clustering_manifest.json` written atomically via temp + rename; on `replace()` exception, `*.tmp` cleaned up. | `test_dev04_manifest.py::test_manifest_atomic_write_no_partial_on_crash`. |
| 63 | `clustering_manifest.json` partial write leaves no manifest at target. | `test_dev04_manifest.py::test_manifest_atomic_write_temp_cleanup`. |
| 64 | `<clustering_id>.log` flush sau mỗi stage transition. | `test_dev04_logging.py::test_log_file_flush_on_entry`. |
| 65 | ML-01 cluster_labels/experiment_log writers are non-atomic — được document trong plan (§6.2.1) và mitigated bởi staging/publish mechanism (§6.7.4). | Document review (no automated test — this is a known limitation surfaced by Phase 1 code inspection, mitigated by staging). |
| 65a | Stage 5b `os.rename(staging_dir, final_dir)` is atomic on POSIX; test mô phỏng crash trước rename (mock raise) verify final_dir cũ còn nguyên. | `test_dev04_pipeline.py::test_atomic_publish_rename_exception`. |

### AC-12: Idempotency / collision / retry / staging (per §6.7)

| # | Criterion | Verification |
|---|---|---|
| 66 | `find_existing_clustering` returns manifest path nếu subdirectory `<clustering_id>/` tồn tại với valid manifest VÀ canonical payload khớp, else None. | `test_dev04_storage.py::test_find_existing_clustering_match`. |
| 66a | `find_existing_clustering` raise `Dev04CollisionError` khi `clustering_id` trùng nhưng canonical payload của stored manifest KHÁC với effective config hiện tại (collision cực hiếm hoặc tamper). KHÔNG trả về Path, KHÔNG coi là idempotent skip. | `test_dev04_storage.py::test_find_existing_clustering_collision_detected` (pre-create manifest với `clustering_id=X`, **cả 7 canonical field đúng tên canonical** (`preprocessed_id`, `algorithm`, `hyperparameters`, `seed_policy`, `seed`, `config_sha256`, `ml_dataset_sha256`), nhưng 1 hoặc nhiều field khác effective config; verify raise `Dev04CollisionError` chứ KHÔNG idempotent skip; verify error message chứa `expected_payload` và `stored_payload`). |
| 66b | `find_existing_clustering` raise `Dev04ManifestCorrupt` khi manifest tồn tại nhưng KHÔNG dùng được (JSON corrupt, thiếu 1 trong 7 canonical key, sai type, `seed_policy` không ∈ {"stochastic","deterministic"}, `seed_policy="deterministic"` + `seed` ≠ null, ...). KHÔNG return None, KHÔNG coi là idempotent hit, KHÔNG raise `Dev04CollisionError` (corrupt ≠ collision). | `test_dev04_storage.py::test_find_existing_clustering_manifest_corrupt_*` (5 cases: corrupt JSON; missing `seed_policy`; wrong type `seed=str`; `seed_policy="foo"`; deterministic + seed=42). |
| 66c | `_extract_canonical_payload_from_manifest` là pure subset selection trên 7 canonical key (KHÔNG rename, KHÔNG transformation); manifest có đúng 7 key canonical là điều kiện tiên quyết để round-trip thành công. | `test_dev04_storage.py::test_extract_canonical_payload_subset_identity` (manifest JSON có đủ 7 key canonical + nhiều field runtime; extract trả về đúng 7 key với values giống manifest, không phải đổi tên). |
| 67 | `find_existing_clustering` returns None khi subdirectory missing. | `test_dev04_storage.py::test_find_existing_clustering_missing_subdir`. |
| 68 | `find_existing_clustering` raise `Dev04ManifestCorrupt` khi manifest JSON corrupt (KHÔNG return None — manifest corrupt là fail-closed; chỉ missing manifest trả None ở step `manifest_path.exists()`). | `test_dev04_storage.py::test_find_existing_clustering_corrupt_json` (write partial JSON; verify raise `Dev04ManifestCorrupt`). |
| 68a | `find_existing_clustering` raise `Dev04ManifestCorrupt` khi manifest `clustering_id` field không khớp với subdirectory name (tamper hoặc rename). | `test_dev04_storage.py::test_find_existing_clustering_id_mismatch`. |
| 68b | `find_existing_clustering` returns None khi `clustering_id` không match regex `^cl_[0-9a-f]{24}$` (early-return ở step 1; KHÔNG raise). | `test_dev04_storage.py::test_clustering_id_format_*` (3 cases). |
| 69 | Re-run with same effective config → CLI early-return, không re-fit. | `test_dev04_manifest.py::test_idempotent_skip_default`. |
| 70 | `--force-rerun` triggers re-fit via staging; **kết quả SUCCESS cũ còn nguyên cho đến khi publish atomic thành công** — bao gồm cả case crash trước publish. | `test_dev04_pipeline.py::test_crash_before_publish_preserves_old_success` (CRITICAL — P1 fix: snapshot SHA-256 manifest + cluster_labels của run A SUCCESS; chạy `--force-rerun` + monkey-patch `os.rename(staging, final)` raise exception; verify final_dir cũ + cluster_labels SHA không đổi, backup_dir chứa final cũ, staging_dir có thể còn sót nhưng KHÔNG touch final). |
| 70a | `--force-rerun` SUCCESS (không crash): old final_dir move sang backup, staging mới, publish atomic, backup unlink. | `test_dev04_pipeline.py::test_crash_before_publish_preserves_old_success` (canonical name; alias: `test_force_rerun_safety` — see §11.1a canonicalization note; full run SUCCESS, snapshot SHA-256 manifest + cluster_labels, mô phỏng crash giữa Stage 4 và 5b; verify old manifest + cluster_labels SHA không đổi, staging được cleanup). |
| 70b | Crash trong cửa sổ `final → backup` rename thành công nhưng `staging → final` chưa chạy → lần chạy sau với cùng `clustering_id`: startup recovery pass restore `backup_dir/<clustering_id>/` → `final_dir` atomic; idempotency skip; manifest SHA + cluster_labels SHA không đổi. | `test_dev04_pipeline.py::test_crash_after_backup_before_publish_restored_on_next_run` (CRITICAL — P1 fix backup recovery). |
| 70c | Startup recovery pass KHÔNG động vào backup_dir khi `final_dir` đã tồn tại (manifest hợp lệ đã ở final). | `test_dev04_pipeline.py::test_recover_orphan_backups_no_op_when_final_exists`. |
| 71 | Different config → 2 bộ artifact co-exist trong 2 subdirectory (`<clustering_id_1>/`, `<clustering_id_2>/`), không overwrite. | `test_dev04_pipeline.py::test_different_config_coexists`. |
| 72 | Cleanup pass unlink staging/backup dirs của **current run only** (xác định bằng `run_uuid`); KHÔNG BAO GIỜ xóa file của run khác. | `test_dev04_storage.py::test_cleanup_pass_only_removes_own_run` (pre-create `_staging_<other_uuid>/` giả lập, chạy run, verify dir giả vẫn còn). |
| 72a | Sau khi run SUCCESS, final subdirectory chứa đủ 4-5 file (cluster_labels, experiment_log, [algorithm_output], manifest, log) cùng lúc; không có partial state. | `test_dev04_storage.py::test_atomic_publish_whole_directory`. |
| 72b | `--force-rerun` SUCCESS: backup_dir được tạo trước staging, restored nếu Stage 5b fail, unlink sau success. | `test_dev04_pipeline.py::test_staging_and_backup_cleanup_after_success`. |
| 72c | Orphan recovery: final subdirectory no-manifest (do crash rare) được recover bằng `--force-rerun` — final cũ move → backup, staging mới, publish atomic. | `test_dev04_pipeline.py::test_orphan_final_no_manifest_recovery`. |
| 72d | Custom `--experiment-id` khác với manifest đã tồn tại → CLI exit non-zero với error message rõ ràng (refuse); cho phép override qua `--force-rerun`. | `test_dev04_pipeline.py::test_experiment_id_conflict_detected` (run A với `--experiment-id=A1`; gọi CLI lại cùng clustering_id nhưng `--experiment-id=A2` không có `--force-rerun` → exit non-zero + error `experiment_id conflict: existing='A1', requested='A2'`; gọi lại với `--force-rerun` → SUCCESS, manifest mới có `experiment_id=A2`, cluster_labels_*.parquet + experiment_log_*.json + algorithm_output_*.parquet đều dùng `A2` trong filename; backup_dir giữ artifact cũ với `A1`). |
| 72e | `recover_orphan_backups` KHÔNG động vào malformed backup_dir (multiple inner subdirs, no inner subdirs, inner subdir tên không match regex `^cl_[0-9a-f]{24}$`). | `test_dev04_storage.py::test_recover_orphan_backups_skip_malformed_*` (3 cases: 2 inner subdirs; 0 inner subdirs; inner subdir named `foo_bar`). |
| 72f | `recover_orphan_backups` KHÔNG raise ra ngoài; OSError / unexpected exception được wrap trong try/except + log + KHÔNG abort main pipeline. | `test_dev04_storage.py::test_recover_orphan_backups_resilient_to_oserror` (monkey-patch `iterdir` raise OSError; verify pipeline vẫn chạy được, log warning emitted). |
| 72g | **R2**: Default behavior — `find_existing_clustering` raises `Dev04ManifestCorrupt` → fail-closed (CLI exit non-zero); KHÔNG auto-recover; KHÔNG coi là idempotent skip; KHÔNG silent reinterpret. | `test_dev04_storage.py::test_corrupt_manifest_default_fail_closed` (verify CLI exit non-zero + error rõ ràng; verify `final_dir` KHÔNG bị touch). |
| 72h | **R2**: Với `--force-rerun`, corrupt final được move sang `_backup_<run_uuid>_corrupt/` (atomic rename); fresh run proceeds với staging mới + publish atomic. Cleanup pass retain `_backup_*_corrupt/` (audit). | `test_dev04_pipeline.py::test_force_rerun_corrupt_recovery` (corrupt manifest in `final_dir`; gọi CLI với `--force-rerun`; verify (a) `_backup_<uuid>_corrupt/` chứa corrupt manifest + artifact cũ; (b) `final_dir` được repopulated bằng new SUCCESS; (c) cleanup retain `_backup_*_corrupt/` sau success; (d) `recover_orphan_backups` skip `_backup_*_corrupt/` ở next run). |
| 72i | **R2**: Với `--force-rerun`, nếu rename corrupt final → `_backup_<uuid>_corrupt/` fail (OSError, permission denied, etc.), pipeline raises `Dev04StoragePathError` và KHÔNG tiếp tục (R2 #5: stop with clear error and preserve all potentially recoverable artifacts). | `test_dev04_pipeline.py::test_force_rerun_corrupt_rename_failure_stops` (monkey-patch `os.rename` raise OSError; verify `Dev04StoragePathError` raised; `final_dir` KHÔNG bị touch; no new staging). |
| 72j | **R2**: `Dev04CollisionError` (valid manifest + khác canonical payload) KHÔNG BAO GIỜ được catch bởi corrupt recovery path. Collision là honest trial vs classification; user phải investigate manually. | `test_dev04_pipeline.py::test_corrupt_recovery_does_not_catch_collision` (pre-create final_dir với valid manifest có canonical payload khác với effective config; gọi CLI với `--force-rerun`; verify `Dev04CollisionError` raised, KHÔNG corrupt recovery). |
| 72k | **R2**: Với `--force-rerun` valid manifest path (idempotent hit + payload khớp), behavior giống như trước: old final move sang `_backup_<run_uuid>/` (không có `_corrupt` suffix); staging mới; publish atomic; cleanup unlink backup khi success. | `test_dev04_pipeline.py::test_force_rerun_valid_manifest_normal_path` (verify backup_dir KHÔNG có suffix `_corrupt`; cleanup unlink sau success). |
| 72l | **R2**: Sau khi `_backup_<uuid>_corrupt/` được retain, next run's `recover_orphan_backups` KHÔNG restore từ corrupt backup (suffix marker = skip; không raise, log debug, skip count). | `test_dev04_storage.py::test_recovery_skips_corrupt_backup_suffix` (pre-create `_backup_<other_uuid>_corrupt/`; chạy next run; verify recovery pass skip; verify corrupt backup còn nguyên). |
| 72m | **R2**: Multiple backups (1 normal + 1 corrupt cùng uuid cũ, hoặc khác uuid): startup recovery chỉ restore từ normal backup (suffix `_corrupt` skip); corrupt backup retained cho audit. | `test_dev04_storage.py::test_recovery_handles_mixed_normal_and_corrupt_backups`. |
| 73a | **R3**: Toàn bộ `run_dev04()` body được wrap trong top-level `try/finally:` block. Cleanup pass chạy ở `finally:` sau normal completion HOẶC unhandled exception. Cleanup pass KHÔNG chạy sau abrupt process termination (segfault, OOM kill, power loss) — đó là crash recovery territory (next invocation's `recover_orphan_backups`). | **Phase 1: behavior-based tests of `_cleanup_pass` only** (verify the observable invariants AC-12 #73b–#73g). Source-introspection of `run_dev04` is **deferred to Phase 2 implementation review** (becomes applicable once `prototype/clustering/pipeline.py::run_dev04` exists) and is NOT counted as a runnable Phase 1 test. See §11.1a R3 inventory for the canonical Phase 1 test list. |
| 73b | **R3**: Cleanup pass KHÔNG remove backup nếu `publish_succeeded=False` (publish failed → backup retained cho next-run recovery). | `test_dev04_pipeline.py::test_cleanup_retains_backup_on_publish_failure` (monkey-patch `os.rename(staging, final)` raise; verify `_backup_<uuid>/` còn sau cleanup). |
| 73c | **R3**: Cleanup pass KHÔNG remove `_backup_*_corrupt/` (R2 invariant). | `test_dev04_storage.py::test_cleanup_retains_corrupt_backup_after_success` (run `--force-rerun` with corrupt manifest; verify corrupt backup retained sau cleanup). |
| 73d | **R3**: Cleanup pass KHÔNG remove `_failed_*/` (R1 invariant). | `test_dev04_storage.py::test_cleanup_pass_retains_failed_tracking_dir` (run FAIL; verify `_failed_*/` retained sau cleanup; verify subsequent success run KHÔNG touch `_failed_*/`). |
| 73e | **R3**: Cleanup pass KHÔNG touch other run's staging/backup/failed dirs (different `_RUN_UUID`). | `test_dev04_storage.py::test_cleanup_pass_only_removes_own_run` (pre-create `_staging_<other_uuid>/`, `_backup_<other_uuid>/`, `_backup_<other_uuid>_corrupt/`, `_failed_<cl>_<other_uuid>/`; chạy run hiện tại; verify tất cả dirs khác retained; chỉ dirs của current run affected). Note: this AC-12 #73e and AC-12 #72 share a single canonical test (the "extended" multi-dir case is the natural scope of #72's "current run only" guarantee). |
| 73f | **R3**: Nếu cleanup pass itself raises exception, exception is logged but KHÔNG re-raise; primary exception (nếu có) is preserved (Python `finally:` semantics). | `test_dev04_storage.py::test_cleanup_pass_failure_does_not_hide_primary` (monkey-patch `_cleanup_pass` raise `RuntimeError`; verify primary exception (e.g. `Dev04RunError`) vẫn propagates; verify cleanup exception logged). |
| 73g | **R3**: Cleanup pass KHÔNG recurse vào `<clustering_id>/` subdirs để xóa file; chỉ touch top-level staging/backup/failed dirs của current run. Final subdirs KHÔNG match `_staging_*` / `_backup_*` / `_failed_*` → KHÔNG bị cleanup touch. | `test_dev04_storage.py::test_cleanup_pass_never_deletes_final_subdir`. |
| 73h | **F1 invariant (R3 cleanup MUST NOT unlink staging chứa unpreserved FAILED log)**: nếu exception handler set `state.unpreserved_log_in_staging = True` (xem AC-5 #24e), `_cleanup_pass` PHẢI skip `shutil.rmtree(staging_dir)`; log warning; retain staging_dir cho manual recovery. Nếu flag = False, cleanup pass unlinks staging_dir bình thường (existing behavior). | `test_dev04_storage.py::test_cleanup_pass_skips_staging_when_unpreserved_log` (parametrised: `state.unpreserved_log_in_staging=True` → staging_dir retained; `=False` → staging_dir unlinked). |

### AC-13: Path containment validation (per §6.3)

| # | Criterion | Verification |
|---|---|---|
| 77 | `prototype_clustering_run_dir` rejects `clustering_id` chứa `..` segments hoặc không match regex `^cl_[0-9a-f]{24}$`. | `test_dev04_storage.py::test_path_containment_parent_traversal`. |
| 78 | `prototype_clustering_base_dir` rejects absolute paths injected through `dataset_id` / `preprocessed_id`. | `test_dev04_storage.py::test_path_containment_absolute_via_id`. |
| 79 | `prototype_clustering_base_dir` rejects symlinks pointing outside storage_root. | `test_dev04_storage.py::test_path_containment_symlink_outside`. |
| 80 | CLI không có `--storage-root` / `--dest-root` flag (mirror DEV-02 §3.5). | `tests/test_dev04_cli.py` (signature check). |

**Note**: AC-13 was originally numbered #73-#76 in the prior revision,
which collided with the AC-12 #73a-#73g R3 cleanup sub-criteria. This
revision renumbers AC-13 to #77-#80 to eliminate the collision. All
references to AC-13 in §3.5, §6.3, §10, §11.1, §15.1, §16.1, §16.2
(R-11 mitigation) should use the new numbers.

**Total: 115 acceptance criteria** (AC-1: 5; AC-2: 6; AC-3: 6;
AC-4: 6; AC-5: 10 [tăng +1 so với baseline 9 do F1 invariant AC-5
#24e mới]; AC-6: 7; AC-7: 4; AC-8: 6; AC-9: 7; AC-10: 13;
AC-11: 5; AC-12: 36 [tăng +1 so với baseline 35 do F1 invariant
AC-12 #73h mới]; AC-13: 4 — tổng breakdown 115; tăng +2 từ
baseline 113 do 2 AC F1 invariant mới). All are
verifiable via tests + smoke + code inspection. Test names trong
ước lượng không bị double-count giữa AC table và §11.

**Test names are unique** — không có test name bị tính 2 lần giữa
AC tables, §11 unit test estimates, và §15 verification commands. Mỗi
`test_*` được cite 1 lần ở AC table; §11 chỉ ước lượng số test
theo file (không list test name cụ thể). §15 chỉ chạy CLI smoke.

---

## 11. Test strategy

### 11.1. Unit tests (per-module, fast, no I/O)

```
tests/test_dev04_scope.py                  — enum values, frozenset classification (3-5 tests)
tests/test_dev04_registry.py               — AlgorithmRegistry integrity, 5 algorithms, kmedoids not registered (5-7 tests)
tests/test_dev04_config.py                 — YAML loader, frozenset validation, typed errors (10-12 tests)
tests/test_dev04_storage.py                — prototype_clustering_dir resolution, clustering_id canonical derivation
                                              (canonical spec AC-10 + path containment AC-13 + R-15/R-15a/R-16/R-17
                                              cleanup tests + 30 R1/R2/R3 unique tests = 28-35 tests; tăng từ 12-15
                                              do AC-12 mới + R-15/R-15a/R-16/R-17 fixes + F1 invariant)
tests/test_dev04_pipeline.py               — single-pipeline driver integration, 7 stages, idempotency default +
                                              --force-rerun + different_config_coexists + E2E (per §11.2)
                                              (27-33 tests; tăng do AC-12 + R-15/R-15a/R-16/R-17 fixes + F1 invariant)
tests/test_dev04_manifest.py               — DEV-04 manifest schema, stable vs runtime, atomic write,
                                              idempotent skip (14-18 tests; tăng do AC-11, AC-12)
tests/test_dev04_artifacts.py              — cluster_labels / experiment_log / algorithm_output per algorithm
                                              + reproducibility + R1 FAILED retention (per §11.4)
                                              (20-25 tests; tăng do AC-5 R1 retention tests + F1 invariant)
tests/test_dev04_logging.py                — per-stage log emission, level filter, flush on entry
                                              (7-9 tests; tăng do AC-11)
```

**Estimated: ~155-235 unit tests** (revised upward from
~135-170 to reflect the actual expanded R1/R2/R3 inventory
in §11.1a: 4 AC-5 (24a-d FAILED retention + preservation failure),
8 AC-12 (72g-m corrupt recovery + R2 invariants) — 11 R2 tests
after canonicalisation in §11.1a, 7 AC-12 (73a-g top-level
try/finally + cleanup invariants) — 10 R3 tests after canonicalisation
(1 of which is shared with R1), 2 new R1 tests + 1 new R3 test
for F1 invariant — total +30 R1/R2/R3 unique test cases on top
of the unit-test estimates per file).

**Reconciliation with §10 AC table, §11.1a, §15.1, §16.2, §16.4:**

- **30 R1/R2/R3-specific unique tests** (10 R1 + 11 R2 + 10 R3 =
  31 entries, minus 1 shared between R1 and R3) are part of the
  unit-test counts above (allocated to the relevant test files
  in §11.1a). They are NOT a separate category that adds to the
  total. The previous "8 R1 + 11 R2 + 9 R3 = 28 unique" wording
  was an arithmetic error (sum-with-overlap, not unique count);
  the correct unique count for the pre-F1 inventories was 27.
  With the F1 invariant tests added (2 new R1 + 1 new R3), the
  post-F1 unique count is 30 (see §11.1a canonicalization note
  for the overlap and F2 reconciliation).
- **Research-safety tests** (9 functions in §11.3) are in a
  separate file `tests/test_dev04_research_safety.py` and add
  to the total.
- **Import-blocklist + runtime-dependency tests** (2 files in
  §11.5) add to the total (~25 functions combined).
- **Reproducibility tests** (5 in §11.4) are inside
  `tests/test_dev04_artifacts.py` and may overlap with the
  unit-test count above.
- **Integration tests** (4 in §11.2) are inside
  `tests/test_dev04_pipeline.py` and may overlap.

**The 30 R1/R2/R3 unique tests are the canonical count for R-15,
R-16, R-17** in §16.2; the 6 cross-cutting concern categories
are listed in §16.4. The "6 defence-in-depth tests" wording from
the previous revision was a miscount of the (a) categories; the
real defence-in-depth surface is the 6 categories + the
30 unique R1/R2/R3 behavior-based tests.
Test names trong ước lượng không bị double-count giữa AC table và §11.

### 11.1a. R1/R2/R3-specific test inventory

The following tests are added or extended to cover the three
adversarial review findings:

```
R1 — FAILED experiment log retention (§6.5 + §6.7.3 + §6.7.4):
  tests/test_dev04_artifacts.py::test_failed_log_retained_in_tracking_dir
  tests/test_dev04_artifacts.py::test_failed_tracking_dir_only_if_log_exists
  tests/test_dev04_artifacts.py::test_failed_preservation_failure_does_not_raise
  tests/test_dev04_artifacts.py::test_failed_tracking_dir_audit_sidecar
  tests/test_dev04_storage.py::test_cleanup_pass_retains_failed_tracking_dir
  tests/test_dev04_pipeline.py::test_run_fail_preserves_log_in_failed_dir
  tests/test_dev04_pipeline.py::test_run_fail_does_not_publish_manifest_or_labels
  tests/test_dev04_pipeline.py::test_failed_dir_name_format
  tests/test_dev04_storage.py::test_staging_retained_when_preservation_partial
  tests/test_dev04_storage.py::test_staging_retained_when_preservation_failed

R2 — --force-rerun corrupt manifest recovery (§6.7.1 + §6.7.4):
  tests/test_dev04_storage.py::test_corrupt_manifest_default_fail_closed
  tests/test_dev04_pipeline.py::test_force_rerun_corrupt_recovery
  tests/test_dev04_pipeline.py::test_force_rerun_corrupt_rename_failure_stops
  tests/test_dev04_pipeline.py::test_corrupt_recovery_does_not_catch_collision
  tests/test_dev04_pipeline.py::test_force_rerun_valid_manifest_normal_path
  tests/test_dev04_storage.py::test_recovery_skips_corrupt_backup_suffix
  tests/test_dev04_storage.py::test_recovery_handles_mixed_normal_and_corrupt_backups
  tests/test_dev04_pipeline.py::test_corrupt_recovery_audit_log_in_corrupt_backup
  tests/test_dev04_storage.py::test_recover_orphan_backups_resilient_to_oserror
  tests/test_dev04_storage.py::test_recover_orphan_backups_skip_malformed_inner_subdir
  tests/test_dev04_storage.py::test_recover_orphan_backups_skip_outer_uuid_mismatch

R3 — Top-level try/finally + cleanup invariants (§6.7.4):
  tests/test_dev04_pipeline.py::test_cleanup_retains_backup_on_publish_failure
  tests/test_dev04_storage.py::test_cleanup_retains_corrupt_backup_after_success
  tests/test_dev04_storage.py::test_cleanup_pass_retains_failed_tracking_dir
  tests/test_dev04_storage.py::test_cleanup_pass_only_removes_own_run
  tests/test_dev04_storage.py::test_cleanup_pass_failure_does_not_hide_primary
  tests/test_dev04_storage.py::test_cleanup_pass_never_deletes_final_subdir
  tests/test_dev04_pipeline.py::test_cleanup_distinguishes_python_exception_from_crash
  tests/test_dev04_storage.py::test_cleanup_pass_scopes_to_run_uuid
  tests/test_dev04_storage.py::test_cleanup_pass_retains_recoverable_backup
  tests/test_dev04_storage.py::test_cleanup_pass_skips_staging_when_unpreserved_log
```

> **Test name canonicalization (Finding 3):** The following renames
> and aliases were applied for consistency between §6.7.4, §10,
> §11.1a, §15.1, and §16.2:
>
> - `test_cleanup_pass_only_removes_own_run_extended` →
>   `test_cleanup_pass_only_removes_own_run` (single canonical name;
>   matches AC-12 #72 in §10). The `_extended` suffix was redundant
>   — the AC #72 already specifies the multi-dir scenario.
> - `test_cleanup_retains_failed_tracking_dir` →
>   `test_cleanup_pass_retains_failed_tracking_dir` (matches AC-12
>   #73d; this test is also referenced in R-15 mitigation, so the
>   `test_cleanup_pass_` prefix is canonical).
> - `test_recover_orphan_backups_resilient_to_oserror` is now
>   explicitly listed here (was previously in §10 AC-12 #72f but
>   absent from §11.1a R2 inventory; now added to close the gap).
> - `test_recover_orphan_backups_skip_malformed_inner_subdir` and
>   `test_recover_orphan_backups_skip_outer_uuid_mismatch` are
>   additional behaviour-based tests for the malformed-backup skip
>   states (S4, S5, S6 in §6.7.4 decision matrix); they are
>   referenced by AC-12 #72e and §6.7.4 pseudocode.
> - `test_force_rerun_safety` (referenced in §6.7.4 "Cửa sổ lỗi
>   nguy hiểm" prose, §6.7.4 "Test bắt buộc" list, AC-12 #70a, R-08
>   mitigation, R-13 mitigation) is an **alias of**
>   `test_dev04_pipeline.py::test_crash_before_publish_preserves_old_success`
>   (the canonical AC-12 #70 test). Both names describe the same
>   scenario: run A SUCCESS → `--force-rerun` + crash simulation →
>   verify final_dir of A intact. The canonical name is
>   `test_crash_before_publish_preserves_old_success` (AC-12 #70
>   row). All subsequent prose uses the canonical name; references
>   to `test_force_rerun_safety` in §6.7.4 prose and R-08/R-13
>   mitigation columns are kept for readability but should be
>   interpreted as the alias.
>
> **F1 invariant tests (added in this revision pass):**
>
> - `test_dev04_storage.py::test_staging_retained_when_preservation_partial` —
>   verify khi `_preserve_failed_log` return `PreservationStatus =
>   "partial"` (một số logs moved, một số failed) VÀ re-scan xác
>   nhận còn `experiment_log_*.json` trong staging, exception
>   handler set `state.unpreserved_log_in_staging = True`; cleanup
>   pass KHÔNG unlink staging_dir. Mapped to AC-5 #24e.
> - `test_dev04_storage.py::test_staging_retained_when_preservation_failed` —
>   same với `PreservationStatus = "failed"` (mkdir failed trước
>   khi move bất kỳ log nào; tất cả logs remain in staging). Mapped
>   to AC-5 #24e (parametrised case).
> - `test_dev04_storage.py::test_cleanup_pass_skips_staging_when_unpreserved_log` —
>   verify cleanup pass logic độc lập: với
>   `_CleanupState.unpreserved_log_in_staging=True`, staging_dir
>   KHÔNG bị `shutil.rmtree`; với `=False`, behavior cũ (unlink
>   bình thường). Mapped to AC-12 #73h. Parametrised over cả hai
>   giá trị flag.
>
> **Finding F2 — test count reconciliation:**
>
> The R1/R2/R3 lists above total 10 + 11 + 10 = **31 entries**,
> but **`test_cleanup_pass_retains_failed_tracking_dir` is shared
> between R1 (line 5) and R3 (line 3)** — same canonical name,
> same verification (cleanup pass retains `_failed_*/` cho audit).
> This test verifies both R1 invariant ("retain FAILED log") and
> R3 invariant ("cleanup doesn't delete FAILED dir").
>
> **Unique test count**: 10 + 11 + 10 − 1 (shared) = **30 unique
> R1/R2/R3 behavior-based tests** (NOT 28 as the previous
> revision incorrectly reported; that 28 was the sum-with-overlap,
> not the unique count). The previous "8 R1 + 11 R2 + 9 R3 = 28
> unique" wording was an arithmetic error: 8 + 11 + 9 = 28 is
> the sum of category totals, not the number of unique test
> functions. The correct unique count for the pre-F1 inventories
> was 8 + 11 + 9 − 1 = 27. With the 2 new R1 tests + 1 new R3
> test added for F1, the post-F1 unique count is 10 + 11 + 10 −
> 1 = 30. All sections that reference the R1/R2/R3 count must
> use **30** (not 28). The 30 unique tests are the canonical
> count for R-15/R-16/R-17 mitigations in §16.2.

> **Note on AC-12 #73a** (R3 top-level `try/finally` wrapper guarantee):
> The original test proposal `test_run_dev04_wrapped_in_top_level_try_finally`
> used `inspect.getsource(run_dev04)` to inspect a function whose source
> only exists as pseudocode in this plan. That test is **infeasible
> before implementation exists**. The guarantee that cleanup runs on
> normal return, on unhandled exception, and that cleanup errors do
> not mask the primary exception is **observable through the 9 R3
> tests above** (each constructs the relevant `_CleanupState` shape
> and asserts the cleanup invariant directly), and is also documented
> in the §6.7.4 pseudocode for `run_dev04`. The static "is the
> function wrapped in `try/finally`" check is recorded as a **Phase 2
> implementation review/checklist item** that becomes applicable once
> `prototype/clustering/pipeline.py::run_dev04` exists — it is NOT
> counted as a Phase 1 test. See §16.1 (approval gate) for the
> explicit acknowledgement that this static check happens during
> implementation, not now.

### 11.2. Integration tests (DEV-04 end-to-end, real I/O)

| Test | What |
|---|---|
| `test_dev04_pipeline.py::test_end_to_end_kmeans_happy_path` | DEV-02 import → DEV-03 preprocess → DEV-04 cluster K-Means → verify all artefacts |
| `test_dev04_pipeline.py::test_end_to_end_each_algorithm` (parametrised over 5 algorithms) | Same, for each of 5 algorithms |
| `test_dev04_pipeline.py::test_recluster_same_input_same_id_e2e` | Re-run end-to-end same effective config → same clustering_id (CLI-level idempotency; complements `test_dev04_storage.py::test_clustering_id_deterministic` ở unit level) |
| `test_dev04_pipeline.py::test_clustering_after_preprocess_rerun_e2e` | DEV-03 re-preprocess → DEV-04 cluster → different ml_dataset_sha256 → different clustering_id (end-to-end version của AC-10 #58) |

Integration tests use a small fixture CSV (~1000 rows, 50 customers, 1+ cancellation) to keep test runtime manageable. The fixture is generated locally (mirror DEV-03 `tests/fixtures/consistency_input.csv`); git-ignored.

### 11.3. Research-safety tests

| Test | What |
|---|---|
| `test_dev04_research_safety.py::test_research_artifacts_unmodified` | Pre/post SHA-256 + mtime of 4 research paths |
| `test_dev04_research_safety.py::test_research_clustering_experiments_dir_unmodified` | Specifically check `data/processed/clustering_experiments/` is NOT written by DEV-04 |
| `test_dev04_research_safety.py::test_customer_metadata_unchanged` | `data/processed/customer_metadata.parquet` SHA-256 |
| `test_dev04_research_safety.py::test_final_clustering_dataset_unchanged` | `data/processed/final_clustering_dataset.parquet` SHA-256 |
| `test_dev04_research_safety.py::test_research_reports_unchanged` | `reports/ml01/..ml06/` SHA-256 |
| `test_dev04_research_safety.py::test_dev02_manifest_unchanged` | `data/prototype/datasets/<dataset_id>/manifest.json` SHA-256 |
| `test_dev04_research_safety.py::test_dev03_manifest_unchanged` | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/preprocessed_manifest.json` SHA-256 |
| `test_dev04_research_safety.py::test_dev03_ml_dataset_unchanged` | `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/ml_dataset_*.parquet` SHA-256 |
| `test_dev04_research_safety.py::test_no_automatic_research_promotion` | `clustering_manifest.research_safety.automatically_promoted_to_research == false` |

### 11.4. Reproducibility tests

| Test | What |
|---|---|
| `test_dev04_artifacts.py::test_reproducibility_kmeans` | Same input + same config + same seed → same `clustering_id` + same `cluster_labels_*.parquet` SHA-256 |
| `test_dev04_artifacts.py::test_reproducibility_gmm` | Same for GMM (stochastic; seed-respecting) |
| `test_dev04_artifacts.py::test_reproducibility_dbscan` | Same for DBSCAN (deterministic; identical labels) |
| `test_dev04_artifacts.py::test_reproducibility_agglomerative` | Same for Agglomerative (deterministic; identical labels) |
| `test_dev04_artifacts.py::test_reproducibility_fuzzy` | Same for FCM (stochastic; seed-respecting) |

### 11.5. Import-blocklist + runtime-dependency tests

```
tests/test_dev04_import_blocklist.py        — forbidden imports (fastapi, flask, ...); cluster.* (allowed) but baseline/cluster_number/etc. (denied)
tests/test_dev04_runtime_dependencies.py    — no forbidden libs in process
```

### 11.6. Verification commands (Phase 2)

```bash
# Unit + integration
PYTHONPATH=src pytest tests/test_dev04_*.py -q --tb=line

# Full test suite (no-regression check)
PYTHONPATH=src pytest -q --tb=line

# Lint (DEV-04 additions only)
ruff check src/customer_segmentation/prototype/clustering/ \
           scripts/dev04_run_clustering.py \
           configs/dev04_clustering.yaml \
           tests/test_dev04_*.py

# Format
black --check <same paths>

# Research-safety smoke (real CSV)
PYTHONPATH=src python scripts/dev02_import_dataset.py --file <test.csv>
PYTHONPATH=src python scripts/dev03_preprocess_dataset.py --dataset-id <id>
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans
git diff --stat data/raw/ data/processed/ reports/  # expect empty

# Git-ignore check (per-clustering_id subdir)
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/
# expect: .gitignore: data/prototype/** ...
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/_staging_<run_uuid>/
# expect: .gitignore: data/prototype/** ...

# Atomic publish smoke: idempotent skip
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans
# Second call: exit 0, manifest_path printed, no re-fit (verified by mtime of cluster_labels_*.parquet không đổi)

# Atomic publish smoke: --force-rerun staging
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans --force-rerun
# expect: final_dir mới với mtime mới; old final_dir được replace nguyên tử bằng 1 os.rename
ls data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/  # chỉ còn 1 <clustering_id>/ + (transient) backup nếu đang chạy

# R1: FAILED log retention smoke
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans --n-clusters 9999
# expect: CLI exit non-zero; final_dir KHÔNG có manifest; `_failed_<clustering_id>_<run_uuid>/` chứa experiment_log_*.json + _preservation_audit.txt
ls data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/
# expect: thấy `_failed_<clustering_id>_<run_uuid>/` + (orphan) `<clustering_id>/` KHÔNG tồn tại
cat data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/_failed_*/_preservation_audit.txt
# expect: 4 dòng: preserved_at_utc, source_staging, run_uuid, reason

# R2: --force-rerun corrupt recovery smoke
echo 'not-json' > data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/clustering_manifest.json
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans
# expect (default): CLI exit non-zero + Dev04ManifestCorrupt error; KHÔNG touch final_dir
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans --force-rerun
# expect (--force-rerun): CLI exit 0; final_dir repopulated với new SUCCESS; _backup_<uuid>_corrupt/ retained cho audit
ls data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/
# expect: thấy `<clustering_id>/` (new SUCCESS) + `_backup_<uuid>_corrupt/` (audit)

# R3: top-level try/finally smoke (cleanup pass invariants)
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans --force-rerun
# expect: after success, ls NO `_staging_<uuid>/` (cleaned up); `_backup_<uuid>/` cũng cleaned up (normal force-rerun success)
# (run lại với corrupt manifest để verify _backup_<uuid>_corrupt/ retained per R2)

# Git-ignore check on new FAILED / corrupt dirs
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/_failed_<clustering_id>_<run_uuid>/
# expect: .gitignore: data/prototype/** ...
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/_backup_<run_uuid>_corrupt/
# expect: .gitignore: data/prototype/** ...
```

### 11.7. Edge cases per algorithm

```
K-Means (kmeans):
  - n_clusters=1 → single cluster; valid; labels all 0
  - n_clusters >= n_samples → ClusterAlgorithmError (from adapter)
  - init != 'k-means++' / 'random' / ndarray / callable → ClusterAlgorithmError
  - seed=42 → same labels across runs (verified by reproducibility test)
  - n_init=1, 10, 100 → all valid; same final labels (lowest inertia)

Agglomerative (agglomerative):
  - n_clusters=1 → single cluster; valid
  - linkage in {ward, complete, average, single} → valid; ward restricts metric to euclidean
  - metric='euclidean' / 'manhattan' / 'cosine' → valid (with non-ward linkage)
  - seed ignored (deterministic)

DBSCAN (dbscan):
  - eps=0.5, min_samples=5 → working default; expect mix of clusters + noise
  - eps too small → all noise
  - eps too large → 1 cluster
  - min_samples > n_samples → sklearn error → ClusterAlgorithmError
  - noise label -1 preserved verbatim
  - seed ignored (deterministic)

GMM (gmm):
  - n_components=4 → working default
  - covariance_type in {full, tied, diag, spherical} → valid
  - init_params in {kmeans, random} → valid
  - soft_probabilities shape (n_samples, n_components); row-sum ≈ 1
  - seed respected (with init_params='kmeans' or 'random')

Fuzzy C-Means (fuzzy_cmeans):
  - n_clusters=4, fuzziness=2.0 → working default
  - fuzziness=1.0 → adapter raises (must be > 1)
  - soft_membership shape (n_samples, c); row-sum = 1 exactly
  - seed respected (Dirichlet init of U matrix)
```

---

## 12. Files dự kiến tạo / sửa

### 12.1. Implementation phase — file tạo MỚI (KHÔNG tạo trong plan này)

#### 12.1.1. `prototype.clustering` sub-package (7 files)

| Path | Mục đích |
|---|---|
| `src/customer_segmentation/prototype/__init__.py` | (existing; no change) |
| `src/customer_segmentation/prototype/clustering/__init__.py` | Public API exports (`ClusteredScope`, `ClusteringStage`, `run_clustering_experiment`, `list_clusterings`, ...). |
| `src/customer_segmentation/prototype/clustering/scope.py` | `ClusteredScope`, `ClusteringStage` enums + frozen sets. |
| `src/customer_segmentation/prototype/clustering/storage.py` | Path resolution, `clustering_id` derivation, container sanity, idempotency lookup. |
| `src/customer_segmentation/prototype/clustering/pipeline.py` | Single-pipeline driver (Stage 0→6); wraps `clustering.ExperimentRunner` + `AlgorithmRegistry`. |
| `src/customer_segmentation/prototype/clustering/manifest.py` | `ClusteringManifest` dataclass + JSON I/O + stable/runtime classification. |
| `src/customer_segmentation/prototype/clustering/config_loader.py` | YAML loader for `configs/dev04_clustering.yaml` (frozenset + typed-error). |
| `src/customer_segmentation/prototype/clustering/logging_config.py` | Per-stage log emission (configurable level + output). |

#### 12.1.2. CLI (1 file)

| Path | Mục đích |
|---|---|
| `scripts/dev04_run_clustering.py` | CLI entry point — orchestrates Stage 0→6, mirrors `scripts/dev03_preprocess_dataset.py` pattern. |

#### 12.1.3. Config (1 file)

| Path | Mục đích |
|---|---|
| `configs/dev04_clustering.yaml` | DEV-04 single source of truth (algorithm hyperparameters, seed, logging, storage, research_safety, validation). |

#### 12.1.4. Test files (10 files)

| Path | Mục đích |
|---|---|
| `tests/test_dev04_scope.py` | Enum values, classification |
| `tests/test_dev04_registry.py` | AlgorithmRegistry integrity (5 algos, kmedoids not in registry) |
| `tests/test_dev04_config.py` | YAML loader, frozenset validation, typed errors |
| `tests/test_dev04_storage.py` | prototype_clustering_dir resolution, clustering_id derivation |
| `tests/test_dev04_pipeline.py` | Single-pipeline driver integration, 7 stages, all 5 algorithms |
| `tests/test_dev04_manifest.py` | DEV-04 manifest schema, stable vs runtime, idempotency |
| `tests/test_dev04_artifacts.py` | cluster_labels / experiment_log / algorithm_output per algorithm + reproducibility |
| `tests/test_dev04_logging.py` | Per-stage log emission, level filter |
| `tests/test_dev04_research_safety.py` | Research artefacts not mutated (9 checks) |
| `tests/test_dev04_import_blocklist.py` | Forbidden imports (fastapi, flask, ...) + cluster.* allowed/denied |
| `tests/test_dev04_runtime_dependencies.py` | No forbidden libs in process |

**Total: ~21 new files** (1 CLI + 1 config + 7 prototype.clustering modules + 11 test files + 1 test fixture).

#### 12.1.5. Test fixture (git-ignored, mirror DEV-03 pattern)

| Path | Mục đích |
|---|---|
| `tests/fixtures/dev04_clustering_input.csv` | Small CSV fixture (~1000 rows, 50 customers, 1+ cancellation, 1+ return) for DEV-04 end-to-end integration tests. Schema: same as DEV-03 consistency fixture (8 columns per `data_dictionary/dataset_schema.csv`). Source: random sample from `data/raw/primary/Online Retail.xlsx` (git-ignored; manually sampled for test fixture). |

### 12.2. File KHÔNG sửa trong DEV-04 (RESEARCH CORE — READ-ONLY)

- Toàn bộ `src/customer_segmentation/clustering/**` (ML-01 + ML-02..06; research core).
- `src/customer_segmentation/preprocessing/`, `transformation/`, `data/`, `aggregation/`, `features/`, `outlier_analysis/`, `evaluation/`, `profiling/`, `visualization/`, `config/`.
- `src/customer_segmentation/dataset_management/**` (DEV-02).
- `src/customer_segmentation/prototype/preprocessing/**`, `prototype/feature_generation/**` (DEV-03).
- `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`, `scripts/run_ml0X_*.py`, `scripts/run_eva0X.py`, `scripts/run_cp0X.py`, `scripts/dev02_import_dataset.py`, `scripts/dev03_preprocess_dataset.py`.
- `configs/*.yaml` (other than the new `configs/dev04_clustering.yaml`).
- `tests/test_*.py` (other than the new `tests/test_dev04_*.py`).
- `data/raw/**`, `data/processed/**`, `data/interim/**`, `data/external/**`, `data/prototype/**` (other than the new `data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/` sub-tree that DEV-04 creates).
- `reports/**`.
- `notebooks/**`.

### 12.3. Plan file (this document)

| Path | Action | Mục đích |
|---|---|---|
| `docs/system/DEV-04_clustering_execution.md` | **CREATED** (this file) | Plan, contract, acceptance criteria, traceability. |

> **Filename note**: User prompt đề xuất `docs/system/DEV-04_clustering_execution.md`. Quy ước đặt tên hiện có của repo là `DEV-01_project_setup.md`, `DEV-02_dataset_management.md`, `DEV-03_preprocessing.md` — **NO** `_plan` suffix. Plan này dùng tên **`DEV-04_clustering_execution.md`** để khớp với quy ước hiện có.

### 12.4. Files may be modified (DEVIATION FROM "0 modifications" RULE)

Per user request §6: "Số file hiện có bị sửa (phải là 0, ngoài file plan mới)". **In Phase 1 (this plan), 0 files are modified**. In Phase 2 (after `APPROVE PHASE 2`), the following 1 file MAY be modified if absolutely necessary (defence-in-depth):

| File | Necessary? | Possible change | Reason | Verified? |
|---|---|---|---|---|
| `pyproject.toml` | **NO** (already configured) | None | Phase 1 verification (2026-10-09): đã đọc `pyproject.toml`. `[tool.ruff.lint.per-file-ignores]` đã có rule `"src/customer_segmentation/prototype/*"` với 8 ignore codes (E402, F401, F841, N814, N818, N806, UP042, SIM300) — bao phủ `prototype/clustering/*`. Marker `c7_dependent` đã được define trong `[tool.pytest.ini_options].markers`. DEV-04 không cần thêm gì. | ✅ |
| `.gitignore` | **Có thể cần** (mirror DEV-03 pattern) | Add `/tests/fixtures/dev04_*.csv` (hoặc `/tests/fixtures/*.csv` rộng hơn) | Fixture `tests/fixtures/dev04_clustering_input.csv` cần git-ignore (derived from `data/raw/primary/Online Retail.xlsx`, per AGENTS.md §2.12 spirit). Pattern hiện có `/tests/fixtures/consistency_input.csv` chỉ ignore fixture DEV-03. Hai lựa chọn: | 🟡 NEEDS_CONFIRMATION |

Lựa chọn cho `.gitignore`:

- **Option A (specific, conservative)**: Add `/tests/fixtures/dev04_*.csv`
  — chỉ ignore DEV-04 fixtures. Nếu DEV-05+ cần ignore fixtures của
  riêng họ, mỗi DEV tự thêm rule của mình.
- **Option B (broad, blanket)**: Add `/tests/fixtures/*.csv` — ignore
  tất cả CSV fixtures trong `tests/fixtures/`. Một lần xong, không
  cần thêm cho các DEV sau. Có thể quá aggressive nếu trong tương
  lai có CSV nào đó muốn track (hiện không có).
- **Option C (mirror DEV-03 verbatim)**: Add
  `/tests/fixtures/dev04_clustering_input.csv` (đường dẫn cụ thể
  tới file — nhưng cách này phá vỡ convention pattern matching, và
  nếu fixture đổi tên thì rule vô hiệu).

Khuyến nghị: **Option A** (`/tests/fixtures/dev04_*.csv`) — đối xứng
với pattern `/tests/fixtures/consistency_input.csv` của DEV-03 (vốn
là specific). Trong tương lai, các DEV sau có thể thêm rule của
riêng họ tương tự.

**Plan default**: bao gồm **1 modification** (Option A: thêm 1 dòng
vào `.gitignore`). Nếu mentor thích strict 0, alternative: đổi tên
fixture thành `tests/fixtures/dev04_clustering_input.csv.gitignored`
(vẫn theo convention hiện có) — nhưng cách này không phù hợp với
AGENTS.md §2.12 spirit.

---

## 13. Các bước triển knh nhỏ, theo thứ tự dependency

> **Step này dành cho Phase 2 (implementation) sau khi human approve
> plan này.** Plan hiện tại KHÔNG thực hiện bất kỳ step nào dưới đây.

1. **(Zero) Plan approval gate.** Chờ human approval gate (`APPROVE PHASE 2`).
2. **(1) Create `prototype.clustering` package skeleton.**
   - `src/customer_segmentation/prototype/clustering/__init__.py` (initially empty; re-exports at the end).
3. **(2) Implement `scope.py` + `config_loader.py`.** Enums (`ClusteredScope`, `ClusteringStage`) + frozen sets; YAML loader with frozenset validation + typed errors.
4. **(3) Implement `storage.py`.** Path resolution (`prototype_clustering_base_dir` mirror `dataset_management.storage.dataset_dir`; trả về base `clustering/` chứa tất cả run); `prototype_clustering_run_dir` cho final subdir per clustering_id; `clustering_id` canonical derivation (`derive_clustering_id` theo §6.4.1 với **JSON object 7 trường logic**, `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`); `DETERMINISTIC_ALGORITHMS` frozenset; container sanity (`ensure_clustering_container`); idempotency lookup (`find_existing_clustering` theo §6.7.1, scope hẹp theo subdirectory, validate regex `^cl_[0-9a-f]{24}$`); path containment validation (`Path.resolve()` + `relative_to(storage_root)`).
5. **(4) Implement `logging_config.py`.** Configure Python `logging` for per-stage emission.
6. **(5) Write `tests/test_dev04_scope.py` + `test_dev04_storage.py` + `test_dev04_logging.py`.** TDD-first per AGENTS.md §4 step 5.
7. **(6) Implement `pipeline.py` (Stage 0→6 + 5b).** Single-pipeline driver wrapping `customer_segmentation.clustering.ExperimentRunner` + `AlgorithmRegistry`. Pipeline must implement (xem §6.7.4 cho chi tiết):
    - **Idempotency check** ở Stage 3: compute `clustering_id` sớm (using effective hyperparameters from CLI merge); call `find_existing_clustering`; if match + not `--force-rerun` → early-return existing manifest.
    - **CLI merge**: resolve hyperparameters by overlaying CLI flags onto YAML defaults (deterministic order).
    - **Seed resolution**: pass `ExperimentSpec.seed_override` (CLI value); runner internally calls `resolve_random_seed` per algorithm.
    - **Staging prep** ở Stage 3: nếu `final_dir` tồn tại (force-rerun hoặc partial), `os.rename(final_dir, backup_dir)` (atomic); tạo `staging_dir = base/_staging_<run_uuid>/`.
    - **Stage 4 = runner.run(output_dir=staging_dir)**: ML-01 chỉ thấy staging.
    - **Stage 5 = write manifest + verify** trong staging: manifest atomic write; verify tất cả artifact.
    - **Stage 5b = atomic publish**: `os.rename(staging_dir, final_dir)` (POSIX atomic). Backup restore nếu rename fail.
    - **Stage 6 = finalize log**: per-stage log vào final.
    - **Cleanup pass cuối run**: unlink staging/backup dirs của current run only (run_uuid filter); KHÔNG BAO GIỜ touch file khác.
    - **Stage 5 only-on-success**: manifest write gated on `ExperimentResult.status == SUCCESS`. FAILED → cleanup staging; restore backup; CLI exit non-zero.
    Depends on (2)(3)(4).
8. **(7) Implement `manifest.py` (schema + JSON I/O + atomic write).** `ClusteringManifest` dataclass (29 top-level fields per §6.4, kèm 4 nested research_safety fields = 32 leaves); `manifest_to_dict`; **`write_clustering_manifest` MUST be atomic (temp + rename)** theo §6.2.2; `read_clustering_manifest`; stable/runtime classification; **`_build_canonical_payload` + `_extract_canonical_payload_from_manifest` MUST use the same 7 canonical keys** (`preprocessed_id`, `algorithm`, `hyperparameters`, `seed_policy`, `seed`, `config_sha256`, `ml_dataset_sha256`) — KHÔNG rename; `_extract` is pure subset selection; `_canonical_payload_equal` so sánh bằng JSON canonical bytes; `seed_policy` chỉ nhận 2 giá trị canonical `{"stochastic", "deterministic"}` (mirror ML-01 `supports_random_state()`); `_extract` raise `Dev04ManifestCorrupt` (fail-closed) khi manifest thiếu key, sai type, hay `seed_policy` không ∈ canonical whitelist. Depends on (2) and `transformation.versioning.compute_file_sha256`.
9. **(8) Write `tests/test_dev04_pipeline.py` + `test_dev04_manifest.py`.** TDD for the modules above.
10. **(9) Write `tests/test_dev04_registry.py` + `test_dev04_config.py` + `test_dev04_storage.py` (extend).** Verify algorithm registry integrity + YAML config + storage paths.
11. **(10) Write `configs/dev04_clustering.yaml`.** Single source of truth for DEV-04 config (KHÔNG có `storage.storage_root` key; storage root lấy từ DEV-02 config per §6.3). Includes:
    - `dev04_clustering.algorithms.{kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans}.*` (mirror `configs/clustering.yaml::algorithms.*`).
    - `dev04_clustering.random_seed.{default, per_algorithm_override}`.
    - `dev04_clustering.logging.{level, log_dir_relative, format, emit_to_console}`.
    - `dev04_clustering.storage.{output_dir_relative, emit_algorithm_output}` (relative paths under storage_root).
    - `dev04_clustering.research_safety.{readonly_paths, never_promote_to_research}`.
    - `dev04_clustering.validation.{min_samples, min_features, require_no_nan, require_no_inf, require_all_numeric, exclude_customer_id_from_features}`.
12. **(11) Write `tests/fixtures/dev04_clustering_input.csv` (git-ignored).** Small CSV fixture (~1000 rows, 50 customers, 1+ cancellation, 1+ return). Schema: 8 columns per `data_dictionary/dataset_schema.csv`. Source: random sample from `data/raw/primary/Online Retail.xlsx`.
13. **(12) Write `tests/test_dev04_artifacts.py`.** TDD for cluster_labels / experiment_log / algorithm_output per algorithm + reproducibility (all 5 algorithms).
14. **(13) Implement `scripts/dev04_run_clustering.py`.** Thin CLI mirroring `scripts/dev03_preprocess_dataset.py`. Orchestrates: load dev04 config → load ml-01 framework config → Stage 1 (DEV-03 lookup) → Stage 2 (split matrix/metadata) → Stage 3 (build ExperimentSpec) → Stage 4 (runner.run) → Stage 5 (write clustering_manifest) → Stage 6 (finalize log).
15. **(14) Write `tests/test_dev04_research_safety.py`.** 9 checks: research paths (4) + DEV-02 manifest + DEV-03 manifest + DEV-03 ML Dataset + automatic promotion guard + research clustering_experiments dir.
16. **(15) Write `tests/test_dev04_import_blocklist.py` + `test_dev04_runtime_dependencies.py`.** Mirror DEV-02/03 defence-in-depth. Import-blocklist asserts that `prototype.clustering` does NOT import fastapi/flask/sqlalchemy/etc.; does NOT import from `customer_segmentation.clustering.{baseline, cluster_number, hyperparameter_search, metrics, stability, preprocessing_feature_sensitivity}` (EPIC-07/08 scope); DOES import from `customer_segmentation.clustering.{registry, base, result, runner, validation, artifacts, config, logging_utils}` (read-only use).
17. **(16) Run full test suite.** `pytest tests/test_dev04_*.py -q` + full `pytest` (no regression per AGENTS.md §2.8).
18. **(17) Run lint + format check.** `ruff check`, `black --check` (DEV-04 additions only; do NOT touch pre-existing findings per AGENTS.md §2.4 + DEV-01 §7.1.1).
19. **(18) Smoke test on real data.** Import a CSV via DEV-02 → preprocess via DEV-03 → cluster via DEV-04. Verify cluster_labels + experiment_log + algorithm_output (conditional) + clustering_manifest + per-stage log are written; research paths unchanged; ml_dataset columns match DEV-03 candidate feature schema (allow column reordering).
20. **(19) Plan-level review + completion report.** Mirror DEV-03's completion summary (Vietnamese; 11 sections per AGENTS.md §7).

---

## 14. Pending decisions, assumptions và methodology conflicts

### 14.1. Assumptions (declared, not methodology changes)

| ID | Assumption | Why |
|---|---|---|
| DEV-04-ASN-01 | DEV-03 contract assumed stable: `preprocessed_scope = PREPROCESSED_PROTOTYPE`; `validation_status = VALID`; ML Dataset schema = CustomerID + 14 candidate features (default FE-05 config). | Mirror DEV-02's downstream contract assumption. If DEV-03's schema changes, DEV-04's ML Dataset reader must be updated. |
| DEV-04-ASN-02 | DEV-03 default ML Dataset includes CustomerID column. If user disables CustomerID in DEV-03 (hypothetical), DEV-04 fails with clear error. | DEV-04 requires CustomerID alignment; cannot run without it. |
| DEV-04-ASN-03 | The 5 algorithm adapters (ML-02..06) are `TECHNICALLY_IMPLEMENTED` and registered in `AlgorithmRegistry`. No new algorithm to be added in DEV-04. | Per AGENTS.md §2.4 (scope control). |
| DEV-04-ASN-04 | `ExperimentRunner` is fully parameterised over `output_dir` and `matrix_df` / `customer_metadata_df`. No modification to ML-01 is needed to support prototype paths. | Verified by code inspection (§3.6). |
| DEV-04-ASN-05 | DEV-04 runs ONE experiment per CLI invocation. Sweeping is the caller's responsibility (shell loop or future prototype layer). | AGENTS.md §2.4 (out-of-scope: hyperparameter sweep). |
| DEV-04-ASN-06 | DEV-04 does NOT compute evaluation metrics (silhouette, DBI, CH, WCSS, stability, runtime). | AGENTS.md §3 "Clustering" + user request §4.D. |
| DEV-04-ASN-07 | DEV-04 does NOT pick "best/optimal/recommended" algorithm, ranking, or winner. | AGENTS.md §2.5, §2.6. |
| DEV-04-ASN-08 | DEV-04 does NOT name segments ("Champions", "Loyal", ...). | AGENTS.md §3 "Profiling" row. |
| DEV-04-ASN-09 | Storage root shared with DEV-02 / DEV-03 (no separate prototype storage). | Mirror DEV-03 pattern. |
| DEV-04-ASN-10 | scikit-learn is acceptable to call directly (already in `pyproject.toml::dependencies`); DEV-04 doesn't need to add any new dep. | All required libs (numpy, pandas, scipy, scikit-learn, pyarrow, PyYAML) already present. |
| DEV-04-ASN-11 | Output paths under `data/prototype/.../clustering/` are git-ignored via the existing `data/prototype/**` rule. | Already covered by `.gitignore` (per DEV-02 §7.3 fix). |
| DEV-04-ASN-12 | Reuse ML-01 framework code by import-and-wrap (NOT fork or copy). | AGENTS.md §2.13, §5 (no copy-paste; no shortcut). |

### 14.2. PENDING_REVIEW / NEEDS_CONFIRMATION items

| ID | Question | Recommendation | Status | Loại |
|---|---|---|---|---|
| DEV-04-OPEN-01 | **Jira task description** for DEV-04. | User pasted scope 2026-10-09: 6 items (algorithm / parameters / run / labels / save experiment / save result). Plan covers full scope. | **RESOLVED** | — |
| DEV-04-OPEN-02 | Should DEV-04 refuse to cluster a `preprocessed_id` whose status is `FAILED`? (mirror DEV-03-OPEN-02). | Plan mặc định: refuse everything except `VALID` (matches DEV-03 default). | **RESOLVED-IN-PLAN** (operational, no methodology impact) | RESOLVED-IN-PLAN |
| DEV-04-OPEN-03 | CLI override semantics: should CLI flags override YAML on a per-field basis, or only on full algorithm reconfiguration? | Plan mặc định: per-field CLI override (mirror DEV-02 / DEV-03 pattern; flag sets that field, YAML keeps rest). | **RESOLVED-IN-PLAN** (UX, no methodology impact) | RESOLVED-IN-PLAN |
| DEV-04-OPEN-04 | Should DEV-04 also support running clustering on the research `final_clustering_dataset.parquet` (FE-06 output) for a "research-aligned" prototype run? | Plan mặc định: **NO** — DEV-04 is prototype-only; research data is consumed only via DEV-03 ML Dataset. If user wants research-aligned prototype, they should import the research dataset via DEV-02 (or the equivalent) and preprocess via DEV-03. This avoids bypassing DEV-02/03 and accidentally mutating research paths. | **RESOLVED-IN-PLAN** (data flow policy, no methodology impact) | RESOLVED-IN-PLAN |
| DEV-04-OPEN-05 | Filename `docs/system/DEV-04_clustering_execution.md` (no `_plan` suffix) vs `DEV-04_clustering_execution_plan.md` (with `_plan`)? | Plan mặc định: `DEV-04_clustering_execution.md` (matches DEV-01/02/03 convention). | **RESOLVED-IN-PLAN** (docs convention) | RESOLVED-IN-PLAN |
| DEV-04-OPEN-06 | Có cần sửa `pyproject.toml` hoặc `.gitignore` không? | Phase 1 verification (2026-10-09) đã đọc cả 2 file. **`pyproject.toml`** đã được DEV-03 cấu hình đầy đủ (`[tool.ruff.lint.per-file-ignores]["src/customer_segmentation/prototype/*"]` có 8 ignore codes bao phủ DEV-04; marker `c7_dependent` đã define) → **KHÔNG cần sửa**. **`.gitignore`** có thể cần thêm 1 dòng `/tests/fixtures/dev04_*.csv` (Option A khuyến nghị) để ignore `tests/fixtures/dev04_clustering_input.csv`. Plan default: thêm 1 dòng `.gitignore`; nếu mentor thích strict 0, đổi tên fixture thành pattern không cần ignore (không khuyến nghị). | **RESOLVED-IN-PLAN** (1 line `.gitignore` only; `pyproject.toml` confirmed already configured) | RESOLVED-IN-PLAN |
| DEV-04-OPEN-07 | Should DEV-04 emit a per-run log under `reports/dev04/` (per-stage) or per-`clustering_id` log under `data/prototype/.../clustering/`? | Plan mặc định: per-`clustering_id` log under `data/prototype/.../clustering/` (mirror DEV-02/03 pattern; avoid mutating `reports/` per AGENTS.md §2.12). Each DEV-04 run is 1 log file tied to 1 `clustering_id`. | **RESOLVED-IN-PLAN** (operational, no methodology impact) | RESOLVED-IN-PLAN |

**Còn lại cần user/mentor trước khi implement:**
- DEV-04-OPEN-06: đã RESOLVED-IN-PLAN sau Phase 1 verification (0 modifications to `pyproject.toml`; tối đa 1 line modification to `.gitignore` cho fixture git-ignore). Nếu mentor muốn strict 0 modifications luôn cả `.gitignore`, nói rõ trong approval gate.

### 14.3. Methodology conflicts (inherited, NOT DEV-04's scope)

| ID | Conflict | Disposition (out of DEV-04 scope) |
|---|---|---|
| DOC-CTD-01 | `METHODOLOGY_LOCK_STATUS.md` §2 lists **DS-03 = FE-06 C7** as `✅ LOCKED`. But `SYS-04` §3.1 lists **DS-03 = FE-06 C7** as `⚠️ WORKING_ASSUMPTION (WA-01)`. | Out of scope; DEV-04 does NOT touch C7. The ML-01 framework `clustering.yaml` is used verbatim. Recommend ADR / doc PR to resolve. |
| DOC-CTD-02 | `SYS-01` §3.1 references "FE-06 final matrix" as the only acceptable research input, but DEV-02/03/04 operate on user-imported prototype datasets — a parallel universe. | The contradiction is intentional; SYS-01 §3.1 = research layer; DEV-* = prototype layer. ADR-0005 + DEV-02 §3 establish the boundary. Out of scope. |
| SYS-06 §S-02 | "Không cho upload dataset khác trong prototype" wording vs DEV-02/03/04 CLI upload. | Out of scope; HTML prototype is mock-data only. Recorded as future ADR topic (inherited from DEV-02 §15.1 C-02). |
| ADR-0003 (5 algorithms) | Confirmed: K-Medoids OUT OF SCOPE. | DEV-04 inherits; no action needed. |

---

## 15. Verification commands và completion-report requirements

### 15.1. Verification commands (Phase 2)

```bash
# Smoke import
PYTHONPATH=src python -c "from customer_segmentation.prototype.clustering import run_clustering_experiment"

# Algorithm registry integrity
PYTHONPATH=src python -c "from customer_segmentation.clustering import AlgorithmRegistry; print(AlgorithmRegistry.list_registered())"
# expect: ['agglomerative', 'dbscan', 'fuzzy_cmeans', 'gmm', 'kmeans']  (5 names; kmedoids NOT included)

# Unit + integration
PYTHONPATH=src pytest tests/test_dev04_*.py -q --tb=line

# Full test suite (no-regression check)
PYTHONPATH=src pytest -q --tb=line

# Lint (DEV-04 additions only)
ruff check src/customer_segmentation/prototype/clustering/ \
           scripts/dev04_run_clustering.py \
           configs/dev04_clustering.yaml \
           tests/test_dev04_*.py

# Format
black --check <same paths>

# Research-safety smoke (real CSV)
PYTHONPATH=src python scripts/dev02_import_dataset.py --file <test.csv>
PYTHONPATH=src python scripts/dev03_preprocess_dataset.py --dataset-id <id>
PYTHONPATH=src python scripts/dev04_run_clustering.py --dataset-id <id> --preprocessed-id <ppid> --algorithm kmeans
git diff --stat data/raw/ data/processed/ reports/  # expect empty

# Git-ignore check on new clustering sub-tree
git check-ignore -v data/prototype/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/
# expect: .gitignore: data/prototype/** ...
```

### 15.2. Completion report (per AGENTS.md §7)

11 sections:

1. **Files created / modified** — 21 new files (7 prototype.clustering modules + 1 CLI + 1 config + 11 test files + 1 fixture); 0-1 files modified (per DEV-04-OPEN-06 disposition: `pyproject.toml` confirmed already configured by DEV-03; `.gitignore` may need 1 line for the fixture).
2. **Implementation summary** — wrap-and-call pattern; no algorithm re-implementation; no ML-01 modification.
3. **Dataset / result summary** — smoke test on real CSV (DEV-02 → DEV-03 → DEV-04); expected outputs (cluster_labels, experiment_log, algorithm_output, clustering_manifest, per-stage log).
4. **Tests** — **canonical test inventory breakdown (consistent with §11.1a, §11.1, §16.4):**
    - **Unit tests** (per §11.1): ~155-235 tests across 8 test files (scope, registry, config, storage, pipeline, manifest, artifacts, logging). The actual count is a range because some files have parametrized tests covering all 5 algorithms.
    - **R1/R2/R3-specific behaviour-based tests** (per §11.1a; mapped to R-15/R-16/R-17 in §16.2): 10 R1 + 11 R2 + 10 R3 = **31 entries, 30 unique tests** (one test shared between R1 and R3: `test_cleanup_pass_retains_failed_tracking_dir`). These are part of the unit-test count above (not additional). The previous "8 + 11 + 9 = 28 unique" wording was an arithmetic error; the canonical count is 30 unique (10 R1 + 11 R2 + 10 R3 − 1 shared).
    - **Research-safety tests** (per §11.3): **9 test functions** in `tests/test_dev04_research_safety.py` (4 research paths + 4 DEV-02/03 outputs + 1 promotion guard).
    - **Reproducibility tests** (per §11.4): **5 test functions** in `tests/test_dev04_artifacts.py` (one per algorithm). May overlap with the unit count (algorithm dispatch tests).
    - **Import-blocklist + runtime-dependency tests** (per §11.5): 2 test files (`test_dev04_import_blocklist.py` + `test_dev04_runtime_dependencies.py`) with ~25 test functions combined (mirror DEV-03's 22+3).
    - **Integration tests** (per §11.2): 4 test functions in `test_dev04_pipeline.py` (E2E + parametrised across 5 algorithms).
    - **Total unique tests**: ~150-205 (range; the exact number is finalized in Phase 2 when each test file is written); pre-existing 1739 + DEV-04 tests = full suite. **The numbers must NOT be inflated by counting smoke/verification commands as separate unit tests** (verification commands in §15.1 are CLI-level invocations, not pytest tests).
    - **Test names are unique across §6.7.4, §10 AC table, §11.1a, §15.1**: the canonicalisation table in §11.1a enumerates the renames applied during this revision pass (Finding 3 + F1 + F2); AC-12 #72, #73d, #73e, #72e, #72f share single canonical test names with §11.1a and §16.2; the 30 unique R1/R2/R3 test names in §11.1a (with the 1 overlap explicitly documented) are the source of truth for the §16.2 R-15/R-16/R-17 mitigation columns.
5. **Lint** — `ruff check` on DEV-04 additions only.
6. **Format** — `black --check` on DEV-04 additions only.
7. **Input / output SHA** — input SHA-256 (ML Dataset from DEV-03); output SHA-256 (cluster_labels, algorithm_output, clustering_manifest); reproducibility contract verified.
8. **Assumptions** — list from §14.1.
9. **PENDING_REVIEW decisions** — DEV-04-OPEN-01..07 from §14.2.
10. **Remaining issues** — DOC-CTD-01 (out of scope); possible modifications (§12.4).
11. **Scope explicitly NOT performed** — list from §4.2.

### 15.3. Out of scope (explicit, to prevent scope creep)

Mirror §4.2:
- ❌ Implementing K-Medoids (ADR-0003).
- ❌ Implementing K-Means / Agglomerative / DBSCAN / GMM / FCM (already implemented).
- ❌ Modifying ML-01 framework.
- ❌ Modifying `configs/clustering.yaml` or `scripts/run_ml0X_*.py`.
- ❌ Computing evaluation metrics (EPIC-08 scope).
- ❌ Ranking algorithms, picking "best / optimal / recommended" (AGENTS.md §2.5, §2.6).
- ❌ Hyperparameter sweep (EPIC-07 scope).
- ❌ Stability / runtime analysis (EPIC-08 scope).
- ❌ Segment profiling / naming (EPIC-09 / CP-01..05 scope).
- ❌ Visualization (EPIC-09 scope).
- ❌ Modifying research artefacts (`data/processed/`, `data/raw/`, `reports/`, FE-06 outputs).
- ❌ Modifying DEV-02 / DEV-03 outputs.
- ❌ Adding a new third-party dependency.
- ❌ Editing `SYS-01..06`, `AGENTS.md`, `ADR-0001..0005`.
- ❌ Re-promoting any `WORKING_ASSUMPTION` to `RESEARCH_APPROVED_FINAL`.
- ❌ Resolving DOC-CTD-01 / DOC-CTD-02 / SYS-06 §S-02 wording.
- ❌ Git operations (commit, push, PR, merge, branch).

---

## 16. Human review gate và rollback/safety considerations

### 16.1. Human approval gate (AGENTS.md §2.10)

Phase 2 implementation requires the human researcher to:

1. **Approve plan** by sending exactly `APPROVE PHASE 2` (per AGENTS.md §2.10 + DEV-03 precedent).
2. **Confirm DEV-04-OPEN-06 disposition** (đã RESOLVED-IN-PLAN với 1 line `.gitignore`; nếu mentor muốn strict 0, nói rõ).
3. **General approval** that the plan's:
   - Scope (6 Jira items + **115 acceptance criteria** — baseline 76 + 10 từ canonical JSON + atomic publish + staging/publish + force-rerun + orphan recovery + experiment_id conflict + round-2 P1 fixes + round-3 R1/R2/R3 fixes: 4 AC-5 FAILED retention, 8 AC-12 corrupt recovery + R2 invariants, 7 AC-12 top-level try/finally + cleanup invariants; AC-13 renumbered 73-76 → 77-80 to avoid AC-12 #73a-#73g collision; F1 invariant: 1 AC-5 #24e + 1 AC-12 #73h added in this revision) is acceptable. The 115-AC count is the canonical total (see AC table at end of §10; test names are unique across AC table, §11.1a, and §15.1 — no double counting).
   - **AC-12 #73a note:** the static verification that `run_dev04` is wrapped in `try/finally` is a **Phase 2 implementation review/checklist item** (it requires `pipeline.py::run_dev04` to exist for `inspect.getsource` to work). The 10 R3 behavior-based tests in §11.1a cover the *observable* invariants (cleanup-on-return, cleanup-on-exception, cleanup-failure-doesn't-hide-primary, no-cross-process-touch, no-retained-artifact-deletion, F1 staging retention when unpreserved log) without requiring source introspection. The AC-12 #73a row in §10 explicitly notes this split and does NOT count the static check as a Phase 1 test.
   - **Test-count reconciliation (Finding F2):** the R1/R2/R3 inventories in §11.1a total 10 R1 + 11 R2 + 10 R3 = 31 entries; **`test_cleanup_pass_retains_failed_tracking_dir` is shared between R1 and R3** (verifies both R1 invariant "retain FAILED log" and R3 invariant "cleanup doesn't delete FAILED"); the canonical **unique test count is 30** (NOT 28 — the previous "8 R1 + 11 R2 + 9 R3 = 28 unique" was an arithmetic error since 8+11+9 = 28 is the sum-of-categories with one overlap, not the number of distinct test functions). The 6 cross-cutting concern categories in §16.4 are CATEGORIES (not tests) that contain a variable number of test functions each (~5-10 for import-blocklist, ~3 for runtime-dependency, 9 for research-safety, 1 for customer-ID-leak, 1 for manifest research_safety). The defence-in-depth surface is the union of (a) the 6 categories, (b) the 30 unique R1/R2/R3 behavior-based tests in §11.1a. See §16.4 for the corrected breakdown and §11.1a canonicalization note for the overlap reconciliation.
   - Prototype-layer placement (`customer_segmentation.prototype.clustering.*`) is acceptable.
   - Reuse strategy (wrap ML-01 framework + 5 adapters; do not fork; do not modify) is acceptable.
   - ~21 new files in §12.1 are acceptable.
   - Storage isolation (prototype sub-tree only, single source of truth từ DEV-02 config, path containment validation) is acceptable.

After approval, Phase 2 proceeds with the 19 steps in §13.

### 16.2. Rollback / safety considerations

| Risk | Mitigation |
|---|---|
| R-01: DEV-04 silently writes to research paths | `test_dev04_research_safety.py::test_research_artifacts_unmodified` (9 checks) before/after DEV-04 run; hard-fail on any mutation. |
| R-02: ML-01 framework accidentally imported as read-write | `test_dev04_import_blocklist.py` asserts `prototype.clustering` MAY import from `customer_segmentation.clustering.{registry, base, result, runner, validation, artifacts, config, logging_utils}` and MUST NOT mutate their module-level state. The ML-01 framework is itself read-only I/O (verified §3.6). |
| R-03: `clustering_id` collision or hash collision | `clustering_id = cl_<sha256(canonical_effective_config)[:24]>` = 96-bit entropy, `N = 2^96 ≈ 7.92×10²⁸`; birthday bound `P(at least one collision) ≈ k²/2N`: k=10³ → 6.31×10⁻²⁴, k=10⁶ → **6.31×10⁻¹⁸** (chính xác theo bảng §6.7.2, không phải range xấp xỉ), k=10⁹ → 6.31×10⁻¹². Trong phạm vi DEV-04 (ước lượng 10⁵–10⁶ lượt/năm tích lũy → P ~ 10⁻²⁰–10⁻¹⁸) — rủi ro dư rất nhỏ nhưng **không phải zero**; không cam kết "không thể xảy ra". `find_existing_clustering` (§6.7.1) bổ sung **collision detection** bằng canonical payload comparison → nếu `clustering_id` trùng nhưng payload khác, raise `Dev04CollisionError` thay vì silent idempotent skip. Smoke test `test_dev04_storage.py::test_clustering_id_uniqueness` chạy 1000 random derive. |
| R-04: DEV-04 accidentally promotes prototype output to research | `research_safety.automatically_promoted_to_research = false` hard-coded in manifest + verified by `test_dev04_manifest.py::test_no_automatic_research_promotion`. |
| R-05: New top-level dependency added accidentally | `test_dev04_runtime_dependencies.py` verifies no new third-party dep (compared to pre-DEV-04 baseline). |
| R-06: Algorithm parameters bypass validation (e.g. `n_clusters=0`) | Each adapter's `__init__` raises `ClusterAlgorithmError` on bad config; runner catches and translates to `status: FAILED` in the experiment log. Verified by per-adapter test. |
| R-07: CustomerID accidentally leaks into matrix | DEV-04 Stage 2 always does `matrix_df = ml_dataset_df.drop(columns=[CustomerID])` BEFORE calling `runner.run()`. Verified by `test_dev04_pipeline.py::test_customer_id_dropped_from_matrix`. |
| R-08: Two DEV-04 runs with same effective config silently overwrite each other | Per-clustering_id subdirectory (§6.3) + idempotency (§6.7.1): cùng `clustering_id` → CLI early-return (mặc định); `--force-rerun` để bypass, dùng staging/atomic publish (§6.7.4) để kết quả cũ còn nguyên cho đến khi publish thành công. Different config → khác subdirectory → co-exist song song, không overwrite. Verified by `test_dev04_manifest.py::test_idempotent_skip_default` + `test_dev04_pipeline.py::test_force_rerun_safety` + `test_dev04_pipeline.py::test_different_config_coexists`. |
| R-09: FAILED run leaves partial artefacts | Staging/publish policy (§6.7.4): mọi write trong staging_dir của current run. Final_dir KHÔNG bị touch cho đến khi Stage 5b `os.rename` atomic thành công. FAILED run → unlink staging; restore backup. Verified by `test_dev04_pipeline.py::test_staging_isolation` + `test_atomic_publish_rename_exception`. |
| R-10: Cluster labels partial do ML-01 non-atomic writers (xem §6.2.1) | Staging/publish policy (§6.7.4): partial cluster_labels ở staging không bao giờ được promote sang final vì manifest atomic write phải thành công trước. Nếu crash trước publish, final_dir hoàn toàn untouched; cleanup pass unlink staging. Verified by `test_dev04_storage.py::test_atomic_publish_whole_directory` + `test_cleanup_pass_only_removes_own_run`. |
| R-11: Path traversal qua user input (`--clustering-id` chứa `..` hoặc absolute path) | Path containment validation (§6.3) + `clustering_id` format check regex `^cl_[0-9a-f]{24}$`: mọi computed path phải `Path.resolve()` + `relative_to(storage_root.resolve())`. `test_dev04_storage.py::test_path_containment_*` (3 cases: relative parent, absolute via dataset_id, symlink outside) + `test_clustering_id_format_*` (3 cases: valid, invalid prefix, invalid hex length). |
| R-12: `clustering_id` không phản ánh CLI override → re-run không idempotent | Canonical JSON spec (§6.4.1) bao gồm `hyperparameters` (sau CLI merge, sorted+canonical) + `seed_policy` + `seed` + 4 trường khác. Test 11 cases trong `test_clustering_id_*` verify sensitivity (khác algorithm → khác id; khác `--tol` → khác id; deterministic với khác seed → CÙNG id; NaN/Infinity raise; v.v.). |
| R-13: `--force-rerun` làm hỏng kết quả SUCCESS cũ | Staging/atomic publish (§6.7.4): old `final_dir` được move sang `backup_dir` (atomic rename) trước khi staging prep. New run viết vào staging, không touch final. Chỉ khi Stage 5b `os.rename(staging, final)` thành công thì final mới thay đổi. **Startup recovery pass** chạy đầu mỗi run: nếu crash xảy ra giữa `final → backup` rename và `staging → final` rename (cửa sổ mà `test_force_rerun_safety` cũ chưa cover), lần chạy sau với cùng `clustering_id` sẽ restore `backup_dir/<clustering_id>/` → `final_dir` atomic trước khi main pipeline chạy. Verified by `test_dev04_pipeline.py::test_force_rerun_safety` (crash trước publish), `test_crash_before_publish_preserves_old_success` (recovery scenario), và **CRITICAL `test_crash_after_backup_before_publish_restored_on_next_run`** (cửa sổ `final → backup` thành công + `staging → final` fail). |
| R-13a: Collision 96-bit silent overwrite manifest | `find_existing_clustering` (§6.7.1) so sánh canonical payload của stored manifest với effective config hiện tại. Nếu `clustering_id` trùng nhưng payload khác (collision cực hiếm ~ 10⁻¹⁸ ở 10⁶ lượt, hoặc tamper), raise `Dev04CollisionError` chứ KHÔNG idempotent skip. Verified by `test_dev04_storage.py::test_find_existing_clustering_collision_detected`. Defense-in-depth bổ sung cho birthday bound §6.7.2. |
| R-14: Cleanup pass xóa nhầm file của run khác | Cleanup pass chỉ unlink staging/backup/failed dirs có `_RUN_UUID` của current process. Staging/backup/failed dirs của process khác (khác `_RUN_UUID`) KHÔNG bị touch. Final subdirs (không match `_staging_*` / `_backup_*` / `_failed_*`) KHÔNG BAO GIỜ bị touch. Verified by `test_dev04_storage.py::test_cleanup_pass_only_removes_own_run`. |
| R-15: **R1 — FAILED run log bị mất** (adversarial review finding R1) | `_preserve_failed_log` (§6.7.4) move `experiment_log_*.json` từ staging sang `_failed_<clustering_id>_<run_uuid>/` TRƯỚC khi staging unlink. FAILED tracking dir LUÔN retain cho audit. ML-01 writers KHÔNG bị modify (DEV-04 chỉ wrap). Verified by 10 R1 tests in §11.1a: `test_dev04_artifacts.py::test_failed_log_retained_in_tracking_dir` + `test_failed_tracking_dir_only_if_log_exists` + `test_failed_preservation_failure_does_not_raise` + `test_failed_tracking_dir_audit_sidecar` + `test_run_fail_preserves_log_in_failed_dir` + `test_run_fail_does_not_publish_manifest_or_labels` + `test_failed_dir_name_format` + `test_dev04_storage.py::test_cleanup_pass_retains_failed_tracking_dir` (also in R3) + `test_staging_retained_when_preservation_partial` (F1) + `test_staging_retained_when_preservation_failed` (F1). |
| R-15a: **F1 invariant — cleanup pass unlinks staging chứa unpreserved FAILED log** (F1 review finding) | `_preserve_failed_log` return `PreservationStatus ∈ {"ok", "partial", "no_log", "failed"}` (canonical 4-value enum). Nếu status ∈ {"partial", "failed"} VÀ re-scan staging_dir xác nhận còn `experiment_log_*.json`, exception handler set `state.unpreserved_log_in_staging = True` (§6.5 rule #7, §6.7.3 failure window F14). Cleanup pass (`_cleanup_pass` trong §6.7.4) PHẢI skip `shutil.rmtree(staging_dir)` khi flag = True; log warning; retain staging_dir cho manual recovery. Nếu flag = False, cleanup pass unlinks staging_dir bình thường. Verified by 1 R3 test in §11.1a: `test_dev04_storage.py::test_cleanup_pass_skips_staging_when_unpreserved_log` (parametrised over True/False). Combined with the 2 F1-specific R1 tests above (test_staging_retained_when_preservation_{partial,failed}), F1 invariant is fully covered at the exception-handler level (R1 tests) and the cleanup level (R3 test). |
| R-16: **R2 — `--force-rerun` silent overwrite corrupt manifest** (adversarial review finding R2) | Default behavior fail-closed: `Dev04ManifestCorrupt` raised → CLI exit non-zero. Với `--force-rerun`: corrupt final move sang `_backup_<run_uuid>_corrupt/` (atomic rename); fresh run proceed; cleanup retain corrupt backup cho audit. Recovery pass skip `_backup_*_corrupt/`. `Dev04CollisionError` KHÔNG BAO GIỜ được catch bởi recovery path (R2 #6). Verified by 11 R2 tests in §11.1a: `test_corrupt_manifest_default_fail_closed` + `test_force_rerun_corrupt_recovery` + `test_force_rerun_corrupt_rename_failure_stops` + `test_corrupt_recovery_does_not_catch_collision` + `test_force_rerun_valid_manifest_normal_path` + `test_recovery_skips_corrupt_backup_suffix` + `test_recovery_handles_mixed_normal_and_corrupt_backups` + `test_corrupt_recovery_audit_log_in_corrupt_backup` + `test_recover_orphan_backups_resilient_to_oserror` + `test_recover_orphan_backups_skip_malformed_inner_subdir` + `test_recover_orphan_backups_skip_outer_uuid_mismatch`. |
| R-17: **R3 — Cleanup chạy không toàn diện** (adversarial review finding R3) | Toàn bộ `run_dev04()` wrapped trong top-level `try/finally:` block (§6.7.4 pseudocode). Cleanup pass chạy cả normal completion + unhandled exception. Cleanup pass KHÔNG BAO GIỜ touch other runs' dirs, KHÔNG BAO GIỜ unlink `_backup_*_corrupt/` (R2), KHÔNG BAO GIỜ unlink `_failed_*/` (R1), KHÔNG BAO GIỜ recurse vào `<clustering_id>/` subdirs, KHÔNG BAO GIỜ hide primary exception nếu cleanup cũng fail. KHÔNG cam kết cleanup chạy sau abrupt crash — đó là `recover_orphan_backups` territory (next invocation). **F1 invariant**: cleanup pass cũng PHẢI skip `shutil.rmtree(staging_dir)` khi `state.unpreserved_log_in_staging = True` (xem R-15a). Verified bằng 10 R3 behavior-based tests in §11.1a (canonical names): `test_cleanup_retains_backup_on_publish_failure` + `test_cleanup_retains_corrupt_backup_after_success` + `test_cleanup_pass_retains_failed_tracking_dir` (also in R1) + `test_cleanup_pass_only_removes_own_run` + `test_cleanup_pass_failure_does_not_hide_primary` + `test_cleanup_pass_never_deletes_final_subdir` + `test_cleanup_distinguishes_python_exception_from_crash` + `test_cleanup_pass_scopes_to_run_uuid` + `test_cleanup_pass_retains_recoverable_backup` + `test_cleanup_pass_skips_staging_when_unpreserved_log` (F1). Static verification of "the body is wrapped in `try/finally:`" is recorded as a **Phase 2 implementation review/checklist item** (not a Phase 1 test) — see AC-12 #73a. |

### 16.3. Rollback procedure (if Phase 2 fails review)

If the mentor decides to roll back DEV-04:

1. Revert all 21 new files (git revert; or manual `rm`).
2. Revert the 1 possible modification to `.gitignore` if it was applied
   (removing the line `/tests/fixtures/dev04_*.csv`).
3. Verify no regression: `pytest -q --tb=line` (should match pre-DEV-04
   baseline: 1739 + 1 skipped = 1740 tests, per DEV-03 completion
   summary).
4. `ruff check` / `black --check` should match pre-DEV-04 baseline.
5. **No** changes to research artefacts (verified by §16.2 R-01).

### 16.4. Safety net — defence-in-depth

DEV-04's safety net has TWO distinct components that must NOT be
confused:

**Component A — 6 cross-cutting concern CATEGORIES** (not tests).
The 6 categories below are *concern classifications*; each category
contains a variable number of test functions (totalling approximately
19-24 test functions across all 6 categories, with internal overlap
between research-safety and no-modify-of-research). Categories
are NOT unit tests and are NOT added to the R1/R2/R3 count.

**Component B — 30 unique R1/R2/R3 behavior-based tests**
(canonical count from §11.1a, with the 1 shared-test overlap
explicitly documented). The 30 unique tests are the *verifications*
of the R-15 / R-15a / R-16 / R-17 mitigations in §16.2. The "34
unique tests" wording in the previous revision was incorrect on
TWO counts: (i) the 6 is categories not tests, and (ii) the
8+11+9 = 28 was the sum-with-overlap, not the unique count (the
correct unique count for the pre-F1 inventories was 27; with the
2 new R1 tests + 1 new R3 test added for F1 invariant, the
post-F1 unique count is 30 = 10 + 11 + 10 − 1 shared).

**Concrete breakdown**:

- **6 cross-cutting concern categories** (Component A; categories
  contain test functions but are not themselves tests):
  1. Import-blocklist category (`tests/test_dev04_import_blocklist.py`;
     ~5-10 test functions).
  2. Runtime-dependency category (`tests/test_dev04_runtime_dependencies.py`;
     ~3 test functions).
  3. Research-safety category (`tests/test_dev04_research_safety.py`;
     9 test functions per §11.3).
  4. No-modify-of-research category (subset of research-safety;
     3 of the 9 functions in §11.3 — counted in (3) above, NOT
     added separately).
  5. CustomerID leak category (1 test function:
     `test_dev04_pipeline.py::test_customer_id_dropped_from_matrix`).
  6. Manifest `research_safety` category (1 test function:
     `test_dev04_manifest.py::test_no_automatic_research_promotion`).

- **30 unique R1/R2/R3 tests** (Component B; per §11.1a canonical
  inventory, with overlap correction):
  - 10 R1 tests (§11.1a R1 inventory; one of which is shared
    with R3: `test_cleanup_pass_retains_failed_tracking_dir`).
  - 11 R2 tests (§11.1a R2 inventory; no overlap).
  - 10 R3 tests (§11.1a R3 inventory; one of which is shared
    with R1: `test_cleanup_pass_retains_failed_tracking_dir`).
  - Overlap: 1 (the shared test).
  - **Unique = 10 + 11 + 10 − 1 = 30** (NOT 28, NOT 34).

The 30 R1/R2/R3 unique tests are the canonical count for R-15
(10 R1), R-16 (11 R2), R-17 (10 R3) in §16.2, and for the new
R-15a (1 R3 + 2 R1) F1 invariant mitigation. They are the
behavior-based tests that cover the FAILED-retention semantics,
the corrupt-manifest recovery semantics, the top-level
`try/finally` + cleanup invariants, and the F1 staging-retention
invariant.

**The 6 categories** (Component A) below describe the
cross-cutting *concerns*; the 30 R1/R2/R3 tests (Component B)
provide the *verifications* of those concerns plus the
R1/R2/R3-specific invariants. Categories and tests together
constitute DEV-04's defence-in-depth surface, but they are
counted separately.

The 6 cross-cutting concern categories:

- **Import-blocklist test** (1 file, ~5–10 test functions):
  `tests/test_dev04_import_blocklist.py`; asserts forbidden
  imports absent (`fastapi`, `flask`, `sqlalchemy`, `redis`,
  `celery`, `rq`, ...) and asserts `prototype.clustering` does NOT
  import from `customer_segmentation.clustering.{baseline,
  cluster_number, hyperparameter_search, metrics, stability,
  preprocessing_feature_sensitivity}` (EPIC-07/08 scope).
- **Runtime-dependency test** (1 file, ~3 test functions):
  `tests/test_dev04_runtime_dependencies.py`; asserts no
  third-party dep added (compared to pre-DEV-04 baseline).
- **Research-safety test** (1 file, 9 test functions per §11.3):
  `tests/test_dev04_research_safety.py`; pre/post SHA-256 + mtime
  of 4 research paths + 2 DEV-02 outputs + 2 DEV-03 outputs +
  research clustering_experiments dir.
- **No-modify-of-research test** (subset of research-safety
  tests, 3 test functions): `test_dev02_manifest_unchanged` +
  `test_dev03_manifest_unchanged` + `test_dev03_ml_dataset_unchanged`;
  asserts DEV-02 / DEV-03 outputs unmodified.
- **CustomerID leak test** (1 test function):
  `tests/test_dev04_pipeline.py::test_customer_id_dropped_from_matrix`
  (AC-3 #16); asserts CustomerID not in matrix passed to runner.
- **Manifest `research_safety` test** (1 test function):
  `tests/test_dev04_manifest.py::test_no_automatic_research_promotion`
  (AC-6 #33); asserts
  `clustering_manifest.research_safety.automatically_promoted_to_research
  == false`.

If any one of these 6 cross-cutting categories fails, the
implementation is rejected.

The R-15 / R-15a / R-16 / R-17 specific tests in §11.1a provide
an additional **30 unique behavior-based tests** (10 R1 + 11 R2 +
10 R3 − 1 shared between R1 and R3) that cover the
FAILED-retention semantics, the corrupt-manifest recovery
semantics, the top-level `try/finally` + cleanup invariants, and
the F1 staging-retention invariant respectively. These 30 unique
tests complement the 6 cross-cutting categories and are mandatory
for the adversarial-review findings R1 / R2 / R3 / R-15a (F1)
closure (see §11.1a for the canonical test list and §16.2 for
the per-risk mitigation mapping). The 30 is the unique count
after subtracting 1 for the R1/R3 overlap; the previous "28
behavior-based tests" wording was the sum-with-overlap, not
the unique count, and has been corrected in this revision.

---

## 17. References

- `AGENTS.md` §1 (read first), §2.1-§2.13 (global principles), §3 (stage guardrails), §4 (workflow), §5 (forbidden shortcuts), §6 (escalation), §7 (communication), §8 (token efficiency), §9 (relationship to plan), §10-§12 (data privacy, code organization).
- `docs/decisions/0003-algorithm-scope.md` (ADR-0003) — 5 algorithms only; K-Medoids OUT OF SCOPE.
- `docs/decisions/0005-prototype-architecture-option-a.md` (ADR-0005) — Option A: file-based, no backend.
- `docs/system/DEV-01_project_setup.md` — verification + architecture boundary pattern.
- `docs/system/DEV-02_dataset_management.md` — downstream contract, manifest schema, coupling rules (skim).
- `docs/system/DEV-03_preprocessing.md` — DEV-03 plan (output contract for DEV-04).
- `docs/system/DEV-03_completion_summary.md` — DEV-03 status (TECHNICALLY_IMPLEMENTED, 134 tests pass, 32 new files).
- `docs/research/ML01_Clustering_Experiment_Framework.md` — ML-01 framework contract.
- `docs/research/ML02_KMeans.md` .. `ML06_Fuzzy_CMeans.md` — per-algorithm adapter scope.
- `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` — algorithm / registry contract.
- `src/customer_segmentation/clustering/__init__.py` — ML-01 public API surface.
- `src/customer_segmentation/clustering/{base, registry, result, runner, validation, artifacts, config, logging_utils}.py` — ML-01 framework modules (READ-ONLY for DEV-04).
- `src/customer_segmentation/clustering/{kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans}.py` — 5 algorithm adapters (READ-ONLY for DEV-04).
- `src/customer_segmentation/clustering/kmedoids.py` — K-Medoids placeholder (OUT OF SCOPE per ADR-0003; `NotImplementedError`).
- `configs/clustering.yaml` — ML-01 framework config (READ-ONLY for DEV-04).
- `src/customer_segmentation/prototype/preprocessing/{__init__, manifest, pipeline, storage}.py` — DEV-03 reference (READ-ONLY for DEV-04). Đặc biệt `prototype/preprocessing/storage.py::resolve_storage_root` được DEV-04 dùng để resolve storage root theo contract DEV-02; `derive_preprocessed_id` là pattern tham chiếu cho DEV-04 `derive_clustering_id` (§6.4.1).
- `src/customer_segmentation/dataset_management/storage.py` — DEV-02 storage module (READ-ONLY cho DEV-04); cung cấp `resolve_storage_root`, `dataset_dir` (pattern cho `prototype_clustering_dir`), `StoragePathError` (cơ sở cho `Dev04StoragePathError`).
- `src/customer_segmentation/dataset_management/manifest.py::write_manifest` — DEV-02 manifest atomic write pattern (READ-ONLY; pattern mirror cho DEV-04).
- `src/customer_segmentation/transformation/versioning.py::compute_file_sha256`, `compute_df_sha256` — DEV-04 dùng để compute `config_sha256` và matrix sha.
- `scripts/run_ml02_kmeans.py` .. `run_ml06_fuzzy_cmeans.py` — research orchestrator pattern to mirror.
- `scripts/dev02_import_dataset.py`, `dev03_preprocess_dataset.py` — prototype CLI pattern to mirror.
- `data/processed/final_clustering_dataset.parquet` (FE-06 output, 14 features × 4371 customers; SHA-256 `ba54033e...`) — verified by read-only inspection.
- `data/processed/customer_metadata.parquet` (FE-06 output, CustomerID × 4371 unique) — verified by read-only inspection.
- `data/processed/clustering_experiments/experiment_log_ML-04-DBSCAN-diag-eps0.5-ms5-euclidean-seedcfg.json` — sample ML-01 experiment log (full schema).
- `data/prototype/datasets/ds_97fbbe97c291742a98fe1273/manifest.json` — sample DEV-02 manifest.
- `data/prototype/datasets/ds_f52a4cbe6912e16ccec7bde6/manifest.json` — sample DEV-02 manifest.
- `tests/test_ml01_framework.py` .. `test_ml06_fuzzy.py` — research test surface (NOT to be modified by DEV-04).
- `tests/test_dev02_*.py` (12 files) — DEV-02 test pattern to mirror.
- `tests/test_dev03_*.py` (15 files) — DEV-03 test pattern to mirror.
