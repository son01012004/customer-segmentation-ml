# DEV-05 — Final Technical Review Report (Post-Remediation)

> **Mã task:** DEV-05 Final Technical Review
> **Trạng thái đầu vào:** `MINOR FINDINGS ADDRESSED — awaiting human reviewer`
>   (`docs/system/DEV-05_remediation_report.md`, ngày 2026-10-10)
> **Trạng thái đầu ra:** `READY WITH ACCEPTED LIMITATIONS`
> **Loại artefact:** Final technical review (BỔ SUNG; không sửa verification
> report cũ, không sửa remediation report).
> **Ngày review:** 2026-10-10
> **Phạm vi review:** Đối chiếu hai MINOR findings F1 (`_make_manifest.dataset_id`)
> và F2 (`n_clusters_realized` semantics) đã được remediation xử lý, kiểm tra
> phạm vi thay đổi, chất lượng test, không tự mở rộng scope.

> **CRITICAL DISCLAIMER (AGENTS.md §2.10):** Trạng thái DEV-05 ở mọi mốc
> đều là `TECHNICALLY IMPLEMENTED` — KHÔNG đồng nghĩa `RESEARCH DECISION
> APPROVED`. Mentor / human researcher gate còn PENDING.

---

## 1. Scope của review

Review chỉ kiểm tra:

- F1 + F2 đã được remediation xử lý đúng plan v1.2 + ADR-0006 hay chưa.
- Phạm vi thay đổi có giới hạn đúng 3 file (2 modified/added bởi remediation
  + 1 report mới) hay không.
- Tests mới có meaningful assertions.
- Không có methodology change, không có Git operations, không có scope
  expansion.

Review KHÔNG chạy lại toàn bộ evaluation suite đã chạy trong verification
report; chỉ rerun targeted synthetic-data tests theo brief.

---

## 2. Review checklist kết quả

### 2.1. Phạm vi thay đổi

| File | Loại thay đổi | Trạng thái Git | Có thuộc remediation không? |
|---|---|---|---|
| `src/customer_segmentation/prototype/evaluation/pipeline.py` | Modify (F1 + F2) | `??` (untracked) | ✅ — thuộc remediation |
| `tests/test_dev05_pipeline_helpers.py` | Add (15 tests mới) | `??` (untracked) | ✅ — thuộc remediation |
| `docs/system/DEV-05_remediation_report.md` | Add (báo cáo) | `??` (untracked) | ✅ — báo cáo remediation |

Tất cả 3 file là `untracked` (`??`); không file nào `M` (modified) hoặc
`A` (staged) do agent này. Có 4 file tracked bị modified (`M .gitignore`,
`M docs/system/SYS-01_requirements.md`, `M docs/system/SYS-05_api_design.md`,
`M pyproject.toml`) nhưng đây là pre-existing snapshot từ trước remediation
(đã hiển thị trong initial git status khi bắt đầu conversation) — nằm
ngoài phạm vi DEV-05.

**`git diff HEAD` cho 3 file remediation:** rỗng (vì cả 3 untracked).
**`git diff HEAD` cho ADR-0006 / plan v1.2 / verification report / pyproject.toml
/ DEV-02/03/04 source:** rỗng (không thay đổi).

**Verdict:** ✅ Phạm vi giới hạn đúng, không có out-of-scope modification.

### 2.2. F1 — `_make_manifest.dataset_id` propagation

**Đã verify:**

1. `_make_manifest` nhận `dataset_id: str` thành parameter keyword-only
   (bắt buộc). Source inspection xác nhận:
   ```python
   def _make_manifest(
       *,
       evaluation_id: str,
       dataset_id: str,                  # ← caller-supplied
       clustering_id: str,
       clustering_manifest_data: dict[str, Any],
       ...
   ):
       ...
       # dataset_id is supplied by the caller (DEV-04 manifest does not
       # contain it; per plan §4.1 it is not a required field of the
       # clustering_manifest_data). Do NOT re-derive it from
       # clustering_manifest_data — that would yield an empty string for
       # every valid DEV-04 run.
       dataset_id_str = str(dataset_id)
   ```
   Comment trong source ghi rõ không re-derive từ `clustering_manifest_data`.

2. Call site trong `run_evaluation_pipeline` (line 730-732) truyền
   `dataset_id=dataset_id` — đây là function input parameter (đã validated
   ở Stage A trước khi gọi), không phải field từ clustering manifest:
   ```python
   manifest = _make_manifest(
       evaluation_id=evaluation_id,
       dataset_id=dataset_id,        # ← pipeline function input
       clustering_id=clustering_id,
       clustering_manifest_data=clustering_manifest_data,
       ...
   )
   ```

