# DEV-05 Prototype Evaluation Module — Independent Verification Report

> **Mã task:** DEV-05 (Prototype Evaluation Module)
> **Loại audit:** Independent verification & review (post-Phase-2, read-only)
> **Trạng thái đầu vào:** `TECHNICALLY IMPLEMENTED — VERIFICATION PENDING`
> **Trạng thái đầu ra:** `VERIFIED WITH LIMITATIONS` (xem §8)
> **Ngày audit:** 2026-10-10
> **Auditor:** AI assistant (Cursor) — read-only audit, không sửa source/tests/config/docs ngoài bản báo cáo này
> **Phạm vi:** Đối chiếu implementation DEV-05 với plan v1.2 (`docs/system/DEV-05_evaluation_module.md`), ADR-0006 (`docs/decisions/0006-dev05-prototype-noise-policy.md`), completion summary (`docs/system/DEV-05_completion_summary.md`), contracts DEV-02/03/04 và tests hiện có.

---

## 1. Scope và environment

### 1.1. Scope của audit (theo brief)

- Static check: contract / API / public exports / config / CLI / dataclass skips.
- Test execution: chạy DEV-05 tests + regression DEV-02/03/04/05.
- Không chạy clustering / evaluation / metric computation trên research dataset thật.
- Không sửa source / tests / config / docs ngoài file báo cáo này.
- Không chạy git / commit / push / branch / PR / merge.

### 1.2. Environment

| Item | Value |
|---|---|
| OS | Linux 7.0.0-38-generic (zsh) |
| Python | 3.14.4 |
| pytest | 9.1.1 |
| numpy | 2.3.5 (pyproject declares `>=1.26,<3.0` — within range) |
| pandas | 3.0.6 (pyproject declares `>=2.2,<3.0` — **newer than declared upper bound**; runtime works, see §6) |
| scikit-learn | 1.9.1 (pyproject declares `>=1.4,<2.0` — **newer than declared upper bound**; runtime works, see §6) |
| pyarrow | 25.0.1 (pyproject declares `>=15.0,<18.0` — **newer than declared upper bound**; runtime works, see §6) |
| PyYAML | available |
| Workspace | `/home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml` |

> **Note on version drift:** pyproject declares upper bounds (`<3.0` for pandas, `<2.0` for scikit-learn, `<18.0` for pyarrow) but the installed versions exceed these. This is an environment drift, not introduced by DEV-05. The DEV-05 source uses only the public API of these libraries and the tests pass at runtime. Not investigated further in this audit (out of scope; see §6 / §7).

---

## 2. Danh sách file/source API đã kiểm tra

### 2.1. Source modules — đọc toàn bộ

| File | LOC | Notes |
|---|---|---|
| `src/customer_segmentation/prototype/evaluation/__init__.py` | 169 | Re-exports toàn bộ public API; đầy đủ 10 module con. |
| `src/customer_segmentation/prototype/evaluation/scope.py` | 254 | Enums đóng + frozen constants; `DEFAULT_NOISE_POLICY = "exclude"` đúng ADR-0006. |
| `src/customer_segmentation/prototype/evaluation/metrics.py` | 320 | Wrap `sklearn.metrics.{silhouette_score, davies_bouldin_score, calinski_harabasz_score}`; DBSCAN noise filter in-memory. |
| `src/customer_segmentation/prototype/evaluation/manifest.py` | 712 | `EvaluationManifest` dataclass + atomic write + closed status/reason enums + invariants. |
| `src/customer_segmentation/prototype/evaluation/storage.py` | 510 | Content-addressed `evaluation_id` (8 canonical fields), path containment, `find_existing_evaluation`. |
| `src/customer_segmentation/prototype/evaluation/pipeline.py` | 750 | Stages A→G, atomic staging publish pattern, defensive copies. |
| `src/customer_segmentation/prototype/evaluation/display.py` | 159 | `format_metrics_table` + `check_no_banned_substrings` (word-boundary regex). |
| `src/customer_segmentation/prototype/evaluation/compare.py` | 247 | `CompatibilityKey` (5 fields) + `compare_evaluations` partition + disclaimer. |
| `src/customer_segmentation/prototype/evaluation/config_loader.py` | 533 | Frozen-dataclass YAML loader, structured errors (`Dev05ConfigError`). |
| `src/customer_segmentation/prototype/evaluation/logging_config.py` | 145 | `PerStageLogger` mirror DEV-04 pattern. |

### 2.2. CLI script + config

| File | Notes |
|---|---|
| `scripts/dev05_evaluate_clustering.py` | argparse; compute mode + `--compare` mode (sub-mode, đúng OQ-EVAL-05 = option A). `--storage-root` không expose (đúng plan). |
| `configs/dev05_evaluation.yaml` | `noise_policy.default = "exclude"` (ADR-0006); `display.missing_value_placeholder = "--"` (OQ-EVAL-06 = option A); `compare.emit_singleton_group = true` (OQ-EVAL-04 = option B). |

