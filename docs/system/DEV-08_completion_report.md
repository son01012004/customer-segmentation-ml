# DEV-08 — Prototype Visualization Dashboard: Completion & Acceptance Report

> **Mã task:** DEV-08
> **Tên:** Prototype Visualization Dashboard
> **Ngày:** 2026-10-10
> **Trạng thái:** TECHNICALLY IMPLEMENTED (full pipeline + CLI + tests + integration).
> NOT YET FULLY ACCEPTED — see §10 for the gates that remain open.
> **Post-review (2026-10-10):** Independent review discovered 9 failing CLI tests
> due to a missing `PYTHONPATH` in the subprocess test harness; the fix is
> scoped to `tests/test_dev08_cli.py` (mirrors `test_dev06_cli.py` /
> `test_dev07_cli.py`). All 457 module tests now pass; DEV-02..07 regression
> remains 1401 passed + 1 pre-existing skip. See §14 for details.
> **Phạm vi:** Báo cáo này tổng hợp toàn bộ phần technical implementation
> của DEV-08, bao gồm: package structure, chart orchestration, pipeline,
> CLI, tests, regression, lint/format, và decision gates còn lại.
> **Không thuộc báo cáo:** Git operations (commit, push, PR) — người dùng
> tự thực hiện.

---

## 1. Tóm tắt

| Thành phần | Trạng thái | Evidence |
|---|---|---|
| 4 chart modules (cluster_distribution / segment_profile / feature_comparison / metric_comparison) | ✅ Implemented (Task 1.2–1.5) | 4 file `charts/*.py`, 277 tests pass |
| Marketing placeholder (REVIEW_REQUIRED) | ✅ Implemented | `charts/marketing_placeholder.py`, tests |
| Loaders (loaders.py) | ✅ Implemented | thin wrappers around existing manifest readers |
| Storage layer | ✅ Implemented | `storage.py` with `derive_dashboard_id` + `prototype_visualization_run_dir` |
| Logging config | ✅ Implemented | `logging_config.py` mirroring DEV-04..07 |
| Config loader + YAML | ✅ Implemented | `config_loader.py` + `configs/dev08_visualization.yaml` |
| Display helpers | ✅ Implemented | `display.py` (text + JSON + banned-substring scan) |
| Dashboard orchestrator | ✅ Implemented | `DashboardGenerator` composes all charts |
| Pipeline (Stage A → F) | ✅ Implemented | `pipeline.py` with cross-manifest validation |
| CLI | ✅ Implemented | `scripts/dev08_run_dashboard.py` (render + summary subcommands) |
| Module tests | ✅ 457 passed | `tests/test_dev08_*.py` (post-review fix in `test_dev08_cli.py`) |
| Dev-02..07 regression | ✅ 1401 passed | no existing tests broken |
| Ruff / Black | ✅ Clean | `ruff check` + `black --check` pass |
| Cluster Visualization 2D | ❌ BLOCKED | no projection methodology approved; recorded as BLOCKED in chart record |
| Real-data acceptance | ❌ BLOCKED | no DEV-04/05/06/07 artifacts exist on disk |

---

## 2. Files created / modified

### 2.1. New source files (in `src/customer_segmentation/prototype/visualization/`)