3. Persistence: `dataset_id_str` được truyền vào `build_evaluation_manifest`
   với `dataset_id=dataset_id_str` → `EvaluationManifest.dataset_id` →
   `manifest_to_dict(...)` → atomic write JSON → `read_evaluation_manifest`
   trong test round-trip khôi phục đúng giá trị. Source confirmed (lines
   376, 605, 706-820 trong `manifest.py`).

4. CLI consistency: `scripts/dev05_evaluate_clustering.py` line 203-209
   truyền `dataset_id=args.dataset_id` (đã required-validate ở line 189-194)
   xuống `run_evaluation_pipeline`. CLI đã luôn truyền `dataset_id` từ
   trước remediation — bug chỉ nằm ở `_make_manifest` không đọc nó. F1 fix
   sửa đúng chỗ.

**Verdict:** ✅ F1 fix đúng scope, đúng semantics, không mở rộng thay đổi.

### 2.3. F2 — `n_clusters_realized` semantics

**Đã verify:**

1. Helper `_compute_n_clusters_realized` ở `pipeline.py:274-308` có docstring
   liệt kê rõ 3 case:
   - non-density → count all unique labels (bất kể policy).
   - density + `exclude` → count unique non-noise labels.
   - density + `include` → count unique labels including `-1`.

2. Implementation:
   ```python
   if is_density_based and noise_policy == "exclude":
       non_noise_mask = labels != noise_label
       if not non_noise_mask.any():
           return 0
       return int(np.unique(labels[non_noise_mask]).size)
   return int(np.unique(labels).size)
   ```
   - `non_noise_mask` là boolean indexing tạo view tạm — không in-place.
   - All-noise (`not non_noise_mask.any()`) trả 0 (count thực của empty
     filtered set, đúng plan §5.5 rule 2: `0` ở đây không phải fake
     placeholder mà là count thực).
   - Fall-through: non-density hoặc density+include → `np.unique(labels).size`.

3. Call site ở `pipeline.py:658-662` đặt SAU khi `is_density_based` được
   tính, SAU khi `labels` được resolve, SAU khi `noise_count`/`noise_ratio`
   được compute, TRƯỚC khi gọi `compute_internal_metrics`:
   ```python
   n_clusters_realized = _compute_n_clusters_realized(
       labels=labels,
       noise_label=DBSCAN_NOISE_LABEL,
       is_density_based=is_density_based,
       noise_policy=effective_noise_policy,
   )
   ```
   Đúng plan §5.4.4 — order quan trọng vì nếu tính trước noise filter
   decision, `n_clusters_realized` không khớp với data actually passed to
   sklearn.

4. `effective_noise_policy` resolve đúng: `noise_policy or config.noise_policy.default`
   (line ~510). Default từ config là `"exclude"` (ADR-0006).

5. Metric validity: `compute_internal_metrics` (gọi ở line ~670) đã tự apply
   noise filter in-memory trên `X[mask]; labels[mask]` (đã covered bởi
   `test_dev05_metrics.py::TestDBSCANNoise::test_exclude_applied_uniformly_to_three_metrics`,
   PASSED). Helper `_compute_n_clusters_realized` chỉ compute count, không
   compute metric — không tạo giá trị giả, không duplicate logic.

6. All-noise under exclude: `n_samples_used_for_compute = n_samples_input -
   noise_count = 0`; metrics ở `TestDBSCANNoise::test_all_noise_returns_not_applicable`
   (PASSED) trả 3× `NOT_APPLICABLE/ALL_NOISE`. `n_clusters_realized=0` là
   count thực của empty filtered set — khớp với manifest field
   `n_samples_used_for_compute=0` và `metric_status=NOT_APPLICABLE`.

**Verdict:** ✅ F2 fix đúng scope, đúng semantics ADR-0006, không tạo
fake default, không suy metric validity.

### 2.4. Evaluation ID derivation

`derive_evaluation_id` (line 689) signature không thay đổi; 8 canonical
fields (clustering_id, preprocessed_id, dataset_id, ml_dataset_sha256,
config_sha256, noise_policy, metric_set_hash, schema_version) preserved.
`dataset_id` từ caller vẫn là 1 trong 8 field — không tạo collision
với evaluation_id derivation trước đây (cũng dùng dataset_id từ caller).

`canonical_expected` dict (line 695) cũng dùng `dataset_id` từ caller.
Idempotency semantics không thay đổi.