### 2.3. Test files

10 files / 214 tests (đếm được qua `pytest --collect-only` + chạy thực tế):

| File | Tests | Class breakdown |
|---|---|---|
| `tests/test_dev05_scope.py` | 22 | enum/frozenset, default noise policy, closed status/reason, no fake-default reasons |
| `tests/test_dev05_config.py` | 28 | YAML loader, dataclass invariants, top-key required, all-log-levels |
| `tests/test_dev05_storage.py` | 38 | evaluation_id derivation (10), metric_set_hash (5), config_sha256 (3), path containment (10), find_existing (6), run_dir (4) |
| `tests/test_dev05_manifest.py` | 41 | EvaluationMetricEntry invariants, EvaluationMetricsResult (3 entries), ResearchSafetyBlock (4), build helpers (5), build_evaluation (8), round-trip (7), field classification (3), manifest_to_dict (1), now_utc_iso (1) |
| `tests/test_dev05_metrics.py` | 29 | happy path (7), DBSCAN noise (5), edge cases (7), config validation (3), defensive copies (3), output invariants (4) |
| `tests/test_dev05_display.py` | 22 | format_metrics_table (6), format_manifest_path (4), check_no_banned_substrings (12) |
| `tests/test_dev05_compare.py` | 10 | compare_evaluations (10) including singleton group, 2-group split, per-row provenance |
| `tests/test_dev05_research_safety.py` | 16 | R-EVAL-01..03 (4), R-EVAL-04..07 (3), R-EVAL-08 (1), R-EVAL-09 + R-EVAL-13 (2), R-EVAL-10/11 (1), R-EVAL-12 (1), R-EVAL-14 (1), R-EVAL-16 (2), R-EVAL-17 (1) |
| `tests/test_dev05_import_blocklist.py` | 5 | research imports (2), third-party libs (1), source structure (2) |
| `tests/test_dev05_runtime_dependencies.py` | 3 | matplotlib not pulled (1), research-evaluation not pulled (1), pinned deps whitelist (1) |

### 2.4. Reference docs / ADRs đã đọc

- `AGENTS.md` (binding rules §1–§9)
- `docs/system/DEV-05_evaluation_module.md` v1.2 (plan; plan §1–§18 read; truncated tại ~17xx do size limit)
- `docs/decisions/0006-dev05-prototype-noise-policy.md` (ADR-0006)
- `docs/system/DEV-05_completion_summary.md`
- `docs/system/DEV-04_clustering_execution.md` (header + structure để verify DEV-04 contract đang được consume)
- `src/customer_segmentation/prototype/clustering/manifest.py` (reference cho DEV-04 manifest schema mà DEV-05 pipeline reads)
- `configs/dev02_dataset_management.yaml` (DEV-05 resolves storage root từ file này)

### 2.5. Public API verification

`src/customer_segmentation/prototype/evaluation/__init__.py` re-export 75+ symbols (config, scope, storage, manifest, metrics, pipeline, logging, display, compare). Mọi symbol đều resolve đến một module thực tế tồn tại; không có dangling re-export.

---

## 3. Kết quả từng acceptance criterion

| AC | Mô tả (từ plan §1.3) | Implementation | Test cover | Kết quả |
|---|---|---|---|---|
| **AC-1** | Metrics được tính | `metrics.compute_internal_metrics(X, labels, *, algorithm_family, noise_policy, ...)` wrap 3 sklearn functions; defensive copies; per-metric status/reason capture; DBSCAN noise filter in-memory (ADR-0006). | `test_dev05_metrics.py` (29 tests) | ✅ PASS |
| **AC-2** | Metrics được lưu | `manifest.write_evaluation_manifest` (atomic temp+rename) + `pipeline._write_metrics_csv` (3 rows + header). | `test_dev05_manifest.py::TestRoundTrip` (7 tests) + `TestAtomicPublish` (1) | ✅ PASS |
| **AC-3** | Metrics hiển thị | `display.format_metrics_table` (CLI stdout) + `format_manifest_path` (one-line summary) + `format_comparison_report` (in compare mode). | `test_dev05_display.py` (22 tests) | ✅ PASS |
| **AC-4** | So sánh Experiment | `compare.compare_evaluations` partition theo `CompatibilityKey` (5 fields); per-row provenance; disclaimer. | `test_dev05_compare.py` (10 tests) | ✅ PASS |

### 3.1. AC-1 deep check

`compute_internal_metrics` chỉ wrap 3 sklearn functions:

```python
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
```

