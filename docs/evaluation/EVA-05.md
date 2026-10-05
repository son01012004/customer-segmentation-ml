# EVA-05 — Ánh xạ Research Question & Kết luận đánh giá

> **Task ID:** EPIC-08 / EVA-05
> **Status:** IMPLEMENTED dưới dạng report-only deliverable (không có
> source package; không có runner script; không có tests)
> **Generated:** 2026-09-23

## 1. Mục tiêu

Ánh xạ ba research question sang evidence hiện có, tóm tắt trạng thái
trả lời per-RQ dưới methodology boundary hiện tại, và ghi lại các
limitation đang mở cùng các item future-work. Ở nơi evidence hiện có
không đủ cho một quyết định methodology (ví dụ: cross-algorithm
recommendation), report ghi rõ `NOT AUTHORIZED` thay vì sinh ra một
judgement non-pre.

## 2. Scope

### 2.1. In scope

- RQ1 — So sánh thuật toán dưới điều kiện controlled.
- RQ2 — Preprocessing sensitivity dưới fixed feature representation.
- RQ3 — Stability và Reproducibility.
- Evidence mapping per RQ (source experiment, metric, result, answer).
- Methodology gate recording (quyết định nào PENDING và quyết định nào
  LOCKED).
- Limitations và further research sections.

### 2.2. Out of scope

- Cross-algorithm ranking / composite score / claim "best / winner /
  optimal / recommended".
- Algorithm recommendation.
- Business-relevance mapping (deferred sang EPIC-09).
- Re-running bất kỳ thí nghiệm nào.
- Methodology change.

## 3. Input

Read-only:

| Nguồn | Vai trò |
|---|---|
| `docs/methodology/research_questions.md` | RQ definitions |
| `docs/decisions/0004-research-questions.md` | ADR-0004 (RQ lock) |
| `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md` | Pending decisions catalogue |
| `AGENTS.md` | Global principles §2 |
| `reports/exp01/exp01_baseline_summary.csv` | EXP-01 default K=4 |
| `reports/exp03/exp03_selected_configurations.csv` | EXP-03 working-selected |
| `reports/exp04/exp04_preprocessing_sensitivity.csv` | EXP-04 Family B (K-Means only) |
| `reports/exp05/exp05_*_aggregate.csv` | Block R / S / N |
| `reports/evaluation/eva01/eva01_experiment_repository.parquet` | Kho lưu trữ per-run chuẩn hoá |
| `reports/evaluation/eva02/eva02_report.md` | Quality boundary documentation |
| `reports/evaluation/eva03/eva03_report.md` | Stability / reproducibility evidence |
| `reports/evaluation/eva04/eva04_comparison_matrix.csv` | Per-algorithm evidence matrix |

## 4. Phương pháp / Implementation

### 4.1. Implementation status

**Implemented dưới dạng report-only deliverable**. Không có package
`src/customer_segmentation/evaluation/eva05/`, không có
`scripts/run_eva05.py`, và không có `tests/test_eva05.py`.

Các artifact được sinh ra bằng cách đọc RQ definitions, pending-decisions
catalogue, và evidence summaries, sau đó viết hai output file:

- `reports/evaluation/eva05/eva05_rq_matrix.csv` (10 rows × 7 cols,
  CSV-quoted).
- `reports/evaluation/eva05/eva05_report.md` (RQ-by-RQ analysis,
  methodology gate, limitations, further research).

Điều này nhất quán với task brief ban đầu yêu cầu chính xác hai output
file đó.

### 4.2. RQ Answer Matrix schema

```
RQ, Evidence, Experiment, Metric/Indicator, Result, Answer, Limitation
```

Matrix bị hard-bounded ở ba RQ chính thức (không có RQ mới nào được đưa
vào). Mỗi dòng ánh xạ:

- evidence nào được sử dụng;
- thí nghiệm nào sinh ra evidence đó;
- metric / indicator nào đang được đọc;
- kết quả thí nghiệm là gì;
- câu trả lời nào được kết quả hỗ trợ;
- limitation / scope boundary nào áp dụng.

### 4.3. Methodology gate

Methodology gate là binding tường minh rằng KHÔNG có cross-algorithm
recommendation nào được sinh ra vì:

- `EPIC08-CLAIM-01` là PENDING.
- `EPIC08-CROSS-ALG-01` là PENDING.
- `EPIC08-WORKING-01` là PENDING.
- `EXP03-SEL-02` mang `TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING`.
- `EXP03-KM-01` mang `TIED_WORKING_SELECTED` với ghi chú tường minh
  "KHÔNG ép chọn 1 config".

Các status này được ghi verbatim từ `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`
(một audit mà agent có thể đọc của mọi pending / deferred decision).

