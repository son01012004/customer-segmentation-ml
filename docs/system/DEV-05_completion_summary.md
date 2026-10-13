# DEV-05 Prototype Evaluation Module — Completion Summary

**Mã task:** DEV-05
**Jira pipeline:** `Calculate Metrics / Display Metrics / Compare Experiments`
**Trạng thái:** TECHNICALLY IMPLEMENTED (Phase 2; chờ human reviewer / mentor
for RESEARCH_APPROVED gate per AGENTS.md §2.10)
**Ngày hoàn thành:** 2026-10-09
**Plan:** `docs/system/DEV-05_evaluation_module.md` v1.2
**ADR:** `docs/decisions/0006-dev05-prototype-noise-policy.md` (Accepted)

---

## 1. Files created / modified

### 1.1. Source code (10 files mới trong prototype layer)

```
src/customer_segmentation/prototype/evaluation/
├── __init__.py                 (updated — public API re-exports of all 10 modules)
├── scope.py                    (Phase 2A — enums + frozen constants)
├── config_loader.py            (Phase 2A — frozen dataclass YAML loader)
├── storage.py                  (Phase 2A — content-addressed id + path resolution)
├── manifest.py                 (Phase 2B — EvaluationManifest schema + atomic I/O)
├── metrics.py                  (Phase 2C — sklearn wrappers + DBSCAN noise filter)
├── logging_config.py           (Phase 2E — PerStageLogger façade)
├── pipeline.py                 (Phase 2F — Stage A→G orchestrator)
├── display.py                  (Phase 2G — format_metrics_table + banned-substring check)
└── compare.py                  (Phase 2H — CompatibilityKey + compare_evaluations)
```

### 1.2. CLI script

```
scripts/dev05_evaluate_clustering.py   (Phase 2G — argparse + compute / compare modes)
```

### 1.3. Config

```
configs/dev05_evaluation.yaml          (Phase 2A — single source of truth; ADR-0006 default = "exclude")
```

### 1.4. Test files (10 files, 214 tests)

```
tests/test_dev05_scope.py                  (22 tests — enum invariants)
tests/test_dev05_config.py                 (28 tests — YAML loader + dataclass invariants)
tests/test_dev05_storage.py                (38 tests — evaluation_id, path containment, find_existing)
tests/test_dev05_manifest.py               (41 tests — manifest I/O, atomic write, round-trip)
tests/test_dev05_metrics.py                (29 tests — sklearn wrappers, edge cases, DBSCAN noise)
tests/test_dev05_display.py                (22 tests — format_metrics_table + banned-substring scan)
tests/test_dev05_compare.py                (10 tests — compatibility partition + no-ranking guarantee)
tests/test_dev05_research_safety.py        (16 tests — R-EVAL-01..17)
tests/test_dev05_import_blocklist.py       (5 tests — forbidden imports)
tests/test_dev05_runtime_dependencies.py   (3 tests — declared deps only)
```

**Tổng cộng DEV-05:** 214 tests (PASS, 0 FAIL, 0 SKIP).
**Cộng dồn repo (DEV-02 + DEV-03 + DEV-04 + DEV-05):** 682 tests PASS, 1 SKIP
(DEV-03 C7-dependent test, pre-existing).

---

## 2. Implementation summary

DEV-05 cung cấp prototype-layer evaluation capability với 3 internal
clustering metrics (Silhouette, Davies-Bouldin, Calinski-Harabasz) trên
output của DEV-04.

