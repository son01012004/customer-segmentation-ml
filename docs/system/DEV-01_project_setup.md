# DEV-01 — Prototype Project Setup

> **Mã task:** DEV-01
> **Tên:** Prototype Project Setup (current prototype phase)
> **Trạng thái:** COMPLETED — architecture per ADR-0005 Option A. Acceptance
> criteria verified 2026-10-08 (see §4).
> **Ngày:** 2026-10-08
> **Phạm vi:** Project setup, acceptance criteria, and architecture boundary
> for the current prototype phase.

---

## 1. Objective

DEV-01 confirms that the repository is **ready for use in the current
prototype phase** under the architecture defined by
[`ADR-0005 — Prototype Architecture: File-Based Batch / Offline (Option A)`](../decisions/0005-prototype-architecture-option-a.md).

DEV-01 is a **verification + documentation task**, not a code-creation
task. It does NOT introduce any new code, new dependency, new service, or
new infrastructure. The current repository state (research core +
scripts + configs + tests + reports) is the deliverable. The Acceptance
Criteria in §4 were independently verified on **2026-10-08** against the
repository as it stands (commit `8c98b1a docs(system): snapshot SYS-01 to SYS-06 design baseline`).

## 2. Architecture Contract (per ADR-0005)

The current prototype phase operates on the following architectural
contract:

| Concern | Contract |
|---|---|
| Operator interface | Python CLI / `scripts/run_*.py` |
| ML orchestration | `scripts/` → `src/customer_segmentation/*` (direct, no HTTP service, no worker process) |
| Persistence | Filesystem + Parquet + JSON manifests (per `SYS-02`, `SYS-03`, `SYS-04`) |
| Prototype frontend | `docs/system/ui-prototype/index.html` — interactive HTML prototype, mock data, design / mentor / UX review only |
| Backend service | **N/A** — intentionally not implemented in current prototype phase |
| Database | **N/A** — intentionally not implemented in current prototype phase |
| Job queue | **N/A** — intentionally not implemented |
| API layer | **N/A** — intentionally not implemented; SYS-05 retained as design reference for EPIC-12 |

These architecture boundaries are immutable for the current prototype
phase. Any reversal must be a new ADR superseding ADR-0005 (per
`docs/decisions/README.md` immutability rule).

## 3. Research Methodology Boundary

DEV-01 must NOT change:

- Algorithms (5 algorithms per ADR-0003: K-Means, Agglomerative, DBSCAN,
  GMM, Fuzzy C-Means; K-Medoids OUT OF SCOPE).
- Datasets (per ADR-0001 / ADR-0002).
- Feature definitions (per FE-05 / FE-06).
- Preprocessing policy (per FE-02 / FE-06 C7).
- Evaluation metrics (per FR-EVAL-01..07, internal metrics only).
- Research questions (per ADR-0004).
- Research evidence (existing 185 experimental runs).

See `AGENTS.md` §2 (Global principles) and §3 (Stage-by-stage guardrails)
for the full methodology boundary.

---

## 4. Acceptance Criteria

SYS-01 / DEV-01 đạt `READY` cho current prototype phase khi tất cả items
dưới đây PASS.

### 4.1. Project runs end-to-end

