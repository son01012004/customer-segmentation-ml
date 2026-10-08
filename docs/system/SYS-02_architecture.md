# SYS-02 — System Architecture

| Field           | Value                                                 |
| --------------- | -------------------------------------------------------------- |
| Document ID     | SYS-02                                                       |
| Parent         | [SYS-01_requirements.md](./SYS-01_requirements.md)         |
| Status         | DRAFT — pending mentor/researcher review (REVIEW_REQUIRED)   |
| Scope          | Architecture for the offline prototype defined in SYS-01 §3  |
| Out of scope   | SYS-03 Data Model, SYS-04 ML Processing Pipeline, SYS-05 API Design, SYS-06 Prototype UI (separate documents; see §18 I-09) |
| Constraint set | §1.2 (5 algorithms only, K-Medoids OUT); §1.4 (3 RQs locked, see ADR-0004); §1.5 (research core = SOLE ML ground truth, no re-implementation under `src/`); §1.7 (no best/winner/optimal/recommended claims); §1.8 (WCSS = diagnostic only); §1.9 (internal metrics only — no external proxy); §1.10 (no hard-coded segment names); §1.11 (Marketing module = REVIEW_REQUIRED, not MKT-01..05); §1.12 (prototype scope, single-machine); §1.13 (reuse `configs/` and `src/customer_segmentation/` as-is); §1.14 (filesystem + parquet, no DB) |

> **Reading order:** This file describes *what* the offline prototype looks
> like and *how the pieces are wired together*. It does **not** change
> any methodology, dataset, algorithm scope, or research-question
> definition. All such decisions remain owned by SYS-01 §1 and the
> original research plan in `docs/methodology/`. Where a section says
> "see SYS-01 §X.Y", that is authoritative.

---

## 1. Purpose

This document fulfils the architecture-description requirement in
SYS-01 §5 (the brief lists SYS-02 as the deliverable for the
"System Architecture" scope, with the architectural sections
listed in §17 below):

> *"The system shall be described by an architecture document that
> identifies logical components, their responsibilities, their interfaces,
> and the data flow between them, sufficient for a new contributor to
> locate where a given capability lives."*

It also fulfils the SYS-01 non-functional requirements that have
architectural implications (NFR-ARC-002 modularity, NFR-ARC-003
configuration isolation, NFR-01 reproducibility, NFR-AUD-001/002
auditability, plus the research constraints CON-01..CON-16).

The architecture described here is an **offline, file-based, batch
prototype**. There is no request/response service, no scheduled job
runner, no message broker, no online learning loop, and no production
deployment topology. Those concerns belong to SYS-05 (API Design) and
SYS-06 (Prototype UI) and are explicitly **out of scope** for this
document (SYS-01 §5). See also §18 I-09 regarding the SYS-03..06
mapping convention.

---

## 2. Architectural style

### 2.1 Style

The prototype follows a **layered batch-pipeline architecture** with a
**configuration-as-input** discipline on top.

Layers, top to bottom:

1. **Configuration layer** — YAML files under `configs/` (SYS-01 §1.13,
   NFR-ARC-003). All thresholds, paths, seeds, feature lists,
   algorithm registries, and stage toggles are read from these files
   at run time. No value that influences methodology is hard-coded in
   Python.
2. **Driver / orchestration layer** — Python scripts under `scripts/`
   that load the configuration, invoke the corresponding pipeline, and
   write a run manifest. One driver per experiment / stage. Drivers do
   not contain business logic.
3. **Pipeline layer** — Composable Python modules under
   `src/customer_segmentation/` that perform the actual work. Pipelines
   are split by responsibility (preprocessing, transformation,
   features, clustering, evaluation). Each module is independently
   importable.
4. **Data / storage layer** — Filesystem **under the repository working
   directory** (SYS-01 §1.14). All persisted artefacts are written as
   parquet files under `data/processed/`, `data/interim/`, or
   `reports/<stage>/`. **No database**, no remote object store, no
   in-memory cache that survives a process boundary. Datasets under
   `data/raw/primary/` remain **read-only** (SYS-01 §1.3).

This is the same style already used by the research core in this
repository (see `scripts/run_exp01_baseline.py`,
`scripts/run_fe01_audit.py`, `src/customer_segmentation/clustering/`).
SYS-02 does not introduce a new style; it documents the existing one
and adds the prototype-only orchestration on top (SYS-01 §1.13).

### 2.2 Why not microservices, not event-driven

SYS-01 §1.12 limits the deliverable to a single-machine, single-user
prototype. Microservices, message queues, and event buses introduce
operational surface area that this prototype does not need and that
NFR-ARC-002 (modularity) can be satisfied with by Python module
boundaries alone. If a service-style interface is later added, that
concern is owned by SYS-05 (API Design), not by SYS-02.

### 2.3 Why not a notebook-driven architecture

Notebooks remain available for exploration under `notebooks/` per
SYS-01 §1.13, but the **prototype drivers are scripts, not notebooks**
because:

- Scripts can be invoked from the command line with explicit arguments
  (reproducibility, NFR-REP-001).
- Scripts can be linted, formatted, and unit-tested (`ruff`, `black`,
  `pytest`) per AGENTS.md §2.8.
- Notebooks hide DAG structure and make lineage (SYS-02 §10) harder to
  audit (NFR-AUD-001).

This matches the existing repository convention.

---

## 3. Logical components

The prototype is decomposed into the logical components listed below.
Each component has a **single responsibility**, a **documented
interface**, and an **owner module path** in the repository.

| ID  | Component                  | Responsibility                                                                | Owner module path                                              | Source of truth                              |
| --- | -------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------- |
| C-01 | Configuration registry    | Load, validate, and expose YAML configuration for every stage                 | `src/customer_segmentation/config/`                           | SYS-01 §1.13, NFR-ARC-003                    |
| C-02 | Driver / orchestration    | Run a single pipeline end-to-end and write a run manifest                     | `scripts/run_<stage>.py`                                      | SYS-01 §1.12, NFR-REP-001                    |
| C-03 | Preprocessing pipeline     | Cleaning, missing values, duplicates, invalid records, outliers               | `src/customer_segmentation/preprocessing/`                    | FR-DATA-01, FR-DATA-02                              |
| C-04 | Aggregation pipeline     | Build customer-level aggregates from transactions                              | `src/customer_segmentation/aggregation/`                       | FE-01..FE-04 evidence                              |
| C-05 | Feature engineering       | RFM + extended behavioural features (RFM Extended 14 features, locked)        | `src/customer_segmentation/features/`                          | FR-EXP-02, FR-DATA-04                              |
| C-06 | Transformation pipeline | Skewness correction, scaling, redundancy handling                            | `src/customer_segmentation/transformation/`                    | FR-EXP-03, CON-03                              |
| C-07 | Clustering registry      | Algorithm factory for the 5 approved algorithms only                          | `src/customer_segmentation/clustering/registry.py`             | FR-EXP-01, FR-CLUSTER-01, ADR-0003              |
| C-08 | Clustering runner       | Fit one algorithm on one feature matrix, produce labels + parameter data     | `src/customer_segmentation/clustering/runner.py`               | FR-CLUSTER-01..05                              |
| C-09 | Internal evaluation     | Silhouette, Davies–Bouldin, Calinski–Harabasz + WCSS as **diagnostic only** | `src/customer_segmentation/clustering/metrics.py`            | FR-EVAL-01..05                              |
| C-10 | Stability evaluation (RQ3 / EXP-05) | Per-seed / per-perturbation label agreement measurement for stability and reproducibility evidence (RQ3, EXP-05, EPIC-08). **Specific stability metrics and matching protocol are NOT LOCKED at architecture level** — see §18 I-10. | `src/customer_segmentation/evaluation/eva03/` (stability utilities) | REVIEW_REQUIRED — methodology for stability metrics (e.g. ARI / AMI / Hungarian matching) is owned by EPIC-08 plan, not SYS-02. |
| C-11 | Experiment runner       | EXP-01..05: baseline, cluster-number search, hyperparameter search, preprocessing sensitivity (RQ2 / EXP-04), stability / reproducibility (RQ3 / EXP-05). **Note:** RFM-only vs RFM-Extended feature-set sensitivity is **FUTURE WORK** (RQ2 reformulated), not implemented in C-11. | `scripts/run_exp0X_*.py` + the `src/customer_segmentation/clustering/` modules they call | FR-EXP-06, ADR-0004, RQ2 reformulation |
| C-12 | Run manifest writer    | Persist run metadata: input/output SHA-256, config hash, seed, environment   | `src/customer_segmentation/clustering/artifacts.py` (extend)   | FR-EXP-07, NFR-01                          |
| C-13 | Profiling stage         | CP-01..05: descriptive statistics per segment                                  | `src/customer_segmentation/profiling/cp0X/`                   | FR-SEG-01..11, FR-SEG-08, CON-16            |
| C-14 | Reporting writer       | Write JSON / Markdown / parquet reports under `reports/<stage>/`            | existing utilities under `src/customer_segmentation/features/report.py`, `transformation/report.py`, etc. | FR-REPORT-01, FR-REPORT-02 |
| C-16 | **OUT OF SCOPE — Marketing module (REVIEW_REQUIRED)** | Profile → activation recommendations. Per SYS-01 §1.11: no MKT-01..05 IDs, no roadmap claims. | not built in SYS-02 scope | FR-MKT-01..06 (REVIEW_REQUIRED) |

