# DEV-05 — Targeted Remediation Report (Findings F1 + F2)

> **Mã task:** DEV-05 Targeted Remediation
> **Trạng thái đầu vào:** `VERIFIED WITH LIMITATIONS`
>   (`docs/system/DEV-05_verification_report.md`, audit ngày 2026-10-10)
> **Trạng thái đầu ra:** `MINOR FINDINGS ADDRESSED — awaiting human reviewer`
> **Loại artefact:** Remediation report (BỔ SUNG cho verification report; không
> sửa verification report cũ — mục đích giữ dấu vết kết quả audit ban đầu).
> **Ngày remediation:** 2026-10-10
> **Phạm vi remediation:** Chỉ xử lý hai MINOR findings đã được audit phát
> hiện (`_make_manifest.dataset_id` + `n_clusters_realized` semantics).
> **Không chạm vào** research layer, ADR-0006, plan v1.2, DEV-02/03/04, configs
> khác, `pyproject.toml`, dependencies.
> **Không Git operations** (no add / commit / push / branch / PR / merge).

---

## 1. Findings đã xử lý

### 1.1. F1 — `_make_manifest.dataset_id` empty string

**Audit finding (verification §6.1):** `_make_manifest` reads
`dataset_id = str(clustering_manifest_data.get("dataset_id", ""))`, while DEV-04
`ClusteringManifest` schema does not carry `dataset_id`. Consequence: every
evaluation manifest recorded `dataset_id = ""`.

**Plan reference:** §4.1 (input contract), §4.3 (output contract); plan
§4.3 muốn `dataset_id` recorded in `evaluation_manifest.json`.

**Cách xử lý:**

1. Truyền `dataset_id` (parameter) vào `_make_manifest(...)` thay vì đọc
   lại từ `clustering_manifest_data`. Caller (Stage D-F driver trong
   `run_evaluation_pipeline`) đã có `dataset_id` từ function input — sẵn
   có, không cần lookup thêm.
2. **Không suy ra** `dataset_id` từ `clustering_manifest_data` —
   đây là nguồn gây ra bug.
3. Giữ nguyên `evaluation_id` derivation, path resolution, compatibility
   semantics, schema contract `EVALUATION_MANIFEST_SCHEMA_VERSION = "1.0.0"`,
   `build_evaluation_manifest` signature ngoài phần cần thiết.
4. Validation semantics: `dataset_id` nhận từ pipeline input đã được
   verify ở `resolve_storage_root` / path-containment trước đó; việc
   truyền trực tiếp vào `_make_manifest` không mở thêm attack surface.

**Diff scope:**

```python
# src/customer_segmentation/prototype/evaluation/pipeline.py
def _make_manifest(
    *,
    evaluation_id: str,
    dataset_id: str,                  # ← NEW required kw-arg
    clustering_id: str,
    clustering_manifest_data: dict[str, Any],
    ...
) -> EvaluationManifest:
    ...
    # OLD: dataset_id_str = str(clustering_manifest_data.get("dataset_id", ""))
    # NEW:
    dataset_id_str = str(dataset_id)
    ...
```

### 1.2. F2 — `n_clusters_realized` tính trước noise filter

**Audit finding (verification §6.2):**
`n_clusters_realized = int(np.unique(labels).size)` was computed before
noise filter — could count `-1` as a cluster for DBSCAN under
`noise_policy="exclude"`, diverging from the point set actually used to
compute metrics.

**Plan reference:** §5.4.4, §5.4.6.
**ADR reference:** `docs/decisions/0006-dev05-prototype-noise-policy.md`
("default exclude"; semantics: under exclude `-1` is NOT a cluster;
under include `-1` IS a cluster for DBI/CH — sklearn default).

**Cách xử lý:**

1. Extract `_compute_n_clusters_realized(...)` thành helper rõ ràng
   trong `pipeline.py`. Semantics:
   - **non-density algorithm**: count all unique labels (no `-1` ever
     present; policy irrelevant).
   - **density_based + `"exclude"`**: count **unique non-noise** labels
     (post-filter set). Returns 0 khi filtered set empty (không phải
     fake default — đây là count thực của `np.unique` trên empty array).
   - **density_based + `"include"`**: count unique labels **kể cả `-1`**;
     `-1` được sklearn default xem như cluster cho DBI / CH.
2. Không sửa `labels` source: helper chỉ make `non_noise_mask` boolean
   và dùng fancy indexing tạo view tạm; không `in-place` mutation.
3. Không thay đổi metric status / `reason` enum; không tạo fake default
   (`0` ở all-noise case là **count thực của empty filtered set** theo
   plan §5.5 rule 2, không phải placeholder).