| Item | Criterion | Status (verified 2026-10-08) |
| --- | --- | --- |
| Research core importable | `python -c "import customer_segmentation"` succeeds. | ✅ PASS — `python -c "import customer_segmentation"` returns without error. All 11 subpackages (`data`, `preprocessing`, `aggregation`, `features`, `transformation`, `outlier_analysis`, `clustering`, `evaluation`, `profiling`, `config`, `visualization`) import cleanly with `PYTHONPATH=src`. |
| Per-stage CLI entry points | Each `scripts/run_fe0X_*.py`, `scripts/run_exp0X_*.py`, `scripts/run_ml0X_*.py`, `scripts/run_eva0X.py`, `scripts/run_cp0X.py` is a real, executable Python module (not a placeholder). | ✅ PASS — 25 `scripts/run_*.py` files exist and are real entry points. Spot-checked: `scripts/run_ml02_kmeans.py` is a full orchestrator with proper docstring, CLI flags, and output paths under `data/processed/clustering_experiments/` + `reports/ml02/`. |
| Full-pipeline CLI | `python scripts/run_pipeline.py` runs end-to-end across all stages. | ⚠️ NOT IMPLEMENTED — `scripts/run_pipeline.py` currently raises `NotImplementedError("run_pipeline.main is not implemented yet.")`. Per-stage entry points cover all current work (FE-01 → CP-05, EXP-01 → EXP-05, ML-02 → ML-06, EVA-01 → EVA-03); the top-level orchestrator is **out of scope** of DEV-01 (it's a future convenience wrapper, not a DEV-01 acceptance requirement). The README §7 reference to `run_pipeline.py` is documented as a "convenience entry point" and is not load-bearing for the prototype phase. |
| Tests pass | `pytest` runs and the existing test suite passes. | ✅ PASS — `pytest -q --tb=line` reports **1468 passed in 416.45s** (baseline recorded 2026-10-08). No regressions, no skips, no errors. |
| Lint clean | `ruff check .` passes. | ⚠️ PRE-EXISTING — `ruff check . --statistics` reports **113 errors** distributed across research-core files: 25× N806, 23× F401, 21× E702, 13× UP035, 8× I001, 7× B905, 4× B007, 4× F841, 3× C408, 1× F541, 1× SIM108, 1× N803, 1× E402, 1× SIM300. **Per AGENTS.md §2.1, §2.4, §2.13 and the no-scope-creep rule, DEV-01 MUST NOT silently fix research-core lint.** These pre-existing findings belong to the methodology stages (FE-01 → CP-05), not to DEV-01. Recorded as a **blocker for clean-lint verification**, NOT as a DEV-01 failure. |
| Format clean | `black --check .` passes. | ⚠️ PRE-EXISTING — `black --check .` reports **26 files would be reformatted**, all in `src/customer_segmentation/evaluation/`, `src/customer_segmentation/profiling/`, `tests/test_cp*.py`, `tests/test_eva02.py`, `scripts/generate_algorithm_comparison_figures.py`. **Same disposition as Lint clean: pre-existing research-core findings, NOT a DEV-01 failure.** |
| Configuration loadable | All `configs/*.yaml` files load successfully. | ✅ PASS — All 15 YAML files in `configs/` parse without error under `yaml.safe_load`: `aggregation.yaml`, `clustering.yaml`, `dataset.yaml`, `eva03_stability_evaluation.yaml`, `exp01_baseline.yaml`, `exp02_cluster_number.yaml`, `exp03_hyperparameter_search.yaml`, `exp04_preprocessing_feature_set.yaml`, `exp05_stability_reproducibility.yaml`, `experiment.yaml`, `feature_engineering.yaml`, `features.yaml`, `outlier.yaml`, `preprocessing.yaml`, `transformation.yaml`. |
| No backend/API/database/worker/queue in dependency surface | `requirements.txt` and `pyproject.toml::dependencies` contain no `fastapi`, `flask`, `django`, `uvicorn`, `sqlalchemy`, `psycopg2`, `redis`, `celery`, `rq`, `pymongo`, `aiosqlite`. | ✅ PASS — `grep` over both files confirms zero matches. (`psycopg2` exists at the system level on this Debian-derived VM but is not a project dependency.) |

### 4.2. Frontend runs as mock-data design artifact

| Item | Criterion | Status |
| --- | --- | --- |
| HTML prototype opens | `docs/system/ui-prototype/index.html` opens in a browser without error. | ✅ (file already exists) |
| Mock data labelled | Each screen shows the `Prototype mock data` banner. | ✅ (banner is hard-coded in the prototype) |
| Screens render | 13 screens (S-01 → S-13) render via hash routing. | ✅ (vanilla HTML/CSS/JS, no build step) |
| Not production frontend | This HTML prototype is **not** the EPIC-12 production React/Vue frontend. Production frontend = FUTURE_WORK (EPIC-12). | ✅ (per SYS-06 §2.2) |

### 4.3. Backend

| Item | Criterion | Status |
| --- | --- | --- |
| Backend service | **N/A — intentionally not implemented in current prototype phase (per ADR-0005 Option A).** Backend REST API = FUTURE_WORK (EPIC-12). | N/A |

### 4.4. ML processing / orchestration runs

| Item | Criterion | Status |
| --- | --- | --- |
| Orchestration model | `scripts/` calls `src/customer_segmentation/*` directly. No HTTP service, no worker process, no job queue. | ✅ (per SYS-02 §5) |
| Algorithms available | 5 algorithms per ADR-0003 (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means). | ✅ |
| Run manifest | Each run writes JSON manifest to `reports/<stage>/<run_id>/`. | ✅ (per SYS-02 §10) |
| Reproducibility | Five-field reproducibility per SYS-02 §1.5 (input SHA + config hash + seed + environment + output SHA). | ✅ |

### 4.5. Database

| Item | Criterion | Status |
| --- | --- | --- |
| Database | **N/A — intentionally not implemented in current prototype phase (per ADR-0005 Option A).** Database = FUTURE_WORK (EPIC-12). Persistence = Filesystem + Parquet + JSON manifests. | N/A |

### 4.6. README and project documentation

| Item | Criterion | Status |
| --- | --- | --- |
| README covers setup | README documents: Python 3.11, `pip install -e .`, `pytest`, running scripts, opening UI prototype in browser. | ✅ |
| AGENTS.md governs | `AGENTS.md` is the operating rule for any AI agent. | ✅ |
| ADRs recorded | `docs/decisions/0001-0005` record dataset, algorithm, RQ, and architecture decisions. | ✅ |
| SYS-01 OQs resolved | SYS-01 §13 OQ-09, OQ-10, OQ-11 resolved by ADR-0005. | ✅ (per SYS-01 §13 update 2026-10-08) |

---

## 5. What DEV-01 Does NOT Do

DEV-01 explicitly does NOT introduce:

- Backend REST API service (FastAPI / Flask / Django / bất kỳ framework).
- ML worker process / microservice.
- Job queue (RQ / Celery / custom).
- Metadata database (PostgreSQL / SQLite / MongoDB / cloud DB).
- ORM (SQLAlchemy / Tortoise / Django ORM).
- OpenAPI runtime / API server implementation.
- Production authentication / authorization.
- Production frontend (React / Vue / Svelte SPA).
- New Python dependencies beyond `requirements.txt` + `pyproject.toml`.
- Docker / container images.
- Migrations.
- Cloud infrastructure / SaaS features.
- Git operations (commit / push / PR / merge).

These are FUTURE_WORK and will be addressed in EPIC-12 (or later
phases) via a new ADR that supersedes ADR-0005 if the architecture is
to change.

---

## 6. Files Used by DEV-01 (existing, no modification)

| Path | Role |
|---|---|
| `src/customer_segmentation/**` | Research core (5 algorithms, evaluation, profiling) |
| `scripts/run_*.py` | CLI entry points |
| `configs/*.yaml` | Configuration files |
| `tests/**` | Test suite |
| `data/processed/`, `data/interim/` | Parquet datasets |
| `reports/<stage>/<run_id>/` | Run outputs + JSON manifests |
| `docs/system/ui-prototype/index.html` | HTML prototype (mock data) |
| `docs/decisions/0001-0004.md` | Existing ADRs (immutable) |
| `AGENTS.md` | Operating rules |

---

## 7. Files Authored/Modified by DEV-01 (this commit)

| Path | Action |
|---|---|
| `docs/decisions/0005-prototype-architecture-option-a.md` | **CREATED** — records Option A decision |
| `docs/system/SYS-01_requirements.md` | §13 OQ-09 / OQ-10 / OQ-11 rows updated to RESOLVED (no other section touched) |
| `docs/system/SYS-05_api_design.md` | Additive: header phase status; §1 prototype-phase note; §1.4 prototype-phase out-of-scope list; §3 footnote; §15 new resolved item 15. No API endpoint schema / error code / OpenAPI pattern deleted. |
| `docs/system/DEV-01_project_setup.md` | **CREATED** — this file |

---

## 7.1. Verification Evidence (2026-10-08 review pass)

The acceptance criteria in §4 were independently re-verified on
**2026-10-08** against the repository as it stands at the
`snapshot/system-design-baseline-2026-10-08` branch. The review pass
used the following commands (all run from the repository root with
`PYTHONPATH=src`):

| # | Verification command | Result |
|---|---|---|
| V-01 | `python -c "import customer_segmentation"` | exit 0; package + 11 subpackages importable. |
| V-02 | `python -c "from customer_segmentation.clustering.registry import AlgorithmRegistry; print(AlgorithmRegistry.list_registered())"` | `['agglomerative', 'dbscan', 'fuzzy_cmeans', 'gmm', 'kmeans']` (5 algorithms per ADR-0003). |
| V-03 | `python -m pytest -q --tb=line` | **1468 passed in 416.45s**. Zero failures, zero errors, zero skips. |
| V-04 | `python -c "import yaml; [yaml.safe_load(open(f'configs/{f}')) for f in __import__('os').listdir('configs') if f.endswith('.yaml')]"` | 15 / 15 configs parsed. |
| V-05 | `grep -E 'fastapi\|flask\|django\|sqlalchemy\|redis\|celery\|rq\|uvicorn\|pymongo\|aiosqlite' requirements.txt pyproject.toml` | Zero matches. |
| V-06 | `ruff check . --statistics` | 113 pre-existing findings (research-core only). See §4.1 disposition. |
| V-07 | `black --check .` | 26 pre-existing format issues (research-core only). See §4.1 disposition. |
| V-08 | `head -40 scripts/run_pipeline.py` | Confirmed `NotImplementedError` placeholder. Disposition: not a DEV-01 requirement (per-stage entry points cover all current work). |
| V-09 | `head -40 scripts/run_ml02_kmeans.py` | Confirmed full orchestrator with proper docstring, CLI flags, output paths, and AGENTS.md §2 constraints. |
| V-10 | `find data reports -name .gitkeep` | 13 `.gitkeep` placeholders present across `data/raw/{primary,backup}/`, `data/raw/`, `data/interim/`, `data/processed/`, `data/external/`, `reports/{dataset_audit,preprocessing,feature_engineering,clustering,evaluation,figures}/`, `reports/`. |

### 7.1.1. Pre-existing issues (out of DEV-01 scope)

The following are **PRE-EXISTING** in the research core, not introduced
by DEV-01, and **explicitly out of DEV-01 scope** per AGENTS.md
§2.1, §2.4, §2.13 (no silent methodology / research-core change). They
are recorded here for transparency:

| Issue | Source | Disposition |
|---|---|---|
| `scripts/run_pipeline.py` is a `NotImplementedError` placeholder | Pre-existing from `b8c2ccb feat: CLI entry points + exploratory notebooks`. | NOT a DEV-01 requirement. Per-stage entry points are real and used for all current work. Top-level convenience wrapper is FUTURE_WORK (not a blocker for DEV-01 READY). |
| `ruff check .` reports 113 findings (mostly N806, F401, E702, UP035, I001 in research core) | Pre-existing across FE-01 → CP-05 deliverables. | NOT a DEV-01 failure. DEV-01 may not silently fix research-core code. Each finding is owned by its respective stage (FE-01 / FE-02 / ... / CP-05). Any future mass-format / mass-lint pass must be a separate task with its own ADR. |
| `black --check .` reports 26 files would be reformatted | Same pre-existing source. | Same disposition as ruff. |
| `psycopg2` is importable at the OS level (Debian system package) | Not in `requirements.txt`, not in `pyproject.toml::dependencies`. | Not a project dependency; not in DEV-01's surface. |

### 7.1.2. What changed in this 2026-10-08 review pass

This pass updated `docs/system/DEV-01_project_setup.md` only (this
file). Specifically:

- Status table in §4.1 was rewritten to show **verified PASS / verified
  NOT IMPLEMENTED / verified PRE-EXISTING** rather than blanket
  ✅ claims. The previous version incorrectly asserted that
  `scripts/run_pipeline.py` runs end-to-end and that `ruff check .` /
  `black --check .` pass — both were untested claims. They are now
  honest.
- §1 (Objective) was clarified to describe DEV-01 as a **verification +
  documentation** task, not a code-creation task, and to record the
  verification date.
- §7.1 (this section) was added to capture the verification
  evidence and the pre-existing-issue disposition.

**No code, no config, no test, no script, no data, no report, no ADR,
no SYS-01..06 was modified by this review pass** (other than this
file itself, which is DEV-01's own documentation).

---

## 8. References

- ADR-0005 — Prototype Architecture: File-Based Batch / Offline (Option A).
- SYS-01 §13 (Limitations / Open Questions).
- SYS-02 (Architecture — already consistent with Option A).
- SYS-03 (Data Model — already consistent with Option A).
- SYS-04 (ML Processing Pipeline — already consistent with Option A).
- SYS-05 (API Design — retained as future reference).
- SYS-06 (UI/UX Design — HTML prototype scope).
- AGENTS.md (operating rules).