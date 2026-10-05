# EVA-04 — So sánh thuật toán toàn diện

> **Task ID:** EPIC-08 / EVA-04
> **Status:** IMPLEMENTED dưới dạng report-only deliverable (không có
> source package; không có runner script; không có tests)
> **Generated:** 2026-09-23

## 1. Mục tiêu

Sinh ra một comparison matrix per-algorithm cùng phân tích theo algorithm
family để reviewer có thể đọc các quan sát đa-evidence cho mỗi thuật toán
trong năm thuật toán dưới một header nhất quán. Deliverable là **so sánh
mô tả**, không phải cross-algorithm ranking.

## 2. Scope

### 2.1. In scope

- Một dòng per algorithm trong comparison matrix CSV.
- Quality (multi-metric tại EXP-03 working-selected).
- Stability (reproducibility / seed / perturbation reuse từ EVA-03).
- Cluster balance (label-ID-independent partition min/max + DBSCAN noise).
- Runtime (EXP-01 working-default mean).
- Interpretability (qualitative, không có scoring).
- Phân tích qualitative theo algorithm-family.

### 2.2. Out of scope

- Cross-algorithm ranking / composite score / winner / optimal /
  recommended.
- Promotion của `WORKING_SELECTED` thành `FINAL / BEST / OPTIMAL`.
- Methodology change.
- Re-running bất kỳ thí nghiệm nào.

## 3. Input

Read-only:

| Nguồn | Vai trò |
|---|---|
| `reports/exp01/exp01_baseline_summary.csv` | EXP-01 default K=4 metrics |
| `reports/exp03/exp03_selected_configurations.csv` | EXP-03 working-selected per algorithm |
| `reports/exp05/exp05_reproducibility_aggregate.csv` | Block R |
| `reports/exp05/exp05_seed_sweep_aggregate.csv` | Block S |
| `reports/exp05/exp05_noise_perturbation_aggregate.csv` | Block N |
| `reports/evaluation/eva01/eva01_algorithm_summary.csv` | Per-(experiment, algorithm) |
| `reports/evaluation/eva02/eva02_report.md` | Quality boundary documentation |
| `reports/evaluation/eva03/eva03_report.md` | Stability / reproducibility evidence |

## 4. Phương pháp / Implementation

### 4.1. Implementation status

**Implemented dưới dạng report-only deliverable**. Không có package
`src/customer_segmentation/evaluation/eva04/`, không có
`scripts/run_eva04.py`, và không có `tests/test_eva04.py`.

Các artifact được sinh ra bằng cách đọc các CSV nguồn trong ad-hoc
session work và viết hai output file:

- `reports/evaluation/eva04/eva04_comparison_matrix.csv` (5 rows × 23 cols)
- `reports/evaluation/eva04/eva04_report.md` (phân tích mô tả)

Điều này nhất quán với task brief ban đầu yêu cầu chính xác hai output
file đó; nó KHÔNG phải methodology gate violation.

### 4.2. Comparison matrix schema

```
algorithm, algorithm_family, configuration_evaluated,
exp01_n_clusters_baseline, exp01_silhouette_baseline, exp01_dbi_baseline,
exp01_ch_baseline, exp01_wcss_baseline,
k, silhouette, dbi, calinski_harabasz, wcss,
runtime_seconds_mean, execution_time_class,
reproducibility_evidence_block_r, seed_stability_evidence_block_s,
perturbation_robustness_evidence_block_n,
metric_variation_summary, cluster_balance_qualitative,
interpretability_qualitative,
advantages, limitations
```

Ngoài ra: `Configuration Evaluated` được label là
`EXP-03 working-selected (…)` per row, không bao giờ được promote thành
BEST/OPTIMAL.

### 4.3. Algorithm family mapping

| Thuật toán | Family |
|---|---|
| K-Means | Partition-based |
| Agglomerative | Hierarchical |
| DBSCAN | Density-based |
| GMM | Model-based (probabilistic) |
| Fuzzy C-Means | Fuzzy clustering |

## 5. Đánh giá / Phân tích

### 5.1. Cross-source numerical consistency

Các giá trị trong matrix khớp 1:1 với các CSV nguồn theo các giá trị
đã được báo cáo:

| Thuật toán | EVA-04 sil @ working-selected | EXP-03 sil |
|---|---|---|
| K-Means | 0.6291 | 0.6291 |
| Agglomerative | 0.8033 | 0.8033 |
| DBSCAN | 0.1598 | 0.1598 |
| GMM | 0.5702 | 0.5702 |
| FCM | 0.6296 | 0.6296 |

### 5.2. Phân tích theo algorithm family

Report MD chứa một section per family. Mỗi section:

- Mô tả algorithm family (partition / hierarchical / density / model /
  fuzzy).
- Liệt kê evidence quan sát được (multi-metric quality, stability,
  runtime, cluster balance, interpretability).
- Ghi lại advantages và limitations một cách qualitative.
- KHÔNG đưa ra cross-family winner.

### 5.3. Ranking / recommendation framework

Report MD chứa một template quan sát mô tả
(`Dimension → Evidence → Metric/Indicator → Interpretation →
Limitation`). **Framework KHÔNG ĐƯỢC apply** để sinh ra
`Score → Weight → Total → Rank → Winner`.

## 6. Artifacts

| File | Content |
|---|---|
| `reports/evaluation/eva04/eva04_comparison_matrix.csv` | 5-row × 23-column matrix |
| `reports/evaluation/eva04/eva04_report.md` | Narrative per-algorithm và per-family analysis |

## 7. Validation

- **Source cross-check**: tất cả numeric values trong matrix truy ngược
  1:1 về source CSVs (đã xác minh per algorithm trong §5.1).
- **Methodology token scan**: không có ngôn ngữ
  `best / winner / optimal / recommended / composite / overall ranking`
  nào được dùng để chỉ một algorithm; chỉ framework / template wording.
- **Direct tests**: KHÔNG CÓ (không có `tests/test_eva04.py`).

## 8. Kết quả / Findings

- Năm dòng, một per algorithm, không trùng.
- Configuration Evaluated được label `EXP-03 working-selected` per row.
- Mỗi thuật toán mang một pattern quan sát multi-metric / multi-block
  (Quality / Stability / Cluster balance / Runtime / Interpretability).

## 9. Limitations

| ID | Limitation | Source |
|---|---|---|
| L1 | EVA-04 không có source package / runner / tests; deliverable là report-only. Tái sinh các artifact yêu cầu re-running một ad-hoc session work thay vì `python3 scripts/run_eva04.py`. | absent package + scripts + tests |
| L2 | Hyperparameter comparison (EXP-01 default vs EXP-03 working-selected) là label-level KHÔNG ĐƯỢC ĐÁNH GIÁ; chỉ metric-level được trình bày. | `EV03-HP-01` |
| L3 | ARI / AMI / NMI / Hungarian KHÔNG ĐƯỢC COMPUTE cho matrix. | EPIC-08 pending |
| L4 | "Cluster balance" là qualitative; không có balance score nào được tính. | methodology gate |
| L5 | Runtime comparability — protocol EXP-01 giống nhau xuyên suốt algorithms (comparable); runtimes EXP-03 working-selected sử dụng một harness khác (KHÔNG trực tiếp comparable với EXP-01). | `eva04_report.md` §7 |
| L6 | DBSCAN K semantics — realised, không phải requested; so sánh với fixed-K algorithms là heuristic. | `eva02_report.md` §3 |
| L7 | EXP-03 working-selected mang status `WORKING_SELECTED` (không được promote); `EXP03-SEL-02` và `EXP03-KM-01` là TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING. | `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md` |

## 10. Research Status

- **Implemented** (deliverable artifacts hiện diện và traceable).
- **Verified** (numerical consistency với source artifacts).
- **Working assumption**: `Configuration Evaluated = EXP-03
  working-selected` được ghi là `WORKING_SELECTED` only.
- **Pending review**: `EXP03-SEL-02`, `EXP03-KM-01`, `EPIC08-CROSS-ALG-01`,
  `EPIC08-CLAIM-01`.
- **Deferred / future work**: pairwise ARI / AMI / NMI / Hungarian
  computation; hyperparameter stability comparison; cross-algorithm
  preprocessing sensitivity.

## 11. Traceability

- Outputs → `reports/evaluation/eva04/`
- Methodology → `docs/methodology/research_questions.md`
- Pending decisions → `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`