**Verdict:** ✅ Evaluation ID derivation không thay đổi, không có regression.

### 2.5. Tests — meaningful assertions

| Test class | # tests | Assertion nature |
|---|---|---|
| `TestMakeManifestDatasetId` | 4 | (a) record từ input, (b) non-empty sau fix, (c) round-trip qua JSON, (d) caller wins khi stray key có trong dict. Tất cả assert trên observable manifest field, không mock private state. |
| `TestComputeNClustersRealized` | 10 | Cover full 3-case matrix: non-density (2 policy, 1 single-cluster), density+exclude (4 case: có noise, all-noise, single non-noise, no noise), density+include (2 case: -1 as cluster, all-noise), immutability, no-fake-default. |
| `TestF1F2Integration` | 1 | Build manifest via `_make_manifest` với DBSCAN synthetic data (4 noise + 2 clusters of 4) → write → read → assert đủ 8 field (`dataset_id`, `n_clusters_realized`, `n_samples_input`, `n_samples_used_for_compute`, `noise_count`, `noise_ratio`, `algorithm_family`, `noise_policy_used`). |

Không có test nào assert trên implementation details như "helper has
been called once" hay "private var X equals Y". Tất cả assert trên public
behavior hoặc documented semantics. Test sử dụng synthetic `np.array` /
`pd.DataFrame` / `tmp_path` — không cần research data hay DEV-04
artefact thật.

**Verdict:** ✅ Tests có assertion meaningful, cover edge cases, không
flaky, không phụ thuộc research data.

### 2.6. Không có out-of-scope change

Đã verify bằng `git diff HEAD` cho:
- `docs/decisions/0006-dev05-prototype-noise-policy.md` — không thay đổi.
- `docs/system/DEV-05_evaluation_module.md` (plan v1.2) — không thay đổi.
- `docs/system/DEV-05_verification_report.md` — không thay đổi.
- `docs/system/DEV-05_completion_summary.md` — không thay đổi.
- `configs/dev05_evaluation.yaml` — không thay đổi (default `exclude` preserved).
- `pyproject.toml` — không thay đổi bởi remediation (pre-existing diff đã có
  từ snapshot trước conversation).
- `src/customer_segmentation/prototype/clustering/` (DEV-04) — không thay đổi.
- `src/customer_segmentation/clustering/`, `src/customer_segmentation/evaluation/`
  (research core) — không thay đổi.
- DEV-02 / DEV-03 source và tests — không thay đổi.

**Verdict:** ✅ Không có out-of-scope modification.

### 2.7. Test commands + results (rerun)

**Targeted F1+F2 tests:**
```
$ PYTHONPATH=src python3 -m pytest tests/test_dev05_pipeline_helpers.py -v
============================= 15 passed in 0.87s ==============================
```

**DBSCAN noise policy tests (cross-check F2 integration với metrics module):**
```
$ PYTHONPATH=src python3 -m pytest tests/test_dev05_metrics.py -v
============================= 29 passed in 0.89s ==============================
```
Cụ thể `TestDBSCANNoise` (5 tests) PASS:
- `test_exclude_applied_uniformly_to_three_metrics`
- `test_exclude_values_match_sklearn_on_filtered_subset`
- `test_include_does_not_filter`
- `test_all_noise_returns_not_applicable`
- `test_non_density_does_not_filter`

**Full DEV-05 suite:**
```
$ PYTHONPATH=src python3 -m pytest tests/test_dev05_*.py
============================= 229 passed in 1.63s ==============================
```

**Regression DEV-02/03/04/05:**
```
$ PYTHONPATH=src python3 -m pytest tests/test_dev02_*.py tests/test_dev03_*.py \
    tests/test_dev04_*.py tests/test_dev05_*.py
======================= 697 passed, 1 skipped in 17.08s =======================
```

Skip duy nhất (pre-existing, không liên quan F1/F2):
```
SKIPPED [1] tests/test_dev03_consistency.py:241: AC 38b is OPT-IN
(C7-dependent). Default skip per plan §9.1.
```

**Verdict:** ✅ Tất cả test pass. Skip pre-existing không thuộc remediation scope.

### 2.8. Lint / format status

Theo brief: "Report lint/format status accurately. Do not claim Ruff or Black
passed if unavailable or not executed."

**Ruff (F722, SIM105, N803, SIM910, I001, F401):**

Tool: ruff 0.x (available in env này — khác với verification report §7.1
ghi "ruff chưa cài"). Env đã thay đổi; tool hiện khả dụng.