| Component | Mô tả |
|---|---|
| **Scope** | `EvaluatedScope.EVALUATED_PROTOTYPE` (1 giá trị); không bao giờ promote |
| **3 metrics** | silhouette, davies_bouldin, calinski_harabasz (sklearn wrapped) |
| **Pipeline stages** | A (preflight) → B (lookup) → C (validation) → D (compute) → E (manifest write) → F (atomic publish) → G (finalize log) |
| **Content-addressed identity** | `evaluation_id = "ev_" + SHA256(canonical_json(...))[:24]` với 8 canonical fields |
| **Idempotency** | `find_existing_evaluation()` với collision detection |
| **Atomic publish** | Staging → `os.rename`; force-recompute backup pattern |
| **DBSCAN noise policy** | Uniform exclusion (per ADR-0006); `noise_policy_used` recorded in manifest |
| **Status taxonomy** | 4-value closed enum (VALID_VALUE / NOT_APPLICABLE / MISSING / COMPUTATION_ERROR); 17 reason codes |
| **No fake defaults** | `metric_value = None` iff `status != VALID_VALUE` (R-EVAL rule) |
| **No ranking** | `BANNED_SUBSTRINGS` scan trên display + compare output (R-EVAL-08) |
| **Side-effect discipline** | Chỉ ghi vào `evaluation/<ev_id>/` subtree (R-EVAL-04..07) |

---

## 3. Tests

### 3.1. Unit tests (component-level)

| File | Tests | Coverage |
|---|---|---|
| `test_dev05_scope.py` | 22 | Enum invariants, METRIC_REASON_BY_STATUS, no-fake-defaults, closed enums |
| `test_dev05_config.py` | 28 | YAML parsing, defaults, error paths, dataclass invariants |
| `test_dev05_storage.py` | 38 | `evaluation_id` derivation, regex, path containment, find_existing, collision |
| `test_dev05_manifest.py` | 41 | Round-trip, atomic write, density_based noise_count, scope enforcement |
| `test_dev05_metrics.py` | 29 | sklearn wrapper correctness, DBSCAN noise exclusion, edge cases, defensive copies |
| `test_dev05_display.py` | 22 | format_metrics_table, R-EVAL-08 banned-substring scan, word-boundary regex |
| `test_dev05_compare.py` | 10 | Compatibility partition, singleton groups, no-ranking guarantee, provenance |
| `test_dev05_research_safety.py` | 16 | R-EVAL-01..17 invariants; FE-06 ref check; immutability; atomic publish |
| `test_dev05_import_blocklist.py` | 5 | Forbidden imports (research evaluation, forbidden clustering submodules, plotting libs) |
| `test_dev05_runtime_dependencies.py` | 3 | Declared deps only; no matplotlib / seaborn / plotly at runtime |

### 3.2. Per-AC coverage (per plan §12)

| AC | Code path | Test file / tests |
|---|---|---|
| **AC-1**: Metrics được tính | `metrics.py::compute_internal_metrics` | `test_dev05_metrics.py` (29 tests) |
| **AC-2**: Metrics được lưu | `manifest.py::write_evaluation_manifest` + `pipeline.py::_write_metrics_csv` | `test_dev05_manifest.py` (round-trip + atomic), `test_dev05_research_safety.py::TestAtomicPublish` |
| **AC-3**: Metrics hiển thị | `display.py::format_metrics_table` + CLI `scripts/dev05_evaluate_clustering.py` | `test_dev05_display.py` (22 tests) |
| **AC-4**: So sánh Experiment | `compare.py::compare_evaluations` + CLI `--compare` | `test_dev05_compare.py` (10 tests) |

### 3.3. R-EVAL coverage (per plan §10.1)

- R-EVAL-01..03: `test_dev05_research_safety.py::TestResearchSafetyBlock` (4 tests)
- R-EVAL-04..07: `test_dev05_research_safety.py::TestPathContainment` (3 tests)
- R-EVAL-08: `test_dev05_display.py::TestCheckNoBannedSubstrings` (12 tests)
- R-EVAL-09: `test_dev05_research_safety.py::TestNoFe06Reference` (2 tests)
- R-EVAL-10/11: `test_dev05_research_safety.py::TestUpstreamImmutability` (1 test)
- R-EVAL-12: `test_dev05_research_safety.py::TestMetricSetClosed` (1 test)
- R-EVAL-13: `test_dev05_research_safety.py::TestNoFe06Reference::test_no_test_uses_real_fe06_data`
- R-EVAL-14: `test_dev05_research_safety.py::TestNoiseImmutability` (1 test)
- R-EVAL-15: covered by `test_dev05_import_blocklist.py` (5 tests)
- R-EVAL-16: `test_dev05_research_safety.py::TestManifestCsvConsistency` (2 tests)
- R-EVAL-17: `test_dev05_research_safety.py::TestAtomicPublish` (1 test)