### 3.1 Component C-16 status

Per SYS-01 §1.11, the marketing activation module is **REVIEW_REQUIRED**
in this prototype. It is listed in the table so that its absence from
the runtime architecture is explicit, not implicit. SYS-02 does **not**
design it.

---

## 4. Component interfaces (logical, architecture-level)

This section describes each logical component's **responsibility and
contract** at architecture level: what it accepts, what it returns,
and which boundary conditions it enforces. It deliberately does
**not** lock Python function signatures, type hints, or module
internals — those are implementation details owned by the
implementation phase that follows SYS-02 review.

For each component, the architecture specifies:

- **Accepts:** the logical inputs (files, configs, label arrays, …).
- **Returns:** the logical outputs (dataframes, reports, label
  arrays, manifest entries, …).
- **Enforces:** the boundary conditions (e.g. "raises on unknown
  algorithm", "no segment names").
- **Does not:** explicit non-destinations to prevent scope creep.

Any change to these contracts that affects **methodology**, a
**locked decision**, or an **ADR-anchored policy** must be made
through a new ADR (AGENTS.md §2.9). Routine code-style refactors
inside a component that do not change its accepts/returns/enforces
contract do not require an ADR.

### 4.1 Configuration registry (C-01)

- **Accepts:** a path to a YAML file under `configs/`; optionally a
  schema name (or an internal schema registry).
- **Returns:** a validated configuration object usable by drivers
  and pipeline modules.
- **Enforces:** rejects unknown top-level keys, missing required
  keys, out-of-range thresholds; **raises before any pipeline
  starts** (NFR-REP-001).
- **Does not:** embed default values for methodology-affecting
  fields inside Python code; those defaults must come from
  configuration (SYS-01 §1.13, NFR-ARC-003).
- **Repository evidence:** the project already exposes
  configuration-loading utilities for the feature-engineering and
  transformation stages. SYS-02 does not redesign it; it points at
  the existing pattern.

### 4.2 Driver / orchestration (C-02)

- **Accepts:** command-line arguments (config path, input path,
  output directory, seed).
- **Returns:** exit code; side-effects on the filesystem (artefacts
  under `data/interim/`, `data/processed/`, `reports/<stage>/<run_id>/`).
- **Enforces:** one manifest per run; partial-rerun safety (§11);
  no silent overwrite of `data/raw/primary/`.
- **Does not:** compute metrics, load CSVs, or filter rows. Drivers
  delegate to pipeline modules.

### 4.3 Preprocessing pipeline (C-03)

- **Accepts:** a transaction-level dataframe already loaded from
  `data/raw/primary/`; a configuration block.
- **Returns:** a cleaned dataframe + a `ProcessingReport`
  capturing dropped-row counts per rule, imputation summary, and
  outlier summary.
- **Enforces:** does not mutate the input; returns a new object;
  raw files remain read-only (SYS-01 §1.3).
- **Does not:** silently invent or drop rows beyond the audited
  preprocessing policy in the config.

### 4.4 Aggregation pipeline (C-04)

- **Accepts:** the cleaned transaction-level dataframe; a
  configuration block.
- **Returns:** a customer-level dataframe (one row per
  `CustomerID`).
- **Enforces:** aggregation keys, value columns, and filters come
  from configuration.
- **Does not:** deduplicate `CustomerID` silently if the
  aggregation rule produces duplicates — that would be a policy
  change (see §11).

### 4.5 Feature engineering (C-05)

- **Accepts:** the customer-level dataframe; a configuration block.
- **Returns:** a feature dataframe carrying the locked feature set
  (RFM Extended, 14 features per ADR-0004 / SYS-01 FR-EXP-02).
- **Enforces:** uses the existing implementations in
  `src/customer_segmentation/features/`; does **not** introduce a
  parallel implementation.
- **Does not:** materialise an "RFM-only" feature set as a current
  capability. RFM-only vs RFM-Extended comparison is **FUTURE WORK**
  (RQ2 reformulated, see `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`).

### 4.6 Transformation pipeline (C-06)

- **Accepts:** the feature dataframe; a configuration block.
- **Returns:** a transformed feature dataframe + a
  `TransformationReport`.
- **Enforces:** applies skewness correction, scaling, and
  redundancy handling per the locked transformation policy
  (FE-06 C7 = median imputation + Yeo-Johnson + RobustScaler;
  WORKING_ASSUMPTION status, see METHODOLOGY_LOCK_STATUS WA-01).
- **Does not:** pick a different scaler/transform without an ADR.

### 4.7 Clustering registry (C-07)

- **Accepts:** an algorithm name (string).
- **Returns:** the corresponding clustering-algorithm class.
- **Enforces:** exposes **only the five approved algorithms**
  (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means). Any other
  name — including `kmedoids` — must raise at runtime, not
  silently fall back (ADR-0003).
- **Does not:** add a new algorithm class without an ADR.

### 4.8 Clustering runner (C-08)

- **Accepts:** a feature matrix `X`; an algorithm name (resolved
  through C-07); a parameter dictionary; a seed.
- **Returns:** a `ClusterResult` carrying the label array, the
  parameter dictionary actually used, and the algorithm name.
- **Enforces:** no metric is computed inside the runner; metrics
  are the responsibility of C-09 / C-10.
- **Does not:** pick the "best" / "recommended" algorithm. Selection
  belongs to the experiment runner (C-11) and to the human /
  researcher.

### 4.9 Internal evaluation (C-09)

- **Accepts:** a feature matrix `X`; a label array `labels`; an
  optional flag to include WCSS as a diagnostic.
- **Returns:** an `InternalMetrics` record with silhouette,
  Davies–Bouldin, Calinski–Harabasz, and (optionally) WCSS.
- **Enforces:**
  - WCSS is present **only** when the flag is set **and** the
    algorithm exposes WCSS. WCSS is **diagnostic, not selection**
    (SYS-01 §1.8, METHODOLOGY_LOCK_STATUS WA-07).
  - On degenerate input (single label), `silhouette` is `NaN`
    rather than imputed.
  - **No external metric, no proxy metric, no business-side KPI**
    is computed at this layer (SYS-01 §1.9).
- **Does not:** pick a "winning" algorithm or compute a rank.

### 4.10 Stability evaluation (C-10)

- **Accepts:** a feature matrix `X`; an algorithm name; a parameter
  dictionary; a list of seeds; a perturbation specification.
- **Returns:** a `StabilityReport` carrying per-run (seed and/or
  perturbation) label arrays and an aggregate agreement summary.
- **Enforces:** the architecture layer **does not lock** which
  stability metric is used, which label-matching protocol is used,
  or how ties are resolved. Those are owned by the EPIC-08 plan
  (METHODOLOGY_LOCK_STATUS §4 deferred decisions: EPIC08-ARI,
  EPIC08-STAT, EPIC08-CI, EPIC08-RUNTIME). At architecture level
  the contract is: "produce per-run label arrays and an aggregate
  agreement summary".
- **Does not:** invent or hard-code a specific metric or matching
  algorithm in `C-10`. Any concrete metric / protocol is left to
  EPIC-08 plan and is **REVIEW_REQUIRED** at architecture level
  (see §18 I-10).

### 4.11 Experiment runner (C-11)

- **Accepts:** a stage configuration (`configs/exp0X_*.yaml`); a seed.
- **Returns:** an `ExperimentSummary` carrying per-run internal
  metrics (C-09), per-run parameter dictionaries, per-run SHA-256
  of inputs and outputs, and configuration metadata.
- **Enforces:** no "winner", "best", "ranking" is computed at this
  layer (SYS-01 §1.7, AGENTS.md §2.5, LIM-11 in
  METHODOLOGY_LOCK_STATUS).
- **Does not:** introduce cross-algorithm ranking without a mentor
  decision (EPIC08-CROSS-ALG-01, EPIC08-CLAIM-01).

### 4.12 Run manifest writer (C-12)

- **Accepts:** stage name, unique run identifier, config path, config
  hash, input SHA-256 entries, output SHA-256 entries, seed,
  environment block.
- **Returns:** the path of the written manifest file (and the file
  on disk).
- **Enforces:** UTF-8 JSON, `sort_keys=True` for stable diffs;
  per the manifest schema in §10.
- **Does not:** mutate `data/raw/primary/`; does not embed
  `print()`-based run-critical information.

### 4.13 Profiling (C-13)

- **Accepts:** the feature dataframe; a label array; a configuration
  block.
- **Returns:** a `SegmentProfile` carrying per-segment descriptive
  statistics (count, mean, median, std, min, max, quantiles) for
  every feature column.
- **Enforces:** **no segment names** ("Champions", "Loyal", …).
  Each segment is referred to by its integer label only
  (SYS-01 §1.10, AGENTS.md §3 Profiling, CON-16 in SYS-01).
- **Does not:** produce business interpretation or activation
  recommendations — that is the marketing module (REVIEW_REQUIRED,
  see §3.1).

### 4.14 On Python code-illustrative type signatures

Earlier drafts of this section embedded illustrative Python code
blocks (def signatures, dataclass shapes). They have been removed
because they tend to be read as implementation contracts, which is
not the role of an architecture document. Where a Python
signature is needed to clarify a contract, it appears in the
component's implementation module, not in SYS-02.

---

## 5. Runtime view — end-to-end main flow

The main flow is the sequence executed when the operator runs
EXP-01 (baseline). Other experiments share most of the same steps.

```
Operator
   │  (command line)
   ▼
scripts/run_exp01_baseline.py            [C-02 driver]
   │  load
   ▼
src/customer_segmentation/config/        [C-01 config registry]
   │  validated config
   ▼
src/customer_segmentation/data/loader.py [reads data/raw/primary/, READ-ONLY]
   │  raw transactions DataFrame
   ▼
src/customer_segmentation/preprocessing/ [C-03]
   │  cleaned DataFrame + ProcessingReport
   ▼
src/customer_segmentation/aggregation/   [C-04]
   │  customer-level DataFrame
   ▼
src/customer_segmentation/features/      [C-05]
   │  feature DataFrame (RFM + extended)
   ▼
src/customer_segmentation/transformation/ [C-06]
   │  transformed feature DataFrame + TransformationReport
   ▼
src/customer_segmentation/clustering/registry.py   [C-07]
   │  one of 5 algorithm classes
   ▼
src/customer_segmentation/clustering/runner.py     [C-08]
   │  labels + fitted estimator
   ▼
src/customer_segmentation/clustering/metrics.py    [C-09]
   │  InternalMetrics (no WCSS in baseline; + diagnostics on request)
   ▼
src/customer_segmentation/clustering/artifacts.py   [C-12]
   │  reports/<stage>/<run_id>_manifest.json + per-run parquet
   ▼
Operator (reads reports/)
```

### 5.1 Why the main flow is strictly linear

- Each stage writes a parquet file plus a manifest entry **before**
  the next stage starts. This makes partial reruns possible
  (NFR-REP-002).
- Each stage reads its inputs from a known path under `data/` or
  `reports/` — never from a previous stage's in-memory state.
  This makes lineage reconstructable from disk alone (NFR-AUD-001).
- There is no feedback loop, no hyperparameter search running
  inside the main flow, and no model registry. Search is an
  explicit experiment (EXP-03) that lives in `scripts/` not in
  the main flow (SYS-01 §1.7).

### 5.2 Where experiments deviate from the main flow

This table reflects the **current locked scope** of each experiment
(ADR-0004 + METHODOLOGY_LOCK_STATUS). The "Algorithm coverage"
column names which algorithms are in scope **for that experiment**
under the current methodology. It is **not** a recommendation, and it
is **not** a cross-algorithm ranking.

| Experiment | Stages before clustering                              | Loop axis                                                    | Algorithm coverage (current scope)                       |
| ----------- | ----------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| EXP-01      | full preprocessing → transformation                 | none (single fixed configuration)                            | one fixed algorithm, fixed k                            |
| EXP-02      | full preprocessing → transformation             | k (number of clusters)                                       | K-Means, Agglomerative                                  |
| EXP-03      | full preprocessing → transformation             | algorithm-specific hyperparameter grids                       | all 5 algorithms                                         |
| EXP-04      | full preprocessing → transformation          | **preprocessing variants only** (RQ2 / METHODOLOGY_LOCK_STATUS) | one algorithm (K-Means per LIM-03), K fixed (LIM-04)        |
| EXP-05      | full preprocessing → transformation             | seeds (Block R) + perturbation (Block N); see Block coverage below | per-algorithm, see Block coverage below                    |

EXP-04 notes (current scope):
- **Preprocessing sensitivity only.** The current EXP-04 scope is
  the **preprocessing axis** under a fixed feature representation
  (RQ2 reformulation, ADR-0004).
- **RFM-only vs RFM-Extended feature-set sensitivity is FUTURE WORK**
  (RQ2 reformulation; tracked by
  `RFM_ONLY_FUTURE_WORK_PLAN.md`). It is **not** part of C-11 today
  and **not** listed as a current capability.
- EXP-04 currently runs on K-Means only with a fixed k
  (LIM-03, LIM-04 in METHODOLOGY_LOCK_STATUS).

EXP-05 notes (RQ3, EXP-05 Block R / S / N coverage per research evidence):
- **Block R (reproducibility / same-seed rerun):** the experiment
  runs the selected algorithm multiple times with the same seed and
  confirms label agreement (FR-EXP-09 in SYS-01, NFR-01).
- **Block S (seed sweep):** runs the selected algorithm across a
  small seed set and measures label agreement; deterministic-only
  configurations are excluded by design (LIM-06).
- **Block N (noise / perturbation):** perturbs the feature matrix
  with a small Gaussian perturbation (sigma grid), runs the
  algorithm, and measures label agreement.
- The specific stability metric and label-matching protocol are
  **owned by the EPIC-08 plan** and are **not** hard-coded in the
  architecture (see §4.10 and §18 I-10).

EXP-03 hyperparameter grids **must come from configuration** (C-01),
not from hard-coded constants (SYS-01 §1.13, NFR-ARC-003).

### 5.3 Algorithms → drivers and experiments

The five approved algorithms are wired into the prototype as follows.
This mapping is normative for **scope** (which algorithm classes may be
referenced by name): any driver that runs an algorithm outside this
table is by definition outside scope (SYS-01 §1.2, ADR-0003). It is
**not** a statement that every algorithm is exercised by every
experiment; per-experiment coverage is governed by §5.2 and by the
experiment's own approved plan.

| Algorithm       | Source module (research core)                                    | Algorithm class may be referenced by drivers | Notes                                          |
| --------------- | ---------------------------------------------------------------- | --------------------------------------------- | ---------------------------------------------- |
| K-Means         | `src/customer_segmentation/clustering/kmeans.py`                  | yes                                           | baseline algorithm; supports WCSS diagnostic  |
| Agglomerative   | `src/customer_segmentation/clustering/agglomerative.py`          | yes                                           | supports linkage + k sweeps                   |
| DBSCAN          | `src/customer_segmentation/clustering/dbscan.py`                 | yes                                           | density-based; WCSS not defined               |
| GMM             | `src/customer_segmentation/clustering/gmm.py`                    | yes                                           | probabilistic; WCSS not defined                |
| Fuzzy C-Means   | `src/customer_segmentation/clustering/fuzzy_cmeans.py`           | yes                                           | soft assignments; WCSS not defined             |
| ~~K-Medoids~~   | `src/customer_segmentation/clustering/kmedoids.py` (existing)    | **no** — registry rejects; module retained for historical reference only | OUT per ADR-0003 / SYS-01 §1.2 / LIM-02 |

SYS-02 does **not** add wrappers around these modules. It calls them
through the existing registry (`clustering/registry.py`, C-07) and
runner (`clustering/runner.py`, C-08). If a wrapper is later needed
for a reason not present today, it must be proposed as an ADR
(AGENTS.md §2.9).

---

## 6. Data flow

### 6.1 Logical data flow

```
data/raw/primary/Online Retail.xlsx                (read-only, immutable)
        │
        ▼
data/interim/<stage>/<run_id>/<artifact>.parquet   (cleaned, imputed, outliers)
        │
        ▼
data/processed/<stage>/<run_id>/<artifact>.parquet (aggregates, features, transformed)
        │
        ▼
reports/<stage>/<run_id>/<artifact>.parquet        (labels, metrics, profiles, manifest)
```

### 6.2 Path handling rule

- All data paths are **resolved from `configs/*.yaml`**, never
  hard-coded (SYS-01 §1.13, NFR-ARC-003, AGENTS.md §5).
- The repository working directory is the single root. No absolute
  paths. No environment-specific defaults.
- `data/raw/primary/` is read-only at the filesystem level (SYS-01
  §1.3, AGENTS.md §2.12).

### 6.3 Schema handoff between stages

Each stage consumes a documented schema and produces a documented
schema. The schema is the same one documented in
`docs/data_dictionary/` for the underlying columns and is extended
per stage with new derived columns. Example:

| Stage       | Input columns                  | Output columns                                                  |
| ----------- | ------------------------------ | --------------------------------------------------------------- |
| Aggregation | InvoiceNo, StockCode, Quantity, UnitPrice, CustomerID, InvoiceDate, CancellationFlag | CustomerID, n_transactions, total_quantity, total_spend, ... |
| RFM         | CustomerID + dates             | CustomerID, Recency, Frequency, Monetary                        |
| Transformation | RFM + extended               | CustomerID + same names, transformed values                     |
| Reporting     | (label, feature)               | CustomerID, label, feature columns + metric columns            |

The full schema for the prototype output is recorded in SYS-03 (Data
Model), which is the owner of column-level contracts (this SYS-02
document only sketches the per-stage hand-off direction).

---

## 7. Deployment view

There is no production deployment topology in this prototype
(SYS-01 §1.12, §5). The "deployment view" for SYS-02 is therefore
limited to the **local execution environment**.

### 7.1 Local execution environment

- **Hardware:** a single workstation (no cluster, no GPU cluster,
  no distributed compute). The architecture does not require
  multi-node execution.
- **Operating system:** Linux (Ubuntu 22.04 LTS-class) or macOS. The
  repository is platform-agnostic for the algorithms in scope
  (SYS-01 §1.13).
- **Python:** the version pinned in `pyproject.toml` (currently
  3.11.x). Recorded in run manifests.
- **Dependency installation:** `pip install -e .` from the
  repository root, or the project's standard install command.
- **Working directory:** the repository root. All paths are relative
  to it.

### 7.2 What is *not* in the deployment view

- No containers, no Dockerfiles, no Kubernetes manifests in SYS-02
  scope.
- No cloud accounts, no remote storage, no remote services.
- No CI/CD pipeline. CI configuration is **out of scope** for
  SYS-02; if CI is later added, it is owned by whichever SYS-NN
  document is responsible for test strategy (per SYS-01 §11.5; see
  also §18 I-09 on the SYS-03..06 mapping convention).
- No reverse proxy, no API gateway, no TLS termination.

### 7.3 What is in scope for the deployment view

- The Python interpreter and its pinned dependencies.
- Required CLI tools: `python`, `pytest`, `ruff`, `black`.
- The input file `data/raw/primary/Online Retail.xlsx` (read-only,
  pre-existing).
- The output directories `data/interim/`, `data/processed/`,
  `reports/` (writable by the user account running the scripts).

---

## 8. Operational view

There is no production operations surface for this prototype
(SYS-01 §1.12, §5). The "operational view" for SYS-02 is therefore
limited to the **manual, local, single-user execution model**.

### 8.1 Single-user, single-workstation execution

- One researcher runs scripts from the command line.
- No concurrent runs on the same checkout. If two runs share
  inputs, the run manifest disambiguates them by `run_id`.
- No scheduling. No cron, no systemd timer, no GitHub Action.

### 8.2 Run identity

- Every driver invocation generates a **unique run identifier**
  (`run_id`) of the form `<stage>_<UTC-timestamp>_<6-hex>`,
  derived from the platform clock plus a small random suffix.
- `run_id` is the primary key for the run manifest and for every
  artefact under `reports/<stage>/<run_id>/`. It exists to make a
  run uniquely addressable on disk and in logs; it is **not** a
  reproducibility contract on its own.
- **Reproducibility** of the run's output is provided by the
  combination of (a) **input SHA-256**, (b) **config hash**,
  (c) **seed**, (d) **environment block** (Python version, key
  library versions, OS), and (e) **output SHA-256**. These five
  fields together are what the manifest records and what a reviewer
  uses to verify that a rerun produced the same labels (FR-EXP-09,
  NFR-01, EXP-05 Block R). The unique `run_id` only identifies
  *which* run produced the artefact.

### 8.3 Logging

- One log file per run, under `reports/<stage>/<run_id>/<run_id>.log`,
  plain UTF-8 text.
- Log level is read from configuration (`configs/logging.yaml` or
  an equivalent key in the stage config). Default level: INFO.
- No log shipping, no centralised log store.

### 8.5 Restart policy

- A run that fails after writing artefacts to disk does **not**
  overwrite previously written artefacts; it appends `.partial` to
  the artefact filenames until the manifest is written. A run
  whose manifest is successfully written is considered complete;
  a run without a manifest is incomplete and may be re-run.
- The researcher inspects `reports/<stage>/<run_id>/` to triage
  failed runs.

---

## 9. Cross-cutting concerns

### 9.1 Configuration discipline

- All methodology-affecting values live under `configs/`.
- Scripts and modules read configuration; they do not embed values.
- A change to a configuration file is recorded as a separate
  change in version control (commit / PR) and is accompanied by a
  brief note in `docs/experiment_logs/` (SYS-01 §1.13).

### 9.2 Reproducibility

Per FR-EXP-09 and NFR-01, reproducibility of a run's output is
defined by the combination of the following five fields, **all of
which are recorded in the run manifest** (§10):

1. **Input SHA-256** of every declared input artefact (raw dataset,
   interim artefacts, processed dataset — content-addressed).
2. **Config hash** of the YAML configuration used for the run.
4. **Seed** (read from configuration; never generated at runtime).
3. **Environment block** (Python interpreter version, key library
   versions, OS).
5. **Output SHA-256** of every declared output artefact.

A reviewer reruns a configuration and compares the new output
SHA-256s against the manifest; identical SHA-256s ⇒ the run
reproduced. Where the underlying library supports it, determinism
is enforced (`numpy.random`, `random`, scikit-learn
`random_state`, `PYTHONHASHSEED`). EXP-05 Block R is the
methodology-level enforcement of this rule.

### 9.3 Auditability

- Every output artefact has a path back, through the manifest, to
  the configuration file, the input SHA, and the run identity
  (NFR-AUD-001).
- The manifest is JSON, machine-readable, UTF-8, `sort_keys=True`
  for stable diffs (NFR-AUD-002).

### 9.4 Modularity

- Per NFR-ARC-002, modules under `src/customer_segmentation/` are
  organised by responsibility. Cross-module imports go through
  package `__init__.py` or explicit module paths, never through
  private symbols (`_*`).
- Each module has at least one unit test under `tests/` whose name
  starts with `test_<module>.py` (AGENTS.md §2.13).

### 9.5 Error handling

- Errors are raised as early as possible.
- Configuration errors fail before any pipeline starts (NFR-REP-001).
- Schema mismatches fail at the data loader boundary, before
  preprocessing mutates state.
- Numerical errors (overflow, NaN propagation) are caught at the
  stage boundary and recorded in the run manifest, not silently
  swallowed.

### 9.6 Security and privacy

- No personally identifying information is added by any component
  beyond the existing `CustomerID` (already in the dataset).
- No data leaves the workstation. No network calls in the
  prototype code path (SYS-01 §1.12).
- Raw and processed datasets are not committed to the repository
  (AGENTS.md §2.12).

### 9.7 Internationalisation and locale

The prototype produces English-language reports. Numeric formatting
follows Python's default `repr` (no thousand separators in
artefacts, no locale-dependent decimal commas). This is documented
here so that any later locale change is a deliberate config
change, not a hidden Python default.

