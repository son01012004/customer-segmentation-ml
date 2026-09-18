# Agent Rules — Customer Segmentation ML

This file defines the **operating rules** for any AI agent (Cursor, GitHub
Copilot, Claude, custom agents, or any contributor) working on this
repository.

These rules are binding for the foundation phase and for every later
stage (FE-01, preprocessing, RFM, extended features, clustering,
evaluation, profiling, visualization).

If a rule here ever needs to change, the change must be made in a Pull
Request that is reviewed and recorded as an ADR in
[`docs/decisions/`](./docs/decisions/).

---

## 1. Read the repository first

Before editing any code or configuration, an agent must:

1. Read this `AGENTS.md` end to end.
2. Read `README.md` end to end.
3. Read `docs/methodology/` (current research questions and study design).
4. Read `docs/data_dictionary/` (current schema).
5. Read the most recent ADRs in `docs/decisions/`.
6. Read the most recent experiment log in `docs/experiment_logs/`.
7. Read the relevant `configs/*.yaml` for the stage being modified.

If the task is not clearly defined by the above, the agent must **stop**
and ask the human lead for clarification instead of guessing.

---

## 2. Hard constraints (DO NOT violate)

The following are **non-negotiable** for every agent action in this
repository.

### 2.1 Research integrity

- **Do not** modify the research questions in `docs/methodology/`.
- **Do not** modify the research methodology, unit of analysis, or
  benchmarking protocol.
- **Do not** modify the four benchmark algorithms: K-Means, K-Medoids,
  Agglomerative Clustering, DBSCAN. They are fixed by the methodology.
- **Do not** invent, fabricate, or estimate dataset statistics,
  hyperparameters, cluster counts, evaluation metrics, or any other
  numerical research result.
- **Do not** call any algorithm "best", "winning", or "recommended" until
  the full evaluation framework has been executed and documented in
  `docs/experiment_logs/`.

### 2.2 Data privacy

- **Do not** commit raw datasets (`data/raw/**`), interim data
  (`data/interim/**`), processed data (`data/processed/**`), or external
  data (`data/external/**`) to Git.
- **Do not** delete or move the primary dataset from
  `data/raw/primary/Online Retail.xlsx` without an explicit user request
  recorded as an ADR.
- **Do not** add new datasets without recording provenance (source URL,
  license, SHA-256) in `configs/dataset.yaml` and the relevant ADR.
- **Do not** commit generated reports or figures under `reports/**`.

### 2.3 Code organization

- All reusable logic must live in `src/customer_segmentation/`.
- Notebooks (`notebooks/`) are for exploration, reporting, and
  communication only. They must import from `src/`, not duplicate logic.
- Public functions and classes must have docstrings and type hints.
- New public behavior must come with at least one unit test under
  `tests/`.

### 2.4 Scope discipline

- **Do not** start a task that has not been explicitly assigned. For
  example, if FE-01 is the next stage, do not jump ahead into
  preprocessing, clustering, evaluation, profiling, or visualization
  unless the user has explicitly requested that scope.
- **Do not** edit files outside the scope of the assigned task. If an
  out-of-scope fix is required, mention it in the PR description and let
  the human reviewer decide.
- **Do not** rewrite large portions of files when a smaller change is
  sufficient.

### 2.5 Reproducibility

- All experiments must be logged in `docs/experiment_logs/` with: config
  hash, random seed, environment info, raw dataset SHA-256, and paths to
  generated artifacts.
- Random seeds must come from `configs/experiment.yaml` (or a
  stage-specific config), never from a hard-coded literal in code.

### 2.6 Decisions and provenance

- Every meaningful methodology or engineering decision must be recorded
  as an ADR in `docs/decisions/` using the template in that directory.
- The ADRs already in `docs/decisions/` are **immutable**. To reverse a
  decision, write a *new* ADR that supersedes the old one.
- The data dictionary in `docs/data_dictionary/` is the canonical source
  of column semantics. If a column is referenced in code or report, its
  meaning must already be documented there (or referenced via an ADR
  that fills the gap).

### 2.7 Git hygiene

- **Do not** run `git commit`, `git push`, `git add`, or any other
  state-changing Git command unless the user explicitly asks for it.
- **Do not** create or modify a remote (`git remote add`, `git remote
  set-url`), or create a GitHub repository on behalf of the user.
- Branch changes are out of scope unless explicitly requested.

---

## 3. Stage-by-stage guardrails

| Stage             | Forbidden actions                                                                   |
| ----------------- | ----------------------------------------------------------------------------------- |
| FE-01             | Running preprocessing, building features from raw data, fitting any model.          |
| Preprocessing     | Inventing row counts, dropping rules, or imputation values that are not audited.    |
| Feature eng.      | Changing the RFM formula or the extended-feature set without an ADR.                |
| Transformation    | Picking a scaler/transform without an ADR documenting the rationale.                |
| Clustering        | Picking a "best" k or algorithm before evaluation runs.                              |
| Evaluation        | Reporting internal metrics without stability and runtime; ignoring silhouette for     |
|                   | density-based clusters.                                                             |
| Profiling         | Inventing segment names ("Champions", "Loyal") without an ADR-supported mapping.    |
| Visualization     | Hard-coding cluster colors or labels in multiple places — use a single source.      |

---

## 4. Required workflow for any non-trivial change

1. Confirm the assigned task ID (DS-05, FE-01, PR-02, ...).
2. Confirm the scope (which files, which configs).
3. Read the relevant section of this file and the README.
4. Make the change.
5. Update or add tests under `tests/`.
6. Run `ruff check .`, `black --check .`, and `pytest` locally.
7. If a decision was made, write the ADR **before** opening the PR.
8. Open a PR using `.github/PULL_REQUEST_TEMPLATE.md`.
9. Wait for human review. Do not self-merge.

---

## 5. Forbidden shortcuts

- Copy-pasting logic from a notebook into `src/` (or vice versa).
- Adding a "quick fix" that bypasses the config layer.
- Hard-coding paths instead of resolving them from `configs/*.yaml`.
- Adding a new dependency to `requirements.txt` without also adding it
  to `[project.dependencies]` in `pyproject.toml` and without an ADR
  explaining why.
- Skipping the data dictionary update when adding a new feature column.

---

## 6. Escalation

If at any point an agent:

- Is unsure about the scope of a task,
- Discovers a methodology contradiction,
- Needs to violate any rule above,

…then the agent must **stop**, surface the issue clearly in the
conversation, and wait for human direction. Do not improvise.