---

## 4. Acceptance criteria (4 mục của Jira)

| # | Jira item | DEV-05 deliverable | Status |
|---|---|---|---|
| 1 | Calculate Metrics | `compute_internal_metrics(X, labels, *, algorithm_family, noise_policy, ...)` → `EvaluationMetricsResult` (3 entries) | ✅ |
| 2 | Save Result | `evaluation_manifest.json` (atomic write) + `metrics_long.csv` (3 rows + header) + log | ✅ |
| 3 | Display Metrics | CLI `scripts/dev05_evaluate_clustering.py` in bảng metrics; `format_metrics_table(result)` helper | ✅ |
| 4 | Compare Experiments | `compare_evaluations([Path, ...])` với CompatibilityKey partition + per-row provenance; CLI `--compare` mode | ✅ |

---

## 5. PENDING_REVIEW / scope notes

| ID | Decision | Status |
|---|---|---|
| DEV-05-OPEN-01 | Noise policy default = "exclude" (uniform across 3 metrics) | `WORKING_ASSUMPTION` (ADR-0006 prototype-scope); research-layer status UNCHANGED |
| DEV-05-OPEN-02 | `metric_set` defaults to all 3 internal metrics | `WORKING_ASSUMPTION` |
| DEV-05-OPEN-03 | `evaluation_id` derivation includes `schema_version` (defence against silent reinterpretation) | `RESOLVED-IN-IMPLEMENTATION` |
| DEV-05-OPEN-04 | Compare singleton group behaviour (OQ-EVAL-04) | `RESOLVED` (B: emit singleton group) |
| DEV-05-OPEN-05 | CLI compare mode (OQ-EVAL-05) | `RESOLVED` (A: sub-mode flag) |
| DEV-05-OPEN-06 | Display missing-value convention (OQ-EVAL-06) | `RESOLVED` (A: em-dash in CLI; blank in CSV) |
| DEV-05-OPEN-07 | Soft probabilities / fuzzy silhouette (OQ-EVAL-07) | `DEFERRED` (out of scope for DEV-05) |
| DEV-05-OPEN-08 | EPIC-08 deferred decisions (ARI/AMI/runtime/CI) | `DEFERRED` (post-Phase-2 increment) |

---

## 6. Scope explicitly NOT performed (per plan §1.2)

- ❌ Ranking algorithms, "best/winner/optimal/recommended/final" framing
- ❌ Modify ML-01 framework / 5 algorithm adapters
- ❌ Modify research-core `customer_segmentation.evaluation.*` (read-only)
- ❌ Hyperparameter sweep / K-sweep / preprocessing sensitivity sweep
- ❌ ARI / AMI / Hungarian / stability / statistical tests / CI / runtime comparison
- ❌ Visualization (matplotlib / seaborn / plotly) — explicitly forbidden by import blocklist
- ❌ Segment profiling / cluster naming
- ❌ Modify DEV-02 / DEV-03 / DEV-04 output contracts / manifests
- ❌ Build backend / API / database / worker / queue (ADR-0005)
- ❌ Promote prototype evaluation to research evidence
- ❌ Run metric evaluation on `data/processed/final_clustering_dataset.parquet`
- ❌ Git operations (commit / push / PR / merge / branch)
- ❌ WCSS / inertia (lives in research core; out of AC scope)
- ❌ New third-party dependencies (only `scikit-learn`, `numpy`, `pandas`, `pyarrow`, `pyyaml` — already in `pyproject.toml`)

---

## 7. Research-safety guarantees (R-EVAL-01..17)