### 9.8 Versioning of configuration

- Configuration files are version-controlled together with code.
- A configuration file's content hash is recorded in the manifest.
- A configuration change without a corresponding code change is
  recorded in `docs/experiment_logs/` (SYS-01 §1.13).

---

## 10. Lineage and run manifest

Every run produces a single manifest document. The manifest is the
**single source of truth** for "what was run, with what, on what input,
to what output".

### 10.1 Manifest location

`reports/<stage>/<run_id>/<run_id>_manifest.json`

`run_id` is the unique run identifier (§8.2). It is **not** a
reproducibility contract on its own; reproducibility is provided by
the combination of `inputs.*.sha256`, `config_hash`, `seed`,
`environment`, and `outputs.*.sha256` (see §9.2).

### 10.2 Manifest schema (normative)

The five reproducibility fields are the **only** fields required to
establish that a rerun reproduced the same output. All other fields
are descriptive metadata.

```json
{
  "run_id": "exp01_2026-01-15T10-00-00Z_a1b2c3",
  "stage": "exp01_baseline",
  "schema_version": "1.0.0",
  "created_utc": "2026-01-15T10:00:00Z",
  "config_path": "configs/exp01_baseline.yaml",
  "config_hash": "sha256:<hex>",
  "inputs": {
    "raw_transactions": {
      "path": "data/raw/primary/Online Retail.xlsx",
      "sha256": "sha256:<hex>",
      "row_count": 0
  },
    "preprocessed": {
      "path": "data/interim/preprocessing/<run_id>/cleaned.parquet",
      "sha256": "sha256:<hex>",
      "row_count": 0
    }
  },
  "outputs": {
    "labels": {
      "path": "reports/exp01_baseline/<run_id>/labels.parquet",
      "sha256": "sha256:<hex>",
      "row_count": 0
    },
    "internal_metrics": {
      "path": "reports/exp01_baseline/<run_id>/internal_metrics.json",
      "sha256": "sha256:<hex>"
    }
  },
  "seed": 0,
  "environment": {
    "python": "3.11.x",
    "platform": "linux",
    "key_libraries": {
      "numpy": "x.y.z",
      "pandas": "x.y.z",
      "scikit-learn": "x.y.z",
      "scipy": "x.y.z"
    }
  },
  "assumptions": [],
  "pending_decisions": []
}
```

