# Agent Rules — Customer Segmentation ML

This file defines the **operating rules** for any AI agent (Cursor, GitHub
Copilot, Claude, custom agents, or any contributor) working on this
repository.

These rules are binding for the foundation phase and for every later
stage (FE-01, preprocessing, RFM, extended features, transformation,
clustering, evaluation, profiling, visualization).

If a rule here ever needs to change, the change must be made in a Pull
Request that is reviewed and recorded as an ADR in
[`docs/decisions/`](./docs/decisions/).

---

## 1. Read the repository first

Before editing any code or configuration, an agent must:

1. Read this `AGENTS.md` end to end.
2. Read `README.md` end to end.
3. Read `docs/methodology/` (current research questions and study design).
4. Read `docs/data_dictionary/` (current schema).
5. Read the most recent ADRs in `docs/decisions/`.
6. Read the most recent experiment log in `docs/experiment_logs/`.
7. Read the relevant `configs/*.yaml` for the stage being modified.

If the task is not clearly defined by the above, the agent must **stop**
and ask the human lead for clarification instead of guessing.

---

## 2. Global principles (apply to every phase)

These principles are **universal**. They must be honoured across FE-01,
preprocessing, RFM, feature engineering, transformation, clustering,
evaluation, profiling, visualization, and any future stage.

### 2.1 Research integrity

- Không được invent data, kết quả thí nghiệm, tham khảo/tài liệu,
  hoặc kết luận nghiên cứu.
- Không được thay đổi research methodology một cách âm thầm.
- Không được tự đổi WORKING_ASSUMPTION thành FINAL_DECISION.
- Mọi quyết định methodology chưa được approve phải được đánh dấu rõ:
  `WORKING_ASSUMPTION` hoặc `MENTOR_REVIEW_PENDING` tuỳ context.
- Không được tự ý thay đổi research questions trong `docs/methodology/`,
  unit of analysis, hoặc benchmarking protocol.
- Không được sửa benchmark algorithms cố định bởi methodology
  (K-Means, Agglomerative Clustering, DBSCAN, Gaussian Mixture Model, Fuzzy C-Means).
  K-Medoids is OUT OF SCOPE (per ADR-0003).
- Không được gọi thuật toán/feature nào là "best", "winning",
  "recommended", "optimal" trước khi full evaluation framework đã chạy
  và được ghi vào `docs/experiment_logs/`.

Nếu ambiguity có thể ảnh hưởng research methodology → **dừng** và báo
cáo cho human researcher.

Nếu chỉ là technical implementation ambiguity không ảnh hưởng
methodology → có thể dùng convention hiện có của repository và ghi rõ
trong implementation notes.

### 2.2 Phase isolation

Mỗi phase:

- Chỉ implement đúng approved plan của phase đó.
- Có thể READ output của phase trước.
- **Không** được tự ý MODIFY output của phase trước.
- **Không** được sửa methodology của phase trước.
- **Không** được mở rộng scope sang phase sau.

Nếu phase sau cần thay đổi output phase trước → báo cáo và chờ
human decision.

### 2.3 Data integrity

Dataset đầu vào của một phase phải:

- Được READ-ONLY nếu plan yêu cầu.
- Được kiểm tra schema.
- Được kiểm tra row count khi phù hợp.
- Được kiểm tra SHA-256 khi phase yêu cầu reproducibility/integrity.
- Không được mutate silently.

**Không** được sửa raw/processed dataset chỉ để test pass hoặc SHA khớp.

Nếu phát hiện dataset discrepancy → investigate, report, không tự
overwrite.

### 2.4 Scope control

Không tự thêm vào scope phase hiện tại:

- clustering
- scaling
- transformation
- model training
- evaluation
- hyperparameter tuning
- visualization
- deployment
- PR / documentation artifact ngoài scope

trừ khi approved plan của phase hiện tại yêu cầu rõ ràng.

Không tự "cải tiến" methodology.

### 2.5 Research decision language

Không tự dùng các từ: `best`, `worst`, `recommended`, `optimal`,
`superior`, `final`, `winner` để mô tả feature, algorithm, model hoặc
methodology nếu chưa có basis/approval phù hợp.