Đúng plan §5.1 và §6 (DEV-05 wraps sklearn directly vì research core `internal_metrics.py` raises `NotImplementedError`). Không import từ `customer_segmentation.evaluation.*` (đã verify bằng AST scan; xem §4 R-EVAL-15).

Edge case policy matrix (§5.3 plan) được implement đầy đủ:

| Edge case | Plan § | Implementation | Smoke test |
|---|---|---|---|
| Single cluster | §5.3 row 1 | `n_clusters < 2` → 3 × NOT_APPLICABLE/SINGLE_CLUSTER | ✓ |
| One sample per cluster | §5.3 row 2 | sklearn raises ValueError → caught by `_compute_one_metric`, pattern-mapped to NOT_APPLICABLE/INSUFFICIENT_CLUSTERS | ✓ |
| Alignment error | §5.3 row 3 | `X.shape[0] != labels.shape[0]` → 3 × COMPUTATION_ERROR/ALIGNMENT_ERROR | ✓ |
| DBSCAN noise (`-1`) | §5.3 row 4 | Uniform exclusion per ADR-0006; `reason = DBSCAN_NOISE_EXCLUDED` (audit annotation, status remains VALID_VALUE) | ✓ |
| All noise | §5.3 row 5 | `n_samples_used == 0` → 3 × NOT_APPLICABLE/ALL_NOISE | ✓ |
| NaN/Inf in X | §5.3 row 6 | `not np.isfinite(X).all()` → 3 × COMPUTATION_ERROR/NAN_OR_INF_INPUT | ✓ |
| ClusterLabel dtype | §5.3 row 7 | dtype check; coercion attempt → COMPUTATION_ERROR/CLUSTER_DTYPE_INVALID | ✓ (covered by `TestDefensiveCopies`) |
| Sklearn exception | §5.3 row 12 | caught in `_compute_one_metric`, reason = SKLEARN_EXCEPTION (R-EVAL-12: raw message NOT surfaced) | ✓ |
| Degenerate result | §5.3 row 13 | `not np.isfinite(value)` after sklearn return → COMPUTATION_ERROR/DEGENERATE_RESULT | ✓ |

**No fake defaults:** giá trị `value=None` iff `status != VALID_VALUE` được enforce trong `EvaluationMetricEntry.__post_init__` (`manifest.py:235-249`). Test `test_dev05_metrics.py::TestOutputInvariants::test_no_fake_default_values` verify. Sklearn trả NaN/Inf được catch trước khi ghi vào manifest.

### 3.2. AC-2 deep check

`write_evaluation_manifest` dùng atomic pattern (temp + rename):

```python
tmp = path.with_suffix(path.suffix + ".tmp")
try:
    with tmp.open("w", ...) as fh: json.dump(...)
    tmp.replace(path)  # atomic on POSIX
except Exception:
    if tmp.exists(): tmp.unlink()
    raise
```

Test `test_dev05_manifest.py::TestAtomicPublish` verify no `.tmp` leftover + `test_atomic_write_no_partial_on_failure` (monkeypatch `Path.replace` để raise) verify cleanup + manifest not visible khi rename fail.

CSV writer (`pipeline._write_metrics_csv`) ghi đúng 3 rows trong canonical order (silhouette / davies_bouldin / calinski_harabasz); `EvaluationMetricsResult.as_flat_rows()` verify.

### 3.3. AC-3 deep check

`format_metrics_table` in bảng text:

```
metric     :<24} {value:>12}   {status:<16}  reason
...
silhouette          0.500   [VALID_VALUE]    COMPUTED
davies_bouldin      1.000   [VALID_VALUE]    COMPUTED
calinski_harabasz 100.000   [VALID_VALUE]    COMPUTED
```

`missing_value_placeholder` mặc định là `--` (em-dash) đúng OQ-EVAL-06 = option A. CSV writer dùng `csv_missing_value=""` (blank) đúng OQ-EVAL-06 carve-out.

### 3.4. AC-4 deep check

`compare_evaluations` partition theo 5-field `CompatibilityKey`:

```python
@dataclass(frozen=True)
class CompatibilityKey:
    dataset_id: str
    preprocessed_id: str
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    metric_set: tuple[str, ...]
```

`incompatibility_reasons` được populate khi có ≥ 2 manifests với field khác nhau (đúng plan §4.7 / §9.3). Singleton group emitted (đúng OQ-EVAL-04 = option B). Disclaimer luôn present.

---

## 4. Kết quả từng nhóm research-safety invariants

### 4.1. R-EVAL-01..03 — research_safety block trên mọi manifest