```
$ ruff check src/customer_segmentation/prototype/evaluation/pipeline.py \
              tests/test_dev05_pipeline_helpers.py

Found 8 errors.
[*] 3 fixable with the `--fix` option.
```

| # | Code | Location | Introduced bởi remediation? |
|---|---|---|---|
| 1 | F822 Undefined name `Lifecycle` in `__all__` | pipeline.py:99 | NO (pre-existing) |
| 2 | SIM105 Use `contextlib.suppress` | pipeline.py:145 | NO (pre-existing) |
| 3 | SIM105 Use `contextlib.suppress` | pipeline.py:149 | NO (pre-existing) |
| 4 | N803 Argument name `X` should be lowercase | pipeline.py:168 | NO (pre-existing, trong `_validate_inputs`) |
| 5 | N803 Argument name `X` should be lowercase | pipeline.py:328 | NO (pre-existing, trong `_make_manifest`) |
| 6 | SIM910 Use `.get()` without default | pipeline.py:367 | NO (pre-existing) |
| 7 | I001 Import block is un-sorted | tests/test_dev05_pipeline_helpers.py:23 | **YES** (test file mới) |
| 8 | F401 `build_evaluation_manifest` imported but unused | tests/test_dev05_pipeline_helpers.py:40 | **YES** (test file mới) |

`ruff check src/customer_segmentation/prototype/evaluation/` (full DEV-05
source) reports 17 errors. 8 còn lại nằm ở `manifest.py`, `metrics.py`,
`compare.py`, `display.py`, v.v. — pre-existing, không thuộc remediation.

Theo `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`, các N803 cho
`X` đã được ignore ở `src/customer_segmentation/evaluation/*` nhưng
KHÔNG ở `src/customer_segmentation/prototype/evaluation/*` (vì `prototype/*`
chỉ ignore E402, F401, F841, N814, N818, N806, UP042, SIM300). Đây là
deviation giữa convention research core và prototype layer — pre-existing.

**Black format check:**

```
$ black --check src/customer_segmentation/prototype/evaluation/pipeline.py \
                tests/test_dev05_pipeline_helpers.py
would reformat tests/test_dev05_pipeline_helpers.py
would reformat src/customer_segmentation/prototype/evaluation/pipeline.py

Oh no! 💥 💔 💥
2 files would be reformatted.
```

Cả 2 file đều không tuân thủ black format. Test file là do agent tạo
trong remediation. `pipeline.py` chứa nhiều dòng dài vượt 88-char line
limit và cấu trúc import block không sort sẵn — pre-existing trong source.

**Verdict:** ⚠️ Ruff và Black KHÔNG pass. Tuy nhiên:

- 6/8 ruff errors và cả 2 black diffs trong `pipeline.py` là **pre-existing**
  (không do remediation gây ra). Brief §2 cấm modify source / tests / config;
  nên không thể tự fix trong review này.
- 2 ruff errors trong test file mới (`I001` import sort, `F401` unused
  `build_evaluation_manifest`) là minor cosmetic — agent tạo test có
  thể clean up nếu được phép (cleanup không thuộc "sửa source/tests" nếu
  hiểu theo nghĩa "sửa behavior"). Hiện không clean up vì review là
  read-only.
- Lint status này KHÔNG làm thay đổi correctness của F1 / F2 fix, không
  introduce regression, không ảnh hưởng research methodology.
- Human reviewer quyết định: (a) merge as-is + fix lint trong increment
  sau, hoặc (b) yêu cầu agent rerun với cleanup trước khi merge.

---

## 3. Findings (review pass)

Phân loại theo mức độ ảnh hưởng.