Key rules:

- `schema_version` follows semver. A breaking change to the
  manifest schema is a new major version.
- All paths are **repository-relative**, never absolute.
- `assumptions` and `pending_decisions` are free-form; they exist
  so that the manifest is also a small audit log (NFR-AUD-001/002).
- `inputs.*.row_count` and `outputs.*.row_count` are present where
  the artefact is row-shaped; omitted for metrics / plots.
- `run_id` is unique per invocation; reproducibility is governed by
  the five-field combination, not by `run_id`.

---

## 11. Failure modes and partial-rerun safety

Because the prototype runs as a sequence of long steps on a real
dataset, partial failures must not leave the operating pipeline in an
unrecoverable state. This section enumerates the failure modes the
architecture responds to, and the response.

### 11.1 Failure mode matrix

| Stage              | Failure                                          | Detection                                  | Response                                                                                                  |
| ------------------ | ------------------------------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| C-01 config        | invalid / missing keys                          | schema validation in load_config()         | raise before any pipeline starts (NFR-REP-001); no artefacts written                                    |
| C-01 config        | unknown algorithm name                           | registry lookup                            | raise `UnknownAlgorithmError`; no artefacts written                                                       |
| C-03 preprocessing | schema drift in raw input                         | data loader checks                          | raise before any cleaning; raw data untouched (SYS-01 §1.3)                                                |
| C-03 preprocessing | numerical exception (overflow, all-NaN column)  | per-stage NaN/Inf guard                    | record in `ProcessingReport.errors`; abort the run; re-run.sh                                                    |
| C-04 aggregation   | duplicate `CustomerID` produced by aggregation rule | post-aggregation uniqueness check       | raise; do not silently deduplicate without an ADR (AGENTS.md §2.9)                                        |
| C-05 features      | RFM reference date missing from config            | config schema                              | raise at C-01; cannot start                                                                              |
| C-06 transformation | non-numeric column in converted matrix                          | in type spec                                              | raise at runtime; do not coerce                                                                                     |
| C-08 clustering    | algorithm does not converge                      | estimator's own check                        | record in `ClusterResult.status`; surface in report; do not invent a label array                        |
| C-08 clustering    | all labels identical (degenerate cluster)       | post-fit label cardinality check            | record as observation; do not stop                                                          |
| C-09 metrics       | degenerate labels (single label) make silhouette undefined | metrics layer check                            | record `silhouette = NaN`; do not impute; do not drop the row                                          |
| C-12 manifest      | output file write failure (disk full, permission) | `OSError` at write                         | raise; previous `.partial` artefacts retained (see §8.5); re-run                                          |
| Whole run          | uncaught exception                                | driver top-level                            | exit non-zero; manifest may be missing → run incomplete → in §8.5                                                  |

