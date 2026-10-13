# DEV-04 Prototype Clustering Execution — Completion Summary

**Mã task:** DEV-04
**Jira pipeline:** `Choose Algorithm / Configure Parameters / Run Experiment / Produce Cluster Labels / Save Experiment / Save Result`
**Trạng thái:** TECHNICALLY IMPLEMENTED (DEV-04 Phase 2, chờ human reviewer)
**Ngày hoàn thành:** 2026-10-09
**Dựa trên plan:** `docs/system/DEV-04_clustering_execution.md` (Phase 1 read-only; Phase 2 = implementation)

---

## 1. Files created / modified

### 1.1. Source code (7 files mới trong prototype layer)

```
src/customer_segmentation/prototype/clustering/__init__.py        (updated — public API exports)
src/customer_segmentation/prototype/clustering/scope.py           (new — enum + constants)
src/customer_segmentation/prototype/clustering/storage.py          (new — content-addressed storage)
src/customer_segmentation/prototype/clustering/config_loader.py  (new — YAML config loader)
src/customer_segmentation/prototype/clustering/manifest.py       (new — clustering_manifest.json schema)
src/customer_segmentation/prototype/clustering/logging_config.py  (new — per-stage logging)
src/customer_segmentation/prototype/clustering/pipeline.py       (new — Stages 0→6)
```

### 1.2. CLI script

```
scripts/dev04_run_clustering.py   (new — mirrors scripts/run_ml0X_kmeans.py pattern)
```

### 1.3. Config

```
configs/dev04_clustering.yaml   (created Phase 1; verified Phase 2)
```

### 1.4. Test files (10 files)

```
tests/test_dev04_scope.py            (9 tests — enum/frozenset invariants)
tests/test_dev04_config.py          (17 tests — config loading/validation)
tests/test_dev04_storage.py         (18 tests — clustering_id derivation, path containment, idempotency)
tests/test_dev04_manifest.py        (12 tests — manifest I/O, atomic write, round-trip)
tests/test_dev04_logging.py         (10 tests — logging façade, per-stage, finalize)
tests/test_dev04_cli.py              (5 tests — CLI argparser, hyperparameter collection)
tests/test_dev04_pipeline.py         (7 integration tests — end-to-end with synthetic ML Dataset)
tests/test_dev04_safety.py          (26 tests — R-15/R-17/R-13/R-16 invariants)
tests/test_dev04_research_safety.py  (6 tests — research artefacts unmodified, promotion guard)
tests/test_dev04_import_blocklist.py (32 tests — forbidden libs + forbidden subpackages, runtime + static)
tests/test_dev04_runtime_dependencies.py (16 tests — no new libs, no forbidden imports)
```

**Tổng cộng:** 158 tests mới cho DEV-04 (sau Phase 2 safety remediation).

---

## 2. Implementation summary

DEV-04 cung cấp prototype-layer clustering execution capability dựa trên:

| Component | Mô tả |
|---|---|
| **Scope** | `ClusteredScope.CLUSTERED_PROTOTYPE` — chỉ 1 giá trị; không bao giờ promote |
| **5 Algorithms** | `kmeans`, `agglomerative`, `dbscan`, `gmm`, `fuzzy_cmeans` |
| **Pipeline stages** | 0 (preflight) → 1 (lookup DEV-03 manifest) → 2 (matrix split) → 3 (build ExperimentSpec) → 4 (runner.run()) → 5 (write manifest) → 5b (atomic publish) → 6 (finalize log) |
| **Content-addressed identity** | `clustering_id = "cl_" + SHA256(canonical_json(...))[:24]` |
| **Idempotency** | `find_existing_clustering()` — collision detection nếu cùng id nhưng payload khác |
| **Atomic publish** | Staging directory → atomic `os.rename`; crash recovery via orphan backup |
| **Hyperparameter filter** | `ALGORITHM_HP_KEYS` map — chỉ pass params phù hợp cho từng adapter |
| **`random_state` injection** | Stochastic algorithms (kmeans/gmm/fuzzy_cmeans) luôn inject `effective_seed` để hash consistency |