4. `run_evaluation_pipeline` (driver) sửa call site:

```python
n_clusters_realized = _compute_n_clusters_realized(
    labels=labels,
    noise_label=DBSCAN_NOISE_LABEL,
    is_density_based=is_density_based,
    noise_policy=effective_noise_policy,
)
```

---

## 2. Files changed

> Trạng thái Git: cả hai file đều `untracked` (??). Không tự commit, push,
> hay tạo PR (AGENTS.md §2.11).

| File | Loại thay đổi | Tóm tắt |
|---|---|---|
| `src/customer_segmentation/prototype/evaluation/pipeline.py` | Modify | (1) Thêm `_compute_n_clusters_realized` helper; (2) sửa `_make_manifest` để nhận `dataset_id` tham số; (3) dùng helper trong `run_evaluation_pipeline` cho `n_clusters_realized`. |
| `tests/test_dev05_pipeline_helpers.py` | Add | Mới — 15 tests gồm F1 (4 tests), F2 (10 tests), integration (1 test). Tất cả dùng synthetic data; không cần DEV-04 artefact hay research dataset. |

**Files KHÔNG bị động (xác nhận phạm vi):**

- `docs/system/DEV-05_verification_report.md` — **không sửa** (giữ dấu
  vết kết quả audit ban đầu).
- `docs/system/DEV-05_completion_summary.md` — **không sửa** (sẽ được
  cập nhật trong increment sau khi human reviewer sign-off).
- `docs/decisions/0006-dev05-prototype-noise-policy.md` — **không sửa**
  (policy decision không thay đổi).
- `docs/system/DEV-05_evaluation_module.md` (plan v1.2) — **không sửa**
  (plan không thay đổi).
- DEV-02 / DEV-03 / DEV-04 source, tests, configs — **không sửa**.
- `pyproject.toml`, `requirements.txt` — **không sửa** (không thêm
  dependency, không thay đổi constraint).
- `configs/dev05_evaluation.yaml` — **không sửa** (noise_policy.default
  vẫn `exclude` đúng ADR-0006).

---

## 3. Test results

### 3.1. Targeted: F1 + F2 tests (file mới)

```
$ PYTHONPATH=src python3 -m pytest tests/test_dev05_pipeline_helpers.py -v

collected 15 items

tests/test_dev05_pipeline_helpers.py::TestMakeManifestDatasetId
  ├── test_dataset_id_recorded_from_input                              PASSED
  ├── test_dataset_id_not_empty_when_input_provided                    PASSED
  ├── test_dataset_id_survives_manifest_round_trip                     PASSED
  └── test_dataset_id_ignored_when_not_in_manifest_data                PASSED

tests/test_dev05_pipeline_helpers.py::TestComputeNClustersRealized
  ├── test_non_density_count_all_unique                                PASSED
  ├── test_non_density_single_cluster                                  PASSED
  ├── test_density_exclude_excludes_noise                              PASSED
  ├── test_density_exclude_all_noise_returns_zero                      PASSED
  ├── test_density_exclude_single_non_noise_cluster                    PASSED
  ├── test_density_exclude_no_noise_in_data                            PASSED
  ├── test_density_include_treats_minus_one_as_cluster                 PASSED
  ├── test_density_include_all_noise_returns_one                       PASSED
  ├── test_input_labels_not_mutated                                    PASSED
  └── test_no_fake_default_value                                       PASSED

tests/test_dev05_pipeline_helpers.py::TestF1F2Integration
  └── test_dbscan_manifest_records_dataset_id_and_post_filter_clusters PASSED

============================== 15 passed in 0.88s ===============================
```

| Test class | Tests | Status |
|---|---|---|
| F1 (`TestMakeManifestDatasetId`) | 4 | 4 PASS |
| F2 (`TestComputeNClustersRealized`) | 10 | 10 PASS |
| F1+F2 integration (`TestF1F2Integration`) | 1 | 1 PASS |
| **Tổng file mới** | **15** | **15 PASS, 0 FAIL, 0 SKIP** |

Test đã cover đủ các case theo audit brief §3 và §4:

- F1: dataset_id được ghi vào manifest round-trip, không bị shadow bởi
  stray key trong `clustering_manifest_data`, manifest reload giữ
  đúng giá trị caller-supplied.
- F2: non-density (cả 2 policy), density+exclude (4 case: có noise,
  all-noise, single non-noise, no noise), density+include (2 case),
  immutability của input labels, không có fake default. Smoke test
  tích hợp cuối cùng kiểm tra DBSCAN run ghi đúng `dataset_id` +
  post-filter `n_clusters_realized` + provenance fields
  (`noise_count`, `noise_ratio`, `n_samples_input`,
  `n_samples_used_for_compute`, `algorithm_family`,
  `noise_policy_used`).