| R-EVAL | Guarantee | Verification |
|---|---|---|
| 01 | `automatically_promoted_to_research = False` always | `TestResearchSafetyBlock` |
| 02 | `appeared_in_research_evidence = False` always | `TestResearchSafetyBlock` |
| 03 | `scope = "EVALUATED_PROTOTYPE"` always | `TestResearchSafetyBlock` |
| 04 | No write to `data/raw/**`, `data/interim/**`, `data/external/**` | `TestPathContainment` + `find_existing_evaluation` regex |
| 05 | No write to `reports/**` | Same |
| 06 | Writes only into `evaluation/<ev_id>/` subtree | `TestPathContainment` |
| 07 | No write to DEV-02..04 staging / backup / failed-tracking dirs | `prototype_evaluation_run_dir` regex |
| 08 | No "best/winner/optimal/ranking/composite_score" outside disclaimer | `TestCheckNoBannedSubstrings` + `TestNoBannedSubstrings` |
| 09 | Never reads `final_clustering_dataset.parquet` | `TestNoFe06Reference` |
| 10 | DEV-03 ML Dataset parquet bytes unchanged | `TestUpstreamImmutability` (path-only, not file bytes) |
| 11 | DEV-04 cluster_labels / experiment_log SHA unchanged | Same |
| 12 | `metric_set` restricted to 3 names | `TestMetricSetClosed` |
| 13 | No test against real FE-06 data | `TestNoFe06Reference::test_no_test_uses_real_fe06_data` |
| 14 | Noise / label immutability (in-memory filter only) | `TestNoiseImmutability` |
| 15 | Source-agnostic metric set (no ARI/AMI/WCSS) | `TestMetricSetClosed` |
| 16 | Manifest / metric-set consistency | `TestManifestCsvConsistency` |
| 17 | Atomic publish (temp file + rename) | `TestAtomicPublish` |

---

## 8. Verification

```bash
# 1. Lint (ruff)
ruff check src/customer_segmentation/prototype/evaluation/ \
          scripts/dev05_evaluate_clustering.py \
          tests/test_dev05_*.py
# (run separately; ruff not yet installed in this env)

# 2. Format check (black)
black --check src/customer_segmentation/prototype/evaluation/ \
              scripts/dev05_evaluate_clustering.py \
              tests/test_dev05_*.py
# (run separately; black not yet installed in this env)

# 3. All DEV-05 tests
PYTHONPATH=src python3 -m pytest tests/test_dev05_*.py -v
# → 214 passed, 0 failed, 0 skipped

# 4. Full regression
PYTHONPATH=src python3 -m pytest tests/test_dev02_*.py tests/test_dev03_*.py \
    tests/test_dev04_*.py tests/test_dev05_*.py
# → 682 passed, 1 skipped (DEV-03 C7-dependent, pre-existing)
```

**Status:** TECHNICALLY IMPLEMENTED.
**Next gate:** Human reviewer / mentor must approve `RESEARCH_APPROVED`
per AGENTS.md §2.10 before any DEV-05 evaluation output is cited as
research evidence. The noise-policy decision in ADR-0006 is also
gated on mentor review at the research layer (CON-15 / WA-08 /
EXP01-MET-01 / MENTOR_REVIEW_FORM line 47 are NOT modified by this
Phase 2 implementation).

---

## 9. Remaining issues / future work

| Issue | Priority | Note |
|---|---|---|
| Final research approval | HIGH | Human reviewer / mentor must approve before evaluation results cited as research evidence |
| OQ-EVAL-EPIC-08 (ARI/AMI/runtime/CI) | LOW | Deferred to post-Phase-2 increment; not blocking DEV-05 |
| Visualization | OUT-OF-SCOPE | EPIC-10 owned; SYS-06 owned |
| `run_evaluation_pipeline` integration test on real DEV-04 artefact | MEDIUM | Currently covered by `test_dev05_metrics.py` + `test_dev05_pipeline.py`-style tests with synthetic data; real DEV-04 integration test deferred (would require published DEV-04 artefact on disk, which depends on DEV-04 having run end-to-end against a real dataset) |
| Plan document v1.2 still says "PLAN — PHASE 1 ONLY" | MEDIUM | Should be updated to "TECHNICALLY IMPLEMENTED" after this summary is approved |

---

*Generated by AI agent as Phase 2 closing artefact; per AGENTS.md §7 the
final report is in Vietnamese; the human researcher retains final
authority on the research methodology decision (per AGENTS.md §2.10).*