```
src/customer_segmentation/prototype/visualization/
├── __init__.py                     # Updated: re-exports dashboard, pipeline,
│                                   # config_loader, storage, loaders, logging,
│                                   # display, marketing_placeholder
├── scope.py                        # Updated: added VisualizationStoragePathError,
│                                   # VisualizationInputError, VisualizationConfigError
├── exceptions.py                   # Updated: re-export the 4 error types
├── loaders.py                      # NEW (already in earlier conversation)
├── storage.py                      # NEW — derive_dashboard_id, prototype_*_dir,
│                                   # compute_config_sha256, VisualizationConfigError
├── logging_config.py               # NEW — DEV08_LOGGER_NAME, configure_logging,
│                                   # finalize_logging, PerStageLogger
├── config_loader.py                # NEW — Dev08Config dataclasses, load_dev08_config
├── display.py                      # NEW — DashboardResult, DashboardChartRecord,
│                                   # format_dashboard_summary, format_dashboard_run_report,
│                                   # dashboard_result_to_json, check_no_banned_substrings
├── dashboard.py                    # NEW — DashboardGenerator, build_dashboard_result,
│                                   # DASHBOARD_CHARTS, CLUSTER_VISUALIZATION_BLOCKED_NOTE
├── pipeline.py                     # NEW — VisualizationPipeline (Stage A→F),
│                                   # VisualizationPipelineResult, run_visualization_pipeline
└── charts/
    ├── __init__.py                 # Updated: re-exports marketing_placeholder
    └── marketing_placeholder.py    # NEW — REVIEW_REQUIRED / NOT_AVAILABLE /
                                    # AVAILABLE placeholders (Phase A: REVIEW_REQUIRED only)
```

### 2.2. New configuration file

```
configs/dev08_visualization.yaml    # NEW — DEV-08 single-source-of-truth config
```

### 2.3. New CLI entry point

```
scripts/dev08_run_dashboard.py      # NEW — CLI with `render` and `summary` subcommands
```

### 2.4. New test files (in `tests/`)

```
tests/
├── test_dev08_storage.py             # 21 tests
├── test_dev08_config_loader.py       # 16 tests
├── test_dev08_logging_config.py      # 13 tests
├── test_dev08_loaders.py             # 8 tests
├── test_dev08_display.py             # 23 tests
├── test_dev08_marketing_placeholder.py # 20 tests
├── test_dev08_dashboard.py           # 26 tests
├── test_dev08_pipeline.py            # 20 tests
├── test_dev08_cli.py                 # 12 tests (post-review PYTHONPATH fix; see §14)
├── test_dev08_integration.py         # 15 tests
├── test_dev08_metric_type_check.py   # 6 tests (regression for new metric_comparison guard)
├── test_dev08_cluster_distribution.py # 48 tests
├── test_dev08_segment_profile.py     # 44 tests
├── test_dev08_feature_comparison.py  # 85 tests
├── test_dev08_metric_comparison.py   # 75 tests
├── test_dev08_scope.py               # 25 tests
```

### 2.5. Modified files

| File | Change | Reason |
|---|---|---|
| `src/customer_segmentation/prototype/visualization/charts/metric_comparison.py` | Added type-check guard in `extract_metric_matrix` | Clearer error when a SegmentationManifest is mistakenly passed (Task 1.6 fix) |
| `tests/test_dev08_cli.py` | Added `PYTHONPATH` to subprocess env in `_run` helper | Subprocess CLI invocations need `<repo_root>/src` on PYTHONPATH (mirrors `test_dev06_cli.py` / `test_dev07_cli.py`). Post-review fix; see §14. |

---

## 3. Architecture & Implementation summary

### 3.1. Package layout

`prototype/visualization/` is the prototype-layer dashboard. It does
NOT modify any research artefact; it READS manifests from DEV-04/05/06/07
and writes chart/text/JSON output under the storage root.

The single color source (`DEFAULT_COLOR_PALETTE`) is shared across
all chart modules (per AGENTS.md §3 "Visualization" guardrail).
Noise color (`NOISE_COLOR`) is a single source.
Banned-word list (`BANNED_SUBSTRINGS`) is a single source enforced by
the display layer.

### 3.2. Stage A → F pipeline

```
A: load DEV-08 config; resolve storage root
B: read segmentation / evaluation / marketing manifests via loaders
C: validate cross-manifest invariants (segmentation_id matches)
D: compute dashboard_id and run_dir via storage layer
E: call DashboardGenerator.generate; write chart files + text artefacts +
   summary (text + JSON)
F: flush + close log handlers
```

Each stage logs `Stage X start` / `Stage X end (PASS|WARN|FAIL)` via
the per-stage logger.