### 11.2 Partial-rerun safety rule

A failed run never silently overwrites a previous successful run.
A successful run is identified by the presence of its manifest.
A failed run without a manifest may be re-invoked; the new
invocation produces a new `run_id`, and any new artefacts are
written under the new run directory (no in-place overwrite of the
old one).

### 11.3 What the architecture does *not* do on failure

- It does not retry a failing stage automatically. Auto-retry
  hides the source of the failure (NFR-AUD-001).
- It does not impute missing values to make a stage "succeed".
  Missing-value policy is part of methodology and is owned by the
  configuration (SYS-01 §1.13).
- It does not delete partial artefacts on failure. The researcher
  inspects `reports/<stage>/<run_id>/` to triage.

---

## 12. Cross-component relationships

### 12.1 Dependency graph (compile-time)

```
C-02 (driver) → C-01 (config) → filesystem
C-02 → C-03, C-04, C-05, C-06, C-08, C-09, C-12
C-08 → C-07
C-09 ← C-08
C-12 ← C-03, C-04, C-05, C-06, C-08, C-09
C-13 ← C-05, C-06, C-08
C-15 (manifest verifier) ← C-12
```

C-15 is a thin verification utility that reads a manifest and
re-hashes its declared inputs/outputs. It is a separate script
`scripts/verify_manifest.py`. Its design is deferred
(see §18 I-05); it is **not** part of the SYS-02 main flow.

