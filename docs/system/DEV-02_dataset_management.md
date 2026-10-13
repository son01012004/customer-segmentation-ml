# DEV-02 — Dataset Management (Prototype)

> **Mã task:** DEV-02
> **Tên:** Dataset Management (Import / List / Detail / Schema / Missing / Stats / Validation / Provenance)
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config, no ADR, no SYS edit, no Git op)
> **Ngày:** 2026-10-08
> **Phạm vi:** Add a **prototype-layer** capability to import, validate,
> and inspect one-off tabular datasets (CSV / Parquet) for use by the
> prototype UI and downstream DEV-03 → DEV-09. **Does NOT** modify the
> canonical FE-06 research dataset, the 185 experimental runs, or any
> research methodology.
> **Architecture:** Option A (ADR-0005) — offline, single-machine,
> file-based. No backend, no API, no database, no worker, no queue.

---

## 1. Objective

DEV-02 provides the **prototype dataset-management surface** that the
HTML prototype and downstream prototype-layer DEVs (DEV-03..09) need
to operate on a user-supplied dataset, while keeping the research
canonical artefacts (FE-06, raw/primary, raw/backup, reports/**)
strictly immutable.

Concretely, DEV-02 implements:

1. **Import / Upload** a CSV or Parquet file from disk.
2. **Dataset List** — enumerate imported datasets from the prototype
   storage root.
3. **Dataset Detail** — return manifest + schema + missing + stats for
   one dataset.
4. **Schema Detection** — conservative per-column type classification
   (numeric / string / boolean / datetime / mixed).
5. **Missing-Value Detection** — read-only count / rate, mirroring
   `audit.missing_profile` semantics.
6. **Basic Statistics** — numeric + categorical summary, mirroring
   `audit.numerical_profile` and `audit.categorical_profile`.
7. **Validation** — three independent categories
   (file-level / structural / data-quality), each producing a result of
   `PASS` / `WARNING` / `FAIL` and mapping to a lifecycle status
   `NOT_VALIDATED` / `VALIDATING` / `VALID` / `FAILED`.
8. **Dataset Provenance** — manifest with stable identity / provenance
   fields plus runtime metadata; portable source-path field
   (filename or relative path, never absolute).

All eight capabilities operate on a single, content-addressed dataset
identity `dataset_id = ds_<sha256-prefix-24>` so re-imports of the
same file content are **idempotent** (no duplicate artefacts).

---

## 2. Scope

### 2.1. In scope (DEV-02)

- New module package `src/customer_segmentation/dataset_management/`
  with public Python API.
- One new CLI entry point: `scripts/dev02_import_dataset.py`.
- One new YAML config: `configs/dev02_dataset_management.yaml`.
- One new test directory: `tests/test_dev02_*.py` (~50–70 tests).
- New on-disk storage sub-tree: `data/prototype/datasets/<dataset_id>/`.
- New documentation: `docs/system/DEV-02_dataset_management.md` (this file).
- Reuse of:
  - `customer_segmentation.data.audit` (`basic_overview`,
    `missing_profile`, `numerical_profile`, `categorical_profile`).
  - `customer_segmentation.data.validator.ValidationResult` (raw
    container; DEV-02 wraps its own typed result on top).
  - `customer_segmentation.transformation.versioning.compute_file_sha256`
    (reused for `dataset_id` derivation).
  - `customer_segmentation.config.loader` enum / frozenset convention
    (mirrored for `ValidationStatus` and `DatasetScope`).

### 2.2. Out of scope (DEV-02)

- ❌ Modifying `data/raw/primary/`, `data/raw/backup/`, `data/processed/`,
  or `reports/**` (read-only research artefacts; see §11).
- ❌ Modifying any of `src/customer_segmentation/data/audit.py`,
  `data/loader.py`, `data/validator.py`, or
  `transformation/versioning.py`. DEV-02 **imports** from them; it
  does **not** extend or rewrite them.
- ❌ Implementing DEV-03, DEV-04, DEV-05, DEV-06, DEV-07, DEV-08, DEV-09.
  DEV-02 only provides a stable contract
  (`dataset_id` + `sha256` + manifest path) that they will later
  consume.
- ❌ RFM-only materialisation. (Future research work, owned by
  `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.)
- ❌ Editing SYS-01..06, AGENTS.md, ADR-0001..0005.
- ❌ Adding new third-party dependencies (no `chardet`, no
  `python-magic`, no `fastavro`, no `orjson`, etc.). DEV-02 is built
  on the existing `pandas` + `pyarrow` + `PyYAML` surface only.
- ❌ CLI flag `--dest-root` or any user override of the storage root.
  The storage root is fixed in `configs/dev02_dataset_management.yaml`.
- ❌ CLI flag `--scope`. The `dataset_scope` is hard-coded to
  `IMPORTED_PROTOTYPE` (per ADR-0005 + §6.1 below).
- ❌ Bulk import, re-import with `--replace`, automatic re-validation
  of historical imports, or any side-effect against a non-imported
  dataset.
- ❌ HTML UI changes. The existing
  `docs/system/ui-prototype/index.html` continues to render mock data;
  the UI sync is a **separate, future UI iteration** (see §15).
- ❌ Git operations (commit / push / PR / merge / branch).

---

## 3. Architecture

### 3.1. Placement in the layered batch-pipeline (SYS-02 §2.1)

| Layer | DEV-02 placement | Existing example |
|---|---|---|
| Configuration | reads `configs/dev02_dataset_management.yaml` | `configs/preprocessing.yaml` |
| Driver / orchestration | new `scripts/dev02_import_dataset.py` | `scripts/run_fe01_audit.py` |
| Pipeline / module | new `src/customer_segmentation/dataset_management/` | `src/customer_segmentation/data/`, `transformation/`, etc. |
| Data / storage | new `data/prototype/datasets/<dataset_id>/` (additive sub-tree) | `data/processed/`, `data/interim/`, `reports/<stage>/<run_id>/` |

DEV-02 adds an **orthogonal** prototype-layer sub-tree. It does **not**
replace, override, or alias any existing layer.

### 3.2. Coupling rules (mirror of §11 of SYS-01..06 design)

`customer_segmentation.dataset_management` MAY import from:

- `customer_segmentation.data.audit` (read-only reuse).
- `customer_segmentation.data.validator` (read-only reuse of
  `ValidationResult` container).
- `customer_segmentation.transformation.versioning` (read-only reuse
  of `compute_file_sha256`).
- `customer_segmentation.config.loader` (**pattern reuse only** — DEV-02
  does not call any loader; it only mirrors the `frozenset`-based
  enum-convention pattern).
- stdlib + `pandas` + `pyarrow` + `PyYAML` (already in
  `pyproject.toml::dependencies`).

`customer_segmentation.dataset_management` MUST NOT import from:

- `customer_segmentation.preprocessing` (research-methodology surface;
  see AGENTS.md §3).
- `customer_segmentation.features`, `.clustering`, `.evaluation`,
  `.profiling`, `.aggregation`, `.outlier_analysis`.
- `customer_segmentation.transformation.*` **except**
  `transformation.versioning.compute_file_sha256` (documented reuse).
- `customer_segmentation.visualization` (DEV-02 has no plotting
  surface; if/when a plot is needed it is added in a downstream DEV).
- Any backend / API / database / queue library
  (`fastapi`, `flask`, `django`, `uvicorn`, `sqlalchemy`, `psycopg2`,
  `redis`, `celery`, `rq`, `pymongo`, `aiosqlite`).

`customer_segmentation.dataset_management` MUST NOT add any new
dependency to `pyproject.toml` or `requirements.txt`. The DEFENSIVE
check for forbidden imports lives in
`tests/test_dev02_import_blocklist.py`.

### 3.3. Module structure (7 files)

```
src/customer_segmentation/dataset_management/
    __init__.py          — public API exports (DatasetScope, ValidationStatus,
                            import_dataset, list_datasets, get_dataset, ...).
    scope.py             — DatasetScope enum, ValidationStatus enum,
                            ValidationResult enum, frozen sets
                            (mirrors config/loader convention).
    storage.py           — path resolution, container sanity, dataset_id
                            derivation (sha256 prefix), idempotency lookup.
    importer.py          — single-pipeline driver (file preflight → read →
                            inspect → validate → atomic write), schema
                            detection (conservative), missing + statistics
                            via audit.*, mixed-type detector.
    manifest.py          — Manifest dataclass, JSON read/write, stable-vs-
                            runtime field classification, idempotency
                            metadata refresh.
    validation.py        — file-level / structural / data-quality checks,
                            aggregate result, lifecycle status mapping
                            (Stage D only).
    list.py              — enumerate manifests from filesystem with
                            optional filter by scope / status / name.
```

| Module | Responsibility | Approx. lines |
|---|---|---|
| `scope.py` | Enums + classification helpers | < 80 |
| `storage.py` | Path resolution, `dataset_id` derivation, container sanity | < 140 |
| `importer.py` | Single-pipeline driver, schema detection, mixed detector | < 350 |
| `manifest.py` | Manifest dataclass + JSON I/O + stable/runtime classification | < 230 |
| `validation.py` | file / structural / data-quality checks + result → status map | < 300 |
| `list.py` | Enumerate from filesystem with filter | < 120 |
| `__init__.py` | Public API surface + import-blocklist defence | < 100 |
| **Total** |  | **~1320** |

### 3.4. What got merged and why

- `schema_detect.py` → folded into `importer.py` (single-purpose, used
  only inside the import flow).
- `missing.py` → folded into `importer.py` (thin wrapper over
  `audit.missing_profile`; not warranting a file).
- `statistics.py` → folded into `importer.py` (thin wrapper over
  `audit.numerical_profile` / `audit.categorical_profile`).

What is **kept** as a separate module and why:

- `validation.py` — the three-category validation + lifecycle mapping
  has its own cohesion and is the most error-prone stage; a dedicated
  module makes the rules easy to read and test in isolation.
- `manifest.py` — Manifest schema, JSON I/O, and stable-vs-runtime
  field classification are non-trivial and have their own concerns
  (provenance, idempotency, portability); keeping it separate avoids
  `importer.py` ballooning past the line target.
- `scope.py` — Enums live in their own file (matching the
  `config/loader.py` convention); this keeps the dataset-management
  types easy to discover and stable.

### 3.5. No new module is created without a reason

- ❌ No `errors.py` — typed exceptions are colocated with the module
  that raises them (e.g. `ManifestError` in `manifest.py`,
  `StoragePathError` in `storage.py`).
- ❌ No `cli.py` — the CLI is a single thin script that delegates to
  `importer.import_dataset()`.
- ❌ No `__main__.py` — DEV-02 has no `python -m` surface; the CLI is
  a script.

---

## 4. Reuse

This section is the **single source of truth** for what DEV-02
imports, what it does NOT re-implement, and what new code it adds
that is genuinely new (not duplication of an existing helper).

| Reused symbol | From | Used by DEV-02 for | Why reuse, not re-implement |
|---|---|---|---|
| `basic_overview(df)` | `data.audit` | row/column counts, dtype strings, memory bytes | Already produces a deterministic `AuditSummary`; no methodology change. |
| `missing_profile(df)` | `data.audit` | per-column missing count + rate | Same semantics as FE-01; keeps `data/prototype/**` consistent with `reports/fe01/**`. |
| `numerical_profile(df)` | `data.audit` | per-numeric-column mean / std / min / max / quantiles | Same as above. |
| `categorical_profile(df)` | `data.audit` | per-categorical-column count / unique / top values | Same as above. |
| `ValidationResult` | `data.validator` | raw container for one check's outcome | Same container used across the research core; one less type to learn. |
| `compute_file_sha256(path)` | `transformation.versioning` | file integrity, `dataset_id` derivation | Already used by FE-06, EXP-01..05. |
| `frozenset`-based enum convention | `config.loader` | `DatasetScope`, `ValidationStatus`, `ValidationResult` enums | Mirrors the existing convention so reviewers don't see a new pattern. |

What DEV-02 does **NOT** reuse and must add new (because nothing in
the research core covers it):

- `dataset_id` derivation → `storage.py::derive_dataset_id(sha256)`.
- Content-addressed storage layout → `storage.py::dataset_dir(...)`.
- Per-import idempotency lookup → `storage.py::find_existing_dataset(sha256)`.
- Schema detector (conservative) → `importer.py::detect_schema(df)`.
- Mixed-type detector (deterministic) → `importer.py::detect_mixed(series)`.
- Single validation pipeline → `importer.py::run_import_pipeline(...)`.
- Manifest schema + JSON I/O + stable/runtime classification →
  `manifest.py`.
- Lifecycle status → `ValidationStatus` enum + mapping table
  (per §9 of this plan).
- Storage-root config loader → a small helper inside
  `dataset_management.__init__` that mirrors the
  `config.loader._read_yaml` pattern but for the new
  `dev02_dataset_management.yaml`.

---

## 5. Data flow

### 5.1. Single linear pipeline (A → B → C → D → E)

```
   ┌─ Stage A: file_preflight (validation.file_level) ─────┐
   │  - exists? readable? supported extension?              │
   │  - size <= max_file_size_mb?                           │
   │  - sha256 computable?                                  │
   │  - source-path policy (allow_external_source)?         │
   │  - destination-container sanity (always under          │
   │    storage_root, computed once from config)            │
   │  → on FAIL: abort; no reads; CLI exit 3                │
   └────────────────────────────────────────────────────────┘
                              ↓ (only on PASS)
   ┌─ Stage B: read_dataframe ──────────────────────────────┐
   │  - pandas.read_csv / read_parquet                      │
   │  - returns in-memory DataFrame (NEVER mutates source)  │
   │  → on FAIL: abort; no artefact; CLI exit 2             │
   └────────────────────────────────────────────────────────┘
                              ↓ (only on read success)
   ┌─ Stage C: inspect (no side-effects) ───────────────────┐
   │  - C1: detect schema per column (conservative, §8)     │
   │  - C2: count missing (audit.missing_profile)           │
   │  - C3: compute statistics                              │
   │         (audit.numerical_profile,                      │
   │          audit.categorical_profile)                    │
   │  - C4: detect mixed-type (deterministic, head sample)  │
   │  → inspect only; never write a partial artefact        │
   └────────────────────────────────────────────────────────┘
                              ↓ (always, even if stats fail)
   ┌─ Stage D: validation (3 categories) ───────────────────┐
   │  - file_level (already passed in Stage A; recorded     │
   │    as PASS in the manifest for idempotent outputs)     │
   │  - structural: row_count>0, col_count>0, no dup cols,  │
   │    valid column names, no all-NULL column              │
   │  - data_quality: NaN, Inf, constant column,            │
   │    duplicate rows, mixed-type column                   │
   │  - aggregate result ∈ {PASS, WARNING, FAIL}            │
   │  - map result → validation_status per §9.3             │
   └────────────────────────────────────────────────────────┘
                              ↓
   ┌─ Stage E: artefact write (single decision point) ──────┐
   │  - if validation_status ∈ {VALID, NOT_VALIDATED}:      │
   │       atomic write data + atomic write manifest        │
   │       write to <storage_root>/<dataset_id>/             │
   │       update last_seen_utc if manifest exists          │
   │  - if validation_status == FAILED:                     │
   │       DO NOT write data file                           │
   │       DO NOT write manifest.json                        │
   │       report failure; CLI exit 2                       │
   └────────────────────────────────────────────────────────┘
```

**Hard rules enforced by the pipeline:**

1. **No partial artefact.** If validation fails, the dataset is **not**
   retained on disk under `data/prototype/datasets/`.
2. **Atomic write.** Each artefact is written to a temp path inside the
   target directory, then renamed. An exception before rename
   guarantees an unlinked temp.
3. **Single decision point.** The validation aggregate result is the
   **only** switch that gates Stage E.
4. **Inspect is read-only.** Stage C has no filesystem side-effects.
5. **CLI exit codes carry the pipeline stage to the operator:**
   - `0` — success (new dataset written) or `REUSED_EXISTING_DATASET`
     (idempotent re-import).
   - `2` — validation FAIL (Stage D or upstream). No artefact written.
   - `3` — file preflight FAIL (Stage A). No reads.
   - `1` — unexpected error.

### 5.2. Re-import (idempotency) flow

```
import --file foo.csv
    → Stage A computes sha256
    → storage.find_existing_dataset(sha256) scans
      data/prototype/datasets/*/manifest.json
    → if found:
          if same content (sha256 equal):
              print REUSED_EXISTING_DATASET,
              update last_seen_utc on the existing manifest,
              exit 0 (no new artefact created)
          else:
              continue to Stage B (new dataset)
    → if not found:
          continue to Stage B
```

Idempotency is **content-keyed**, not name-keyed. Two CSV files with
identical bytes get the same `dataset_id`; renaming the file does not
create a new dataset.

### 5.3. List / Detail flow

`list_datasets()`:

1. Scan `data/prototype/datasets/*/manifest.json`.
2. For each, parse the manifest.
3. Apply optional filter (scope, status, name substring).
4. Return a list of `DatasetSummary` (id, name, scope, status, sha256,
   created_utc, row_count).

`get_dataset(dataset_id)`:

1. Locate `<storage_root>/<dataset_id>/manifest.json`.
2. Read it; raise `DatasetNotFound` if absent.
3. Return a `DatasetDetail` containing the manifest, the artefact
   path, the storage directory, and a typed `ValidationStatus`.

---

## 6. Module Design — Public Interfaces

### 6.1. `scope.py`

```python
from enum import Enum
from typing import Final

class DatasetScope(str, Enum):
    """Scope of a dataset in the prototype storage layer.

    Currently only one value is used; the enum is defined to keep
    room for future in-house research datasets without changing the
    manifest schema.
    """
    IMPORTED_PROTOTYPE = "IMPORTED_PROTOTYPE"

DATASET_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in DatasetScope)


class ValidationStatus(str, Enum):
    """Lifecycle status of a single dataset over time."""
    NOT_VALIDATED = "NOT_VALIDATED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    FAILED = "FAILED"

VALIDATION_STATUSES: Final[frozenset[str]] = frozenset(s.value for s in ValidationStatus)


class ValidationResult(str, Enum):
    """Per-pass outcome of a validation run."""
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"

VALIDATION_RESULTS: Final[frozenset[str]] = frozenset(s.value for s in ValidationResult)
```

### 6.2. `storage.py`

```python
def derive_dataset_id(sha256_hex: str) -> str:
    """Return 'ds_' + first 24 hex chars of the SHA-256."""

def dataset_dir(storage_root: Path, dataset_id: str) -> Path:
    """Return <storage_root>/<dataset_id>. Asserts it's inside storage_root."""

def find_existing_dataset(storage_root: Path, sha256_hex: str) -> Path | None:
    """Return the existing manifest path if one with this sha256 exists, else None."""

def resolve_storage_root(config: Mapping[str, Any]) -> Path:
    """Return the storage root as an absolute path (resolved against CWD)."""

class StoragePathError(ValueError): ...
```

### 6.3. `importer.py`

```python
@dataclass(frozen=True)
class ImportRequest:
    source_path: Path
    name: str | None
    config_path: Path
    allow_external_source: bool

@dataclass(frozen=True)
class ImportResult:
    dataset_id: str
    storage_dir: Path
    artefact_path: Path
    manifest_path: Path
    validation_status: ValidationStatus
    validation_summary: dict[str, Any]
    reused: bool        # True if REUSED_EXISTING_DATASET

def import_dataset(req: ImportRequest) -> ImportResult: ...

def detect_schema(df: pd.DataFrame) -> list[ColumnSchema]: ...
def detect_mixed(series: pd.Series, sample_size: int = 1000) -> bool: ...
```

### 6.4. `manifest.py`

```python
@dataclass(frozen=True)
class Manifest:
    schema_version: str
    dataset_id: str
    dataset_scope: str
    name: str
    original_filename: str
    format: str
    storage: StorageInfo
    sha256: str
    row_count: int
    column_count: int
    columns: list[ColumnInfo]
    missing_summary: dict[str, float]
    statistics_summary: StatisticsSummary
    validation: ValidationBlock
    validation_status: str
    created_utc: str
    last_seen_utc: str
    provenance: Provenance
    research_safety: ResearchSafety

def write_manifest(manifest: Manifest, path: Path) -> None: ...
def read_manifest(path: Path) -> Manifest: ...
def update_last_seen(manifest: Manifest) -> Manifest: ...
def stable_field_names() -> frozenset[str]: ...
def runtime_field_names() -> frozenset[str]: ...
```

### 6.5. `validation.py`

```python
@dataclass(frozen=True)
class CategoryResult:
    result: str            # PASS / WARNING / FAIL
    errors: list[str]
    warnings: list[str]
    stats: dict[str, Any]

@dataclass(frozen=True)
class ValidationBlock:
    file_level: CategoryResult
    structural: CategoryResult
    data_quality: CategoryResult

def aggregate(block: ValidationBlock) -> str: ...    # PASS / WARNING / FAIL
def map_to_lifecycle(aggregate: str) -> str: ...    # NOT_VALIDATED / VALID / FAILED

def run_validation(
    df: pd.DataFrame,
    file_level_result: CategoryResult,
) -> ValidationBlock: ...
```

### 6.6. `list.py`

```python
@dataclass(frozen=True)
class DatasetSummary:
    dataset_id: str
    name: str
    scope: str
    validation_status: str
    sha256: str
    created_utc: str
    last_seen_utc: str
    row_count: int
    column_count: int
    artefact_path: Path

def list_datasets(
    storage_root: Path,
    *,
    scope: str | None = None,
    status: str | None = None,
    name_substring: str | None = None,
) -> list[DatasetSummary]: ...

def get_dataset(storage_root: Path, dataset_id: str) -> Manifest: ...
```

### 6.7. `__init__.py` — public API

```python
from customer_segmentation.dataset_management.scope import (
    DatasetScope, ValidationStatus, ValidationResult,
    DATASET_SCOPES, VALIDATION_STATUSES, VALIDATION_RESULTS,
)
from customer_segmentation.dataset_management.storage import (
    derive_dataset_id, dataset_dir, find_existing_dataset,
    resolve_storage_root, StoragePathError,
)
from customer_segmentation.dataset_management.importer import (
    ImportRequest, ImportResult, import_dataset, detect_schema,
    detect_mixed,
)
from customer_segmentation.dataset_management.manifest import (
    Manifest, write_manifest, read_manifest, update_last_seen,
    stable_field_names, runtime_field_names,
)
from customer_segmentation.dataset_management.validation import (
    CategoryResult, ValidationBlock, run_validation,
    aggregate, map_to_lifecycle,
)
from customer_segmentation.dataset_management.list import (
    DatasetSummary, list_datasets, get_dataset,
)
```

No `from __future__` import inside `__init__.py` is required; the
package exposes only names that are themselves import-safe.

---

## 7. Storage

### 7.1. Layout

```
data/
├── raw/{primary,backup}/        # READ-ONLY research artefacts
├── interim/                     # research stage outputs
├── processed/                   # research stage outputs (FE-06 lives here)
├── external/                    # external reference data
└── prototype/                   # NEW (DEV-02) — additive sub-tree
    └── datasets/
        └── <dataset_id>/
            ├── <original_filename>     e.g. foo.csv
            └── manifest.json
```

`data/prototype/datasets/` is the **only** new sub-tree created by
DEV-02. It is git-ignored because `data/**` is already in
`.gitignore` (verified by `git check-ignore` in Phase 2 — see §12.1).

### 7.2. Container sanity

The storage root is resolved from `configs/dev02_dataset_management.yaml`
and validated at runtime:

- `storage_root` is resolved against the CWD (the repository root when
  invoked from `scripts/dev02_import_dataset.py`).
- `dataset_dir = storage_root / dataset_id` is **always** under
  `storage_root` after `Path.resolve()`. There is no CLI flag that lets
  the user redirect the destination — the storage root is fixed at
  config load time.
- Symlink traversal: if `storage_root` is a symlink, the resolved
  real path must still be inside the repository's `data/` directory
  (a future enhancement; not blocking DEV-02 — see §12.1).

### 7.3. `.gitignore` rule for `data/prototype/`

`data/prototype/datasets/` is a new sub-tree introduced by DEV-02 and
must not be tracked by Git (per AGENTS.md §2.12 "không commit
generated reports / figures dưới `reports/**`" spirit, and to keep
the prototype layer fully isolated from the research evidence).

After the final smoke verification on 2026-10-08, the original
"no `.gitignore` edit needed" claim in this section was found to
be incorrect: the existing `.gitignore` only listed
`/data/raw/**`, `/data/interim/**`, `/data/processed/**`, and
`/data/external/**` — there was no rule covering `data/prototype/`.
A targeted rule has now been added (single line, no other change):

```gitignore
# data/prototype (DEV-02 — prototype dataset storage, scope=IMPORTED_PROTOTYPE)
/data/prototype/**
```

Verification (2026-10-08):

```text
$ git check-ignore -v data/prototype/datasets/
.gitignore:114:/data/prototype/**   data/prototype/datasets/
(exit code 0)
```

- `data/prototype/datasets/`, `data/prototype/datasets/<dataset_id>/`,
  and every file under them now resolve to the new rule (line 114).
- `git status` no longer reports `data/prototype/` as an untracked
  candidate; the only DEV-02-related entries under `git status` are
  the source/tests/config/plan files (which are expected to be
  reviewed and committed by the human researcher).
- No `.gitkeep` is created under `data/prototype/`. The subtree is
  intended to be 100% derived from imports and must remain
  self-cleaning; tracking a placeholder would conflict with the
  "no empty placeholder for derived data" rule used for
  `data/processed/`, `data/interim/`, and `data/external/`.

The `.gitignore` edit is the **only** change required to keep the
DEV-02 storage layer out of the research evidence. No code, no
config, no ADR, and no SYS-01..06 doc was modified for this fix.

> **Historical note (pre-2026-10-08).** Earlier revisions of this
> section claimed "`data/**` is already in `.gitignore`". That claim
> was a plan-side error — the actual file listed the four research
> sub-trees explicitly, not a `data/**` blanket. The plan was
> amended in place; no separate ADR was opened because the fix is a
> one-line gitignore addition that does not change DEV-02
> methodology, storage layout, schema, or semantics.

### 7.4. Storage-root config

```yaml
# configs/dev02_dataset_management.yaml
dataset_management:
  storage_root: "data/prototype/datasets"
  max_file_size_mb: 256
  supported_import_formats: ["csv", "parquet"]
  default_csv_encoding: "utf-8"
  source_path_policy:
    allow_external_source: false   # default; CLI --allow-external-source overrides for one invocation
  readonly_research_paths:
    - "data/raw/primary"
    - "data/raw/backup"
    - "data/processed"
    - "reports"
```

The CLI does **not** expose `--dest-root` or any other storage-root
override. The only CLI flags are:

```
--file <path>                       # required
[--name <display-name>]             # optional
[--allow-external-source]           # default: off
[--max-file-size-mb 256]            # default: 256
[--config configs/dev02_dataset_management.yaml]
```

---

## 8. Manifest schema (exact minimal field set)

```json
{
  "schema_version": "1.0.0",
  "dataset_id": "ds_abc123def4567890...",
  "dataset_scope": "IMPORTED_PROTOTYPE",
  "name": "<user-supplied or filename-derived>",
  "original_filename": "<original file name>",
  "format": "csv | parquet",

  "storage": {
    "directory": "data/prototype/datasets/<dataset_id>",
    "artifact_path": "<dataset_id>/<original_filename>",
    "file_size_bytes": 12345
  },

  "sha256": "<64 hex>",
  "row_count": 0,
  "column_count": 0,

  "columns": [
    {
      "name": "...",
      "inferred_type": "numeric | string | boolean | datetime | mixed",
      "nullable": true,
      "missing_count": 0
    }
  ],

  "missing_summary": { "<column_name>": <missing_pct>, ... },
  "statistics_summary": {
    "numeric": { "<col>": {"count": 0, "mean": 0.0, "std": 0.0, "min": 0, "median": 0, "max": 0}, ... },
    "categorical": { "<col>": {"count": 0, "unique_count": 0}, ... }
  },

  "validation": {
    "file_level":    { "result": "PASS|FAIL", "errors": [], "warnings": [] },
    "structural":    { "result": "PASS|WARNING|FAIL", "errors": [], "warnings": [], "stats": {} },
    "data_quality":  { "result": "PASS|WARNING|FAIL", "errors": [], "warnings": [], "stats": {} }
  },
  "validation_status": "NOT_VALIDATED | VALIDATING | VALID | FAILED",

  "created_utc": "ISO-8601 timestamp",
  "last_seen_utc": "ISO-8601 timestamp",

  "provenance": {
    "import_method": "cli",
    "source_filename": "<portable filename>",
    "source_relative_path": "<relative path or null>",
    "license": null,
    "notes": "Imported for prototype validation. NOT research evidence."
  },

  "research_safety": {
    "automatically_promoted_to_research": false,
    "scope": "IMPORTED_PROTOTYPE",
    "appeared_in_research_evidence": false,
    "read_only_paths_unmodified": [
      "data/raw/primary",
      "data/raw/backup",
      "data/processed",
      "reports"
    ]
  }
}
```

**Required fields (no optional, no nullable):** `schema_version,
dataset_id, dataset_scope, name, original_filename, format, storage,
sha256, row_count, column_count, columns, missing_summary,
statistics_summary, validation, validation_status, created_utc,
provenance, research_safety`.

`provenance.source_filename` is the **portable** source identifier
(filename only). `provenance.source_relative_path` is the path
relative to the directory the CLI was invoked from, **or null** if
the file was outside the repository and `--allow-external-source` was
not set. The manifest **never** stores an absolute source path.

### 8.1. Stable vs runtime fields (revised per Rev 05 of the prior plan)

| Stable (equal across re-import of the same content) | Runtime (may differ across imports) |
|---|---|
| `schema_version` | `created_utc` (may update to "last_seen_utc") |
| `dataset_id` | `last_seen_utc` (may update) |
| `dataset_scope` | `provenance.import_method` (stable in practice) |
| `name` (if user-supplied) | `provenance.source_relative_path` (may differ if CWD differs) |
| `original_filename` | `environment.python` |
| `format` | `environment.platform` |
| `storage.directory` | `environment.key_libraries` |
| `storage.artifact_path` | `config_hash` (may differ if config file changed) |
| `storage.file_size_bytes` | |
| `sha256` | |
| `row_count` | |
| `column_count` | |
| `columns` | |
| `missing_summary` | |
| `statistics_summary` | |
| `validation` (content) | |
| `validation_status` (unchanged unless a fresh validation pass runs) | |
| `provenance.license` | |
| `provenance.notes` | |
| `research_safety.*` | |

Tests assert stable-field equality across two imports of the same
file content. They **do not** assert byte-for-byte JSON equality.

### 8.2. CLI scope parameter (no scope flag)

The CLI exposes **no** `--scope` flag. `dataset_scope` is hard-coded
to `IMPORTED_PROTOTYPE`. Rationale: a user must not be able to elevate
a one-off imported CSV to canonical-research status via the CLI. Any
future elevation pathway requires a separate code path with proper
gates — explicitly **NOT** exposed by DEV-02.

---

## 9. Validation

DEV-02 uses a **two-layer model**: dataset lifecycle status and
per-pass validation result. They are not the same thing and must not
be conflated.

### 9.1. Dataset lifecycle status

```
NOT_VALIDATED  →  VALIDATING  →  VALID
                       │
                       └────────────→  FAILED
```

State transitions:

- **NOT_VALIDATED** — manifest written; no validation run has occurred.
- **VALIDATING** — a validation run is in progress (set in memory at
  the start of `run_validation(...)` and cleared to `VALID` or `FAILED`
  on completion).
- **VALID** — at least one validation pass ran; the latest result is
  `PASS` or `WARNING` (WARNING ⇒ VALID with `validation.warnings[]`
  populated).
- **FAILED** — the latest validation pass returned `FAIL` (errors ≥ 1,
  with optional warnings).

`IMPORTED` is **not** a lifecycle status. `INVALID` is **not** a
lifecycle status. `IMPORTED_PROTOTYPE` is the `dataset_scope` value
of any imported dataset — a separate concern.

### 9.2. Per-pass validation result

Each category is independent:

```
file_level    ∈ {PASS, FAIL}
structural    ∈ {PASS, WARNING, FAIL}
data_quality  ∈ {PASS, WARNING, FAIL}
```

Aggregate result codes:

- **PASS** — all three categories PASS.
- **WARNING** — at least one category WARNING, none FAIL.
- **FAIL** — at least one category FAIL.

### 9.3. Mapping (lifecycle ⇄ result)

| Validation result | → Dataset lifecycle status |
|---|---|
| (no validation yet) | `NOT_VALIDATED` |
| Validation in flight | `VALIDATING` |
| `PASS` | `VALID` |
| `WARNING` | `VALID` (with `validation.warnings[]` populated) |
| `FAIL` | `FAILED` (with `validation.errors[]` populated) |

### 9.4. Rules per category

#### 9.4.1. file_level

| Check | PASS | FAIL |
|---|---|---|
| File exists | continue | raise |
| Read permission | continue | raise |
| Format is supported (`csv`, `parquet`) | continue | raise |
| SHA-256 computable | continue | raise |
| File size ≤ `max_file_size_mb` | continue | raise |
| Source path inside repository, OR `--allow-external-source` | continue | raise |

#### 9.4.2. structural

| Check | PASS | WARNING | FAIL |
|---|---|---|---|
| `row_count > 0` | yes | — | no (empty file) |
| `column_count > 0` | yes | — | no |
| All column names non-empty strings | yes | — | no |
| No duplicate column names | yes | — | no |
| Column names contain only `[A-Za-z0-9_.-]` | yes | — | if contains shell-unsafe chars |
| No all-NULL column | yes | yes | — |

#### 9.4.3. data_quality

| Check | PASS | WARNING | FAIL |
|---|---|---|---|
| NaN present | no | yes | — |
| Inf / -Inf present | no | yes | — |
| Constant column | no | yes | — |
| Duplicate rows (full-row) | no | yes | — |
| Mixed-type column | no | yes | — |

### 9.5. Destination safety

- `storage_root` is loaded from `configs/dev02_dataset_management.yaml`
  (the CLI has no override).
- `Path.resolve()` is applied to `storage_root`; the resulting path
  must remain **inside** the repository's `data/` directory.
- Because the CLI does not accept `--dest`, the user cannot redirect
  the destination to a sensitive path.
- Source files may be anywhere (e.g. `/tmp/mydata.csv`); the
  destination is **always** under `data/prototype/datasets/`.

---

## 10. Schema Detection (conservative)

### 10.1. Per-column rules

| Pandas dtype | `inferred_type` | Notes |
|---|---|---|
| `int*`, `float*`, `complex*` (incl. nullable Int / Float) | `numeric` | |
| `bool`, boolean (with NaN) | `boolean` | only when dtype itself is boolean |
| `datetime64[ns/...]`, `DatetimeTZDtype` | `datetime` | actual datetime dtype |
| `object` (with exactly one runtime type after null-drop + head sample) | `string` (if that type is `str`) | see §10.3 |
| `object` (with ≥2 runtime types after null-drop + head sample) | `mixed` | see §10.3 |
| `string` (pandas StringDtype) | `string` | |
| Categorical | `string` | categories treated as strings |

### 10.2. Explicitly NOT applied (conservative)

- ❌ `0/1` → `boolean` (0/1 may be numeric counts or codes).
- ❌ Unix-integer in tens of digits → `datetime` (e.g. `1700000000`
  is treated as `numeric`).
- ❌ ISO-8601 string → `datetime` (string column stays `string` until
  a parser is invoked — DEV-02 does NOT parse).
- ❌ String patterns (e.g. `"true"`, `"false"`) → `boolean` (stays
  `string`).

### 10.3. Mixed-type detector (deterministic)

A column is reported as `mixed` **if and only if** the column is an
`object` dtype AND, after excluding `None` / `NaN` / `pd.NaT`, the
non-null values contain at least **two distinct Python runtime types**
from a fixed set, drawn from the **first 1000 non-null values** in
row order (no shuffling, no `random.sample`).

Frozen type-rank set (in this exact order, module-level constant):

```
MIXED_TYPE_RANKS = frozenset({
    "bool", "int", "float", "complex", "str", "bytes",
    "datetime", "date", "decimal", "list", "tuple", "dict",
})
```

Deterministic algorithm:

```python
def detect_mixed(series: pd.Series, sample_size: int = 1000) -> bool:
    if series.dtype != "object":
        return False
    non_null = series.dropna()
    if non_null.empty:
        return False
    sample = non_null.head(sample_size)
    types = {type(v).__name__ for v in sample}
    return len(types & MIXED_TYPE_RANKS) >= 2
```

**Strict no-cast / no-parse / no-transform rules:**

- The mixed detector does NOT coerce booleans to ints.
- The mixed detector does NOT parse ISO strings to datetimes.
- The mixed detector does NOT parse `"true" / "false"` strings to
  booleans.
- The mixed detector does NOT invoke any `pd.to_*` parser.
- The mixed detector does NOT mutate the source DataFrame.

The mixed detector ONLY inspects `type(v).__name__` per value (mapped
through the fixed set above) and returns a deterministic result.

### 10.4. What schema detection MUST NOT do

- ❌ rename columns,
- ❌ drop / keep rows,
- ❌ coerce types,
- ❌ impute missing,
- ❌ encode categorical,
- ❌ parse or transform anything,
- ❌ cast source data.

Schema detection is **inspect-only, report-only, no-side-effect**.

---

## 11. Security / Research Safety

### 11.1. Hard rule — never write to research artefacts

DEV-02 **must not** write, mutate, delete, or rename anything under
the following paths:

- `data/raw/primary/**` (UCI Online Retail raw primary)
- `data/raw/backup/**` (UCI Online Retail II raw backup)
- `data/processed/**` (FE-06 canonical; the
  `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
  artefact lives here)
- `reports/**` (FE-01..06, EXP-01..05, EVA-01..03, CP-01..05 evidence)

These four paths are listed in the manifest's
`research_safety.read_only_paths_unmodified` field as documentation.
The **enforcement** is the import-blocklist + the storage-root
constraint: the storage root is always `data/prototype/datasets/`, so
the only path the import pipeline can ever write to is one inside that
sub-tree. Research paths are physically unreachable from the import
pipeline.

### 11.2. Read-side access policy

DEV-02 does **not** restrict which file the user passes as `--file`.
A user who has read access to `data/raw/primary/Online Retail.xlsx`
may pass it as `--file`; the pipeline will read it. The pipeline will
**not** write to `data/raw/primary/` because the destination is fixed
under `data/prototype/datasets/`. We do not invent a read-side
restriction (which would be inconsistent with the repository's
existing read-isolation model and would make the CLI harder to use
for legitimate prototype work).

### 11.3. Source-path portability

`provenance.source_relative_path` records the path **relative to the
CWD** (typically the repository root) when the file is inside the
repository, or `null` if it is outside and `--allow-external-source`
was passed. The manifest never stores the **absolute** source path.

`provenance.source_filename` always stores the file's basename.

### 11.4. Symlink / unsafe source policy

Default = strict. `--allow-external-source` is the only escape hatch.

- A `--file` whose resolved real path is **outside** the repository
  is **rejected** with exit code 3, unless `--allow-external-source`
  is passed.
- A `--file` that is a symlink to inside the repository is accepted
  (the resolved real path is inside the repository).
- A `--file` that is a symlink to outside the repository is rejected
  by default; accepted with `--allow-external-source`.

The destination (storage root) is never a symlink target — it is
always the literal path resolved from the config.

### 11.5. Path-traversal / absolute-path safety

Because the CLI does **not** accept `--dest` or `--dest-root`, there
is no user-controlled path that lands at the destination. The
`storage_root` is fixed in config; the dataset id is content-derived;
the artefact filename is the user-supplied `--file`'s basename. No
`..` segment in the filename is allowed (it is rejected in Stage A).

### 11.6. CSV encoding policy

- Default encoding: UTF-8.
- Non-UTF-8 CSV is **rejected with a clear error message** at Stage B.
  DEV-02 does **not** add a `chardet` dependency. A future extension
  point is documented in the manifest's
  `provenance.notes` field but not implemented in DEV-02.

### 11.7. Import-blocklist (defence-in-depth)

`tests/test_dev02_import_blocklist.py` asserts that the
`customer_segmentation.dataset_management` package's `__init__` module
does **not** expose any of the following names at import time:

```
fastapi, flask, django, uvicorn, sqlalchemy, psycopg2, redis, celery,
rq, pymongo, aiosqlite, jinja2, jinja2_async, gunicorn, starlette,
boto3, requests_async, httpx
```

(Not all of these are equal threats; the list is a **belt-and-braces**
defence against accidental dependency on a forbidden surface.)

The same test asserts that `__init__.py` does **not** import from
`customer_segmentation.preprocessing`,
`.features`, `.clustering`, `.evaluation`, `.profiling`,
`.aggregation`, `.outlier_analysis`, or `.visualization`.

---

## 12. Test Plan

### 12.1. Test files (~50–70 tests, all behavioural)

```
tests/
    test_dev02_scope.py            — enum values, classification (3–5 tests)
    test_dev02_storage.py          — path resolution, container sanity,
                                     dataset_id derivation (8–10 tests)
    test_dev02_importer_csv.py     — CSV import happy + edge cases
                                     (10–12 tests)
    test_dev02_importer_parquet.py — Parquet import happy + edge cases
                                     (8–10 tests)
    test_dev02_manifest.py         — manifest schema, stable vs runtime
                                     fields, idempotency (8–10 tests)
    test_dev02_validation.py       — file / structural / data-quality
                                     categories, status mapping (8–10 tests)
    test_dev02_list.py             — list / filter / detail (5–7 tests)
    test_dev02_research_safety.py  — research artefacts not mutated
                                     (5–6 tests)
    test_dev02_mixed_detector.py   — deterministic mixed-type detector
                                     (10–12 tests)
    test_dev02_import_blocklist.py — forbidden import / surface names
                                     absent (3–5 tests)
    test_dev02_runtime_dependencies.py — no forbidden libs in process
                                         (3–5 tests)
```

### 12.2. Edge cases (per Rev 10 of the prior plan)

```
[Importer]
  - CSV happy path
  - Parquet happy path
  - nonexistent file
  - unsupported extension (.xlsx in DEV-02; old FE-01 .xlsx loader is
    not reused by DEV-02)
  - malformed CSV (truncated, mismatched quote)
  - malformed Parquet (corrupted file)
  - invalid encoding (latin-1 fixture masquerading as utf-8)
  - empty dataset (0 rows but header present)
  - empty columns list (header only, no data rows)
  - duplicate column names
  - mixed types in one column
  - constant column (single unique value)
  - duplicate rows
  - very large file (parameterised; just over the limit)
  - symlink source path with --allow-external-source off → reject
  - source file outside repository (with --allow-external-source) → ok
  - source file outside repository (without --allow-external-source) →
    reject

[Schema detect]
  - all numeric → inferred_type numeric
  - all string → inferred_type string
  - actual boolean dtype → inferred_type boolean
  - actual datetime dtype → inferred_type datetime
  - integer 0/1 column → inferred_type numeric (NOT boolean)
  - integer unix-timestamp column → inferred_type numeric (NOT datetime)
  - ISO-8601 string column → inferred_type string (NOT datetime)
  - mixed (numbers + strings) → inferred_type mixed
  - mixed (numbers + datetimes) → inferred_type mixed
  - empty (all-NULL) column → not crash; reported as nullable
  - sample-size determinism: same head sample for 1000+ rows
  - sample-size determinism: fewer than sample_size non-null values

[Missing]
  - All NaN → missing_count = row_count
  - No missing → 0
  - Mirrors audit.missing_profile existing behaviour; no new policy

[Statistics]
  - Numeric: count, mean, std, min, median, max against pandas direct
    computation
  - Categorical: count, unique_count against pandas
  - Empty column handling
  - Constant column handling (mean == constant value, std == 0)

[Validation]
  - Valid dataset → file=PASS, structural=PASS, data_quality=PASS,
    validation_status=VALID
  - Empty dataset → file=PASS, structural=FAIL, validation_status=FAILED
  - Duplicate columns → structural=FAIL
  - Constant columns → data_quality=WARNING, validation_status=VALID
  - NaN present → data_quality=WARNING, validation_status=VALID
  - Inf present → data_quality=WARNING, validation_status=VALID
  - External source without flag → file=FAIL, validation_status=FAILED
  - status mapping WARNING→VALID with warnings[] populated
  - status mapping FAIL→FAILED with errors[] populated
  - FAILED validation → no artefact written (no partial artefact)
  - Stable: idempotent re-import: same sha256 → same dataset_id,
    no second artefact

[Provenance / idempotency]
  - same content → same sha256 → same dataset_id
  - 2nd import with same content → reuse existing dataset directory
    (no new artefact created)
  - stable fields equal across two imports; runtime fields may differ
  - manifest.created_utc may update on re-import (last_seen_utc)
  - manifest.source_relative_path is null for external source with flag
  - manifest.source_filename always equals basename of source file
  - research_safety.automatically_promoted_to_research == false always
  - dataset_scope == IMPORTED_PROTOTYPE always

[Research safety]
  - before-import snapshot of data/raw/primary, data/raw/backup,
    data/processed, reports/ (sha256 + mtime)
  - after-import snapshot
  - assert sha256 + mtime unchanged for every snapshot target
  - FE-06 canonical (whatever parquet lives under data/processed/) is
    one of the snapshot targets
  - NO assertion about reading source from canonical paths
    (DEV-02 has no policy on read-side access; only the destination is
    bounded by the fixed storage root)
```

### 12.3. Acceptance criterion for the full test suite

Acceptance = **no regression** against the pre-DEV-02 baseline.
The pre-DEV-02 baseline is documented as informational in
`docs/system/DEV-02_dataset_management.md §13.3` (this plan) but
**not** treated as a hard pass/fail threshold. The acceptance test
is the *map* of pre/post pass-fail, not a numerical floor.

This is consistent with DEV-01 §7.1, AGENTS.md §2.4, and the Rev 05
fix from the prior DEV-02 plan.

### 12.4. No git-diff-based tests

DEV-02 contains **no test** that inspects `git diff` output, file
timestamps, or any other non-behavioural source-control signal. The
research-safety test uses pre/post **behavioural snapshots** (sha256
of read artefacts) instead.

---

## 13. Acceptance Criteria mapping

| # | Criterion | Verification |
|---|---|---|
| 1 | CSV import works end-to-end | `tests/test_dev02_importer_csv.py::test_csv_import_happy_path` |
| 2 | Parquet import works end-to-end | `tests/test_dev02_importer_parquet.py::test_parquet_import_happy_path` |
| 3 | File-based architecture | manual inspection: only `data/prototype/datasets/<id>/<file>` + `manifest.json` written |
| 4 | SHA-256 computed | manifest contains `sha256`; equal to `compute_file_sha256` of the written artefact |
| 5 | Manifest generated | `tests/test_dev02_manifest.py::test_manifest_schema_complete` |
| 6 | Re-import is idempotent (same content → same `dataset_id`) | `tests/test_dev02_manifest.py::test_idempotent_reimport_same_dataset_id` |
| 7 | List works | `tests/test_dev02_list.py::test_list_after_import` |
| 8 | Schema detection conservative | `tests/test_dev02_importer_csv.py::test_conservative_schema_no_zero_one_boolean`, `test_conservative_schema_no_unix_int_datetime`, `test_conservative_schema_iso_string_stays_string` |
| 9 | Mixed-type detector deterministic | `tests/test_dev02_mixed_detector.py::test_*` |
| 10 | Missing detection works (mirrors `audit.missing_profile`) | `tests/test_dev02_importer_csv.py::test_missing_summary_reflects_audit` |
| 11 | Basic statistics works | `tests/test_dev02_importer_csv.py::test_statistics_match_pandas` |
| 12 | Validation works (3 categories, single pipeline) | `tests/test_dev02_validation.py::test_three_category_validation` |
| 13 | Lifecycle status mapping | `tests/test_dev02_validation.py::test_lifecycle_status_mapping` |
| 14 | FAILED validation → no artefact written | `tests/test_dev02_validation.py::test_failed_validation_no_partial_artifact` |
| 15 | `dataset_scope == IMPORTED_PROTOTYPE` always | `tests/test_dev02_manifest.py::test_scope_always_imported_prototype` |
| 16 | `research_safety.automatically_promoted_to_research == false` always | `tests/test_dev02_research_safety.py::test_no_automatic_research_promotion` |
| 17 | Canonical research artefacts not mutated | `tests/test_dev02_research_safety.py::test_research_artifacts_unmodified` |
| 18 | Imported dataset referenceable for DEV-03..09 | docstring + integration snippet in §14 below |
| 19 | Storage root fixed from config (no CLI override) | `tests/test_dev02_storage.py::test_cli_has_no_dest_root_argument` |
| 20 | No backend/API/database/worker/queue in dependency surface | `tests/test_dev02_runtime_dependencies.py::test_no_forbidden_libs` and `tests/test_dev02_import_blocklist.py` |
| 21 | All new tests pass | `pytest tests/test_dev02_*.py` |
| 22 | Existing test suite not regressed (no previously-passing test now fails) | full `pytest`; pre/post pass-fail map; any prior-pass-now-fail = regression ⇒ halt + investigate |
| 23 | Documentation complete | `docs/system/DEV-02_dataset_management.md` written (this file) |
| 24 | `audit.py` and `versioning.py` public symbols still present (no silent API removal) | `tests/test_dev02_research_safety.py::test_audit_and_versioning_symbols_intact` |

### 13.3. Baseline reference (informational, not gating)

Pre-DEV-02 pytest baseline (recorded 2026-10-08, commit
`8c98b1a`): **1468 passed** in ~7 minutes.

This number is **informational**. It is **not** a pass/fail
threshold. Post-DEV-02, the acceptance is: every test that passed
pre-DEV-02 also passes post-DEV-02. Any newly added test
(`test_dev02_*.py`) is expected to pass on its own merit.

---

## 14. DEV-03 → DEV-09 Dependencies (downstream contract)

DEV-02 emits the following stable contract. **DEV-03..09 MUST consume
this; they MUST NOT invent a new dataset-management layer.**

```python
{
  "dataset_id": "ds_abc123def4567890...",
  "sha256": "...",
  "dataset_scope": "IMPORTED_PROTOTYPE",
  "manifest_path": "data/prototype/datasets/<dataset_id>/manifest.json",
  "artifact_path": "data/prototype/datasets/<dataset_id>/<original_filename>",
  "validation_status": "VALID | NOT_VALIDATED | VALIDATING | FAILED",
  "row_count": N,
  "columns": [...]
}
```

How downstream DEVs reference a dataset:

```python
from customer_segmentation.dataset_management import (
    get_dataset, resolve_storage_root, DatasetScope,
)
from customer_segmentation.config import load_dev02_config  # future helper, NOT in DEV-02

cfg = load_dev02_config()  # or pass path explicitly
root = resolve_storage_root(cfg)
manifest = get_dataset(root, dataset_id="ds_abc123def4567890...")
df = pd.read_parquet(Path(root) / manifest.storage.artifact_path)
```

`DatasetScope` and `ValidationStatus` are the public type enums;
downstream DEVs may import them for type-checking the manifest.

### 14.1. Mapping to downstream DEVs

| Downstream DEV | Consumes from DEV-02 | Does NOT consume |
|---|---|---|
| DEV-03 (preprocessing) | `dataset_id`, `manifest_path`, `artifact_path`, `validation_status` | the import CLI; uses the public API. |
| DEV-04 (feature engineering) | `dataset_id`, `manifest.columns[]` (column names + types) | the validation block. |
| DEV-05 (clustering) | `dataset_id`, `validation_status` (= `VALID` required to run) | the missing summary. |
| DEV-06 (evaluation) | `dataset_id`, `validation_status` | statistics summary. |
| DEV-07 (profiling) | `dataset_id` | the full manifest; only the id. |
| DEV-08 (visualization) | `dataset_id` | the manifest; only the id (UI layer). |
| DEV-09 (reporting) | `dataset_id`, `validation_status`, `sha256` | the columns[] list. |

### 14.2. What DEV-02 does NOT do (re-asserted)

- ❌ Implement DEV-03 preprocessing.
- ❌ Implement DEV-04 feature engineering.
- ❌ Implement DEV-05 clustering.
- ❌ Implement DEV-06 evaluation.
- ❌ Implement DEV-07 profiling.
- ❌ Build a CLI for downstream DEVs.
- ❌ Build an API endpoint.
- ❌ Build a database.

---

## 15. Conflicts and Open Decisions

### 15.1. Detected conflicts (NOT modified in this plan)

| # | Conflict | Severity | Disposition |
|---|---|---|---|
| C-01 | SYS-06 §S-03 tabs (`Overview, Features, Provenance, Usage / Lineage`) vs DEV-02 manifest fields (`Overview, Schema, Missing, Statistics, Validation, Provenance`). | MEDIUM | HARD STOP — do not edit SYS-06 in DEV-02. Recorded as a future ADR topic. The HTML prototype is mock-data only (per ADR-0005); the manifest is the source of truth for the prototype layer. When the UI is re-synced to the manifest, this conflict must be resolved by an ADR + SYS-06 revision. |
| C-02 | SYS-06 §S-02 says "**Không cho upload dataset khác trong prototype**" while DEV-02 introduces an upload capability. | MEDIUM | HARD STOP — do not edit SYS-06 in DEV-02. The SYS-06 statement is a UI / research constraint statement; the DEV-02 capability is a prototype-layer (not research) capability that is enabled via CLI, not via the UI. The HTML prototype is unaffected. Future ADR must reconcile: either (a) keep SYS-06 as a UI constraint while explicitly authorising the CLI capability, or (b) revise SYS-06. |
| C-03 | SYS-06 §S-02 says "chỉ hiển thị dataset primary đã freeze (Online Retail → FE06-v1.0)" — this is a UI-side filter. DEV-02's `list_datasets()` does not enforce this filter at the public API level. | LOW | The filter is a **UI** concern, not a public API concern. The HTML prototype already implements the filter as mock behaviour. When the UI is re-synced to DEV-02, the UI layer will apply the filter; the public API continues to return all `IMPORTED_PROTOTYPE` datasets. |
| C-04 | SYS-01 §13 OQ-09/10/11 were resolved by ADR-0005 (Option A) on 2026-10-08. SYS-02/03/04 are `DRAFT — pending mentor/researcher review`. DEV-02's `data/prototype/datasets/` sub-tree is additive and does not contradict any resolved OQ. | INFORMATIONAL | Recorded; no action in DEV-02. Future SYS-02/03 review should mention the additive sub-tree. |
| C-05 | `configs/dataset.yaml` registry lists primary + backup only. DEV-02 does **not** add an entry to that registry. | NONE | `configs/dev02_dataset_management.yaml` is a **separate** config file. No edit to `dataset.yaml`. |
| C-06 | `data/raw/primary/` and `data/processed/` are read-only research paths. DEV-02's storage root is `data/prototype/datasets/` (additive, git-ignored). | NONE | Already resolved by §11.1. |

### 15.2. Open decisions (carried from the prior plan)

| # | Decision | Recommendation |
|---|---|---|
| D-01 | Manifest writes `last_seen_utc` on re-import (idempotency) | YES — single field, helps audit, doesn't affect identity. |
| D-02 | Pre-source check: refuse read of `data/raw/primary/...` if user passes it as `--file` | NO by default. Read access is not restricted; write is restricted (by the fixed storage root). |
| D-03 | Symlink source path policy | STRICT default (reject external symlink unless flag set). |
| D-04 | Empty-file (0 rows or 0 cols) handling | REJECT (Stage D structural FAIL → no artefact). |
| D-05 | CSV encoding detection | SIMPLEST: error on non-UTF-8 with clear message; do NOT add chardet; document extension point. |

### 15.3. Open SYS-06 conflicts requiring future ADR (recorded, not implemented)

| Topic | Why | Recommended ADR file (when ready) |
|---|---|---|
| Extend SYS-01..06 to formally support `IMPORTED_PROTOTYPE` dataset capability | SYS-01 §3 OOS, SYS-06 §8 S-02/S-03 currently scoped around canonical FE-06 only. DEV-02 introduces a new dataset management contract outside existing SYS scope. | `docs/decisions/0006-imported-prototype-dataset-capability.md` |
| Reconcile SYS-06 §S-02 "no upload" wording with the CLI capability introduced by DEV-02 | The wording in SYS-06 was written before the prototype-layer capability existed. | Same ADR 0006 (sub-topic) or a follow-up. |

**Neither ADR is created in this plan.** They are recommendations
for the human researcher / mentor. DEV-02 implementation can proceed
because DEV-02's contract is fully self-contained; the ADR's role is
documentation alignment, not capability gating.

---

## 16. Traceability: Research → System → Implementation → Test

| Research / methodology source | System requirement (SYS-01) | Implementation (DEV-02) | Test |
|---|---|---|---|
| ADR-0001 (UCI Online Retail primary) | FR-DATA-01..06 (read-only) | `research_safety.read_only_paths_unmodified`; storage root is `data/prototype/`, not `data/raw/primary/` | `test_research_artifacts_unmodified` |
| ADR-0003 (5 algorithms, K-Medoids OUT) | FR-CLUSTER-01..05 | DEV-02 does NOT touch clustering | (no DEV-02 test needed) |
| ADR-0004 (RQ1/RQ2/RQ3) | (carried into EPIC-07..08) | DEV-02 does NOT change RQ | (no DEV-02 test needed) |
| FE-06 C7 (median + Yeo-Johnson + RobustScaler) | FR-DATA-05, FR-DATA-06 | DEV-02 does NOT touch preprocessing | (no DEV-02 test needed) |
| FE-06 SHA-256 (`ba54033e…`) | NFR-01 (reproducibility) | `compute_file_sha256` reused | `test_dataset_id_derivation`, `test_research_artifacts_unmodified` |
| `audit.missing_profile` semantics | FR-DATA-04 | `importer._compute_missing_summary` calls `audit.missing_profile` directly | `test_missing_summary_reflects_audit` |
| `audit.numerical_profile` / `audit.categorical_profile` | FR-DATA-04 | `importer._compute_statistics_summary` calls audit.* directly | `test_statistics_match_pandas` |
| `transformation.versioning.compute_file_sha256` | NFR-01 | reused for `dataset_id` derivation | `test_dataset_id_derivation` |
| `data.validator.ValidationResult` | (research core convention) | reused as raw container inside `CategoryResult` | `test_validation_block_serialisation` |
| AGENTS.md §2.1 (no invented methodology) | — | `dataset_scope = IMPORTED_PROTOTYPE` (only); no auto-promotion | `test_scope_always_imported_prototype`, `test_no_automatic_research_promotion` |
| AGENTS.md §2.4 (scope control) | — | DEV-02 is a capability addition; no methodology / research-core change | `test_audit_and_versioning_symbols_intact` |
| AGENTS.md §2.9 (no silent policy change) | — | all 6 conflicts reported via §15.1; no silent SYS edits | (covered by §15.1) |
| AGENTS.md §2.12 (data privacy) | — | storage under git-ignored `data/`; research paths untouched | `test_research_artifacts_unmodified` |
| AGENTS.md §2.13 (code organization) | — | all reusable logic under `src/customer_segmentation/dataset_management/` | `test_import_blocklist` |
| ADR-0005 Option A (no backend / db) | NFR-ARC-002 | import-blocklist + `pyproject.toml` inspection | `test_no_forbidden_libs`, `test_import_blocklist` |

---

## 17. Self-Review

This section is the author's self-review of the plan, written in
the same turn, with three purposes:

1. **Internal consistency.** Does every section agree with every
   other section?
2. **AGENTS.md compliance.** Does the plan respect the global
   principles (§2) and the stage-by-stage guardrails (§3)?
3. **Acceptance feasibility.** Can each acceptance criterion in §13
   be verified by a test?

### 17.1. Internal consistency

| Check | Result |
|---|---|
| Single validation pipeline (§5.1) used everywhere | OK. All references to "validation" point back to A→B→C→D→E. |
| `dataset_scope = IMPORTED_PROTOTYPE` (no `--scope` flag) | OK. CLI signature in §7.4 has no `--scope`; manifest schema in §8 has `dataset_scope: "IMPORTED_PROTOTYPE"`. |
| `storage_root` is fixed in config (no `--dest-root`) | OK. CLI signature in §7.4 has no `--dest-root`; storage layout in §7.1 places the root under `data/prototype/datasets/`. |
| Two-layer lifecycle model is distinct from result | OK. §9.1 lifecycle and §9.2 result are separately defined; §9.3 mapping table is consistent. |
| Stable vs runtime fields | OK. §8.1 has the full enumeration; manifest dataclass in §6.4 lists every field. |
| Mixed-type detector determinism | OK. §10.3 has the algorithm with frozen type-rank set and head-sample rule. |
| No `.gitkeep` / `.gitignore` edits | OK. §7.3 explicitly says no. |
| No git-diff tests | OK. §12.4 explicitly says no. |
| No hard-coded `pytest >= 1468` | OK. §13.3 reframes as "no regression". |

### 17.2. AGENTS.md compliance

| AGENTS.md rule | Compliance |
|---|---|
| §2.1 Research integrity | OK. DEV-02 does not change algorithms, FE-06, RQ, preprocessing, or evaluation. `IMPORTED_PROTOTYPE` scope is the only scope. |
| §2.2 Phase isolation | OK. DEV-02 does not modify outputs of prior phases (FE-01..06, EXP-01..05, EVA-01..03, CP-01..05). |
| §2.3 Data integrity | OK. Atomic write + idempotency + sha256 verification. |
| §2.4 Scope control | OK. DEV-02 only adds the 8 prototype capabilities listed in §1. No clustering / model training / evaluation / hyperparameter tuning. |
| §2.5 Research decision language | OK. No "best / winner / optimal / recommended / final" claims. `IMPORTED_PROTOTYPE` is explicitly a `dataset_scope`, not a methodology label. |
| §2.6 Feature / model selection | OK. No numerical score, no ranking, no "winner". |
| §2.7 Reproducibility | OK. Manifest records sha256, config hash, environment, created_utc, last_seen_utc. |
| §2.8 Validation | OK. §12 enumerates the test plan; §12.3 specifies the acceptance (no regression, not a hard floor). |
| §2.9 No silent policy change | OK. §15.1 reports all 6 conflicts; none silently fixed. |
| §2.10 Human approval gate | OK. This plan is a Phase 1 read-only deliverable; Phase 2 (implementation) is gated on human approval. |
| §2.11 Git | OK. No git operations performed in this plan. |
| §2.12 Data privacy | OK. `data/prototype/datasets/` is git-ignored; canonical research paths are not written. |
| §2.13 Code organization | OK. All logic under `src/customer_segmentation/dataset_management/`; no duplicate logic from notebooks. |
| §3 Stage-by-stage guardrails | OK. The "Forbidden actions" table for FE-01 ("Running preprocessing, building features from raw data, fitting any model") does not apply to DEV-02 because DEV-02 is a new prototype capability, not a research stage. DEV-02's `import_dataset` does not fit any model; it only reads a CSV/Parquet and writes a manifest. The schema / missing / statistics helpers it calls (`audit.*`) are read-only. |
| §4 Required workflow | OK. This plan is the workflow step "Make the change" precursor; Phase 2 will execute steps 1-9. |
| §5 Forbidden shortcuts | OK. No copy-paste from notebooks; no hard-coded paths; no new dependency. |
| §6 Escalation | OK. Conflicts in §15.1 are surfaced, not silently fixed. |

### 17.3. Acceptance feasibility

Every row in §13 maps to at least one test file. The "manual
inspection" rows are bounded: storage layout (3) and dependency
surface (20) are verified by reading files, not by re-implementing
verification. Tests for 1, 2, 4-19, 21-24 are listed by name in §13
and enumerated in §12.2.

### 17.4. Pre-existing failure disclosure (per AGENTS.md §2.8)

The current repository has the following **pre-existing** items that
will be visible in Phase 2:

- `ruff check .` reports 113 findings in the research core (recorded
  in `docs/system/DEV-01_project_setup.md §7.1.1`). These are
  research-core findings, not DEV-02's responsibility. DEV-02 will
  not introduce new findings; if Phase 2 finds new ruff warnings
  inside `src/customer_segmentation/dataset_management/`, those are
  in-scope and must be fixed before Phase 2 is declared complete.
- `black --check .` reports 26 files would be reformatted in the
  research core. Same disposition.
- `scripts/run_pipeline.py` is a `NotImplementedError` placeholder.
  Not DEV-02's responsibility. The DEV-02 CLI is its own script.

### 17.5. Scope NOT performed (re-affirmation)

- ❌ No RFM-only materialisation.
- ❌ No FE-06 modification.
- ❌ No SYS-01..06 / AGENTS.md / ADR-0001..0005 modification.
- ❌ No new Python dependency.
- ❌ No CLI flag for storage-root or scope override.
- ❌ No git operation.

---

## 18. HARD STOP — Plan complete

PHASE 1 — PLAN ONLY.

NO FILE MODIFIED (other than this plan document itself).
NO CODE IMPLEMENTED.
NO CONFIG CREATED.
NO ADR CREATED.
NO SYS DOCUMENT MODIFIED.
NO GIT OPERATION.

**Status: READY FOR IMPLEMENTATION**, subject to human approval.

**No blockers detected.** All six conflicts (§15.1) are documented
and explicitly do not block implementation. All five open decisions
(§15.2) carry a recommended default; if the human researcher wishes
to override any of them, that is a Phase-1 plan update before
Phase-2 implementation begins.

Chờ human approval:

```
APPROVE PHASE 2
```

trước khi implementation.