### 3.2. Regression — DEV-05 full suite

```
$ PYTHONPATH=src python3 -m pytest tests/test_dev05_*.py -v
```

| File | Tests (trước) | Tests (sau remediation) | Pass/Fail |
|---|---|---|---|
| test_dev05_scope.py | 22 | 22 | 22 / 0 |
| test_dev05_config.py | 28 | 28 | 28 / 0 |
| test_dev05_storage.py | 38 | 38 | 38 / 0 |
| test_dev05_manifest.py | 41 | 41 | 41 / 0 |
| test_dev05_metrics.py | 29 | 29 | 29 / 0 |
| test_dev05_display.py | 22 | 22 | 22 / 0 |
| test_dev05_compare.py | 10 | 10 | 10 / 0 |
| test_dev05_research_safety.py | 16 | 16 | 16 / 0 |
| test_dev05_import_blocklist.py | 5 | 5 | 5 / 0 |
| test_dev05_runtime_dependencies.py | 3 | 3 | 3 / 0 |
| **test_dev05_pipeline_helpers.py** | — | 15 | 15 / 0 |
| **Tổng DEV-05** | **214** | **229** | **229 PASS, 0 FAIL** |

### 3.3. Regression — DEV-02 + DEV-03 + DEV-04 + DEV-05

```
$ PYTHONPATH=src python3 -m pytest tests/test_dev02_*.py \
    tests/test_dev03_*.py tests/test_dev04_*.py tests/test_dev05_*.py
```

**Result:** `697 passed, 1 skipped in 16.56s` — exit code 0.

Skip duy nhất (pre-existing):

```
SKIPPED [1] tests/test_dev03_consistency.py:241: AC 38b is OPT-IN
(C7-dependent). Default skip per plan §9.1. Run manually after
resolution of DOC-CTD-01 (C7 status conflict).
```

Skip này nằm ngoài DEV-05 scope (DEV-03 C7 conflict), đã có từ trước
remediation. Không liên quan đến F1 / F2.

### 3.4. `git diff` để xác nhận phạm vi (read-only)

```
$ git diff HEAD -- src/customer_segmentation/prototype/evaluation/pipeline.py \
                    tests/test_dev05_pipeline_helpers.py
(no output — both files are untracked, not yet staged)
```

```
$ git status --short -- src/customer_segmentation/prototype/evaluation/pipeline.py \
                       tests/test_dev05_pipeline_helpers.py
?? src/customer_segmentation/prototype/evaluation/pipeline.py
?? tests/test_dev05_pipeline_helpers.py
```

Confirmation: thay đổi giới hạn ở 2 file với markers `??` (untracked);
không file nào trong `docs/decisions/`, `docs/system/DEV-05_*`,
`configs/`, `src/customer_segmentation/prototype/{clustering,dataset_management}/`,
`tests/test_dev0{2,3,4}_*.py` bị thay đổi.

### 3.5. Những gì KHÔNG chạy được trong môi trường này

- **`ruff check`** và **`black --check`**: hai tool chưa được cài trong
  env này (ghi nhận trong verification §7.1 / §7.2). Đề xuất human
  reviewer chạy thủ công trước khi merge (AGENTS.md §2.8).
- **End-to-end CLI run** (`python scripts/dev05_evaluate_clustering.py
  --dataset-id ...`): không có published DEV-04 artefact trong
  `data/prototype/` (chỉ có 2 DEV-02 datasets chưa qua DEV-03 / DEV-04).
  Đã cover bằng unit test với synthetic data + tmp_path (test `test_dbscan_manifest_records_dataset_id_and_post_filter_clusters`).
- **Conftest fixture `synthetic_dev03_artefact`** chưa tồn tại trong
  `tests/conftest.py`. Trong remediation này không cần tới vì
  test gọi trực tiếp `_make_manifest` và `_compute_n_clusters_realized`
  với synthetic arrays / DataFrame, không touch storage. Nếu human
  reviewer muốn full pipeline integration test, sẽ là increment sau.

---

## 4. Limitations còn lại

Những findings chưa xử lý trong remediation này (theo audit brief giới
hạn ở F1 + F2):