### 12.2 Allowed and forbidden imports

- A driver (`scripts/`) is allowed to import from
  `customer_segmentation.*`. It is **not** allowed to import
  private symbols (`_*`) or to reimplement pipeline logic.
- A pipeline module is allowed to import from sibling pipeline
  modules and from `customer_segmentation.config`. It is **not**
  allowed to import `customer_segmentation.clustering.metrics` from
  inside a *transformation* module (no upward coupling from a
  downstream module to a downstream-of-downstream module).
- `metrics.py` does not import any other pipeline module. It
  imports only `numpy` / `scipy` / `sklearn` and reads `X` and
  `labels` as arrays.

### 12.3 Forbidden runtime patterns

- No algorithm class outside the locked set of five may be
  instantiated at runtime. The registry must raise.
- No `pickle.load` of a fitted estimator from a previous run is
  trusted without an explicit version pin in the manifest. This is
  documented but **not enforced** in the prototype (the prototype
  does not depend on cross-run pickle reuse).
- No `print` for run-critical information. Run-critical
  information goes into the manifest or the log file.
- No mutation of `data/raw/primary/` (SYS-01 §1.3).

---

## 13. Configuration layout

SYS-02 is **not the owner** of configuration policy. The configs
under `configs/` are owned by their respective methodology
decisions (ADR-0001..0004, FE-06, EXP-0X plans,
METHODOLOGY_LOCK_STATUS). SYS-02's role here is only to **point
at** the configuration files that already exist and to assert that
**all methodology-affecting values come from them**.

If a new capability is added that no existing config can describe,
the new config file is added by the corresponding methodology
decision (with an ADR), not by SYS-02.

No configuration file is created or modified by SYS-02 itself.
Changes to existing configs require an ADR (AGENTS.md §2.9,
SYS-01 §1.13).

---

## 14. Mapping SYS-01 requirements → architecture

This table maps SYS-01 IDs to the architectural element(s) that
satisfy them. The IDs follow SYS-01 §10 (FR-…) and §11 (NFR-…,
CON-…, OOS-…) — not the "SRS-…" naming used in some research notes;
the SRS IDs here are an alias, not a separate taxonomy.

| SYS-01 ID                         | Architecture element(s)                                  |
| --------------------------------- | -------------------------------------------------------- |
| FR-DATA-01, FR-DATA-02            | C-03 preprocessing + data loader (read-only)             |
| FR-DATA-03                        | C-12 manifest (input metadata) + reports                 |
| FR-DATA-04                        | C-05 features (feature info per column)                  |
| FR-DATA-05, FR-DATA-06            | C-01 config (allow-list) + C-02 driver (no edit action)   |
| FR-EXP-01                        | C-07 registry (only 5 algorithms; K-Medoids rejected)     |
| FR-EXP-02                        | C-05 features (RFM Extended 14 features; no RFM-only UI)  |
| FR-EXP-03                        | C-06 transformation (FE-06 C7; status WORKING_ASSUMPTION) |
| FR-EXP-04, FR-EXP-05              | C-01 config + C-02 driver (per-algorithm params + seed)  |
| FR-EXP-06                        | C-08 runner (reuses existing `clustering/runner.py`)      |
| FR-EXP-07                        | C-12 manifest writer + §10 schema                         |
| FR-EXP-08                        | C-02 driver (status lifecycle) + §11.1 failure matrix    |
| FR-EXP-09                        | §8.2 + §9.2 + §10 (five-field reproducibility contract)   |
| FR-EXP-10                        | C-14 reporting writer (run history)                       |
| FR-CLUSTER-01                    | C-07 registry (`list_registered()` = 5 names)            |
| FR-CLUSTER-02                    | C-08 runner (output dtype/shape contract)                |
| FR-CLUSTER-03                    | C-08 runner (GMM `soft_probabilities`)                   |
| FR-CLUSTER-04                    | C-08 runner (FCM `soft_membership`)                      |
| FR-CLUSTER-05                    | C-08 runner (DBSCAN noise = -1; not assigned)             |
| FR-EVAL-01, FR-EVAL-02, FR-EVAL-03 | C-09 metrics layer (silhouette / DBI / CH)              |
| FR-EVAL-04                        | C-09 metrics layer + WCSS = diagnostic only             |
| FR-EVAL-05                        | C-09 metrics layer (runtime, n_repeat=5)                  |
| FR-EVAL-06                        | C-10 stability (reuses EPIC-08 evidence when available)   |
| FR-EVAL-07                        | C-13 profiling (cluster size distribution)               |
| FR-EVAL-08, FR-EVAL-09, FR-EVAL-10 | §4.8 "No winner" / §5.2 "no ranking" / §18 I-11         |
| FR-PRF-001 → FR-SEG-*             | C-13 profiling (per §3 / §4.13; no segment names)         |
| FR-VIZ-01..07                    | SYS-06 (out of scope here; FR-VIZ-06 = single source of cluster colour) |
| FR-MKT-01..06                    | **REVIEW_REQUIRED, not built** — see §3.1                |
| FR-REPORT-01, FR-REPORT-02       | C-14 reporting writer                                     |
| FR-REPORT-03                    | C-02 driver (no commit/push/PR actions)                   |
| NFR-ARC-002                      | §3 components, §12 dependency rules                      |
| NFR-ARC-003                      | §13 configuration layout, §9.1 configuration discipline   |
| NFR-01 (Reproducibility)         | §4.1 config validation, §9.2, §10 manifest               |
| NFR-AUD-001                      | §10 manifest, §6.2 path handling                          |
| NFR-AUD-002                      | §10 stable JSON manifest                                  |
| CON-01 (5 algorithms only)         | §3 C-07, §5.3 table, §12.3 forbidden patterns            |
| CON-02 (RFM Extended only)         | §4.5, §5.2 EXP-04 note (RFM-only = future)               |
| CON-03 (FE-06 C7 only)            | §4.6 transformation contract                             |
| CON-11 (EXP-03 NOT_AVAILABLE)      | §4.11 "no ranking"                                       |
| CON-16 (status not promoted)      | §3 "no segment names", §4.13                             |
| OOS-12 (RFM-only in UI = future)  | §4.5, §5.2 EXP-04 note                                    |