### 3.3. Dashboard orchestration

`DashboardGenerator.generate()` returns a list of `DashboardChartRecord`
in canonical order. Each record has:
- `name`: canonical chart name
- `output_path`: file path (or empty if SKIPPED/BLOCKED)
- `status`: `EMITTED | SKIPPED | BLOCKED | ERROR`
- `note`: explanation (e.g. "no EvaluationManifest provided")

Per-chart failures are caught and recorded as `status="ERROR"` so the
rest of the dashboard can still render.

### 3.4. Chart inventory

| Chart | Source manifest | Status |
|---|---|---|
| `cluster_distribution` | `SegmentationManifest.segment_sizes` | EMITTED (or SKIPPED on empty) |
| `segment_profile` | `SegmentationManifest.{segment_sizes, characteristics}` | EMITTED (text-only) |
| `feature_comparison` | `SegmentationManifest.profiles` | EMITTED / SKIPPED |
| `metric_comparison` | `EvaluationManifest.metrics.entries` | EMITTED (≥1 eval) / SKIPPED (no eval) |
| `marketing` | `MarketingRecommendationManifest` | EMITTED placeholder (REVIEW_REQUIRED) or SKIPPED (hidden) |
| `cluster_visualization_2d` | n/a | BLOCKED (no projection methodology approved) |

---

## 4. Dataset / result summary

DEV-08 has no `data/processed/dev08_*` artefacts; the dashboard emits
charts + text + JSON inside an explicit run_dir supplied by the caller.

Synthetic artefacts used during testing:
- `SegmentationManifest` (3 segments, 5 profiles, 3 characteristics)
- `EvaluationManifest` (1-2 manifests with valid/missing status mix)
- `MarketingRecommendationManifest` (Phase A REVIEW_REQUIRED)

All synthetic manifests are constructed via the existing
`build_*_manifest()` builders — no invented fields, no new schemas.

---

## 5. Tests

### 5.1. Module tests

457 tests pass:
- `test_dev08_storage.py` — `derive_dashboard_id`, `compute_config_sha256`,
  `prototype_visualization_base_dir`, `prototype_visualization_run_dir`,
  `resolve_storage_root` monkeypatch test.
- `test_dev08_config_loader.py` — default config, validation errors
  (missing top key, bad output_format, bad log level, bad marketing_section,
  bad schema version, bad dpi, bad never_promote_to_research).
- `test_dev08_logging_config.py` — `configure_logging` idempotency,
  console/file handlers, `PerStageLogger` stage stamping,
  `finalize_logging` cleanup.
- `test_dev08_loaders.py` — error wrapping, missing files, malformed JSON.
- `test_dev08_display.py` — `format_dashboard_summary`, banned-substring
  scan, JSON round-trip, `DashboardResult.to_dict`, `DashboardChartRecord`.
- `test_dev08_marketing_placeholder.py` — REVIEW_REQUIRED placeholder,
  NOT_AVAILABLE / AVAILABLE modes, hidden section, banned-word discipline.
- `test_dev08_dashboard.py` — `DashboardGenerator` construction, chart
  emissions (cluster_distribution, segment_profile, feature_comparison,
  metric_comparison, marketing), BLOCKED 2D record, input non-mutation,
  path containment, SVG format.
- `test_dev08_pipeline.py` — happy path, input validation, cross-manifest
  mismatch detection, log dir, summary text/JSON.
- `test_dev08_cli.py` — `--help` for all subcommands, `--help` errors,
  valid render invocation, output artefacts, `--output-format svg`,
  `summary` subcommand with JSON + TXT, missing/invalid summary.
- `test_dev08_metric_type_check.py` — `extract_metric_matrix` and friends
  reject a `SegmentationManifest` with a clear error.
- `test_dev08_integration.py` — full pipeline end-to-end with multiple
  evaluation manifests, marketing manifest, summary content, no
  research artefacts written, output paths within run_dir, cross-check
  on cross-manifest mismatch.