---

## 3. Tests

### 3.1. Unit tests

| File | Tests | Coverage |
|---|---|---|
| `test_dev04_scope.py` | 9 | Enum invariants, frozenset symmetry |
| `test_dev04_config.py` | 17 | Default loading, custom YAML, error paths |
| `test_dev04_storage.py` | 18 | clustering_id derivation, path traversal defence, collision detection |
| `test_dev04_manifest.py` | 12 | Round-trip, atomic write, corrupt/missing/error paths |
| `test_dev04_logging.py` | 10 | Per-stage logger façade, file/console handlers, finalize idempotent |
| `test_dev04_cli.py` | 5 | CLI argparser, hyperparameter collection |
| `test_dev04_safety.py` | 26 | R-15/R-17/R-13/R-16 invariants, F1 staging-retained-when-orphan, Stage 6 lifecycle |
| `test_dev04_research_safety.py` | 6 | Research artefacts unmodified, manifest flags, prototype write path |
| `test_dev04_import_blocklist.py` | 32 | Forbidden libs + research subpackages, runtime + static scan |
| `test_dev04_runtime_dependencies.py` | 16 | No new backend libs declared, no forbidden libs imported in source |

### 3.2. Integration tests

| Test | Mô tả |
|---|---|
| `test_pipeline_imports` | Package imports clean |
| `test_kmeans_run_success` | K-Means end-to-end với synthetic ML Dataset |
| `test_deterministic_algorithm_no_seed` | DBSCAN deterministic — seed null in manifest |
| `test_unknown_algorithm_raises` | Unknown algorithm → `Dev04ConfigError` |
| `test_second_run_is_cached` | Idempotency: same config → CACHED |
| `test_force_rerun_overrides_cache` | `--force-rerun` → SUCCESS |
| `test_as_summary_is_json_serialisable` | `as_summary()` JSON round-trip |
| `test_stage_6_recorded_in_success_result` | Stage 6 "finalize_log" appears in `stage_logs` for SUCCESS lifecycle |

### 3.3. R-15 / R-16 / R-17 / R-13 safety coverage (per plan §11.1a, §16.2)

**R-15 (R1, 6 tests):** `_preserve_failed_log` happy path / no-log / no-staging /
partial (mock) / mkdir-failed / multiple-logs. Plus F1 invariant tests
(`test_staging_retained_when_unpreserved_true`, `test_staging_removed_when_unpreserved_false`).

**R-16 (R2, 6 tests):** corrupt manifest default fail-closed; force-rerun corrupt
recovery; corrupt rename failure stops; recovery skips corrupt backup suffix;
collision vs corruption; `recover_orphan_backups` resilient to OSError.

**R-17 (R3, 8 tests):** backup retained on publish failure; backup removed on
success; corrupt backup retained; cleanup only removes own run; cleanup failure
does not hide primary; final subdir never deleted; failed tracking dir retained;
F1 invariant on staging (orphan in staging → retain).

**R-13 (3 tests):** orphan backup restored on next run; recovery skips when
final already exists; recovery skips malformed inner subdir.

**Stage 6 (2 tests):** Stage 6 recorded in success result; F1 invariant end-to-end.

**Tổng:** 158 PASS, 0 FAIL, 0 SKIP (527 PASS, 1 SKIP khi tính cả DEV-02/03/04/ML-01).

**Tổng (per AGENTS.md §7 verification, khi chạy chỉ DEV-04):** 158 PASS, 0 FAIL, 0 SKIP.

---

## 4. Lint

```
$ ruff check src/customer_segmentation/prototype/clustering/ scripts/dev04_run_clustering.py tests/test_dev04_*.py tests/conftest.py
All checks passed!
```

---

## 5. Format

```
$ black --check src/customer_segmentation/prototype/clustering/ scripts/dev04_run_clustering.py tests/test_dev04_*.py tests/conftest.py
All done! ✓ 19 files would be left unchanged.
```