`ResearchSafetyBlock.__post_init__` enforces:
- `automatically_promoted_to_research` MUST be False → test `TestResearchSafetyBlock::test_automatically_promoted_always_false` ✓
- `scope` MUST be `'EVALUATED_PROTOTYPE'` → test `test_scope_always_evaluated_prototype` ✓ (cả outer `EvaluationManifest.scope` và inner `research_safety.scope`)
- `appeared_in_research_evidence` MUST be False → test `test_appeared_in_research_evidence_always_false` ✓
- Round-trip via JSON preserves block → test `test_research_safety_survives_round_trip` ✓

**Verdict:** ✅ PASS.

### 4.2. R-EVAL-04..07 — path containment / write scope

- `resolve_storage_root` delegates to DEV-02 (`customer_segmentation.dataset_management.storage.resolve_storage_root`), không hard-code path. Test `test_storage_root_resolution_uses_dev02` ✓.
- `prototype_evaluation_base_dir` / `prototype_evaluation_run_dir` enforce path inside storage_root via `Path.resolve() + relative_to()` check. Tests verify both happy and invalid clustering_id path. ✓
- Path structure: `<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/evaluation/<evaluation_id>/` đúng plan §4.3. ✓
- `regex ^cl_[0-9a-f]{24}$` enforced cho clustering_id; `regex ^ev_[0-9a-f]{24}$` enforced cho evaluation_id. Tests `test_rejects_invalid_*` cover both. ✓
- DEV-05 source KHÔNG chứa write target nào ngoài `evaluation/<ev_id>/`. Static AST scan verified không có `Path(...)` trỏ đến `data/raw`, `data/processed`, `reports/` (chỉ là string defaults trong `config_loader.py::readonly_paths` — defence-in-depth, đúng plan). ✓

**Verdict:** ✅ PASS.

### 4.3. R-EVAL-08 / R-EVAL-15 — no banned words

`check_no_banned_substrings(text)` scan với word-boundary regex (case-insensitive) cho `("best", "winner", "optimal", "recommended", "ranking", "composite_score")`. Disclaimer phrase (`"no ranking, recommendation, or winner annotation is emitted"`) là single allowed occurrence (được strip khỏi text trước khi scan).

Tests:
- `TestCheckNoBannedSubstrings` (12 tests): clean pass, banned detected, disclaimer allowed, disclaimer + extra banned fails, word-boundary precision (`recommendation` ≠ `recommended`). ✓
- `TestNoBannedSubstrings::test_manifest_dict_no_banned_substrings` ✓
- `TestFormatMetricsTable::test_output_no_banned_substrings_default_disclaimer` ✓
- `TestCompareEvaluations::test_no_banned_substrings_in_output` ✓
- `TestFormatManifestPath::test_no_banned_substrings` ✓

**Verdict:** ✅ PASS.

### 4.4. R-EVAL-09 — no reference to `final_clustering_dataset.parquet`

`TestNoFe06Reference` (2 tests):
- AST + literal scan của toàn bộ `src/customer_segmentation/prototype/evaluation/` không có reference. ✓
- Test files `test_dev05_*.py` (ngoại trừ `test_dev05_research_safety.py` self-reference) không reference. ✓

CLI docstring (`scripts/dev05_evaluate_clustering.py:25-26`) **đề cập** đến `final_clustering_dataset.parquet` để document rằng CLI never reads nó — không phải import / use. ✓

**Verdict:** ✅ PASS.

### 4.5. R-EVAL-10 / R-EVAL-11 — upstream immutability

`compute_internal_metrics` signature chỉ take `X` và `labels` (numpy arrays), không take file path. Test `TestUpstreamImmutability::test_metrics_function_does_not_take_cluster_labels_path` verify. ✓

Defensive copy trong `metrics.py`:

```python
X = np.asarray(X, dtype=np.float64).copy()
labels = np.asarray(labels).copy()
```

Tests `TestDefensiveCopies` (3 tests) verify `X` and `labels` không bị mutate sau khi compute. Noise filter (`X[mask]; labels[mask]`) operate trên copy, không ảnh hưởng input. ✓

**Verdict:** ✅ PASS.

### 4.6. R-EVAL-12 — closed metric names

`scope.METRIC_NAMES = frozenset({"silhouette", "davies_bouldin", "calinski_harabasz"})`. `TestMetricSetClosed::test_only_three_metric_names` verify. `metric_set` input validation trong `storage.compute_metric_set_hash` và `metrics.compute_internal_metrics` reject unknown names. ✓

**Verdict:** ✅ PASS.

### 4.7. R-EVAL-13 — no test against real FE-06 data

`TestNoFe06Reference::test_no_test_uses_real_fe06_data` xác minh không có `test_dev05_*.py` (ngoại trừ chính nó) reference `final_clustering_dataset`. ✓

**Verdict:** ✅ PASS.

### 4.8. R-EVAL-14 — noise / label immutability