Nếu chỉ là candidate, dùng đúng semantics của phase:

- `CANDIDATE`
- `RETAIN_CANDIDATE`
- `PENDING_REVIEW`
- `EXCLUDE`
- `ADJUST`
- `UNSUPPORTED`

`RETAIN_CANDIDATE` **không** đồng nghĩa `FINAL`.

### 2.6 Feature / model selection

Không tạo:

- numerical score
- ranking
- weight
- winner
- "best model"

nếu approved plan không yêu cầu và không có methodology rõ ràng.

Selection phải dựa trên evidence/criteria đã được approve.

### 2.7 Reproducibility

Mỗi implementation phase nên ghi nhận khi phù hợp:

- input dataset/version
- input SHA-256
- output SHA-256
- configuration
- feature list
- parameters
- random seed nếu có
- execution metadata
- assumptions
- pending decisions

Không invent metadata.

### 2.8 Validation

Trước khi kết thúc một implementation phase, agent cần chạy các bước
validation phù hợp với scope:

- Tests phù hợp với phase (`pytest`).
- Lint (`ruff check`).
- Format check (`black --check`).
- Pipeline trên dataset thật nếu scope yêu cầu.
- Kiểm tra output schema, row count, duplicates.
- Kiểm tra missing / error conditions khi phù hợp.
- Kiểm tra reproducibility metadata (input/output SHA, config hash,
  random seed, environment).
- Kiểm tra các hard constraint của phase đó (xem §3).

**Pre-existing failure:**

- Phân biệt rõ lỗi do implementation hiện tại với lỗi pre-existing
  trong repository.
- Không che giấu.
- Không tự nhận là PASS nếu còn failure chưa được giải thích.
- Pre-existing failure được ghi nhận trong completion summary của phase,
  không bị sửa ngoài scope.

### 2.9 No silent policy changes

Không tự đổi:

- dataset
- filtering policy
- missing-value policy
- outlier policy
- cancellation/return treatment
- feature definition
- reference date
- clustering algorithm
- evaluation metric
- transformation
- scaling
- threshold

nếu thay đổi đó ảnh hưởng methodology. Phải report trước.

### 2.10 Human approval gate

AI Agent không được tự coi một phase là "academically approved" chỉ vì
code chạy, tests pass, metrics đẹp, hoặc report hoàn thành.

Phân biệt rõ:

- `TECHNICALLY IMPLEMENTED` — agent đã implement và verify.
- `RESEARCH DECISION APPROVED` — mentor/human researcher đã approve
  các vấn đề methodology.

Mentor/human researcher quyết định các vấn đề methodology.

### 2.11 Git

AI Agent:

- **KHÔNG** commit.
- **KHÔNG** push.
- **KHÔNG** tạo Pull Request.
- **KHÔNG** merge.
- **KHÔNG** thay đổi branch strategy.

Human researcher chịu trách nhiệm Git operations.

### 2.12 Data privacy

- **Không** commit raw datasets (`data/raw/**`), interim data
  (`data/interim/**`), processed data (`data/processed/**`), hoặc
  external data (`data/external/**`) vào Git.
- **Không** xóa hoặc di chuyển primary dataset
  `data/raw/primary/Online Retail.xlsx` mà không có explicit user
  request được ghi vào ADR.
- **Không** thêm dataset mới mà không ghi provenance (source URL,
  license, SHA-256) vào `configs/dataset.yaml` và ADR tương ứng.
- **Không** commit generated reports / figures dưới `reports/**`.

### 2.13 Code organization

- Tất cả reusable logic phải nằm trong `src/customer_segmentation/`.
- Notebooks (`notebooks/`) chỉ dùng cho exploration, reporting,
  communication. Phải import từ `src/`, không duplicate logic.
- Public functions/classes phải có docstrings và type hints.
- Public behavior mới phải có ít nhất một unit test dưới `tests/`.

---

## 3. Stage-by-stage guardrails

Đây là các forbidden actions cụ thể cho từng phase. Nếu một phase không
liệt kê trong bảng dưới, agent vẫn phải tuân thủ §2.