---

## 6. Existing test suite (regression)

| Test suite | Result |
|---|---|
| `tests/test_dev02_*.py` | 178 PASS, 0 FAIL, 0 SKIP |
| `tests/test_dev03_*.py` | 135 PASS, 1 SKIP (AC 38b OPT-IN), 0 FAIL |
| `tests/test_ml01_*.py` | 59 PASS, 0 FAIL, 0 SKIP |
| `tests/test_dev04_*.py` | 158 PASS, 0 FAIL, 0 SKIP |

**Không regression** — tất cả test suites pass.

---

## 7. Safety remediation (Phase 2 follow-up)

Phase 1 verification report đã chỉ ra 7 lỗi safety (R-15, R-17, R-13, R-16) cần khắc phục.
Phase 2 remediation đã hoàn tất:

| Mitigation | Status | Notes |
|---|---|---|
| **R-15** (R1) FAILED-run log preservation | **PASS** | `_preserve_failed_log` với `PreservationStatus ∈ {"ok", "partial", "no_log", "failed"}`; bảo toàn log trước khi xóa staging. |
| **R-15a** (F1) staging retention when preservation partial/failed | **PASS** | `_set_unpreserved_flag` set `state.unpreserved_log_in_staging`; cleanup pass skip `shutil.rmtree(staging_dir)` khi flag = True. |
| **R-16** (R2) corrupt manifest default fail-closed | **PASS** | `find_existing_clustering` raises `Dev04ManifestCorrupt`; `--force-rerun` chuyển corrupt final sang `_backup_<run_uuid>_corrupt/`; không catch `Dev04CollisionError`. |
| **R-17** (R3) top-level try/finally + cleanup invariants | **PASS** | `run_dev04` wrapped trong `try/except BaseException/finally: _cleanup_pass`; cleanup pass scope theo `current_run_uuid`; never unlink `_failed_*/`, `_backup_*_corrupt/`, hoặc `final_dir`; failure logged, primary exception re-raised. |
| **R-13** (orphan backup recovery) | **PASS** | `recover_orphan_backups` khôi phục final_dir từ orphan backup; skip `_backup_*_corrupt/`; resilient to `OSError`. |
| **Stage 6 lifecycle** | **PASS** | Stage 6 (finalize log) ghi `stage_logs.append` đầy đủ; `finalize_logging(handle)` + `psl.stage_end("6")` xuất hiện trong result. |

**Implementation fixes (code) :**

- `src/customer_segmentation/prototype/clustering/pipeline.py`:
  - `_recover_corrupt_final`: raise `Dev04StoragePathError` khi corrupt backup đã tồn tại (fail-closed; giữ nguyên final_dir để operator xử lý).
  - `run_dev04` finally: gọi `_cleanup_pass(state, primary_exc)`.
  - Stage 6: thêm `psl.stage_end("6")` + `stage_logs.append({"stage": "6", "outcome": "PASS", ...})`.

**Test fixes (test code) :**

- `tests/test_dev04_safety.py`:
  - `test_preserve_partial`: chuyển từ `chmod(0o000)` sang `patch.object(shutil, "move", _flaky_move)` (POSIX chmod không block move).
  - `test_cleanup_retains_backup_on_publish_failure`: sửa assertion (staging removed, backup retained) cho khớp contract.
  - `test_cleanup_preserves_orphan_logs`: dùng mock `shutil.move` để thực sự trigger F1 orphan path.
  - `test_corrupt_manifest_default_fail_closed`, `test_corrupt_recovery_does_not_catch_collision`: sửa path từ `tmp_path/ds_test/...` sang `prototype_clustering_base_dir(tmp_path, ...)` để khớp với `find_existing_clustering`.
  - `test_orphan_final_restored_on_next_run`: dùng clustering_id hợp lệ (`cl_[0-9a-f]{24}`) thay vì `cl_recovery_*`.
  - `test_stage_6_recorded_in_success_result`: chuyển fixture `synthetic_dev03_artefact` từ `test_dev04_pipeline.py` sang `tests/conftest.py` để cross-cutting tests có thể dùng.