| # | Mức độ | Mô tả | Trạng thái |
|---|---|---|---|
| R-1 | **MINOR** | `Lifecycle` symbol trong `__all__` (`pipeline.py:99`) không được define trong module. F822. Pre-existing. | Không tự sửa (read-only review). Đề xuất human owner tạo `Lifecycle` class hoặc bỏ khỏi `__all__` trong increment sau. |
| R-2 | **MINOR** | `_capture_library_versions` dùng `try/except/pass` 2 chỗ (pipeline.py:145, 149). SIM105. Pre-existing. | Không tự sửa. |
| R-3 | **INFORMATIONAL** | Argument name `X` trong `_validate_inputs` (line 168) và `_make_manifest` (line 328) vi phạm N803. Pre-existing. `pyproject.toml` đã ignore N803 ở `src/customer_segmentation/evaluation/*` nhưng KHÔNG ở `src/customer_segmentation/prototype/evaluation/*`. | Không tự sửa. Đề xuất thêm N803 vào `[tool.ruff.lint.per-file-ignores]` cho prototype sub-tree (consistency với research core convention). |
| R-4 | **INFORMATIONAL** | `tests/test_dev05_pipeline_helpers.py` có 2 ruff issues (I001 import sort, F401 unused import) + không tuân thủ black. | Không tự sửa (read-only review). Cleanup 2-line nếu human owner muốn. |
| R-5 | **INFORMATIONAL** | Black format không clean cho cả `pipeline.py` lẫn test file. | Không tự sửa. |
| R-6 | **INFORMATIONAL** | `pyproject.toml` upper bounds (`pandas<3.0`, `scikit-learn<2.0`, `pyarrow<18.0`) < installed. Pre-existing env drift (verification §6.3, OUT OF SCOPE remediation). | Không tự sửa. Đề xuất ADR riêng. |

**Không có BLOCKER. Không có MAJOR.**

---

## 4. Trạng thái cuối cùng

### 4.1. Summary

- F1 (`_make_manifest.dataset_id` empty string) — **đã sửa đúng**; caller-supplied
  `dataset_id` được truyền qua parameter, persisted vào manifest, round-trip OK.
- F2 (`n_clusters_realized` semantics) — **đã sửa đúng**; helper
  `_compute_n_clusters_realized` implement đúng 3-case semantics (non-density,
  density+exclude, density+include), tôn trọng immutability của input labels,
  không tạo fake default, không duplicate metric logic.
- Phạm vi thay đổi giới hạn đúng 3 file untracked.
- Không có out-of-scope modification (research layer, ADR-0006, plan v1.2,
  configs, `pyproject.toml`, DEV-02/03/04 đều không thay đổi).
- 15 tests mới (F1: 4; F2: 10; integration: 1) đều PASS; cross-check
  `test_dev05_metrics.py::TestDBSCANNoise` (5 tests) vẫn PASS — không có
  regression trong noise policy handling.
- Full regression: 697 PASS, 1 SKIP (pre-existing DEV-03 C7).
- Lint/format không clean: 6/8 ruff errors pre-existing, 2 trong test file
  mới; black cũng fail. Không block correctness, không block technical
  closure, nhưng nên cleanup trong increment sau.

### 4.2. Limitations còn lại

Tương tự remediation report §4:

1. `pyproject.toml` upper bounds drift (R-6 ở trên) — ngoài remediation scope,
   cần ADR riêng nếu bump.
2. Không có full-pipeline integration test (`test_dev05_pipeline.py`) với
   end-to-end run. Unit tests trên private helpers đã cover đủ semantics.
3. Pre-existing lint issues ở `pipeline.py` không được remediation xử lý
   (vì remediation scope giới hạn F1+F2).
4. Lint issues trong test file mới không được cleanup (vì review read-only).

### 4.3. Kết luận

**`READY WITH ACCEPTED LIMITATIONS`**

Lý do: F1 + F2 đã sửa đúng, đủ test, không regression, không phá vỡ
research-layer safety invariant (R-EVAL-01..17 còn nguyên — verified qua
`test_dev05_research_safety.py` 16 tests vẫn PASS). Lint/format không
clean là cosmetic và pre-existing; không ảnh hưởng technical correctness
của hai fixes.

`TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED` (AGENTS.md §2.10). Mentor
review gate cho ADR-0006 vẫn PENDING — không thuộc technical closure.

### 4.4. Hard stop

Theo AGENTS.md §6, dừng sau report này. Không:
- Tự đóng DEV-05.
- Tự tuyên bố `RESEARCH APPROVED`.
- Git operations (no add / commit / push / branch / PR / merge).
- Modify source / tests / config.

Human owner / mentor quyết định:
1. Accept technical closure với limitations hiện tại.
2. Hoặc yêu cầu cleanup lint / format trong increment trước merge.
3. Hoặc rerun với quyền modify test file để dọn import.
4. ADR-0006 promotion sang research layer là workflow riêng (cần mentor
   review form tick + METHODOLOGY_LOCK_STATUS update).

---

*Generated by AI assistant (Cursor) as a read-only final technical
review for DEV-05. Per AGENTS.md §2.1, §2.2, §2.4, §2.8, §2.10, §2.11,
§2.13: research integrity preserved, phase isolation preserved, no
silent methodology change, no Git operations, no scope expansion to
research layer, technical-closure ≠ research-approval.*