## 5. Đánh giá / Phân tích

### 5.1. RQ1 — So sánh thuật toán dưới điều kiện controlled

- Quality tại EXP-01 working defaults (K=4) và tại EXP-03 working-
  selected per algorithm được ghi.
- Reproducibility (Block R) được verify cho tất cả 5 thuật toán tại
  seed=42 — ANSWERED.
- Seed stability (Block S) và perturbation robustness (Block N) là
  PARTIALLY ANSWERED. ARI/AMI/NMI per-run overlap KHÔNG ĐƯỢC COMPUTE
  trong run này (deferred sang pipeline đánh giá EPIC-08).
- Runtime profile được ghi per algorithm tại EXP-01 working defaults.
- Mỗi thuật toán được mô tả độc lập; không có cross-algorithm ranking
  nào được sinh ra.

### 5.2. RQ2 — Preprocessing sensitivity dưới fixed feature representation

- EXP-04 Family B cung cấp 6 preprocessing scenarios × 5 repeats ×
  K-Means. K-Means silhouette biến thiên từ 0.254 (C1) đến 0.947 (C0);
  do đó K-Means preprocessing sensitivity là measurable.
- Cross-algorithm preprocessing sensitivity KHÔNG ĐƯỢC ĐÁNH GIÁ.
- RFM-only vs RFM Extended comparison KHÔNG ĐƯỢC TRẢ LỜI — Family A là
  DEFERRED per `EXP04-FS-01`.

### 5.3. RQ3 — Stability và Reproducibility

- Reproducibility (Block R): ANSWERED tại seed=42 + EXP-01 working
  defaults cho tất cả 5 thuật toán.
- Seed stability (Block S): PARTIALLY ANSWERED. 3 stochastic algorithms
  × 5 seeds; ARI/AMI/NMI KHÔNG ĐƯỢC COMPUTE.
- Perturbation robustness (Block N): PARTIALLY ANSWERED. 5 algorithms ×
  (sigma=0, 0.01, 0.05) × 3 pseeds; ARI/AMI/NMI KHÔNG ĐƯỢC COMPUTE.
- Hyperparameter stability: KHÔNG ĐƯỢC ĐÁNH GIÁ.
- Assignment consistency (ARI/AMI/Hungarian): KHÔNG ĐƯỢC COMPUTE.

### 5.4. Final algorithm recommendation

`FINAL ALGORITHM RECOMMENDATION: NOT AUTHORIZED UNDER CURRENT
METHODOLOGY`. Đây là methodology gate áp dụng đúng, KHÔNG phải failure
của EVA-05.

### 5.5. Methodology-bound conclusion

Kết luận bị giới hạn ở:

- FE06-v1.0 (RFM Extended, 4,371 customers, 14 features).
- EXP-01 working defaults + EXP-03 working-selected per algorithm.
- EXP-04 Family B (K-Means only).
- EXP-05 Blocks R / S / N.
- Dataset UCI Online Retail.

Kết luận KHÔNG extrapolate sang:

- All retail datasets.
- All customer-segmentation problems.
- All preprocessing strategies.
- All hyperparameters.
- All business contexts.

## 6. Artifacts

| File | Content |
|---|---|
| `reports/evaluation/eva05/eva05_rq_matrix.csv` | 10-row × 7-column RQ matrix |
| `reports/evaluation/eva05/eva05_report.md` | RQ-by-RQ narrative + methodology gate + limitations + further research |

## 7. Validation

- **RQ mapping**: ba RQ (RQ1, RQ2, RQ3) only; không có RQ mới nào được
  đưa vào.
- **Answers**: `ANSWERED`, `PARTIALLY ANSWERED`, `NOT ANSWERED`,
  `NOT COMPUTED`, `NOT EVALUATED`, với explicit evidence pointers.
- **Cross-source check**: claim K-Means silhouette range ở RQ2
  (0.254–0.947 xuyên suốt C0–C7) khớp với `exp04_preprocessing_sensitivity.csv`.
- **Methodology token scan**: `best / winner / optimal / recommended
  / composite / overall ranking` chỉ xuất hiện trong negated / quoted
  context ("not declared", "do NOT", "no …").
- **Direct tests**: KHÔNG CÓ (không có `tests/test_eva05.py`).

## 8. Kết quả / Findings

| RQ | Trạng thái |
|---|---|
| RQ1 — So sánh thuật toán | PARTIALLY ANSWERED |
| RQ2 — Preprocessing sensitivity | PARTIALLY ANSWERED cho K-Means; NOT ANSWERED cho cross-algorithm; NOT ANSWERED cho RFM-only |
| RQ3 — Stability và Reproducibility | Reproducibility ANSWERED; seed / perturbation PARTIALLY ANSWERED; hyperparameter NOT EVALUATED; assignment consistency NOT COMPUTED |