---

## 15. Non-functional requirements coverage

- **Performance is not a target for this prototype.** No SLAs, no
  latency targets, no throughput targets. Where a measurement is
  recorded (wall-clock time of one stage, memory peak), it is
  recorded as **observation**, not as **requirement**. This is a
  conscious choice: the prototype exists to compare internal
  metrics and stability on a fixed dataset, not to serve requests
  (SYS-01 §1.12, §5).
- **Availability** is not a target. The prototype is a single
  workstation. Recovery from a failed run is by re-running the
  script with a fresh `run_id`.
- **Scalability** is not a target. The dataset is the
  `Online Retail.xlsx` dataset, fixed.
- **Maintainability** is addressed via NFR-ARC-002 (modularity)
  and the per-module unit-test rule (AGENTS.md §2.13).
- **Portability** is addressed by Python-only code, no OS-specific
  calls in the pipeline layer, and `pyproject.toml` pinning
  minimum-supported versions.

---

## 16. Conformance — how a reviewer checks that the implementation matches this document

This section makes the SYS-02 architecture **checkable**, not just
readable. A reviewer can use the following checks to verify that an
implementation (a future prototype) actually implements SYS-02.

### 16.1 Module existence checks

The following files / modules must exist after the prototype is
implemented (paths are relative to the repository root):

- `scripts/run_exp01_baseline.py`
- `scripts/run_exp02_cluster_number.py`
- `scripts/run_exp03_hyperparameter_search.py`
- `scripts/run_exp04_preprocessing_feature_set.py`
- `scripts/run_exp05_stability.py`
- `src/customer_segmentation/config/loader.py` (extends existing
  `features/config_loader.py`, `transformation/config_loader.py`)
- `src/customer_segmentation/clustering/registry.py` (already
  exists; must reject non-5 names)
- `src/customer_segmentation/clustering/runner.py`
- `src/customer_segmentation/clustering/metrics.py`
- `src/customer_segmentation/clustering/artifacts.py`

Any of the above missing at the prototype handoff → non-conformance.

### 16.2 Behavioural checks

These are the smallest set of observable behaviours that demonstrate
SYS-02 conformance. They are documented here so a reviewer can run
them and compare to the architecture.

| ID     | Check                                                                                                                       | Expected                                                            |
| ------ | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| C-01-A | Calling `load_config()` with an unknown top-level key raises before any workflow starts.                                    | exception, no artefacts                                            |
| C-01-B | Calling `load_config()` with an unknown algorithm name raises.                                                              | `UnknownAlgorithmError` (or equivalent typed exception)            |
| C-07-A | `registry.get_algorithm("kmedoids")` raises.                                                                                  | exception                                                          |
| C-07-B | `registry.get_algorithm("kmeans")` returns the K-Means class.                                                              | class equality                                                       |
| C-08-A | `fit_one()` for DBSCAN emits `wcss=None` in `InternalMetrics`.                                                              | `wcss is None`                                                     |
| C-09-A | `evaluate_internal()` on a single-label vector produces `silhouette=NaN` and **does not** impute.                            | `isnan(silhouette)`                                                |
| C-12-A | A successful run writes exactly one `<run_id>_manifest.json` under `reports/<stage>/<run_id>/`.                              | file exists                                                         |
| C-12-B | The manifest's `inputs.*.sha256` matches the actual file SHA-256 of the declared input.                                    | hash equality                                                      |
| C-12-C | The manifest's `outputs.*.sha256` matches the actual file SHA-256 of the declared output.                                  | hash equality                                                      |
| NFR-IC-001 | Running `pytest tests/` passes.                                                                                                                       | tests pass                                                          |
| NFR-IC-002 | Running `ruff check .` passes.                                                                                                                   | exit 0                                                              |
| NFR-IC-003 | Running `black --check .` passes.                                                                                                                | exit 0                                                              |
| SCP-IC-001 | A driver (`scripts/run_explicitly_forbidden_marker.py`) that calls a non-5 algorithm does not exist.                                                          | file absent                                                        |
| SCP-IC-002 | `data/raw/primary/Online Retail.xlsx` is unchanged after a run (file mtime unchanged).                                                                  | mtime unchanged                                                    |

### 16.3 Configuration discipline checks

- A grep for `print(` in `src/customer_segmentation/` returns only
  debug-side uses (e.g. `__main__` blocks under `if __name__ ==
  "__main__":`); run-critical information is **not** printed (see §12.3).
- A grep for hard-coded paths in pipeline modules
  (`data/raw`, `reports/`, `Online Retail.xlsx`) returns no matches.
  All paths come from configuration.

### 16.4 Conformance documentation in the prototype handoff

The prototype handoff document must include, per stage, a short
section pointing back to the matching rows in §16.2, with the actual
observed values for that run. The handoff document is owned by SYS-05
(API Design) and is not designed here.

---

## 17. Mapping to brief deliverables

This document is the deliverable for the SYS-02 "System
Architecture" scope. It is **not** the deliverable for **SYS-03
(Data Model)**, **SYS-04 (ML Processing Pipeline)**, **SYS-05 (API
Design)**, or **SYS-06 (Prototype UI)**; those are separate
documents with their own scopes.

> **Important.** The SYS-03..06 mapping convention used in SYS-02
> (Data Model / ML Pipeline / API Design / Prototype UI) is per the
> human-directive override applied during the SYS-02 review pass.
> It **differs** from the mapping listed in SYS-01 §11.5 (Data
> Architecture / Interface-API / Test Strategy / UI-UX Design).
> See §18 I-09 for the divergence and the proposed action.

The brief asks for at least these architectural sections; this
document covers them as follows:

| Architecture topic                                | Section in this document |
| ------------------------------------------------- | ------------------------ |
| Overall architecture style                       | §2                       |
| Components and responsibilities                   | §3 / §4                  |
| Runtime view                                      | §5                       |
| Data flow                                         | §6                       |
| Deployment view (prototype-local)                 | §7                       |
| Operational view (prototype-local)                | §8                       |
| Cross-cutting concerns                            | §9                       |
| Lineage / run manifest                            | §10                      |
| Failure modes / partial-rerun safety              | §11                      |
| Cross-component relationships                     | §12                      |
| Configuration layout                              | §13                      |
| Mapping to requirements                           | §14                      |
| Non-functional coverage                           | §15                      |
| Conformance / how to verify                       | §16                      |
| Mapping to this brief section                    | §17 (this section)       |
| Open issues / pending review                      | §18                      |
| Change log                                        | §19                      |
| Glossary                                          | §B                       |

---

## 18. Open issues / pending review