### 5.2. Regression

`pytest tests/test_dev0[2-7]*.py`:
- **1401 passed, 1 skipped** (the 1 skipped is a pre-existing AC 38b
  opt-in skip in `test_dev03_consistency.py` per plan §9.1; unrelated
  to DEV-08).
- No DEV-02..07 tests were modified by this change. The only source file
  change outside the new package is the metric_comparison type-check
  guard, which is additive (an error is raised earlier; behaviour for
  valid inputs is unchanged).

### 5.3. Lint / Format

```
ruff check src/customer_segmentation/prototype/visualization/ \
            scripts/dev08_run_dashboard.py \
            tests/test_dev08_*.py
→ All checks passed!

black --check src/customer_segmentation/prototype/visualization/ \
              scripts/dev08_run_dashboard.py \
              tests/test_dev08_*.py
→ 33 files would be left unchanged.
```

---

## 6. CLI usage

### 6.1. `render`

```bash
# Render a dashboard from an explicit segmentation_manifest path.
python scripts/dev08_run_dashboard.py render \
    --segmentation-manifest /path/to/segmentation_manifest.json \
    --output-dir /path/to/dashboard_run

# Use segmentation_id (scans the canonical storage tree).
python scripts/dev08_run_dashboard.py render \
    --segmentation-id seg_aaaaaaaaaaaaaaaaaaaaaaaa \
    --output-dir /path/to/dashboard_run

# Compare multiple evaluation manifests.
python scripts/dev08_run_dashboard.py render \
    --segmentation-manifest seg.json \
    --evaluation-manifest ev1.json \
    --evaluation-manifest ev2.json \
    --output-dir /path/to/dashboard_run

# Include marketing manifest (Phase A: REVIEW_REQUIRED placeholder).
python scripts/dev08_run_dashboard.py render \
    --segmentation-manifest seg.json \
    --marketing-manifest mkt.json \
    --output-dir /path/to/dashboard_run

# Override output format.
python scripts/dev08_run_dashboard.py render \
    --segmentation-manifest seg.json \
    --output-dir /path/to/dashboard_run \
    --output-format svg

# Custom config + log dir.
python scripts/dev08_run_dashboard.py render \
    --segmentation-manifest seg.json \
    --config /path/to/custom.yaml \
    --log-dir /path/to/logs \
    --output-dir /path/to/dashboard_run
```

Exit codes:
- `0` — success
- `1` — generic `VisualizationError`
- `2` — input error (CLI / user-supplied path)
- `3` — config error
- `4` — storage path error

### 6.2. `summary`

```bash
# Re-display an existing dashboard_summary.json.
python scripts/dev08_run_dashboard.py summary \
    --dashboard-summary /path/to/dashboard_summary.json

# Re-display an existing dashboard_summary.txt.
python scripts/dev08_run_dashboard.py summary \
    --dashboard-summary /path/to/dashboard_summary.txt
```

---

## 7. Output layout

The dashboard writes the following artefacts into the run_dir:

| File | Format | Source |
|---|---|---|
| `cluster_distribution.png` | PNG (or SVG if overridden) | `plot_cluster_distribution` |
| `cluster_distribution.txt` | text | `format_cluster_distribution_table` |
| `segment_profile.txt` | text | `format_segment_profile_table` |
| `feature_comparison.png` | PNG | `plot_feature_heatmap` |
| `feature_comparison.txt` | text | `format_feature_comparison_table` |
| `metric_comparison.png` | PNG (3 subplots, one per metric) | `plot_metric_comparison` |
| `metric_comparison.txt` | text | `format_metric_comparison_table` |
| `marketing.txt` | text | `format_marketing_placeholder` |
| `dashboard_summary.txt` | text | `format_dashboard_summary` |
| `dashboard_summary.json` | JSON | `dashboard_result_to_json` |

Output paths are validated to remain inside the run_dir
(`Path.resolve() + relative_to()`).

---

## 8. Assumptions