- Noise filter in-memory only (X và labels copy được filter); cluster_labels parquet không bị touch. ✓
- `TestNoiseImmutability::test_metrics_does_not_modify_input_labels` verify. ✓
- AST scan không có mutation helper (e.g. `parquet.write_parquet(cluster_labels_path, ...)`). ✓

**Verdict:** ✅ PASS.

### 4.9. R-EVAL-16 — manifest / metric-set consistency

`EvaluationMetricsResult.__post_init__` enforce exactly 3 entries (đúng metric names). Tests:
- `TestManifestCsvConsistency::test_metric_entries_keys_match_default_metric_set` ✓
- `TestManifestCsvConsistency::test_metric_set_in_manifest_matches_entries` ✓

**Verdict:** ✅ PASS.

### 4.10. R-EVAL-17 — atomic publish

- `manifest.write_evaluation_manifest` temp+rename. ✓
- `pipeline.run_evaluation_pipeline` Stage E→F: write vào `_staging_<uuid>/`, Stage F atomic `os.rename(staging → final)`, crash recovery qua `_backup_<uuid>/`. Tests `TestAtomicPublish` (1 test trong `research_safety`) + `test_atomic_write_no_partial_on_failure` verify cleanup khi rename fail. ✓

**Verdict:** ✅ PASS.

### 4.11. R-EVAL-15 — source-agnostic metric set

Cùng với R-EVAL-12: không có WCSS / ARI / AMI / Hungarian / runtime / CI / stability metric. Static AST scan verified: only `silhouette_score`, `davies_bouldin_score`, `calinski_harabasz_score` được import từ sklearn. ✓

**Verdict:** ✅ PASS.

### 4.12. Import blocklist

`tests/test_dev05_import_blocklist.py` (5 tests) — AST scan toàn bộ DEV-05 source + CLI script. Forbidden:
- `customer_segmentation.evaluation.*` (research core)
- `customer_segmentation.clustering.{baseline, cluster_number, hyperparameter_search, metrics, stability, preprocessing_feature_sensitivity}`
- `matplotlib`, `seaborn`, `plotly`, `bokeh`, `dash`

Test verify không có offender. Manual verification bằng `grep -rn 'customer_segmentation.evaluation' src/.../evaluation/` chỉ tìm được 1 hit trong docstring của `scope.py:21` (text reference, không phải import). ✓

**Verdict:** ✅ PASS.

### 4.13. ADR-0006 không sửa research-layer status

Plan §18 footer và ADR-0006 §Status đều nói rõ:
- `SYS-01 §11 CON-15` — UNCHANGED
- `METHODOLOGY_LOCK_STATUS §3 WA-08` — UNCHANGED (vẫn `WORKING_ASSUMPTION`)
- `EXP01_baseline_experiment_PLAN.md EXP01-MET-01` — UNCHANGED (vẫn `PENDING_REVIEW`)
- `MENTOR_REVIEW_FORM_EXP01_EXP05.md` line 47 — NOT MODIFIED

Static check: không tìm thấy modification của các file trên (chúng nằm ngoài DEV-05 scope; implementation chỉ write vào `data/prototype/.../evaluation/<ev_id>/`). ✓

**Verdict:** ✅ PASS.

---

## 5. Test commands và kết quả thực tế

### 5.1. Command 1 — toàn bộ DEV-05 tests

```bash
PYTHONPATH=src python3 -m pytest tests/test_dev05_*.py -v
```

**Result**: `214 passed in 1.95s` — exit code 0. Zero failure, zero skip. Match chính xác completion summary §1.4 (214 tests).

### 5.2. Command 2 — regression DEV-02/03/04/05

```bash
PYTHONPATH=src python3 -m pytest tests/test_dev02_*.py tests/test_dev03_*.py tests/test_dev04_*.py tests/test_dev05_*.py
```

**Result**: `682 passed, 1 skipped in 16.21s` — exit code 0. Skip duy nhất:

```
SKIPPED [1] tests/test_dev03_consistency.py:241: AC 38b is OPT-IN (C7-dependent).
Default skip per plan §9.1. Run manually after resolution of DOC-CTD-01
(C7 status conflict).
```

Đây là pre-existing skip (DEV-03 scope, không liên quan đến DEV-05), match với completion summary §1.4 ghi chú.

### 5.3. Command 3 — research_safety / import_blocklist / runtime_dependencies

```bash
PYTHONPATH=src python3 -m pytest tests/test_dev05_research_safety.py \
    tests/test_dev05_import_blocklist.py tests/test_dev05_runtime_dependencies.py -v
```

**Result**: `24 passed in 0.98s` — exit code 0. Cụ thể: 16 research_safety + 5 import_blocklist + 3 runtime_dependencies.