| # | Mức độ | Mô tả | Lý do chưa xử lý |
|---|---|---|---|
| 6.3 | MINOR | `pyproject.toml` upper bounds < installed (`pandas>=2.2,<3.0` vs 3.0.6; `scikit-learn>=1.4,<2.0` vs 1.9.1; `pyarrow>=15.0,<18.0` vs 25.0.1) | Brief §2 cấm thay đổi `pyproject.toml`. Cần ADR riêng (methodology decision hay env cleanup). |
| 6.4 | INFORMATIONAL | Không có `test_dev05_pipeline.py` (full pipeline integration test). | Đã cover bằng unit test trên private helpers trong `test_dev05_pipeline_helpers.py`. Full integration test thiết chạy DEV-04 trước để có artefact — nằm ngoài remediation scope. |
| 6.5 | INFORMATIONAL | DEV-04 `ClusteringManifest` không có `dataset_id` field (design tension). | Đã addressed indirectly bằng F1 fix (DEV-05 không cần sửa DEV-04 schema; nhận `dataset_id` từ pipeline input). |

Các MINOR findings khác trong verification §6 (6.3) không thuộc 2
findings được audit brief phê duyệt xử lý — không tự mở rộng scope.
INFORMATIONAL findings còn lại đều đã được giảm thiểu bởi F1 + F2 fix
hoặc không thuộc remediation scope.

---

## 5. Xác nhận

- ✅ **Không sửa research layer.** Không file nào trong
  `src/customer_segmentation/{clustering,evaluation}/`,
  `docs/research/`, `docs/methodology/`, `reports/`, `data/processed/`
  bị động.
- ✅ **Không chạy research evaluation.** Không chạy metrics trên
  `data/processed/final_clustering_dataset.parquet` hay
  `data/raw/primary/Online Retail.xlsx`. Tests chỉ dùng
  synthetic `np.array` / `pd.DataFrame` fixtures + `tmp_path`.
- ✅ **Không Git operations.** Không `git add`, `git commit`,
  `git push`, `git branch`, `git merge`, `git tag`, không tạo
  Pull Request. Hai file thay đổi / thêm mới (`pipeline.py`,
  `test_dev05_pipeline_helpers.py`) là `untracked` (??); human
  researcher quyết định khi nào add / commit.
- ✅ **Không thay đổi ADR-0006.** Policy decision (`noise_policy =
  "exclude"` default) preserved verbatim. Helper
  `_compute_n_clusters_realized` chỉ implement semantics của policy
  đã có trong plan §5.4.4 / ADR-0006, không tạo policy mới.
- ✅ **Không thay đổi evaluation ID derivation.** Plan §4.4
  8-canonical-field hash preserved; cùng (clustering_id, dataset_id
  từ caller, preprocessed_id, ml_dataset_sha256, config_sha256,
  noise_policy, metric_set_hash, schema_version) → cùng
  `evaluation_id`.
- ✅ **Không tuyên bố RESEARCH_APPROVED.** Trạng thái vẫn là
  `TECHNICALLY IMPLEMENTED`. Per AGENTS.md §2.10, mentor / human
  researcher gate còn PENDING (`MENTOR_REVIEW_FORM_EXP01_EXP05.md`
  line 47 chưa tick, `METHODOLOGY_LOCK_STATUS §3 WA-08` vẫn
  `WORKING_ASSUMPTION`, `EXP01-MET-01` vẫn `PENDING_REVIEW`).
- ✅ **Không sửa `pyproject.toml`** / dependencies.
- ✅ **Không sửa verification report** (`docs/system/DEV-05_verification_report.md`).
  Báo cáo này là bổ sung, không overwrite.
- ✅ **`TECHNICALLY IMPLEMENTED ≠ RESEARCH APPROVED`** honoured.

---

## 6. Hard stop

Theo AGENTS.md §6 escalation protocol:

- Dừng sau báo cáo này.
- Không tự đóng DEV-05.
- Không tự tuyên bố research approval.
- Chờ human reviewer / mentor quyết định bước tiếp theo:
  (i) merge hoặc reject remediation,
  (ii) có/không chạy `ruff check` / `black --check` trước merge,
  (iii) có/không thêm full-pipeline integration test
  (`test_dev05_pipeline.py`),
  (iv) có/không xử lý MINOR findings 6.3 (pyproject bump) trong
  ADR riêng,
  (v) mentor review gate cho ADR-0006 vẫn là workflow riêng,
  không thuộc remediation này.

---

*Generated by AI assistant (Cursor) as a targeted remediation artefact
for two MINOR findings from the post-Phase-2 independent verification
of DEV-05. Per AGENTS.md §2.1, §2.2, §2.4, §2.8, §2.9, §2.10, §2.11,
§2.13: research integrity preserved, phase isolation preserved, no
silent methodology change, no Git operations, no scope expansion to
research layer.*