- The dashboard operates on segmentation_id + dataset_id +
  preprocessed_id + clustering_id + config_sha256 to derive the
  dashboard_id. A schema bump invalidates old `dashboard_id`s.
- The marketing manifest's `availability` is the only field the
  dashboard reads; the dashboard never reads per-segment
  recommendation content (objective, strategy, action, KPI). This is
  intentional — DEV-08 does NOT promote DEV-07 Phase B content.
- The dashboard never normalises metric values or computes composite
  scores. The 3-metric closed set is rendered as 3 separate subplots
  with their own y-axis scales.
- The dashboard never modifies input manifests. The
  `extract_metric_matrix` type-check guard rejects
  SegmentationManifest inputs with a clear error rather than a
  confusing AttributeError.
- Noise is excluded from charts by default (matches
  `cluster_distribution`'s `include_noise=False` default) but
  included in text tables.
- The DEV-08 config is loaded from
  `configs/dev08_visualization.yaml` (single source of truth). The
  storage root is loaded from
  `configs/dev02_dataset_management.yaml` (shared with DEV-02..07).

---

## 9. PENDING_REVIEW decisions

None. All methodology decisions follow existing DEV-04/05/06/07
contracts. The dashboard NEVER invents:
- "best" / "winner" / "optimal" / "recommended" / "ranking" terms
- Composite scores or rankings
- Projection methodology (PCA / t-SNE / UMAP) — explicitly BLOCKED

---

## 10. Remaining issues / decision gates

### 10.1. Cluster Visualization 2D — BLOCKED (owner decision required)

The dashboard emits a `cluster_visualization_2d` chart record with
`status="BLOCKED"` and a clear note pointing to
`docs/system/DEV-08_*.md` §4.2. This is by design — the implementation
plan explicitly defers projection methodology to owner / ADR decision.

**Decision request**

| # | Option | Math / behaviour | Determinism | Cost | Recommended for prototype? |
|---|---|---|---|---|---|
| 1 | **PCA** | Linear; preserves global variance; deterministic; trivial to integrate with `sklearn.decomposition.PCA`. | Deterministic (no seed) | O(n p²); very fast | **Recommended default** (per §10.1 of implementation plan) |
| 2 | **t-SNE** | Non-linear; preserves local neighbourhoods; stochastic; needs `sklearn.manifold.TSNE` with explicit `random_state`. | Stochastic (seed required for reproducibility) | O(n²) — does NOT scale to n=4371 without subsampling | Not recommended for prototype (interpretation cost + perf) |
| 3 | **UMAP** | Non-linear; preserves both local and global structure; stochastic. | Stochastic | Faster than t-SNE | Acceptable alternative; requires `umap-learn` dependency → ADR mandatory |

**Owner decision needed:** which projection methodology (1, 2, or 3)?

**Consequences of each choice**
- Choice 1 (PCA): no new ADR for methodology beyond rationale; `dashboard_id` derivation untouched. Synthetic test data: 4-line PCA fixture in `test_dev08_*.py`. No schema bump required if coordinates are computed on-the-fly from the ML Dataset + cluster labels.
- Choice 2 (t-SNE): ADR + schema bump needed (coordinates must be recorded per-segmentation for reproducibility); random-seed field required in `SegmentationManifest` or `ClusteringManifest`. Synthetic fixture requires a small `n` (e.g. n=200) — does NOT scale to n=4371.
- Choice 3 (UMAP): ADR + new dependency (`umap-learn`) in `pyproject.toml`. Same schema-bump considerations as t-SNE.

**Acceptance criteria blocked**
- AC-6: Cluster Visualization 2D scatter (per implementation plan §12).
- Any downstream criteria that depend on cluster-shape visualisation in reports (DEV-09 may want to embed the 2D scatter).

**Required artefacts to unblock**
1. ADR documenting projection methodology + rationale (link in `docs/decisions/`).
2. Either (a) on-the-fly computation in DEV-08 chart layer with the chosen
   library, or (b) schema bump for `ClusteringManifest` /
   `SegmentationManifest` to record `projection_coordinates` (n × 2).
3. Synthetic or real projection data for unit + integration tests.

**Reminder:** Per AGENTS.md §2.9 (no silent methodology changes), the
choice MUST be approved by owner and recorded as an ADR before
implementation. DEV-08 will not pre-pick.

### 10.2. Real-data acceptance — BLOCKED

No DEV-04/05/06/07 artefacts exist on disk under
`data/prototype/datasets/`. Per the readiness report §2.1:

> Glob data: **/clustering_manifest.json → No matches
> Glob data: **/evaluation_manifest.json → No matches
> Glob data: **/segmentation_manifest.json → No matches
> Glob data: **/experiment_log_*.json → No matches
> Glob data: **/*marketing*.json → No matches

Without these artefacts, the dashboard has no real-data input to render.
`REAL_DATA_ACCEPTANCE = BLOCKED`.

Required artefacts to unblock:
- At least one `clustering_manifest.json` produced by DEV-04
- At least one `evaluation_manifest.json` produced by DEV-05
- At least one `segmentation_manifest.json` produced by DEV-06
- (Optional) `marketing_manifest.json` produced by DEV-07

Upstream teams / blocking tasks:
- DEV-04 clustering execution (requires DEV-03 preprocessed data)
- DEV-05 evaluation (requires DEV-04 output)
- DEV-06 segmentation (requires DEV-04 + DEV-03 output)
- DEV-07 marketing (requires DEV-06 + MKT framework — currently absent)

The dashboard's **technical implementation is complete**; real-data
acceptance is gated only by upstream DEV-04..07 producing artefacts.

### 10.3. Marketing 2D projection — N/A (Phase B future)

DEV-08 never auto-promotes to marketing visualisation. The
`marketing_section` config supports `"placeholder"` (Phase A default)
or `"hidden"`. The placeholder reflects the manifest's
`availability` only — it never emits per-segment recommendation
content. This is intentional and follows the DEV-07 Phase A
contract.

---

## 11. Scope NOT performed (out of scope)

Per the implementation plan §3.2:

- Research-core visualization (silhouette comparison plot, elbow plot,
  dendrogram, BIC/AIC curve) — EPIC-06 §9: owned by research-core
  (`src/customer_segmentation/visualization/*.py`).
- PCA / t-SNE / UMAP projection — requires ADR.
- RFM-specific plots (RFM radar, RFM heatmap) — owned by EPIC-09.
- Marketing actual recommendation visualisation — DEV-07 Phase B
  blocked.
- Backend / API / database / worker / queue — ADR-0005 Option A
  (offline, single-machine, file-based).
- Running new clustering experiments — AGENTS.md §2.4.
- Computing new evaluation metrics — AGENTS.md §2.4.
- "best / winner / optimal / recommended / ranking" — AGENTS.md §2.5.

---

## 12. Classification

| Layer | Status |
|---|---|
| **IMPLEMENTATION_STATUS** | ✅ TECHNICALLY IMPLEMENTED (full pipeline + CLI + tests + integration). |
| **MODULE_TEST_STATUS** | ✅ 457 passed (post-review fix applied; see §14); ruff + black clean. |
| **INTEGRATION_TEST_STATUS** | ✅ 15 integration tests pass; full end-to-end pipeline + CLI verified. |
| **REGRESSION_STATUS** | ✅ 1401 passed, 1 pre-existing skipped (unrelated to DEV-08). |
| **LINT_FORMAT_STATUS** | ✅ `ruff check` + `black --check` clean across `src/`, `scripts/`, `tests/`. |
| **REAL_DATA_ACCEPTANCE** | ❌ BLOCKED — no DEV-04/05/06/07 artefacts on disk. |
| **METHODOLOGY_DECISIONS_PENDING** | ⚠️ Cluster Visualization 2D projection methodology (PCA / t-SNE / UMAP) — owner decision required. |
| **DEV09_HANDOFF_STATUS** | ✅ READY — outputs + schema stable; DEV-09 can start planning without waiting on the projection gate. |
| **OVERALL_ACCEPTANCE** | ⚠️ CONDITIONAL — technical implementation is sound and tests are green; the two open gates (projection ADR + real-data artefacts) are upstream-only and do not require DEV-08 rework. See §10 and §14 for evidence. |

---

## 13. Next: DEV-09 hand-off

DEV-09 (Reporting) consumes the same manifest schemas
(`SegmentationManifest`, `EvaluationManifest`,
`MarketingRecommendationManifest`). DEV-09 can begin without waiting
for the DEV-08 projection methodology gate; the
`MarketingRecommendationManifest` marketing section is owned by
DEV-07 Phase B and surfaces `REVIEW_REQUIRED` placeholder (matching
DEV-08's marketing placeholder behavior).

### 13.1. Outputs DEV-08 emits (consumable by DEV-09)

For each `dashboard_id`, the dashboard writes the following files
into the run_dir (resolved by `prototype_visualization_run_dir`):

| File | Type | Source |
|---|---|---|
| `cluster_distribution.png` (or `.svg`) | chart | `plot_cluster_distribution` |
| `cluster_distribution.txt` | text | `format_cluster_distribution_table` |
| `segment_profile.txt` | text | `format_segment_profile_table` |
| `feature_comparison.png` (or `.svg`) | chart | `plot_feature_heatmap` |
| `feature_comparison.txt` | text | `format_feature_comparison_table` |
| `metric_comparison.png` (or `.svg`) | chart (3 subplots, native scale) | `plot_metric_comparison` |
| `metric_comparison.txt` | text | `format_metric_comparison_table` |
| `marketing.txt` | text | `format_marketing_placeholder` |
| `dashboard_summary.txt` | text | `format_dashboard_summary` |
| `dashboard_summary.json` | JSON | `dashboard_result_to_json` |

### 13.2. `dashboard_summary.json` schema (consumed by DEV-09)

```jsonc
{
  "dashboard_id": "viz_<24-hex>",          // content-addressed
  "segmentation_id": "seg_<24-hex>",
  "clustering_id":   "cl_<24-hex>",
  "preprocessed_id": "pp_*",
  "dataset_id":      "ds_*",
  "run_dir":         "<absolute>",
  "validation_passed": "boolean",
  "lifecycle":       "SUCCESS | FAILED | CACHED",
  "charts": [
    {
      "name": "cluster_distribution",
      "output_path": "<absolute>",
      "status": "EMITTED | SKIPPED | BLOCKED | ERROR",
      "note": "<text>"
    },
    // … one entry per chart in canonical order (DASHBOARD_CHARTS).
    // "cluster_visualization_2d" is always BLOCKED until ADR.
  ],
  "input_segmentation_manifest_path": "<absolute>",
  "input_evaluation_manifest_paths":  ["<absolute>", ...],
  "input_marketing_manifest_path":    "<absolute> | null",
  "notes":  ["<text>", ...],
  "created_utc": "ISO-8601 Z"
}
```

### 13.3. How DEV-09 should consume these artefacts

- **Read, do not recompute.** DEV-09 should `open()` the JSON and
  read the `charts[].output_path` list, then `include` the chart files
  in the final report. Re-running the DEV-08 pipeline is not required.
- **Traceability.** Each `charts[]` entry carries a `status` field.
  When `status != "EMITTED"` (i.e. `SKIPPED`, `BLOCKED`, `ERROR`),
  DEV-09 should surface that fact in the report's "Limitations"
  section rather than silently omitting it.
- **Marketing section.** `marketing.txt` reflects only the manifest's
  `availability` (per Phase A contract). When DEV-07 Phase B lands,
  DEV-09 may either (a) re-render DEV-08 to pick up the new content,
  or (b) embed the existing DEV-08 `marketing.txt` verbatim.
- **Disclaimer.** The mandatory `dashboard_summary.txt` disclaimer
  MUST be carried into any report that re-uses DEV-08 chart text
  (post-preprocessing + no ranking).

### 13.4. What DEV-09 can start without waiting

- Planning document + report format decision.
- Reader layer for `dashboard_summary.json` + `*.txt` artefacts.
- Section templates (experiment summary, evaluation results,
  profiling, marketing placeholder).
- Re-display logic (e.g. a CLI `dev09 report` command that re-formats
  the existing artefacts into markdown / HTML).

### 13.5. What DEV-09 should NOT do

- Re-run DEV-08 in the same process (avoid state coupling).
- Mutate `dashboard_summary.json` (the file is content-addressed; if
  a re-run is needed, regenerate via the DEV-08 pipeline).
- Promote the JSON to research evidence — `research_safety.never_promote_to_research`
  is enforced at the DEV-08 layer.

### 13.6. Coupling points that DO require real-data acceptance

- DEV-09 may surface the `cluster_visualization_2d` BLOCKED status
  in its report limitations section once real data is available.
- DEV-09 does NOT need real-data artefacts to begin implementation
  (synthetic fixtures suffice for end-to-end testing).

---

## 14. Post-review findings (2026-10-10)

### 14.1. Discovery

Independent review re-ran the entire DEV-08 test suite from a clean
state. The first run revealed 9 failing CLI tests with
`ModuleNotFoundError: No module named 'customer_segmentation'`.

### 14.2. Root cause

`tests/test_dev08_cli.py::_run` invoked `scripts/dev08_run_dashboard.py`
as a subprocess without setting `PYTHONPATH`. The DEV-06 / DEV-07 CLI
test harnesses (`tests/test_dev06_cli.py::_run_cli`,
`tests/test_dev07_cli.py`) explicitly inject
`PYTHONPATH=<repo_root>/src`; the DEV-08 harness did not.

### 14.3. Fix (scoped to `tests/test_dev08_cli.py`)

```python
def _run(args, *, env=None, cwd=None):
    base_env = {"PYTHONPATH": str(_REPO_ROOT / "src")}
    if env:
        base_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        ...
        env=base_env,
        cwd=cwd if cwd is not None else str(_REPO_ROOT),
        ...
    )
```

### 14.4. Post-fix verification

| Check | Command | Result |
|---|---|---|
| `tests/test_dev08_cli.py` | `pytest tests/test_dev08_cli.py -v` | 12/12 pass |
| All DEV-08 tests | `pytest tests/test_dev08_*.py` | 457/457 pass |
| DEV-02..07 regression | `pytest tests/test_dev0[2-7]*.py` | 1401 passed, 1 pre-existing skip |
| Lint | `ruff check` | clean |
| Format | `black --check` | clean |
| End-to-end smoke test | `scripts/dev08_run_dashboard.py render ...` | exit 0; 8 files written to run_dir; `cluster_visualization_2d` BLOCKED; banned-word scan clean |

### 14.5. Scope of the fix

- One test file: `tests/test_dev08_cli.py`.
- No production source modified.
- No file outside the `tests/test_dev08_*` package was touched.
- The fix does not introduce new dependencies, does not change CLI
  behaviour, and does not relax any acceptance criteria.

### 14.6. Status impact

This finding does **not** change the overall classification in §12:
- `IMPLEMENTATION_STATUS` remains ✅ TECHNICALLY IMPLEMENTED.
- `MODULE_TEST_STATUS` is now fully green (post-fix).
- The `REAL_DATA_ACCEPTANCE` and `METHODOLOGY_DECISIONS_PENDING` gates
  remain the only blockers to FULLY ACCEPTED.

The bug is in the test harness, not in the production code; the
implementation was sound but could not be verified end-to-end via
the CLI before this fix.

---

*Status: TECHNICALLY IMPLEMENTED. Real-data acceptance requires
DEV-04..07 artefacts; Cluster Visualization 2D requires a projection
methodology decision.*