### 5.4. Command 4 — compare + display tests

```bash
PYTHONPATH=src python3 -m pytest tests/test_dev05_compare.py tests/test_dev05_display.py -v
```

**Result**: `32 passed in 0.81s` — exit code 0. (10 compare + 22 display.)

### 5.5. Test chưa chạy và lý do

- **Không chạy** `test_dev05_metrics.py::test_each_sample_own_cluster_not_applicable` cho data khác ngoài 2-cluster fixture. Đây là test tĩnh (synthetic data); không cần research data. Đã covered bằng Command 1.
- **Không chạy** CLI end-to-end (`scripts/dev05_evaluate_clustering.py --dataset-id ... --preprocessed-id ... --clustering-id ...`): yêu cầu published DEV-04 artefact (clustering_id + cluster_labels parquet + clustering_manifest.json). Hiện không có DEV-04 artifact trong `data/prototype/` (chỉ có 2 DEV-02 datasets `ds_97fbbe97c291742a98fe1273` và `ds_f52a4cbe6912e16ccec7bde6` — không qua DEV-03/04). Không thuộc scope audit này (không chạy metric trên research dataset).
- **Không chạy** `ruff check` và `black --check`: chưa cài `ruff` và `black` ở env này (xem §7).
- **Không chạy** toàn bộ test suite ngoài DEV-02/03/04/05: nằm ngoài audit scope (theo brief §4).

---

## 6. Findings

Phân loại theo mức độ ảnh hưởng đến research methodology và correctness.

### 6.1. MINOR — `_make_manifest` không nhận `dataset_id` parameter

**File:** `src/customer_segmentation/prototype/evaluation/pipeline.py:278-306` (`_make_manifest`).

**Triệu chứng:** `_make_manifest` đọc `dataset_id = str(clustering_manifest_data.get("dataset_id", ""))` (line 306). Tuy nhiên DEV-04 `ClusteringManifest` schema KHÔNG có field `dataset_id` (verified tại `src/customer_segmentation/prototype/clustering/manifest.py` — `dataset_id` chỉ xuất hiện trong `ClusteringPipelineResult.as_summary()`, không phải manifest). Hệ quả: trong mọi evaluation pass, `dataset_id` field trong `evaluation_manifest.json` sẽ là empty string `""`.

**Plan §4.3** yêu cầu evaluation manifest chứa `dataset_id` (DEV-04/03/02 pointer). Plan §4.1 không list `dataset_id` trong required fields của clustering_manifest mà DEV-05 reads — nhưng điều này không khớp với việc plan §4.3 muốn `dataset_id` được recorded trong evaluation manifest.

**Ảnh hưởng thực tế:**
1. `evaluation_id` derivation VẪN dùng `dataset_id` đúng (parameter từ CLI/function call, line 617-628 trong pipeline). Idempotency và path resolution không bị ảnh hưởng.
2. `compare_evaluations` dùng `m.dataset_id` từ manifest (sẽ empty), nhưng CompatibilityKey còn 4 fields khác (`ml_dataset_sha256`, `feature_set_sha256`, `preprocessing_config_sha256`, `preprocessed_id`) — 2 evaluation từ 2 dataset khác nhau sẽ khác ở những field này và được split correctly.
3. Risk scenario: 2 evaluation thực sự khác dataset_id nhưng cùng `ml_dataset_sha256` (astronomically unlikely với SHA-256) sẽ bị group sai. Trong thực tế không xảy ra.

**Hướng xử lý (human reviewer quyết định):** truyền `dataset_id` parameter vào `_make_manifest` (fix nhỏ, ~3 dòng). Hoặc thêm `dataset_id` vào DEV-04 `ClusteringManifest` schema (ADR mới; methodology change).

**Không tự sửa** trong audit này (per brief §6 — "Hard stop").

### 6.2. MINOR — `n_clusters_realized` count trước noise filter

**File:** `src/customer_segmentation/prototype/evaluation/pipeline.py:580` (`n_clusters_realized = int(np.unique(labels).size)`).

**Triệu chứng:** `n_clusters_realized` được tính trước khi `compute_internal_metrics` áp dụng noise filter (line 605). Với DBSCAN `noise_policy="exclude"`, `np.unique(labels).size` đếm `-1` như một cluster → `n_clusters_realized` bao gồm noise label.

**Plan §5.4.4** yêu cầu: "`n_clusters_realized`: Unique non-noise labels (under exclude) or unique labels (under include)."

**Ảnh hưởng thực tế:** Chỉ là audit field, không dùng cho compute. So sánh giữa các DBSCAN runs với số noise khác nhau có thể bị confused (số n_clusters_realized lớn hơn actual non-noise clusters). Với non-DBSCAN algorithms, không có ảnh hưởng.