| Stage             | Forbidden actions                                                                   |
| ----------------- | ----------------------------------------------------------------------------------- |
| FE-01             | Running preprocessing, building features from raw data, fitting any model.          |
| Preprocessing     | Inventing row counts, dropping rules, or imputation values that are not audited.    |
| Feature eng.      | Changing the RFM formula or the extended-feature set without an ADR.                |
| Transformation    | Picking a scaler/transform without an ADR documenting the rationale.                |
| Clustering        | Picking a "best" k or algorithm before evaluation runs.                              |
| Evaluation        | Reporting internal metrics without stability and runtime; ignoring silhouette for     |
|                   | density-based clusters.                                                             |
| Profiling         | Inventing segment names ("Champions", "Loyal") without an ADR-supported mapping.    |
| Visualization     | Hard-coding cluster colors or labels in multiple places — use a single source.      |

---

## 4. Required workflow for any non-trivial change

1. Confirm the assigned task ID (DS-05, FE-01, PR-02, ...).
2. Confirm the scope (which files, which configs).
3. Read the relevant section of this file and the README.
4. Make the change.
5. Update or add tests under `tests/`.
6. Run `ruff check .`, `black --check .`, and `pytest` locally.
7. If a decision was made, write the ADR **before** opening the PR.
8. Open a PR using `.github/PULL_REQUEST_TEMPLATE.md`.
9. Wait for human review. Do not self-merge.

---

## 5. Forbidden shortcuts

- Copy-pasting logic from a notebook into `src/` (or vice versa).
- Adding a "quick fix" that bypasses the config layer.
- Hard-coding paths instead of resolving them from `configs/*.yaml`.
- Adding a new dependency to `requirements.txt` without also adding it
  to `[project.dependencies]` in `pyproject.toml` and without an ADR
  explaining why.
- Skipping the data dictionary update when adding a new feature column.

---

## 6. Escalation

If at any point an agent:

- Is unsure about the scope of a task,
- Discovers a methodology contradiction,
- Needs to violate any rule above,

…then the agent must **stop**, surface the issue clearly in the
conversation, and wait for human direction. Do not improvise.

---

## 7. Communication convention

Khi hoàn thành một implementation task, agent output bằng tiếng Việt.

Code / identifier / file name: dùng English convention hiện có của
repository.

Completion summary nên có:

1. Files created / modified
2. Implementation summary
3. Dataset / result summary
4. Tests
5. Lint
6. Format
7. Input / output SHA nếu applicable
8. Assumptions
9. PENDING_REVIEW decisions
10. Remaining issues
11. Scope explicitly NOT performed nếu quan trọng

---

## 8. Token efficiency

Các prompt của phase sau có thể ngắn gọn vì rules đã có trong file này:

> "Đọc AGENTS.md và plan hiện tại. Implement đúng plan. Nếu methodology
> ambiguity → dừng và báo cáo. Không mở rộng scope."

Không cần lặp lại trong mỗi prompt các constraint đã có ở §2 (no commit,
no push, no PR, no invent, no silent methodology change, phase isolation,
input integrity, human approval gate, output reporting requirements).

Phase-specific prompt chỉ cần override / clarify nếu có ngoại lệ.

---

## 9. Relationship to AGENTS.md vs phase plan

| Concern                          | Source of truth                                  |
| -------------------------------- | ------------------------------------------------ |
| Global, cross-phase rules        | `AGENTS.md` (this file)                           |
| Phase-specific methodology       | Approved plan of that phase                      |
| Phase-specific decisions / data  | ADR + report + config của phase đó               |
| Reproducibility metadata        | `reports/<stage>/<stage>_run.json`               |
| Data dictionary / column meaning | `docs/data_dictionary/`                          |

**Không** đưa phase-specific decisions hoặc con số/data statistics
của một phase cụ thể vào file này. Phase-specific thuộc về plan/config/
report của phase đó.

`AGENTS.md` chỉ chứa principle / rule dùng chung, không trở thành
prompt dài cho một phase bất kỳ.
