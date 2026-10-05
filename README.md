# Phân khúc Khách hàng bằng Machine Learning

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Formatter: black](https://img.shields.io/badge/formatter-black-000000.svg)](https://black.readthedocs.io/)
[![Status](https://img.shields.io/badge/status-EPIC--07%20done%20%7C%20EPIC--08%20active-yellow.svg)](#2-tr%E1%BA%A1ng-th%C3%A1i-hi%E1%BB%87n-t%E1%BA%A1i)

> **Ngôn ngữ:** README này viết bằng **tiếng Việt**. Thuật ngữ kỹ thuật
> (RFM, DBSCAN, FE-01, EPIC, ADR, v.v.) giữ nguyên tiếng Anh theo quy ước
> ngành. Code, identifier, file path giữ tiếng Anh.

Dự án nghiên cứu học thuật về **phân khúc khách hàng bằng học máy không
giám sát (unsupervised machine learning)**, áp dụng lên bộ dữ liệu giao
dịch bán lẻ **UCI Online Retail**.

Mục tiêu: phân nhóm khách hàng thành các cụm có ý nghĩa hành vi, đồng
thời so sánh 5 thuật toán clustering trong không gian đặc trưng cấp
khách hàng dưới các điều kiện thí nghiệm có kiểm soát.

> **Trước khi làm bất kỳ việc gì trong repo này**, hãy đọc
> **[`AGENTS.md`](./AGENTS.md)** từ đầu đến cuối. AGENTS.md quy định
> các ràng buộc bắt buộc cho mọi người đóng góp (kể cả AI agent).
> README.md là tài liệu định hướng; AGENTS.md là tài liệu quy tắc.

---

## Mục lục

1. [Dự án này là gì?](#1-d%E1%BB%B1-%C3%A1n-n%C3%A0y-l%C3%A0-g%C3%AC)
2. [Trạng thái hiện tại](#2-tr%E1%BA%A1ng-th%C3%A1i-hi%E1%BB%87n-t%E1%BA%A1i)
3. [Bắt đầu nhanh](#3-b%E1%BA%AFt-%C4%91%E1%BA%A7u-nhanh)
4. [Cấu trúc Repository](#4-c%E1%BA%A5u-tr%C3%BAc-repository)
5. [Bản đồ tài liệu — đọc cái gì trước](#5-b%E1%BA%A3n-%C4%91%E1%BB%93-t%C3%A0i-li%E1%BB%87u--%C4%91%E1%BB%8Dc-c%C3%A1i-g%C3%AC-tr%C6%B0%E1%BB%9Bc)
6. [Phạm vi thuật toán](#6-ph%E1%BA%A1m-vi-thu%E1%BA%ADt-to%C3%A1n)
7. [Chạy thí nghiệm](#7-ch%E1%BA%A1y-th%C3%AD-nghi%E1%BB%87m)
8. [Test, lint, format](#8-test-lint-format)
9. [Quy tắc bảo mật dữ liệu và Git](#9-quy-t%E1%BA%AFc-b%E1%BA%A3o-m%E1%BA%ADt-d%E1%BB%AF-li%E1%BB%87u-v%C3%A0-git)
10. [Quy trình đóng góp](#10-quy-tr%C3%ACnh-%C4%91%C3%B3ng-g%C3%B3p)
11. [Giấy phép](#11-gi%E1%BA%A5y-ph%C3%A9p)
13. [Bảng chú giải thuật ngữ](#13-b%E1%BA%A3ng-ch%C3%BA-gi%E1%BA%A3i-thu%E1%BA%ADt-ng%E1%BB%AF)

---

## 1. Dự án này là gì?

Đây là một dự án nghiên cứu **có tính tái lập (reproducible)** và
**khóa methodology**. Mọi bước trong pipeline đều được tài liệu hóa,
mọi thí nghiệm đều được ghi log, và mọi quyết định methodology đều
được lưu thành ADR (Architecture Decision Record).

**Tổng quan nhanh:**

| Hạng mục | Giá trị |
| --- | --- |
| Dataset | UCI Online Retail (primary); UCI Online Retail II (backup) |
| Số dòng raw | 541,909 giao dịch |
| Đơn vị mô hình hoá | Khách hàng (`CustomerID`) |
| Số khách hàng trong ma trận cuối | **4,371** |
| Không gian đặc trưng cuối | R¹⁴ — RFM Extended |
| SHA-256 ma trận cuối | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Số thuật toán benchmark | 5 (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) |
| Số thí nghiệm đã chạy | EXP-01 → EXP-05 (185 runs) |
| Preprocessing đang dùng | FE-06 C7 (median imputation + Yeo-Johnson + RobustScaler) |
| Research questions | RQ1 (thuật toán), RQ2 (preprocessing), RQ3 (stability) |

**Dự án này KHÔNG phải:**

- Không phải cuộc thi "tìm ra model thắng cuộc" kiểu Kaggle. Không
  thuật toán nào được gọi là "best", "winner", "optimal" cho đến khi
  evaluation framework chạy xong và được duyệt.
- Không phải tutorial. Mọi lựa chọn implementation đều có lý do
  (rationale) được ghi trong ADR hoặc tài liệu methodology.

---

## 2. Trạng thái hiện tại

Pipeline được tổ chức thành **10 EPIC** xuyên suốt data, modelling,
evaluation, và reporting.

- ✅ **EPIC-01 → EPIC-07**: đã hoàn thành.
- 🟡 **EPIC-08**: đang chạy (active).
- ⏳ **EPIC-09 → EPIC-10**: đang chờ.

| Giai đoạn | Trạng thái | Đầu ra chính | Bằng chứng |
| --- | --- | --- | --- |
| DS-05 — Chọn dataset | ✅ Done | UCI Online Retail | [ADR-0001](./docs/decisions/0001-primary-dataset-uci-online-retail.md), [ADR-0002](./docs/decisions/0002-backup-dataset-uci-online-retail-ii.md) |
| FE-01 — Audit dữ liệu | ✅ Done | Audit report | `reports/fe01/`, [docs/data_dictionary/](./docs/data_dictionary/) |
| FE-02 — Làm sạch | ✅ Done | Cleaned dataset | `reports/fe02/` |
| FE-03 — Phân tích outlier | ✅ Done | Outlier report | `reports/fe03/` |
| FE-04 — Aggregate cấp khách hàng | ✅ Done | Customer-level base | `reports/fe04/`, [docs/research/FE04_Customer_Level_Aggregation.md](./docs/research/FE04_Customer_Level_Aggregation.md) |
| FE-05 — Feature engineering | ✅ Done | 14 RFM Extended features | `reports/fe05/`, [docs/research/FE05_Customer_Feature_Engineering.md](./docs/research/FE05_Customer_Feature_Engineering.md) |
| FE-06 — Transformation | ✅ Done | Final clustering dataset | `reports/fe06/`, [docs/research/FE06_Transformation_Final_Dataset.md](./docs/research/FE06_Transformation_Final_Dataset.md) |
| EPIC-06 — Clustering adapters | ✅ Done | 5 algorithm adapters | [src/customer_segmentation/clustering/](./src/customer_segmentation/clustering/), [docs/research/ML0\*.md](./docs/research/) |
| EPIC-07 — Controlled experiments | ✅ Done | EXP-01 → EXP-05 (185 runs) | `reports/exp01/..exp05/`, [docs/evaluation/EVA-01.md](./docs/evaluation/EVA-01.md) |
| **EPIC-08 — Stability + ARI/AMI** | 🟡 **Active** | ARI/AMI/Hungarian outputs | [docs/evaluation/EVA-02.md](./docs/evaluation/EVA-02.md), [EVA-03.md](./docs/evaluation/EVA-03.md) |
| EPIC-09 — Customer profiling | ⏳ Pending | Segment-level profiles | [docs/research/EPIC09_CP05_PLAN.md](./docs/research/EPIC09_CP05_PLAN.md) |
| EPIC-10 — Visualization + report | ⏳ Pending | Final report, figures | (chưa scope chi tiết) |

Sơ đồ pipeline (DS-05 → EPIC-10) xem thêm ở §1 của
[`docs/methodology/methodology_overview.md`](./docs/methodology/methodology_overview.md).

---

## 3. Bắt đầu nhanh

```bash
# 1. Clone và vào repo
git clone <repo-url> customer-segmentation-ml
cd customer-segmentation-ml

# 2. Tạo môi trường ảo (Python 3.11+)
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .          # cài package src/customer_segmentation ở chế độ editable

# 3. Đặt dataset raw vào (KHÔNG commit — đã git-ignored)
#    Vị trí kỳ vọng: data/raw/primary/Online Retail.xlsx
#    Xem §9 để biết quy tắc đặt data.

# 4. Chạy test (chạy được mà không cần raw data)
pytest -q
```

Nếu bạn chỉ muốn **đọc** (không chạy), có thể bỏ bước 3 và chỉ cần
khám phá `docs/` và `src/`.

---

## 4. Cấu trúc Repository

```
customer-segmentation-ml/
├── README.md                 ← file này
├── AGENTS.md                 ← quy tắc cho mọi contributor (ĐỌC TRƯỚC)
├── LICENSE                   ← MIT
├── .gitignore
├── .env.example
├── requirements.txt
├── pyproject.toml
├── conftest.py
│
├── configs/                  ← toàn bộ YAML config (datasets, features, clustering, experiments)
│
├── data/                     ← TOÀN BỘ data đã git-ignored
│   ├── raw/{primary,backup}/    file UCI (git-ignored, chỉ .gitkeep tracked)
│   ├── interim/                  intermediate artefacts (git-ignored)
│   ├── processed/                modelling-ready datasets (git-ignored)
│   └── external/                 external reference data (git-ignored)
│
├── docs/                     ← tài liệu con người đọc (tất cả tracked)
│   ├── methodology/              RQ1..RQ3, study design, benchmarking protocol
│   ├── data_dictionary/          column-level reference cho raw + derived data
│   ├── decisions/                ADR-0001 → ADR-NNNN
│   ├── experiment_logs/          per-experiment reproducibility log
│   ├── research/                 per-stage research notes + algorithm comparison
│   └── evaluation/               EVA-01 → EVA-05 evaluation reports
│
├── notebooks/                ← numbered exploratory notebooks (1 folder / stage)
│
├── src/customer_segmentation/
│   ├── data/                 ← loaders, validators, schema, audit
│   ├── preprocessing/        ← cleaning, missing values, duplicates, outliers
│   ├── aggregation/          ← customer-level aggregation
│   ├── features/             ← RFM, extended features, validation, selection
│   ├── transformation/       ← skewness correction, pipelines, scaling, fill
│   ├── clustering/           ← 5 algorithms + framework (base, registry, runner, metrics, stability)
│   ├── evaluation/           ← internal metrics, stability, runtime, comparison
│   ├── profiling/            ← customer-level segment profiles (CP-01 → CP-05)
│   ├── config/               ← shared config utilities
│   └── outlier_analysis/     ← outlier detection và reporting
│
├── scripts/                  ← CLI entry points (run_*.py cho mỗi stage)
│
├── tests/                    ← pytest tests (chạy không cần raw data)
│
└── reports/                  ← generated reports + figures (TOÀN BỘ git-ignored)
    ├── fe01/ .. fe06/           FE-stage reports
    ├── exp01/ .. exp05/         experiment results
    ├── eva01/                   EVA-01 evaluation outputs
    ├── evaluation_results/      EPIC-08 outputs
    └── experiment_results/      cross-experiment aggregates
```

> Mọi thư mục con trong `data/` và `reports/` đều **git-ignored**. Chỉ
> file placeholder `.gitkeep` được track để giữ cấu trúc sau khi clone.

---

## 5. Bản đồ tài liệu — đọc cái gì trước

Nếu bạn mới tham gia dự án, **đọc theo thứ tự dưới đây**.

### 5.1 Quy tắc vận hành (đọc đầu tiên)

- **[`AGENTS.md`](./AGENTS.md)** — ràng buộc bắt buộc cho mọi
  contributor và AI agent.
  - §1: đọc repo trước khi sửa.
  - §2: global principles (research integrity, phase isolation, data integrity, scope control, v.v.).
  - §3: stage-by-stage guardrails.
  - §4: required workflow cho mọi non-trivial change.
  - §5: forbidden shortcuts.
  - §6: escalation — khi nào dừng và hỏi mentor.
  - §12: data privacy (không commit raw/processed data).

### 5.2 Methodology (đọc thứ hai)

- **[`docs/methodology/research_questions.md`](./docs/methodology/research_questions.md)** —
  RQ1, RQ2, RQ3 với population, feature space, algorithm scope,
  metric treatment, và interpretation boundary.
- **[`docs/methodology/methodology_overview.md`](./docs/methodology/methodology_overview.md)** —
  study design, benchmarking protocol, pipeline map.
- **[`docs/methodology/README.md`](./docs/methodology/README.md)** —
  document index cho thư mục methodology.

### 5.3 Data dictionary (đọc thứ ba)

- **[`docs/data_dictionary/data_dictionary.md`](./docs/data_dictionary/data_dictionary.md)** —
  mọi cột raw: kiểu, vai trò, missing rate, unique values, business
  meaning.
- **[`docs/data_dictionary/dataset_schema.csv`](./docs/data_dictionary/dataset_schema.csv)** —
  schema dạng machine-readable.
- **[`docs/data_dictionary/initial_data_profile.md`](./docs/data_dictionary/initial_data_profile.md)** —
  snapshot trước khi làm sạch.

### 5.4 Decisions / ADRs (đọc khi cần biết lý do "tại sao")

- **[`docs/decisions/README.md`](./docs/decisions/README.md)** — index
  các decision.
- **[`ADR-0001`](./docs/decisions/0001-primary-dataset-uci-online-retail.md)** —
  chọn primary dataset.
- **[`ADR-0002`](./docs/decisions/0002-backup-dataset-uci-online-retail-ii.md)** —
  backup dataset.
- **[`ADR-0003`](./docs/decisions/0003-algorithm-scope.md)** —
  **5-algorithm benchmark (K-Medoids OUT OF SCOPE)** — ADR quan trọng
  nhất cho mọi quyết định về clustering.
- **[`ADR-0004`](./docs/decisions/0004-research-questions.md)** —
  định nghĩa chính thức RQ1, RQ2, RQ3.

### 5.5 Research documents (đọc khi cần deep-dive theo stage)

- **[`docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md`](./docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md)** —
  tổng hợp theory + experimental của 5 thuật toán × 185 runs.
  **Đọc file này trước khi thảo luận bất kỳ câu hỏi "thuật toán nào
  best" nào.**
- **[`docs/research/FE04_Customer_Level_Aggregation.md`](./docs/research/FE04_Customer_Level_Aggregation.md)** —
  rationale cho aggregation cấp khách hàng.
- **[`docs/research/FE05_Customer_Feature_Engineering.md`](./docs/research/FE05_Customer_Feature_Engineering.md)** —
  thiết kế 14-feature RFM Extended.
- **[`docs/research/FE06_Transformation_Final_Dataset.md`](./docs/research/FE06_Transformation_Final_Dataset.md)** —
  rationale cho C7 (median + Yeo-Johnson + RobustScaler).
- **[`docs/research/ML01_Clustering_Experiment_Framework.md`](./docs/research/ML01_Clustering_Experiment_Framework.md)** —
  framework cho clustering experiment.
- **[`docs/research/ML02_KMeans.md`](./docs/research/ML02_KMeans.md)**,
  **[`ML03_Hierarchical_Clustering.md`](./docs/research/ML03_Hierarchical_Clustering.md)**,
  **[`ML04_DBSCAN.md`](./docs/research/ML04_DBSCAN.md)**,
  **[`ML05_GMM.md`](./docs/research/ML05_GMM.md)**,
  **[`ML06_Fuzzy_CMeans.md`](./docs/research/ML06_Fuzzy_CMeans.md)** —
  design notes cho từng thuật toán.
- **[`docs/research/EXP01_baseline_experiment_PLAN.md`](./docs/research/EXP01_baseline_experiment_PLAN.md)**,
  **[`EXP02_cluster_number_PLAN.md`](./docs/research/EXP02_cluster_number_PLAN.md)**,
  **[`EXP05_stability_reproducibility_PLAN.md`](./docs/research/EXP05_stability_reproducibility_PLAN.md)** —
  plan cho từng experiment.
- **[`docs/research/EPIC06_DOCUMENTATION_CONTRACT.md`](./docs/research/EPIC06_DOCUMENTATION_CONTRACT.md)** —
  EPIC-06 documentation contract.
- **[`docs/research/EPIC09_CP05_PLAN.md`](./docs/research/EPIC09_CP05_PLAN.md)** —
  plan cho EPIC-09 customer profiling.
- **[`docs/research/review/`](./docs/research/review/)** —
  deferred / future-work notes (RFM-only comparison, v.v.).

### 5.6 Evaluation reports

- **[`docs/evaluation/EVA-01.md`](./docs/evaluation/EVA-01.md)** —
  baseline + K-sweep + hyperparameter review.
- **[`docs/evaluation/EVA-02.md`](./docs/evaluation/EVA-02.md)** —
  preprocessing sensitivity (EXP-04).
- **[`docs/evaluation/EVA-03.md`](./docs/evaluation/EVA-03.md)** —
  stability + reproducibility (EXP-05).
- **[`docs/evaluation/EVA-04.md`](./docs/evaluation/EVA-04.md)**,
  **[`EVA-05.md`](./docs/evaluation/EVA-05.md)** —
  cross-experiment synthesis.
- **[`docs/evaluation/CP-01.md`](./docs/evaluation/CP-01.md)** →
  **[`CP-05.md`](./docs/evaluation/CP-05.md)** —
  protocol cho customer profiling (EPIC-09).

### 5.7 Experiment logs

- **[`docs/experiment_logs/README.md`](./docs/experiment_logs/README.md)** —
  các trường bắt buộc và quy ước đặt tên cho mỗi run.

---

## Ma trận liên kết chéo (cross-reference)

Bảng đây cho thấy **mỗi câu hỏi thường gặp → tài liệu nào đọc trước →
đọc tiếp cái gì**, giúp tra cứu nhanh theo nhu cầu:

| Bạn muốn biết… | Đọc tài liệu này trước | …rồi đọc tiếp |
| --- | --- | --- |
| Tổng quan dự án | [README.md](./README.md) | [AGENTS.md](./AGENTS.md) §1 |
| Quy tắc bắt buộc khi đóng góp | [AGENTS.md](./AGENTS.md) §2, §4, §5 | [AGENTS.md](./AGENTS.md) §6 (escalation) |
| Research question RQ1/RQ2/RQ3 | [docs/methodology/research_questions.md](./docs/methodology/research_questions.md) | [ADR-0004](./docs/decisions/0004-research-questions.md) |
| Tại sao K-Medoids bị out | [ADR-0003](./docs/decisions/0003-algorithm-scope.md) | [docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md](./docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md) §6 |
| Ý nghĩa từng cột trong raw data | [docs/data_dictionary/data_dictionary.md](./docs/data_dictionary/data_dictionary.md) | [scripts/run_fe01_audit.py](./scripts/run_fe01_audit.py) |
| So sánh 5 thuật toán | [docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md](./docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md) | [docs/evaluation/EVA-01.md](./docs/evaluation/EVA-01.md) → [EVA-02.md](./docs/evaluation/EVA-02.md) → [EVA-03.md](./docs/evaluation/EVA-03.md) |
| Cách chạy 1 experiment | README.md §7 | [docs/research/EXP01_baseline_experiment_PLAN.md](./docs/research/EXP01_baseline_experiment_PLAN.md) |
| Cách viết experiment log | [docs/experiment_logs/README.md](./docs/experiment_logs/README.md) | [AGENTS.md](./AGENTS.md) §2.7 |
| Quy trình mở PR | [AGENTS.md](./AGENTS.md) §4 | [.github/PULL_REQUEST_TEMPLATE.md](./.github/PULL_REQUEST_TEMPLATE.md) |
| Quy tắc không commit data | [AGENTS.md](./AGENTS.md) §2.12 | [.gitignore](./.gitignore) |

---

## 6. Phạm vi thuật toán

5 thuật toán clustering được benchmark (theo [ADR-0003](./docs/decisions/0003-algorithm-scope.md)):

| # | Thuật toán | Loại | Hỗ trợ random seed |
| - | --- | --- | --- |
| 1 | **K-Means** | Hard centroid-based | Có (trục `init`) |
| 2 | **Agglomerative Clustering** | Hierarchical, Ward linkage | Không (deterministic) |
| 3 | **DBSCAN** | Density-based; noise label = -1 | Không (deterministic) |
| 4 | **Gaussian Mi Mixture Model (GMM)** | Probabilistic, soft membership | Có (EM init) |
| 5 | **Fuzzy C-Means** | Soft/fuzzy; Bezdek update | Có (Dirichlet init) |

**K-Medoids là OUT OF SCOPE** trong giai đoạn nghiên cứu này. Việc bổ
sung cần một ADR mới (xem ADR-0003 §Alternatives).

Sensitivity analysis per-algorithm được tài liệu hoá trong EXP-03. Quy
trình chọn: **Silhouette → Davies-Bouldin → Calinski-Harabasz**. Trạng
thái lựa chọn là `WORKING_SELECTED`, **không phải final approved** — chờ
EPIC-08 validate.

---

## 7. Chạy thí nghiệm

Mỗi giai đoạn pipeline có một CLI entry point trong `scripts/`.

```bash
# Feature-engineering stages (FE-01 → FE-06)
python scripts/run_fe01_audit.py
python scripts/run_fe02_cleaning.py
python scripts/run_fe03_outlier_analysis.py
python scripts/run_fe04_aggregation.py
python scripts/run_fe05_feature_engineering.py
python scripts/run_fe06_transformation.py

# Controlled experiments (EPIC-07)
python scripts/run_exp01_baseline.py
python scripts/run_exp02_cluster_number.py
python scripts/run_exp03_hyperparameter_search.py
python scripts/run_exp04_preprocessing_feature_set.py
python scripts/run_exp05_stability.py

# Evaluation / profiling (EPIC-08, EPIC-09)
python scripts/run_eva01.py
python scripts/run_eva02.py
python scripts/run_eva03.py
python scripts/run_cp01.py .. scripts/run_cp05.py
```

Mỗi script:
- đọc YAML config tương ứng từ `configs/`,
- ghi output vào `/reports/<stage>/`,
- in SHA-256 của input dataset và output artefact,
- **không bao giờ** modify input data.

Chạy full pipeline:

```bash
python scripts/run_pipeline.py
```

> Tất cả các file trong `reports/` được **git-ignored** — bạn sẽ thấy
> output nhưng output này không commit được.

---

## 8. Test, lint, format

```bash
# Tất cả tests
pytest -q

# Có coverage
pytest --cov=customer_segmentation --cov-report=term-missing

# Một test file
pytest tests/test_metrics.py -v
```

```bash
# Lint
ruff check .

# Format (in-place)
ruff format .
black .
```

Tests được thiết kế để **chạy được mà không cần raw data** — chúng pass
trên CI và trên máy của mọi contributor ngay sau khi clone.

---

## 9. Quy tắc bảo mật dữ liệu và Git

> Quy tắc đầy đủ: **[`AGENTS.md`](./AGENTS.md)** §2.11, §2.12, §6.
> **Đọc AGENTS.md trước commit đầu tiên của bạn.**

Tóm tắt các ràng buộc không thể thương lượng:

1. **Không bao giờ** commit raw, interim, processed, hay external data.
   `data/**` đã git-ignored.
2. **Không bao giờ** commit generated reports hay figures. `reports/**`
   đã git-ignored.
3. **Không bao giờ** commit file dataset chính
   `data/raw/primary/Online Retail.xlsx`. Đổi tên hoặc di chuyển nó
   cần một ADR.
4. **Không bao giờ** tự ý bịa data, kết quả, tham khảo, hoặc methodology.
5. **Không bao giờ** gọi bất kỳ thuật toán/feature nào là "best",
   "winner", "recommended", "optimal" trước khi evaluation đầy đủ
   được duyệt.
6. **Luôn** ghi mọi quyết định methodology hoặc engineering vào
   `docs/decisions/` (template ADR).
7. **Luôn** ghi mọi experiment run vào `docs/experiment_logs/`.

---

## 10. Quy trình đóng góp

> Quy trình đầy đủ: **[`AGENTS.md`](./AGENTS.md)** §4.

1. Xác nhận task ID của bạn (ví dụ: `FE-04`, `EXP-02`, `EVA-02`).
2. Tạo feature branch:
   ```bash
   git checkout -b <task-id>/<short-name>
   ```
   Ví dụ: `fe05/add-diversity-features`, `exp02/k-sweep-fix`,
   `sonhoang/algorithm-comparison`.
3. Chỉ implement đúng scope của task được giao. **Không** tự ý "cải
   thiện methodology" — hãy báo cáo lên thay vì tự sửa.
4. Thêm hoặc cập nhật tests trong `tests/`.
5. Cập nhật `docs/` nếu bạn thay đổi methodology, configuration, hoặc
   data dictionary.
6. Chạy `ruff check .`, `black --check .`, và `pytest` ở local.
7. Nếu có quyết định methodology, **viết ADR trước khi mở PR**.
8. Mở PR dùng template
   [`.github/PULL_REQUEST_TEMPLATE.md`](./.github/PULL_REQUEST_TEMPLATE.md).
   Điền: task ID, description, files changed, validation performed,
   research impact, reproducibility notes.
9. **Chờ** human review. **Không tự merge.**

**Chiến lược nhánh (branching strategy):**

| Branch | Vai trò |
| --- | --- |
| `master` | Branch default cũ (giữ cho compatibility). |
| `main` | Branch default mới (khuyến nghị cho PR mới). |
| `develop` | Branch tích hợp cho release kế tiếp. |
| `feat/`, `fix/`, `chore/`, `docs/`, `test/` | Branch theo task (ví dụ: `fe05/...`). |
| `<author>/<short-name>` | Branch cá nhân (ví dụ: `sonhoang/...`). |

---

## 11. Giấy phép

Dự án phát hành theo **MIT License**. Xem
[`LICENSE`](./LICENSE) để biết nội dung đầy đủ.

---

## 13. Bảng chú giải thuật ngữ

| Thuật ngữ | Ý nghĩa |
| --- | --- |
| **RFM** | Recency, Frequency, Monetary — mô hình 3-feature kinh điển cho customer value. |
| **RFM Extended** | RFM + 11 extended behavioural feature (tổng 14). Xem [docs/research/FE05_Customer_Feature_Engineering.md](./docs/research/FE05_Customer_Feature_Engineering.md). |
| **FE-01 → FE-06** | Các stage feature-engineering: audit → cleaning → outlier → aggregation → engineering → transformation. |
| **EPIC-01 → EPIC-10** | Các nhóm pipeline từ dataset selection đến visualization. |
| **EXP-01 → EXP-05** | Các controlled experiment (baseline, K-sweep, hyperparameter, preprocessing sensitivity, stability). |
| **EVA-01 → EVA-05** | Các evaluation report. |
| **CP-01 → CP-05** | Các protocol customer profiling (EPIC-09). |
| **RQ1, RQ2, RQ3** | Official Research Questions (theo [ADR-0004](./docs/decisions/0004-research-questions.md)). |
| **ADR** | Architecture Decision Record. Một file / quyết định trong [docs/decisions/](./docs/decisions/). |
| **ML-01 → ML-06** | Tài liệu thiết kế machine-learning: framework + 5 algorithm design notes. |
| **C0 → C7** | Các scenario preprocessing. **C7** = median + Yeo-Johnson + RobustScaler (working config). |
| **K** | Số cluster (điều trị per-experiment; không có "best K"). |
| **Working Assumption** | Cờ trạng thái: "đã implement nhưng chưa được duyệt là final". |
| **WORKING_SELECTED** | Trạng thái lựa chọn hyperparameter của EXP-03 — chờ EPIC-08 validate. |
| **SHA-256** | Hash cryptographic dùng để verify dataset (`data/processed/final_clustering_dataset.parquet` có một cái). |
| **DBSCAN noise** | Điểm được gán label `-1`. Loại trừ khỏi internal metrics và WCSS. |