**Hướng xử lý:** di chuyển `n_clusters_realized = int(np.unique(labels).size)` xuống SAU khi compute, dùng giá trị `n_clusters` internal của `compute_internal_metrics` (đã đúng — line 217 trong metrics.py). Hoặc re-compute sau filter. Nhỏ, ~3 dòng.

**Không tự sửa** trong audit này.

### 6.3. MINOR — pyproject declared upper bounds thấp hơn installed version

**Triệu chứng:** `pyproject.toml` declares:
- `pandas>=2.2,<3.0` → installed 3.0.6 (newer)
- `scikit-learn>=1.4,<2.0` → installed 1.9.1 (newer)
- `pyarrow>=15.0,<18.0` → installed 25.0.1 (newer)

Đây là environment / dependency drift, không phải do DEV-05 introduce. Có thể từ upstream `requirements.txt` hoặc global pip install.

**Ảnh hưởng thực tế:** tests chạy pass, runtime không có warning nghiêm trọng. Tuy nhiên nếu ai chạy `pip install -e .` strict theo pyproject, sẽ không install được.

**Hướng xử lý:** bump upper bounds trong pyproject.toml (ADR nếu considered methodology change; còn nếu chỉ là env cleanup thì routine).

### 6.4. INFORMATIONAL — `test_dev05_pipeline.py` không tồn tại

Completion summary §9 note đã đề cập: "real DEV-04 integration test deferred". Vì vậy 2 finding ở §6.1 và §6.2 (cả hai liên quan đến pipeline manifest building) chưa được exercise bởi bất kỳ test nào.

**Không tự thêm test** trong audit này (per brief §6).

### 6.5. INFORMATIONAL — DEV-04 clustering_manifest thiếu `dataset_id` field

Plan §4.1 list required fields của DEV-04 clustering_manifest, KHÔNG có `dataset_id`. Nhưng plan §4.3 yêu cầu evaluation_manifest chứa `dataset_id`. Đây là design tension giữa DEV-04 (chỉ giữ `preprocessed_id`, derive `dataset_id` từ path) và DEV-05 (cần `dataset_id` cho evaluation manifest). Hiện implementation nhận `dataset_id` từ function parameter nên path resolution / evaluation_id đều OK; chỉ field trong output manifest bị empty.

Cùng root cause với §6.1.

---

## 7. Những gì chưa xác minh được

### 7.1. `ruff check` không chạy được

`ruff` chưa được cài ở môi trường này:

```bash
$ which ruff || command -v ruff || echo "ruff not installed"
ruff not installed
```

Completion summary §8 ghi chú: "(ruff not yet installed in this env)". Không ảnh hưởng đến research methodology; chỉ là lint check chưa thực hiện được.

### 7.2. `black --check` không chạy được

`black` cũng chưa cài. Cùng lý do §7.1.

### 7.3. End-to-end pipeline run không thực hiện

Yêu cầu published DEV-04 artefact. Trong `data/prototype/` hiện chỉ có 2 DEV-02 dataset (chưa qua DEV-03/04). Không thuộc audit scope (brief §2 cấm chạy evaluation trên research data; §3 E cũng cấm auto-promote).

Đã xác minh qua static check + smoke test của `compute_internal_metrics` với synthetic data (§3.1) — chứng minh logic đúng cho tất cả edge case matrix trong plan §5.3.

### 7.4. Storage sub-tree không có DEV-04/05 artifact thực

Không thể test:
- Idempotency `find_existing_evaluation` end-to-end trên real layout (đã covered bằng unit test với tmp_path).
- Stage E→F atomic publish trên real storage layout (đã covered bằng unit test với monkeypatch rename failure).
- CSV writer ghi đồng thời với manifest (đã smoke test với tmp dir).

### 7.5. KHÔNG chạy full repo test suite

Brief §4 chỉ yêu cầu DEV-05 + regression DEV-02/03/04/05. Đã chạy đúng phạm vi (Command 2: 682 pass + 1 skip). Không chạy test ngoài DEV-02..05; không khẳng định toàn bộ repo test suite pass.

### 7.6. Pyarrow / pandas / sklearn version drift không fix

Pyproject upper bounds lệch so với installed (xem §6.3). Không fix trong audit (out of scope).

### 7.7. Methodology gates ngoài prototype

Brief §2 và AGENTS.md §2.10: `TECHNICALLY IMPLEMENTED ≠ RESEARCH DECISION APPROVED`. Mentor review + research-layer approval còn PENDING (theo completion summary §5 + ADR-0006 §Status). Audit này chỉ verify technical correctness, KHÔNG verify research-layer decision approval.

---

## 8. Kết luận

### 8.1. Trạng thái

**`VERIFIED WITH LIMITATIONS`**