| ID   | Issue                                                                                                            | Status                                                                                              |
| ---- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| I-01 | Marketing activation module is REVIEW_REQUIRED. No MKT-01..05 IDs in SYS-02.                                     | REVIEW_REQUIRED                                                                                     |
| I-02 | Whether EXP-05 stability grid (seeds, perturbation factor) belongs in `configs/` only or also                  | EVAL-PENDING                                                                                        |
| I-03 | Whether the prototype should write a top-level `RUN.md` summary per run in addition to JSON.                    | EVAL-PENDING                                                                                        |
| I-04 | Whether `manifest.schema_version` should start at `1.0.0` or `0.1.0` (the latter signals pre-release).          | EVAL-PENDING                                                                                        |
| I-05 | Whether `scripts/verify_manifest.py` (C-15) should be designed by SYS-02 or deferred.                           | EVAL-PENDING                                                                                        |
| I-06 | Whether the manifest `environment.key_libraries` should be auto-detected at runtime or pinned to a fixed list.  | EVAL-PENDING                                                                                        |
| I-07 | Profile segment names ("Champions", …) — explicitly **not** produced in this prototype.                         | DESIGN-EXPLICIT (SYS-01 §1.10, CON-16, FR-SEG-08)                                                  |
| I-08 | Whether K-Medoids will be added in a future prototype iteration. Currently OUT (ADR-0003).                      | POLICY-EXPLICIT (SYS-01 §1.2, ADR-0003, LIM-02)                                                    |
| I-09 | **SYS-03..06 mapping convention divergence.** SYS-02 uses (Data Model / ML Pipeline / API / UI) per human-directive override during the SYS-02 review pass. SYS-01 §11.5 lists (Data Architecture / Interface-API / Test Strategy / UI-UX Design). The two mappings are **not consistent**. | REVIEW_REQUIRED — mentor should pick one convention, update SYS-01 §11.5 and §A.1 if SYS-02 mapping is approved; otherwise re-align SYS-02 to SYS-01 §11.5. |
| I-10 | **Stability metric / matching protocol.** Specific stability metric (ARI / AMI / Hungarian / statistical test / CI method) is **not locked** at architecture level. Owned by EPIC-08 plan (METHODOLOGY_LOCK_STATUS §4 EPIC08-ARI / EPIC08-STAT / EPIC08-CI / EPIC08-RUNTIME). SYS-02 §4.10 only specifies the **logical contract** (per-run label arrays + aggregate agreement summary). | REVIEW_REQUIRED — concrete stability metric/protocol to be confirmed in EPIC-08 plan, not in SYS-02. |
| I-11 | **No cross-algorithm ranking / "best / winner / recommended / optimal / final" claims** anywhere in SYS-02 or in prototype. Cross-algorithm ranking requires mentor decision (EPIC08-CROSS-ALG-01, EPIC08-CLAIM-01, METHODOLOGY_LOCK_STATUS §7). | POLICY-EXPLICIT (AGENTS.md §2.5, §2.6, §2.10; FR-EVAL-08/09/10)                                      |
| I-12 | **EXP-04 axis is preprocessing only.** RFM-only vs RFM-Extended feature-set sensitivity is **FUTURE WORK** (RQ2 reformulation, ADR-0004, RFM_ONLY_FUTURE_WORK_PLAN.md, OOS-12). SYS-02 §5.2 / §14 reflect this. | POLICY-EXPLICIT — do not introduce feature-set sensitivity axis in current EXP-04 scope without mentor approval and an ADR. |
| I-13 | **EXP-05 Block R / S / N coverage** (per research evidence, LIM-06) — Block S excludes deterministic-only configurations by design; the current EXP-05 plan covers a subset of algorithms for Block S. SYS-02 §5.2 reflects Block coverage rather than "only one algorithm" coverage. | POLICY-EXPLICIT — coverage per algorithm per block is owned by EXP-05 plan, not by SYS-02.        |

---

## 19. Change log

| Date       | Author                          | Change                                                                                                                                                          |
| ---------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-10-07 | SYS-02 author (AI assist)       | Initial draft. Status DRAFT. Pending mentor/researcher review.                                                                                                  |
| 2026-10-07 | SYS-02 author (AI assist)       | **Review pass (this revision).** Applied mentor feedback: (1) updated SYS-03..06 mapping per human-directive override and flagged the divergence with SYS-01 §11.5 as I-09; (2) EXP-04 fixed — feature-set RFM-only axis marked FUTURE WORK (RQ2 reformulation); (4) EXP-05 corrected — uses Block R/S/N coverage per research evidence instead of "only one algorithm"; (5) C-10 / §4.10 / §18 I-10 — stability metric / matching protocol explicitly NOT LOCKED at architecture level (owned by EPIC-08 plan); (6) §4 reduced — logical Accepts/Returns/Enforces/Does-not contract replaces illustrative Python signatures; (7) §1.6 constraint removed — RFM-only is no longer treated as a current architecture scope; (8) `run_id` is now "unique run identifier", reproducibility is the five-field combination (input SHA + config hash + seed + environment + output SHA); (9) §14 mapping table rebuilt with SYS-01 FR-/NFR-/CON-/OOS- IDs (not the alias "SRS-…" naming); (10) §13 explicitly states SYS-02 is not the owner of config policy; (11) §16.4 attribution for handoff document corrected to SYS-05 (API Design). Status still DRAFT, REVIEW_REQUIRED. |

---

## A. References

- SYS-01 — Requirements: [`SYS-01_requirements.md`](./SYS-01_requirements.md)
- Methodology: [`docs/methodology/README.md`](../../methodology/README.md)
- Research questions: [`docs/methodology/research_questions.md`](../../methodology/research_questions.md)
- Algorithm scope (ADR-0003): [`docs/decisions/0003-algorithm-scope.md`](../../decisions/0003-algorithm-scope.md)
- Algorithm theory: [`docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md`](../../research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md)
- Data dictionary: [`docs/data_dictionary/data_dictionary.md`](../../data_dictionary/data_dictionary.md)
- AGENTS.md (operating rules): [`../../AGENTS.md`](../../../AGENTS.md)

---

## B. Glossary

| Term                | Meaning in this document                                                       |
| ------------------- | ------------------------------------------------------------------------------- |
| Prototype           | The single-machine, file-based, batch deliverable described in SYS-01 §1.12.  |
| Main flow           | The linear pipeline from raw transactions to internal metrics (SYS-02 §5).     |
| Experiment          | A run that loops on a single design axis (k, hyperparameters, feature set, seed).|
| Run manifest        | The per-run JSON document at `reports/<stage>/<run_id>/<run_id>_manifest.json`. |
| Internal metric     | Silhouette, Davies–Bouldin, Calinski–Harabasz (SYS-01 §1.9).                       |
| WCSS                | Within-cluster sum of squares. **Not a selection criterion** (SYS-01 §1.8).        |
| Algorithm registry | The factory in `clustering/registry.py` returning one of the five approved algorithms (SYS-01 §1.2). |
| REPOSITORY_ROOT     | The directory containing `pyproject.toml` and `configs/`.                       |
| Run identity        | The `<stage>_<UTC-timestamp>_<6-hex>` string that names one driver invocation. |
| REVIEW_REQUIRED     | Marker for components/decisions that require explicit mentor/researcher approval before being treated as final. |

---

> **End of SYS-02.** Status: DRAFT, REVIEW_REQUIRED.
> This document does **not** alter any methodology, dataset, algorithm
> scope, or research-question definition. Those remain owned by
> SYS-01 §1 and the original research plan in `docs/methodology/`.