## 9. Limitations

| ID | Limitation | Source |
|---|---|---|
| L1 | EVA-05 không có source package / runner / tests; deliverable là report-only. Tái sinh yêu cầu ad-hoc session work. | absent package + scripts + tests |
| L2 | ARI / AMI / NMI / Hungarian KHÔNG ĐƯỢC COMPUTE; `labels_hash_unique_count` là proxy yếu hơn. | `EPIC08-STAB-01` PENDING |
| L3 | Cross-algorithm ranking / composite score / winner bị CẤM bởi AGENTS.md §2 và EPIC-08 pending decisions. | `AGENTS.md`; `EXP01_EXP05_PENDING_DECISIONS.md` |
| L4 | Hyperparameter stability (EXP-01 vs EXP-03) KHÔNG ĐƯỢC ĐÁNH GIÁ — labels không được persist. | `EV03-HP-01` |
| L5 | Preprocessing sensitivity cross-algorithm KHÔNG ĐƯỢC ĐÁNH GIÁ — EXP-04 chỉ bao phủ K-Means. | `exp04_preprocessing_sensitivity.csv` |
| L6 | RFM-only vs RFM Extended KHÔNG ĐƯỢC TRẢ LỜI — Family A DEFERRED. | `EXP04-FS-01` |
| L7 | Business relevance KHÔNG ĐƯỢC ĐÁNH GIÁ — EPIC-09 collaboration pending. | `EPIC08-BIZ-01`, `EXP-METRIC-BIZ-01` |
| L8 | Sample sizes cho stability evidence là nhỏ (n=5 seeds, n=3 pseeds); statistical tests KHÔNG ĐƯỢC ĐÁNH GIÁ. | `eva03_report.md` §9 |
| L9 | EXP-04 S06 (C7 — yeo_johnson + robust + median) là FE-06 working baseline; 5 scenarios còn lại là candidate scenarios. | `exp04_preprocessing_sensitivity.csv` |
| L10 | EXP-03 working-selected configurations mang `WORKING_SELECTED` (không được promote). `EXP03-SEL-02` và `EXP03-KM-01` là pending research decisions. | `EXP01_EXP05_PENDING_DECISIONS.md` |

## 10. Research Status

- **Implemented** (deliverable artifacts hiện diện, RQ mapping hoàn
  chỉnh).
- **Verified** (numerical claims cross-checked với source CSVs).
- **Working assumption**: các WORKING_SELECTED configurations được ghi
  như vậy, KHÔNG được promote thành FINAL / BEST / OPTIMAL.
- **Pending review**:
  `EPIC08-CLAIM-01`, `EPIC08-CROSS-ALG-01`, `EPIC08-WORKING-01`,
  `EXP03-SEL-02`, `EXP03-KM-01`,
  `EXP08-FAMILY-A-01`, `EXP-METRIC-BIZ-01`,
  `EPIC08-STAB-01`, `EPIC08-STAB-02`, `EPIC08-STAB-03`.
- **Deferred / out of scope**: pairwise ARI / AMI / NMI / Hungarian,
  statistical tests, hyperparameter stability comparison,
  cross-algorithm preprocessing sensitivity, RFM-only comparison.

## 11. Further Research (đề xuất, chưa thực thi)

1. Pairwise ARI / AMI / NMI / Hungarian sử dụng
   `reports/exp05/exp05_cluster_labels.parquet` (subject to
   `EPIC08-STAB-01` methodology approval).
2. Persist EXP-03 working-selected cluster labels để label-level
   EXP-01 vs EXP-03 comparison trở nên khả thi (giải quyết
   `EV03-HP-01`).
3. Mở rộng EXP-04 sang 4 thuật toán khác trên cùng 6 scenarios.
4. Author FE-06 ADR cho RFM-only materialization
   (`EXP04-FS-02`).
5. Tăng stability sample sizes để cho phép statistical tests
   (`EPIC08-STAB-03`).
6. Hoàn thiện EPIC-08 plan (`EPIC08-PLAN-01`, `EPIC08-WORKING-01`,
   `EPIC08-INPUT-01`, `EPIC08-PROFILE-01`) sao cho cross-algorithm
   claim (nếu được approve) có thể được đưa ra.
7. EPIC-09 business validation (`EPIC08-BIZ-01`,
   `EXP-METRIC-BIZ-01`).

## 12. Traceability

- Outputs → `reports/evaluation/eva05/`
- Methodology → `docs/methodology/research_questions.md`
- RQ ADR → `docs/decisions/0004-research-questions.md`
- Algorithm scope → `docs/decisions/0003-algorithm-scope.md`
- Pending decisions → `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`
- AGENTS.md → global principles