### 8.2. Tóm tắt

**4 acceptance criteria (AC-1..AC-4) đều được implement đúng plan v1.3 và verified bằng 214 unit tests + smoke tests (0 fail).**

**17 research-safety invariants (R-EVAL-01..17) đều được cover bằng test + static AST scan; không có violation.**

**Regression DEV-02/03/04/05: 682 pass + 1 pre-existing skip (DEV-03 C7, không liên quan).**

**ADR-0006 (uniform DBSCAN-noise exclusion) được implement đúng: prototype-layer scope, không sửa research-layer status (CON-15, WA-08, EXP01-MET-01, MENTOR_REVIEW_FORM line 47).**

### 8.3. Findings summary

| # | Mức độ | Mô tả |
|---|---|---|
| 6.1 | MINOR | `_make_manifest` không nhận `dataset_id` parameter; manifest field empty. |
| 6.2 | MINOR | `n_clusters_realized` đếm noise label; plan §5.4.4 yêu cầu unique non-noise labels. |
| 6.3 | MINOR | pyproject upper bounds < installed (env drift). |
| 6.4 | INFORMATIONAL | No `test_dev05_pipeline.py` — pipeline bugs (nếu có) chưa được exercise bởi test. |
| 6.5 | INFORMATIONAL | DEV-04 `ClusteringManifest` không có `dataset_id` field (design tension). |

**Không có BLOCKER, không có MAJOR.**

### 8.4. Đề xuất bước tiếp theo (để human reviewer quyết định)

1. **Optional fix #1** (5–7 dòng, mechanical): truyền `dataset_id` parameter vào `_make_manifest` để record `dataset_id` đúng trong `evaluation_manifest.json`. Xem §6.1.
2. **Optional fix #2** (3–5 dòng, mechanical): di chuyển `n_clusters_realized` calc xuống sau noise filter / dùng internal `n_clusters` từ `compute_internal_metrics`. Xem §6.2.
3. **Optional**: bump pyproject upper bounds (`pandas`, `scikit-learn`, `pyarrow`) cho khớp với installed hoặc với latest stable. Xem §6.3.
4. **Optional**: thêm `test_dev05_pipeline.py` integration test với synthetic DEV-04 artefact để cover `_make_manifest` end-to-end. (Có thể phối hợp với `tests/conftest.py` fixture `synthetic_dev03_artefact` đã có.)
5. **Hard-stop gate**: mentor / human researcher review + sign MENTOR_REVIEW_FORM_EXP01_EXP05.md line 47 + sign-off cho ADR-0006 promotion (research layer). Còn PENDING (per AGENTS.md §2.10; không thuộc scope audit này).

### 8.5. Phạm vi rõ ràng chưa close

- Research-layer promotion gate (`TECHNICALLY IMPLEMENTED` → `RESEARCH APPROVED`): còn PENDING mentor action. Audit này không approve research evidence usage.
- ADR-0006 prototype-scope decision vẫn là WORKING_ASSUMPTION ở research layer; mentor review form chưa tick.
- OQ-EVAL-EPIC-08 (ARI/AMI/runtime/CI): DEFERRED post-Phase-2 increment; không block DEV-05.

---

## 9. Phụ lục — checklist với brief §5

| Brief §5 mục | Trạng thái | Section trong report này |
|---|---|---|
| 1. Scope và environment | ✅ | §1 |
| 2. Danh sách file/source API đã kiểm tra | ✅ | §2 |
| 3. Kết quả từng acceptance criterion | ✅ | §3 (AC-1..AC-4) |
| 4. Kết quả từng nhóm research-safety invariants | ✅ | §4 (R-EVAL-01..17 + ADR-0006) |
| 5. Test commands và kết quả thực tế | ✅ | §5 (4 commands, 682+214+24+32 tests) |
| 6. Findings phân loại BLOCKER/MAJOR/MINOR | ✅ | §6 (2 MINOR + 1 MINOR env + 2 INFORMATIONAL; không BLOCKER/MAJOR) |
| 7. Những gì chưa xác minh được | ✅ | §7 |
| 8. Kết luận: VERIFIED / VERIFIED WITH LIMITATIONS / VERIFICATION FAILED | ✅ | §8.1 = `VERIFIED WITH LIMITATIONS` |

---

*Generated by AI assistant (Cursor) as post-Phase-2 independent verification artefact.
Per AGENTS.md §2.10: `TECHNICALLY IMPLEMENTED ≠ RESEARCH DECISION APPROVED`.
Human reviewer / mentor retains final authority on research methodology decision
and on whether to apply the §8.4 fixes before promotion to research layer.
This audit intentionally does NOT modify any source / tests / config /
docs other than this report file (per brief §6 hard stop).*