**New test files (cross-cutting safety per plan §16.2) :**

- `tests/test_dev04_research_safety.py` (6 tests) — research artefacts unmodified, promotion guard.
- `tests/test_dev04_import_blocklist.py` (32 tests) — forbidden libs + forbidden subpackages, runtime + static scan.
- `tests/test_dev04_runtime_dependencies.py` (16 tests) — no new backend libs declared, no forbidden imports.

**Files changed (tổng kết remediation) :**

```
src/customer_segmentation/prototype/clustering/pipeline.py   (modified — _recover_corrupt_final, Stage 6)
tests/conftest.py                                            (new — shared fixtures)
tests/test_dev04_pipeline.py                                (modified — removed duplicated fixtures, added json import)
tests/test_dev04_safety.py                                  (modified — 6 test bug fixes)
tests/test_dev04_research_safety.py                         (new — 6 tests)
tests/test_dev04_import_blocklist.py                        (new — 32 tests)
tests/test_dev04_runtime_dependencies.py                    (new — 16 tests)
docs/system/DEV-04_completion_summary.md                     (modified — updated test counts, added §7)
```

---

## 7. Scope explicitly NOT performed

- ❌ Clustering evaluation (silhouette, DBI, CH — EPIC-08)
- ❌ Hyperparameter sweep (EPIC-07)
- ❌ Segment profiling / naming (EPIC-09 / CP-01..05)
- ❌ Visualization
- ❌ Algorithm ranking / "best/optimal/recommended" language
- ❌ Promotion to research evidence (`automatically_promoted_to_research = false` always)
- ❌ Modifying ML-01 framework (`customer_segmentation.clustering.*` — READ ONLY reuse)
- ❌ New third-party dependency
- ❌ Git operations (commit, push, PR, merge)

---

## 8. PENDING_REVIEW decisions

| ID | Decision | Status |
|---|---|---|
| DEV-04-OPEN-01 | `n_clusters=4` cho K-Means/GMM/Agglomerative/FCM; `eps=0.5`, `min_samples=5` cho DBSCAN | WORKING_ASSUMPTION |
| DEV-04-OPEN-02 | CLI `--covariance-type` chỉ gmm; `--linkage` chỉ agglomerative | WORKING_ASSUMPTION |
| DEV-04-OPEN-03 | Staging cleanup pass không xóa orphan backup của process khác | RESOLVED-IN-IMPLEMENTATION |

---

## 9. Remaining issues

| Issue | Priority | Note |
|---|---|---|
| Trạng thái là TECHNICALLY IMPLEMENTED, chưa RESEARCH_APPROVED | HIGH | Human researcher cần approve Phase 2 |
| DEV-04 plan (DEV-04_clustering_execution.md) vẫn ghi "PLAN — PHASE 1 ONLY" | MEDIUM | Cần update status sau khi human approve |
| ClusteredScope chỉ có 1 giá trị (`CLUSTERED_PROTOTYPE`) — không có `RESEARCH_APPROVED` enum | INFO | Design decision; promote via ADR, không phải enum value |

---

## 10. Acceptance criteria (6 Jira items)

| # | Jira item | DEV-04 deliverable | Status |
|---|---|---|---|
| 1 | Chọn Algorithm | `--algorithm` CLI flag; `AlgorithmRegistry` dispatch | ✅ |
| 2 | Cấu hình Parameters | `configs/dev04_clustering.yaml` + CLI overrides | ✅ |
| 3 | Run Experiment | `ExperimentRunner.run()` via pipeline | ✅ |
| 4 | Sinh Cluster Labels | `cluster_labels_*.parquet` (ML-01 artifacts) | ✅ |
| 5 | Lưu Experiment | `experiment_log_*.json` (ML-01 payload) | ✅ |
| 6 | Lưu Result | `clustering_manifest.json` + `algorithm_output_*.parquet` (nếu soft) | ✅ |
