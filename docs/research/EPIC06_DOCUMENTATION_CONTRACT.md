# EPIC-06 — Documentation Contract

> **Mục đích của tài liệu này.**
> Đây là **specification** (không phải Mentor document cuối cùng) để chuẩn hóa
> cấu trúc, nội dung, lý thuyết, methodology boundary, formula, visualization
> boundary, verification, mentor review và conclusion cho **sáu tài liệu
> Mentor** tương ứng với sáu task:
>
> - `ML-01` — Clustering Experiment Framework
> - `ML-02` — K-Means
> - `ML-03` — Hierarchical (Agglomerative) Clustering
> - `ML-04` — DBSCAN
> - `ML-05` — Gaussian Mixture Model (GMM)
> - `ML-06` — Fuzzy C-Means + Algorithm Baseline
>
> Sáu file Mentor document sẽ được viết **một lần**, **sau khi toàn bộ
> EPIC-06 hoàn thành**. Trong quá trình triển khai ML-01 → ML-06, agent
> chỉ cập nhật các evidence thực tế trong repo (config, report, artifact,
> test result, code documentation) theo các quy tắc trong contract này.
> KHÔNG tạo Mentor document riêng cho từng task.

---

## 0. Tại sao cần Documentation Contract

Hệ thống clustering của nghiên cứu được chia thành **bốn EPIC**:

| EPIC | Vai trò | Output chính |
|------|---------|--------------|
| **EPIC-06** (ML-01 → ML-06) | Triển khai & cấu hình **algorithm adapters** trên Final Clustering Dataset. | Adapter code, experiment artifacts (`cluster_labels_*`, `experiment_log_*`, `algorithm_output_*`), algorithm-specific reports. |
| **EPIC-07** | Controlled experimental design & execution. | Sweep matrix (algorithm × k × seed × ...), experiment batch logs. |
| **EPIC-08** | Evaluation, comparison, stability, runtime, research comparison visualization. | Metric computation, comparison plots, dashboard. |
| **EPIC-09** | Customer segment analysis / profile. | Segment profile, RFM heatmap, segment size distribution. |

Contract này đảm bảo:

1. Sáu Mentor document sau này có **cấu trúc đồng nhất** — mentor có thể
   đọc song song, so sánh, đánh giá nhất quán.
2. Mỗi task có **phần lý thuyết riêng** đủ sâu để mentor hiểu implementation
   mà không cần đọc thêm giáo trình.
3. **Không trộn scope** giữa các EPIC — không có "best algorithm" trong
   EPIC-06, không có evaluation chính thức trong EPIC-06, không có
   segment profiling trong EPIC-06.
4. Mọi con số trong Mentor document có **provenance rõ ràng** — truy được
   về artifact/report/config.
5. Phân biệt rõ **TECHNICALLY_IMPLEMENTED** / **WORKING_ASSUMPTION** /
   **PENDING_REVIEW** / **OUT_OF_SCOPE**.

---

## 1. Áp dụng contract

### 1.1. Khi nào contract này có hiệu lực

- Có hiệu lực từ khi file này được tạo.
- Áp dụng cho mọi activity trong EPIC-06 (ML-01 → ML-06) và các PR/ADR liên quan.
- Không sửa đổi AGENTS.md, FE-06 contract, hoặc các tài liệu phase khác.

### 1.2. Khi nào sáu Mentor document được viết

- Sau khi **cả sáu task ML-01 → ML-06** đã đạt trạng thái
  `TECHNICALLY_IMPLEMENTED` (code chạy được, tests pass, artifacts đầy đủ).
- Viết một lần, dưới dạng sáu file `.md` riêng biệt trong `docs/research/`:
  - `docs/research/ML01_Clustering_Experiment_Framework.md`
  - `docs/research/ML02_KMeans.md`
  - `docs/research/ML03_Hierarchical_Clustering.md`
  - `docs/research/ML04_DBSCAN.md`
  - `docs/research/ML05_GMM.md`
  - `docs/research/ML06_Fuzzy_CMeans_Algorithm_Baseline.md`
- File `docs/research/ML01_clustering_experiment_framework.md` hiện tại
  (Implementation Notes) sẽ được **tái cấu trúc lại** theo template
  Mentor document trong contract này khi viết Mentor document cuối.

### 1.3. Quy tắc trong quá trình triển khai

Trong khi ML-01 → ML-06 đang chạy, agent **chỉ thu thập và tổ chức evidence**
theo contract. Cụ thể:

| Hoạt động | Làm | KHÔNG làm |
|-----------|-----|-----------|
| Implement algorithm adapter | Code theo plan; ghi docstring đầy đủ | Viết Mentor document cho task đó |
| Generate report | Sinh CSV / JSON / MD theo format quy ước | Đánh giá "best" |
| Update config | Cập nhật `configs/clustering.yaml` + SHA | Đổi methodology silently |
| Update tests | Thêm test cho public behavior mới | Skip test cho adapter mới |
| Sau khi xong một task | Viết completion summary (task ID, files, evidence, SHA) | Viết file `.md` dạng Mentor document |

---

## 2. Cấu trúc bắt buộc của MỖI Mentor Document (template)

Mỗi Mentor document (khi viết cuối EPIC-06) phải có **đúng 12 sections**
theo thứ tự dưới đây. Mỗi section có mục đích rõ ràng và phải được populate
đầy đủ evidence thực tế — KHÔNG để placeholder.

### 2.1. Section 1 — Tên task và vai trò trong nghiên cứu

**Mục đích:** Định vị task trong bức tranh nghiên cứu tổng thể.

**Bắt buộc có:**

| Trường | Nội dung |
|--------|----------|
| Task ID | `ML-0X` (X = 1..6) |
| Tên task | Tên đầy đủ (ví dụ: "K-Means Clustering", "Hierarchical Clustering", "Density-Based Spatial Clustering of Applications with Noise", "Gaussian Mixture Model", "Fuzzy C-Means") |
| Mục tiêu | 1–3 câu tóm tắt mục tiêu cụ thể của task này |
| Vị trí trong research pipeline | Mô tả task này nằm giữa task nào (input từ đâu, output đi đâu) |
| Input | Danh sách file input + SHA-256 + version + vai trò từng file |
| Output | Danh sách file output (artifact path) + nội dung từng file |
| Quan hệ với task trước/sau | Task trước cho input gì; task sau sẽ dùng output này như thế nào |
| Algorithm family | Hard / Density-based / Model-based / Fuzzy / Framework-only |

**Quy tắc:** Input/Output phải có **SHA-256 thực tế** từ execution, không phải placeholder.

### 2.2. Section 2 — Mục tiêu nghiên cứu

**Mục đích:** Giải thích vì sao task này cần thiết trong nghiên cứu customer segmentation, không phải lặp lại Jira checklist.

**Bắt buộc có:**

- Câu hỏi nghiên cứu mà task này góp phần trả lời.
- Mối liên hệ giữa thuật toán và đặc thù dữ liệu khách hàng retail (skewed, mixed signs, density, fuzzy boundaries).
- Cách task này tận dụng FE-06 dataset (input shape, scale, semantics).
- **KHÔNG** mô tả "best algorithm" — đó là việc của EPIC-08.
- **KHÔNG** mô tả "best k" — đó là việc của EPIC-07.

**Template gợi ý:**

> "Task này triển khai [algorithm name] để trả lời một phần câu hỏi nghiên cứu
> về [câu hỏi nghiên cứu]. Trong dataset FE-06 với [đặc điểm], [algorithm]
> phù hợp vì [lý do]. Kết quả của task này là [output] cho EPIC-07 và
> EPIC-08 đánh giá — task KHÔNG tự đánh giá."

### 2.3. Section 3 — Cơ sở lý thuyết

**Mục đích:** Cung cấp lý thuyết tối thiểu đủ để mentor hiểu implementation, công thức, và quyết định.

**Bắt buộc có:**

- Các khái niệm nền tảng của thuật toán (theo danh sách §5 của contract này).
- **Công thức toán học** với ký hiệu rõ ràng (xem §8).
- **Mục đích tối ưu** của thuật toán — tối ưu cái gì, tại sao, ranh giới.
- **Giả định** của thuật toán (distribution, convexity, separability, ...).
- **Hành vi đặc trưng** của thuật toán khi áp dụng lên dữ liệu customer
  retail (heavy-tail, mixed signs, sparse, dense, có/không có ground truth).

**Quy tắc:**

- Lý thuyết **phục vụ trực tiếp cho nghiên cứu**, không viết giáo trình lan man.
- Mỗi công thức phải có **ký hiệu + ý nghĩa + objective**.
- Nếu thuật toán có nhiều variant (linkage, initialization, covariance type, fuzziness), phải liệt kê và giải thích ngắn gọn các variant liên quan.

### 2.4. Section 4 — Phương pháp / Methodology

**Mục đích:** Mô tả chi tiết implementation trong task này, có phân biệt rõ các loại decision.

**Bắt buộc có các nhánh sau:**

#### 4.1. Dữ liệu sử dụng

- File `final_clustering_dataset.parquet` (FE-06 output), shape (n_samples, n_features).
- File `customer_metadata.parquet` (FE-06 output), CustomerID mapping.
- SHA-256 input + version (`FE06-v1.0` mặc định trừ khi có override).
- Feature set: 14 features (liệt kê theo `feature_eligibility.csv`).

#### 4.2. Preprocessing

- KHÔNG thực hiện preprocessing trong ML-01 → ML-06. Nêu rõ đây là việc của FE-06.
- Verify input đã qua FE-06 pipeline (no NaN, no Inf, no constant).

#### 4.3. Algorithm / configuration

- Hyperparameters dùng trong task này (đọc từ `configs/clustering.yaml`).
- Random seed (nếu áp dụng — lấy từ `framework.random_seed.default` và
  `framework.random_seed.per_algorithm_override`).
- Library version (sklearn, scipy, numpy, custom).
- Distance metric (nếu áp dụng).

#### 4.4. Cách chạy

- Lệnh/entry point (`scripts/run_mlXX_*.py` hoặc tương đương).
- Workflow: load framework config → build ExperimentSpec → ExperimentRunner.run → write artifacts.

#### 4.5. Cách lưu kết quả

- Artifact paths theo `framework.output` config:
  - `cluster_labels_{experiment_id}.parquet`
  - `algorithm_output_{experiment_id}.parquet`
  - `experiment_log_{experiment_id}.json`
- Schema của mỗi artifact.

#### 4.6. Cách đảm bảo reproducibility

- `experiment_log` ghi input SHA, output SHA, config SHA, seed used, library versions.
- Random seed policy (`supports_random_state`, `random_seed_used`).
- Determinism flag (nếu applicable).

#### 4.7. Bảng phân loại decision (BẮT BUỘC)

Mỗi task phải có một bảng (hoặc nhiều bảng) ghi rõ:

| Loại decision | Nội dung | Status | Bằng chứng / Nguồn |
|---------------|----------|--------|---------------------|
| TECHNICALLY_IMPLEMENTED | Adapter của task này đã implement | Implemented | File path + test names |
| TECHNICALLY_IMPLEMENTED | Validation matrix theo FE-06 contract | Implemented | `tests/test_ml01_framework.py` |
| WORKING_ASSUMPTION | Hyperparameter default | Working assumption | `configs/clustering.yaml` |
| WORKING_ASSUMPTION | Seed policy | Working assumption | `framework.random_seed.default` |
| WORKING_ASSUMPTION | Working algorithm configuration | Working assumption | Tên config trong YAML |
| PENDING_REVIEW | Methodology decision ảnh hưởng nghiên cứu | MENTOR_REVIEW_PENDING | (sẽ list trong §11) |
| OUT_OF_SCOPE | Task không compute evaluation metrics | Explicit | EPIC-07/08 ownership |
| OUT_OF_SCOPE | Task không pick best algorithm | Explicit | AGENTS.md §2.5 |
| OUT_OF_SCOPE | Task không chạy controlled sweep | Explicit | EPIC-07 ownership |
| OUT_OF_SCOPE | Task không visualize cho so sánh nghiên cứu | Explicit | EPIC-08 ownership |
| OUT_OF_SCOPE | Task không profile segment | Explicit | EPIC-09 ownership |

**Phân biệt rõ:**

- `TECHNICALLY_IMPLEMENTED` ≠ `RESEARCH_APPROVED_FINAL`. (AGENTS.md §2.10)
- `WORKING_ASSUMPTION` ≠ methodology đã được mentor approve.
- `PENDING_REVIEW` cần mentor input mới có thể promote.

### 2.5. Section 5 — Implementation

**Mục đích:** Mô tả implementation ở mức nghiên cứu / kỹ thuật, không copy toàn bộ source code.

**Bắt buộc có:**

- Module/file chính (ví dụ: `src/customer_segmentation/clustering/kmeans.py`).
- Architecture (class hierarchy, base interface, registry pattern).
- Pipeline (load → validate → fit → write).
- Interface (`BaseClusterAlgorithm`, `AlgorithmRegistry.register("name")`).
- Configuration (`configs/clustering.yaml` section nào dùng cho task này).
- Input/output contract (matrix shape, label format, soft output format).
- Validation (các check từ `validation.py`).
- Artifacts (paths + schema + SHA).
- **Pseudocode / công thức / sơ đồ ASCII** khi thực sự giúp hiểu methodology.

**Không bắt buộc nhưng khuyến khích:**

- Sơ đồ class cho adapter (kế thừa `BaseClusterAlgorithm`).
- Bảng API (tên method, input, output).
- Ví dụ output JSON snippet (lấy từ experiment log thật).

### 2.6. Section 6 — Experimental Design Boundary

**Mục đích:** Ngăn trộn scope giữa các EPIC.

**Bắt buộc có 4 bảng rõ ràng:**

| | EPIC-06 (task này) | EPIC-07 | EPIC-08 | EPIC-09 |
|---|--------------------|---------|---------|---------|
| **Algorithm implementation** | ✅ Adapter code | — | — | — |
| **Configuration** | ✅ Working default | Sweep matrix | — | — |
| **Single-fit experiment** | ✅ Một (algo, k, seed) | Batch | — | — |
| **Sweep nhiều k** | ❌ | ✅ | — | — |
| **Sweep nhiều seed** | ❌ | ✅ | — | — |
| **Sweep nhiều config** | ❌ | ✅ | — | — |
| **Compute internal metrics** | ❌ | Partial (per fit) | ✅ Final | — |
| **Stability (ARI/AMI)** | ❌ | Generate | ✅ Aggregate | — |
| **Runtime comparison** | ❌ | Per-run time | ✅ Statistical summary | — |
| **Algorithm comparison** | ❌ | — | ✅ | — |
| **Diagnostic viz (dendrogram, k-distance, BIC)** | ⚠️ Optional per-task | — | — | — |
| **Research viz (silhouette, DBI, CH, elbow)** | ❌ | — | ✅ | — |
| **Segment profile / naming** | ❌ | — | — | ✅ |
| **Pick best algorithm** | ❌ | — | ✅ (sau full eval) | — |
| **Customer profiling** | ❌ | — | — | ✅ |

**Quy tắc:**

- Dấu ✅ = thuộc về EPIC đó.
- Dấu ❌ = KHÔNG thuộc về EPIC đó. KHÔNG được làm trong EPIC-06.
- Dấu ⚠️ = optional, thuộc quyền quyết định của task cụ thể (ví dụ ML-03 có thể
  vẽ dendrogram diagnostic, ML-04 có thể vẽ k-distance plot), nhưng KHÔNG tạo
  research-grade viz.
- Không có cell nào được phép vừa ✅ ở EPIC-06 vừa ✅ ở EPIC-08.

### 2.7. Section 7 — Kết quả thực tế

**Mục đích:** Trình bày kết quả execution thực tế (KHÔNG invent).

**Bắt buộc có:**

| Loại kết quả | Nguồn |
|--------------|--------|
| Số customers | `experiment_log_*.json` → `n_samples` |
| Số features | `feature_eligibility.csv` → `feature_count` |
| Hyperparameters | `experiment_log_*.json` → `hyperparameters` |
| Số clusters | `experiment_log_*.json` → `n_clusters` |
| Runtime | `experiment_log_*.json` → `execution_time` |
| Noise ratio (DBSCAN) | `cluster_labels_*.parquet` → `IsNoise == True` ratio |
| Probability/membership | `algorithm_output_*.parquet` (GMM/Fuzzy) |
| Số tests | `pytest` output cho `tests/test_mlXX_*.py` |
| Dataset version | `configs/clustering.yaml` → `framework.input.dataset_version` |
| SHA-256 (input/output/config) | `experiment_log_*.json` → các trường SHA |

**Quy tắc:**

- Mỗi con số **phải truy xuất được** về artifact/report/config cụ thể.
- **KHÔNG tự tạo số liệu** (AGENTS.md §2.1, §2.7).
- **KHÔNG** báo cáo metric đánh giá (silhouette, DBI, CH, ARI/AMI, ...) vì
  đó là scope EPIC-07/08. Nếu metric được tính trong diagnostic, phải ghi rõ
  `diagnostic_only` và KHÔNG dùng để kết luận.

### 2.8. Section 8 — Công thức và ký hiệu

**Mục đích:** Chuẩn hóa notation cho các algorithm.

**Bắt buộc có:**

Mỗi algorithm có objective/function riêng; phải ghi công thức với:

- **Ký hiệu** (notation): `x_i`, `μ_k`, `Σ`, `c`, `m`, `u_ik`, `d(i,j)`, ...
- **Ý nghĩa** của mỗi ký hiệu (1 dòng).
- **Objective** — mục tiêu tối ưu.
- **Thuật toán tối ưu** cái gì (gradient descent, EM, Lloyd's algorithm, ...).

**Áp dụng cho từng task:**

- ML-01: không có objective riêng; framework-level formulas (information retrieval, registry key).
- ML-02 (K-Means): `J = Σᵢ ‖x_i - μ_{c_i}‖²`, Lloyd's algorithm, khoảng cách Euclidean.
- ML-03 (Hierarchical): linkage formula cho ward/complete/average/single.
- ML-04 (DBSCAN): density-reachability, eps neighborhood, min_samples, core/border/noise.
- ML-05 (GMM): likelihood, EM (E-step, M-step), covariance types.
- ML-06 (Fuzzy C-Means): membership update, objective function với fuzziness parameter `m`.

**Quy tắc:**

- Công thức dùng LaTeX-friendly Markdown (e.g., `$J = \sum_i \|x_i - \mu_{c_i}\|^2$`) — hoặc plain math notation.
- Không đưa công thức chỉ để trang trí — phải giải thích objective.
- Tránh copy từ textbook — chỉ giữ phần phục vụ cho nghiên cứu.

### 2.9. Section 9 — Visualization boundary

**Mục đích:** Ngăn visualization scope creep giữa các EPIC.

**Bắt buộc có 3 bảng phân chia ownership:**

#### 9.1. EPIC-06 (diagnostic / algorithm-specific)

EPIC-06 sở hữu các visualization **diagnostic / algorithm-specific** phục vụ
hiểu thuật toán:

| Task | Visualization (nếu có) | Loại | Status |
|------|------------------------|------|--------|
| ML-01 | (không có — framework only) | — | — |
| ML-02 | Elbow / WCSS diagnostic plot | Diagnostic | Optional |
| ML-03 | Dendrogram, linkage matrix visualization, distance heatmap | Diagnostic | Optional |
| ML-04 | k-distance plot để chọn eps | Diagnostic | Optional |
| ML-05 | BIC / AIC curve theo số components | Diagnostic | Optional |
| ML-06 | Membership distribution per cluster | Diagnostic | Optional |

Quy tắc cho diagnostic viz:

- Phải ghi rõ `diagnostic_only` trong tên file / report.
- KHÔNG dùng để kết luận best algorithm / best k.
- KHÔNG đặt trong `reports/epic08/` (EPIC-08 territory).

#### 9.2. EPIC-08 (research comparison)

EPIC-08 sở hữu các visualization nghiên cứu:

- Silhouette plot / silhouette comparison across algorithms & k.
- Davies-Bouldin comparison.
- Calinski-Harabasz comparison.
- WCSS / Elbow plot (cho analysis, không phải diagnostic).
- Runtime comparison across algorithms.
- Stability (ARI / AMI) distribution plot.
- Parameter sensitivity heatmap.
- Algorithm comparison (multi-metric dashboard).

#### 9.3. EPIC-09 (segment analysis)

EPIC-09 sở hữu các visualization phục vụ phân tích customer segments:

- Segment size (số customer / segment).
- RFM profile (radar / heatmap) theo segment.
- Feature distribution theo segment.
- Boxplot (numeric features × segments).
- Segment characteristics table / chart.
- Customer profiles (per-segment summary).

#### 9.4. Quy tắc tổng quát

- KHÔNG tạo visualization trong `reports/mlXX/` (trừ diagnostic nếu task cho phép).
- KHÔNG tự tạo hình trong Documentation Contract — chỉ list loại viz thực sự
  được tạo trong implementation.
- Mỗi visualization thực sự tạo phải có SHA-256 / file path / generation metadata.

### 2.10. Section 10 — Verification

**Mục đích:** Chứng minh task đã chạy đúng, KHÔNG chỉ ghi "đã test".

**Bắt buộc có:**

#### 10.1. Tests

| Test category | Loại test | Kết quả thực tế |
|---------------|-----------|-----------------|
| Unit tests cho adapter | `tests/test_mlXX_*.py` | Pass count + test names |
| Integration test với FE-06 dataset | Toy/synthetic adapter + real FE-06 dataset | Pass / skip reason |
| Framework test (ML-01) | `tests/test_ml01_framework.py` | Pass count |
| Determinism test | Same seed → same labels | Pass / Fail |

#### 10.2. Lint

- `ruff check .` → số errors / warnings / pass.

#### 10.3. Format

- `black --check .` → pass / fail.

#### 10.4. Reproducibility

- Input SHA-256 unchanged.
- Output SHA-256 matches expected.
- Config SHA-256 recorded.
- Library versions recorded.

#### 10.5. Input integrity

- Matrix không có NaN, Inf, constant features.
- Customer metadata alignment đúng.

#### 10.6. Output integrity

- Cluster labels shape đúng `(n_samples,)`.
- Cluster labels dtype đúng (int64).
- Algorithm-specific outputs đúng shape (GMM probabilities, Fuzzy membership).

#### 10.7. Regression status (nếu phù hợp)

- Pre-existing tests còn pass.
- Không có test bị skip không giải thích.

**Quy tắc:**

- **KHÔNG** ghi "đã test" mà không có số liệu.
- Pre-existing failures phải được ghi rõ trong completion summary của task,
  KHÔNG sửa ngoài scope.

### 2.11. Section 11 — Mentor Review

**Mục đích:** Bảng tổng hợp các decision cần mentor review.

**Template bắt buộc:**

| ID | Nội dung cần review | Loại | Trạng thái |
|----|---------------------|------|------------|
| ML-0X-XX | (mô tả decision) | Methodology / Engineering / Scope | PENDING_REVIEW / DOCUMENTED / CONFIRMED |

**Phân loại:**

- **Methodology** — ảnh hưởng research methodology, cần mentor review + ADR.
  Ví dụ: chọn thuật toán, chọn metric, chọn distance, covariance type, fuzziness parameter.
- **Engineering** — chỉ implementation detail, không ảnh hưởng experimental design.
  Ví dụ: file naming convention, log format, artifact path template.
- **Scope** — phân chia trách nhiệm giữa các EPIC.

**Quy tắc:**

- **KHÔNG** đưa engineering detail nhỏ thành methodology decision.
- Methodology decision phải được gắn với một ADR tương ứng (sẽ tạo sau nếu cần).
- Engineering decision có thể promote final cùng EPIC sau khi reviewer xác nhận.

### 2.12. Section 12 — Kết luận

**Mục đích:** Tổng hợp trạng thái task, không kết luận "best".

**Bắt buộc có 4 phần:**

#### 12.1. Đã hoàn thành

Những gì implementation thực sự làm được, dẫn chứng bằng evidence (file path, SHA, test result).

#### 12.2. Chưa hoàn thành

Những gì task chưa làm (đã nằm trong scope nhưng chưa triển khai, hoặc deferred).

#### 12.3. Pending Mentor Review

Các vấn đề cần mentor xác nhận — liệt kê theo Section 11.

#### 12.4. Chuyển tiếp sang task tiếp theo

- Output của task này là input cho task / EPIC nào.
- Contract giữa task này và consumer (downstream).

**Quy tắc cuối cùng của Section 12:**

- **KHÔNG** viết "best", "optimal", "recommended algorithm", "winner" nếu
  chưa thuộc scope và chưa có controlled evaluation (AGENTS.md §2.5).
- **KHÔNG** gọi WORKING_ASSUMPTION là final methodology.

---

## 3. Lý thuyết bắt buộc cho từng task

Phần này liệt kê các concept mà Mentor document của mỗi task **PHẢI giải thích**.
Không cần viết giáo trình đầy đủ; chỉ cần giải thích đủ để mentor hiểu
implementation.

### 3.1. ML-01 — Clustering Experiment Framework

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **Clustering experiment framework** | Lớp abstraction cho phép chạy nhiều thuật toán clustering trên cùng dataset với cùng schema kết quả. |
| **Experiment reproducibility** | Cách framework đảm bảo cùng input + cùng config + cùng seed → cùng output (trong cùng env). |
| **Standardized pipeline** | Quy trình thống nhất: load → validate → fit → write artifacts. |
| **Algorithm abstraction** | `BaseClusterAlgorithm` interface; mỗi adapter free to expose algorithm-specific outputs. |
| **Algorithm registry** | In-process map `name → adapter class`. Tránh duplicate registration. |
| **Configuration** | YAML schema, fail-fast loader, framework section vs algorithm section. |
| **Experiment result schema** | `ClusterResult` + `MetricsResult` + `ExperimentResult` với algorithm-family-specific fields. |
| **Validation policy** | Matrix checks, customer alignment, identifier leakage. |
| **Reproducibility metadata** | Input SHA, output SHA, config SHA, seed used, library versions. |
| **Logging & artifact management** | File/console logger; artifact paths. |

### 3.2. ML-02 — K-Means

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **K-Means algorithm** | Hard clustering dựa trên centroid; assign mỗi point về centroid gần nhất. |
| **Centroid** | Trung bình cộng của tất cả các points trong cluster. |
| **Distance metric** | Mặc định Euclidean; ảnh hưởng đến kết quả. |
| **Assignment step** | Mỗi point → cluster có centroid gần nhất. |
| **Centroid update step** | Tính lại centroid = mean của cluster. |
| **Objective function (WCSS / Inertia)** | `J = Σᵢ ‖x_i - μ_{c_i}‖²` — tổng bình phương khoảng cách nội cluster. |
| **Initialization** | `k-means++` (default trong sklearn) hoặc random. |
| **Convergence** | Dừng khi centroid không đổi hoặc đạt `max_iter`. |
| **Role of K** | Số cluster phải chọn trước; EPIC-07 sẽ sweep `k_range`. |
| **n_init** | Số random restart; lấy `max(inertia)` across restarts. |
| **Random initialization** | K-Means có thể cho kết quả khác nhau giữa các lần chạy nếu không fix seed. |
| **Hard clustering** | Mỗi point thuộc đúng 1 cluster (không có probability). |
| **Sensitivity to scaling** | K-Means dùng khoảng cách → bị dominated bởi feature có variance lớn (đã mitigate bởi FE-06 scaling). |

### 3.3. ML-03 — Hierarchical (Agglomerative) Clustering

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **Hierarchical clustering** | Xây cây phân cấp (dendrogram); agglomerative (bottom-up) hoặc divisive (top-down). |
| **Agglomerative clustering** | Bắt đầu mỗi point là 1 cluster; merge 2 cluster gần nhất ở mỗi bước. |
| **Distance matrix** | Ma trận khoảng cách giữa tất cả các cặp points / clusters. |
| **Linkage criteria** | Cách tính khoảng cách giữa 2 cluster: single, complete, average, Ward. |
| **Single linkage** | `d(C1, C2) = min_{x∈C1, y∈C2} d(x, y)` — dễ bị chaining. |
| **Complete linkage** | `d(C1, C2) = max_{x∈C1, y∈C2} d(x, y)` — tránh chaining nhưng nhạy với outliers. |
| **Average linkage** | `d(C1, C2) = mean_{x∈C1, y∈C2} d(x, y)` — compromise. |
| **Ward linkage** | Minimize increase in total WCSS khi merge 2 cluster; thường dùng với Euclidean. |
| **Cluster merging** | Quy trình merge đệ quy cho đến khi còn 1 cluster (hoặc đạt `n_clusters`). |
| **Dendrogram** | Cây visualization quá trình merge. Cutting dendrogram ở một height → k clusters. |
| **Cutting dendrogram** | Lấy `k` cluster bằng cách cắt dendrogram ở height tương ứng. |
| **Computational complexity** | O(n³) hoặc O(n² log n) — không scale với dataset lớn (vẫn OK cho n=4371). |
| **Distance metric** | Euclidean (mặc định Ward); có thể precomputed. |
| **Determinism** | Agglomerative là deterministic (không có random state). |

### 3.4. ML-04 — DBSCAN

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **Density-based clustering** | Cluster = vùng dày đặc; tách bởi vùng thưa. |
| **Epsilon neighborhood** | Vùng bán kính `eps` quanh 1 point. |
| **min_samples** | Số tối thiểu points (kể cả point đó) trong eps neighborhood để point được coi là core. |
| **Core point** | Point có ≥ min_samples points trong eps neighborhood. |
| **Border point** | Point không phải core nhưng nằm trong eps neighborhood của 1 core point. |
| **Noise (outlier) point** | Point không phải core, không phải border → label `-1` (sklearn convention). |
| **Density reachability** | Point A density-reachable từ B nếu tồn tại chuỗi core points nối A → B trong eps neighborhood. |
| **Density connectivity** | 2 points density-connected nếu cùng nằm trong eps neighborhood của 1 core point. |
| **DBSCAN behavior** | Phát hiện cluster có hình dạng bất kỳ; xử lý noise; không cần chọn k trước. |
| **Sensitivity to eps & min_samples** | Hai hyperparameter quan trọng; small eps → nhiều noise; large eps → ít cluster. |
| **k-distance plot** | Diagnostic để chọn eps: sort khoảng cách từ mỗi point đến k-th nearest neighbor, tìm "elbow". |
| **Noise ratio** | Tỷ lệ points được label `-1`; phản ánh mức độ tách biệt của data. |
| **Hard clustering** | Mỗi point thuộc 1 cluster HOẶC là noise (KHÔNG có soft probability). |
| **Determinism** | DBSCAN không có random state; deterministic fit. |

### 3.5. ML-05 — Gaussian Mixture Model (GMM)

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **Gaussian distribution** | Phân phối chuẩn n-chiều, parameterized bởi mean vector và covariance matrix. |
| **Mixture model** | Distribution = tổng có trọng số của nhiều Gaussian components. |
| **Latent cluster** | Cluster gán cho mỗi point qua latent variable `z_i ∈ {1, ..., K}`. |
| **EM algorithm** | Expectation-Maximization; iterative procedure để estimate parameters. |
| **E-step** | Tính posterior probability `p(z_i | x_i, θ)` cho mỗi point. |
| **M-step** | Update parameters (weights, means, covariances) để maximize likelihood. |
| **Covariance types** | `full`, `tied`, `diag`, `spherical` — ảnh hưởng số parameters và flexibility. |
| **Soft clustering** | Mỗi point có xác suất thuộc mỗi cluster; `argmax` → hard label. |
| **Posterior probability** | Output của GMM: `P(cluster_k | x_i)`, shape `(n_samples, n_components)`. |
| **Log-likelihood** | Objective để maximize. |
| **BIC / AIC** | Model selection criteria; EPIC-06 có thể dùng diagnostic; EPIC-08 mới chính thức compare. |
| **Initialization** | `kmeans` (default trong sklearn) hoặc random. |
| **Random state** | GMM có random state (initialization). |
| **n_init** | Số random restart cho initialization. |
| **Convergence** | Dừng khi log-likelihood không tăng đáng kể. |

### 3.6. ML-06 — Fuzzy C-Means + Algorithm Baseline

| Concept | Mô tả ngắn cần có |
|---------|-------------------|
| **Fuzzy clustering** | Mỗi point có *membership degree* cho mỗi cluster, không phải hard label. |
| **Membership degree** | `u_ik ∈ [0, 1]` — mức độ point `i` thuộc cluster `k`. |
| **Fuzzy partition** | Ma trận membership `U` shape `(n_samples, c)`; mỗi row sum = 1. |
| **Centroid (fuzzy)** | `v_k = Σᵢ (u_ik)^m · x_i / Σᵢ (u_ik)^m`. |
| **Fuzziness parameter `m`** | Tham số điều khiển "độ mờ"; `m=1` → hard K-Means; `m→∞` → uniform membership. |
| **Membership update** | `u_ik = 1 / Σⱼ (d_ik / d_ij)^(2/(m-1))`. |
| **Centroid update** | Như trên (weighted mean). |
| **Objective function** | `J_m = Σᵢ Σₖ (u_ik)^m · d(x_i, v_k)²`. |
| **Distance metric** | Thường Euclidean; có thể generalize. |
| **Convergence** | Dừng khi membership matrix không đổi (hoặc `max_iter`). |
| **Comparison with hard clustering** | Fuzzy cho biết "không chắc chắn" points (boundary giữa 2 cluster); hard K-Means ép về 1 cluster. |
| **Algorithm baseline** | Có thể là K-Means (làm baseline); hoặc K-Means + so sánh với Fuzzy C-Means cùng `c`. |
| **Implementation choice** | Library: `scikit-fuzzy` (skfuzzy) hoặc custom implementation (do sklearn không có Fuzzy C-Means sẵn). |
| **Soft clustering** | Output = membership matrix; có thể derive hard label bằng `argmax`. |

---

## 4. Formula & notation chuẩn

Notation chuẩn cho toàn EPIC-06 (dùng xuyên suốt các task):

| Symbol | Ý nghĩa |
|--------|----------|
| `n` | Số customers (samples) |
| `p` | Số features |
| `X ∈ ℝ^(n×p)` | Feature matrix |
| `x_i ∈ ℝ^p` | Vector feature của customer `i` |
| `K` hoặc `k` hoặc `c` | Số cluster (tùy algorithm) |
| `μ_k ∈ ℝ^p` | Centroid của cluster `k` (K-Means, Fuzzy C-Means) |
| `c_i ∈ {0, ..., K-1}` | Cluster label của point `i` (hard clustering) |
| `Σ_k ∈ ℝ^(p×p)` | Covariance matrix của component `k` (GMM) |
| `π_k` | Mixing weight của component `k` (GMM) |
| `u_ik` | Membership degree của point `i` trong cluster `k` (Fuzzy) |
| `m` | Fuzziness parameter (Fuzzy C-Means) |
| `d(x_i, x_j)` | Khoảng cách giữa 2 points |
| `eps` | Epsilon neighborhood radius (DBSCAN) |
| `min_samples` | Minimum points in eps neighborhood (DBSCAN) |
| `seed` / `random_state` | Random seed |

### 4.1. Formulas cho mỗi task

| Task | Objective / formula | Algorithm |
|------|---------------------|-----------|
| ML-02 | `J = Σᵢ ‖x_i - μ_{c_i}‖²` | Lloyd's algorithm (assign + update) |
| ML-03 | `d(C₁, C₂)` per linkage | Agglomerative merging |
| ML-04 | (no objective to minimize; density-based) | Eps neighborhood reachability |
| ML-05 | `log L(θ) = Σᵢ log Σₖ π_k · 𝒩(x_i; μ_k, Σ_k)` | EM (E-step + M-step) |
| ML-06 | `J_m = Σᵢ Σₖ (u_ik)^m · ‖x_i - v_k‖²` | Membership + centroid update |

---

## 5. Provenance rule

Mọi con số trong Mentor document phải truy xuất được. Template:

```
[Con số]  -- nguồn -->  [Artifact / Report / Config path]  -- field -->  [Tên field]
```

**Ví dụ:**

- "n_clusters = 4"  -- nguồn --> `data/processed/clustering_experiments/experiment_log_ML-02-KMeans-k4-seed42.json`  -- field --> `cluster_result.n_clusters`
- "execution_time = 0.42s"  -- nguồn --> `experiment_log_*.json`  -- field --> `execution_time`
- "noise_ratio = 0.06"  -- nguồn --> `cluster_labels_*.parquet`  -- field --> `IsNoise.sum() / len(IsNoise)`

**Quy tắc:**

- Nếu không tìm được nguồn → KHÔNG ghi con số đó.
- Có thể trích dẫn bằng code snippet thực tế từ artifact.

---

## 6. Decision-status taxonomy

Mỗi decision trong Mentor document phải dùng đúng một trong các status sau
(nhất quán với AGENTS.md §2.5, §2.10):

| Status | Định nghĩa | Promotion cần gì |
|--------|-------------|------------------|
| `TECHNICALLY_IMPLEMENTED` | Code đã implement, tests pass, artifacts đầy đủ. | (không cần) |
| `WORKING_ASSUMPTION` | Default working config chưa được mentor approve. | Mentor review + ADR |
| `ELIGIBLE_WORKING_ASSUMPTION` | Feature/option được include trong working default nhưng chưa promote final. | Mentor review + ADR |
| `DIAGNOSTIC_ONLY` | Chỉ mang tính báo cáo; không ảnh hưởng quyết định. | (tùy context) |
| `PENDING_REVIEW` | Decision phụ thuộc mentor input. | Mentor review + ADR |
| `MENTOR_REVIEW_PENDING` | Đồng nghĩa `PENDING_REVIEW` trong ML-01 context. | Mentor review + ADR |
| `RESEARCH_APPROVED_FINAL` | Methodology đã được mentor/human researcher approve. | (đã có) |
| `OUT_OF_SCOPE` | Cố ý chưa làm vì thuộc EPIC khác. | (không cần — ghi rõ EPIC owner) |

**Quy tắc:**

- **KHÔNG** dùng: `best`, `worst`, `recommended`, `optimal`, `superior`, `final`, `winner`.
- `RETAIN_CANDIDATE` **KHÔNG** đồng nghĩa `FINAL` (AGENTS.md §2.5).

---

## 7. Boundary discipline — không trộn scope EPIC

### 7.1. EPIC-06 scope (ML-01 → ML-06)

| Cho phép | KHÔNG cho phép |
|----------|----------------|
| Implement algorithm adapter (code) | Compute evaluation metrics (silhouette / DBI / CH / WCSS / ARI / AMI) chính thức |
| Single-fit experiment (1 algo × 1 k × 1 seed) | Sweep nhiều k (EPIC-07) |
| Configuration cho working default | Final methodology approval (mentor) |
| Algorithm-specific artifact schema | Pick best algorithm / best k |
| Diagnostic viz (per-task, optional) | Research comparison viz (silhouette plot, comparison dashboard) |
| Algorithm-specific documentation (theory, formula) | Segment profiling / segment naming |
| Run validation tests | Mutate FE-06 output |
| Run experiment → save labels + log | Commit / push / PR |

### 7.2. EPIC-07 scope

- Controlled experiment design.
- Sweep matrix (algorithm × k × seed × config).
- Batch experiment execution.
- Per-run metrics.

### 7.3. EPIC-08 scope

- Final evaluation metrics (silhouette, DBI, CH, WCSS, ...).
- Stability analysis (ARI/AMI across seeds).
- Runtime comparison.
- Algorithm comparison (ranking chỉ trong EPIC-08 sau khi đã có full eval).
- Research comparison visualization (silhouette plot, dashboard).
- Methodology decision về "best algorithm" (nếu có).

### 7.4. EPIC-09 scope

- Customer segment profiling / analysis.
- Segment naming (Champions, Loyal, ...).
- Segment size distribution.
- RFM profile per segment.
- Feature distribution per segment.

### 7.5. Quy tắc khi viết Mentor document

Khi gặp edge case nằm giữa 2 EPIC:

- **Mặc định:** Thuộc EPIC sau.
- **Trừ khi** task hiện tại thực sự cần làm nó (ví dụ: ML-03 cần compute
  linkage matrix để cắt dendrogram — đó là implementation, không phải
  evaluation).
- **Luôn ghi rõ** ownership trong §6 của Mentor document.

---

## 8. Information cần bảo toàn trong quá trình triển khai ML-01 → ML-06

Đây là danh sách evidence phải được **ghi vào repo** trong quá trình triển
khai, để cuối EPIC có thể viết Mentor document một lần. Agent phải đảm bảo
các evidence này tồn tại và truy xuất được.

### 8.1. Configuration evidence

| File | Bắt buộc ghi |
|------|--------------|
| `configs/clustering.yaml` | Toàn bộ: `framework.*`, `algorithms.*` (per-task hyperparameters), `preprocessing.*` |
| `configs/experiment.yaml` | Random seed, dataset role, pipeline stages, evaluation config |

### 8.2. Code evidence

| File | Bắt buộc ghi |
|------|--------------|
| `src/customer_segmentation/clustering/base.py` | `BaseClusterAlgorithm` docstring |
| `src/customer_segmentation/clustering/registry.py` | `AlgorithmRegistry` docstring + naming convention |
| `src/customer_segmentation/clustering/result.py` | `ClusterResult`, `MetricsResult`, `ExperimentResult` docstrings |
| `src/customer_segmentation/clustering/validation.py` | Validation rules docstring |
| `src/customer_segmentation/clustering/runner.py` | Experiment lifecycle docstring |
| `src/customer_segmentation/clustering/artifacts.py` | Artifact writing rules |
| `src/customer_segmentation/clustering/logging_utils.py` | Logging format |
| `src/customer_segmentation/clustering/config.py` | Config loader |
| `src/customer_segmentation/clustering/kmeans.py` | K-Means adapter (sau ML-02) |
| `src/customer_segmentation/clustering/kmedoids.py` | K-Medoids adapter (sau ML-02) |
| `src/customer_segmentation/clustering/agglomerative.py` | Hierarchical adapter (sau ML-03) |
| `src/customer_segmentation/clustering/dbscan.py` | DBSCAN adapter (sau ML-04) |
| `src/customer_segmentation/clustering/gmm.py` | GMM adapter (sau ML-05, nếu chưa có) |
| `src/customer_segmentation/clustering/fuzzy_cmeans.py` | Fuzzy C-Means adapter (sau ML-06) |

### 8.3. Test evidence

| File | Bắt buộc ghi |
|------|--------------|
| `tests/test_ml01_framework.py` | Framework test (đã có — 59 tests) |
| `tests/test_ml02_kmeans.py` | K-Means adapter test (sau ML-02) |
| `tests/test_ml03_hierarchical.py` | Hierarchical adapter test (sau ML-03) |
| `tests/test_ml04_dbscan.py` | DBSCAN adapter test (sau ML-04) |
| `tests/test_ml05_gmm.py` | GMM adapter test (sau ML-05) |
| `tests/test_ml06_fuzzy.py` | Fuzzy C-Means adapter test (sau ML-06) |
| `tests/test_input_integrity.py` | Input integrity (đã có) |

### 8.4. Artifact evidence (per experiment run)

| File | Nội dung |
|------|---------|
| `data/processed/clustering_experiments/cluster_labels_{experiment_id}.parquet` | CustomerID + ClusterLabel (+ IsNoise) (+ Probability columns nếu soft) |
| `data/processed/clustering_experiments/algorithm_output_{experiment_id}.parquet` | Soft probability / membership matrix (nếu có) |
| `data/processed/clustering_experiments/experiment_log_{experiment_id}.json` | Full ExperimentResult.to_dict() |
| `reports/mlXX/*.csv`, `*.md` | Algorithm-specific reports (diagnostic) |

### 8.5. Metadata evidence (mỗi experiment log JSON phải có)

- `experiment_id`, `status` (SUCCESS / FAILED)
- `algorithm`, `algorithm_version`, `algorithm_family`
- `dataset_version` (e.g., `FE06-v1.0`)
- `dataset_sha256`, `input_path`, `metadata_path`
- `feature_set`, `feature_count`, `n_samples`
- `hyperparameters`, `random_seed`, `random_seed_used`
- `n_clusters`, `cluster_labels_shape`, `cluster_labels_dtype`
- `execution_time`, `timestamp`
- `cluster_result` (algorithm-specific output: soft_probabilities / soft_membership / noise_count / ...)
- `metrics` (TẤT CẢ `None` trong ML-01 → ML-06 — chỉ schema)
- `artifact_paths`
- `error` (nếu FAILED)
- `platform`, `library_versions`
- `scope_boundaries`, `pending_review_notes`, `assumptions`
- `config_source`, `config_sha256`

### 8.6. SHA-256 chain evidence

Mỗi task phải ghi:

- Input SHA-256: `customer_candidates.parquet`, `final_clustering_dataset.parquet`, `customer_metadata.parquet`.
- Config SHA-256: `configs/clustering.yaml`.
- Output SHA-256: các artifact của task.
- Library versions: numpy, pandas, scipy, scikit-learn, pyarrow, skfuzzy (nếu dùng).

### 8.7. Decision log evidence

Mỗi task phải cập nhật vào completion summary (KHÔNG tạo Mentor document):

- Tên decision.
- Status: `WORKING_ASSUMPTION` / `PENDING_REVIEW` / `OUT_OF_SCOPE` / `TECHNICALLY_IMPLEMENTED`.
- Lý do working assumption.
- Evidence (file path, line number, SHA).

---

## 9. Verification checklist (mỗi task)

Trước khi coi một task là `TECHNICALLY_IMPLEMENTED`, verify:

### 9.1. Code-level

- [ ] Adapter subclass `BaseClusterAlgorithm`.
- [ ] Adapter `name`, `version`, `family` attributes đúng.
- [ ] Adapter `fit(X)` returns `ClusterResult` với đầy đủ fields.
- [ ] Adapter `supports_random_state()` trả về giá trị đúng.
- [ ] Adapter KHÔNG mutate input.
- [ ] Adapter registered in `AlgorithmRegistry`.
- [ ] Algorithm-specific fields populated đúng (e.g., `noise_count` cho DBSCAN,
      `soft_probabilities` cho GMM, `soft_membership` cho Fuzzy C-Means).

### 9.2. Test-level

- [ ] Unit tests cho adapter pass.
- [ ] Integration test với FE-06 dataset pass (nếu applicable).
- [ ] Determinism test pass (cùng seed → cùng labels).
- [ ] `pytest tests/test_ml0X_*.py` → all pass.
- [ ] KHÔNG skip tests không giải thích.

### 9.3. Lint / format

- [ ] `ruff check .` pass.
- [ ] `black --check .` pass.

### 9.4. Artifact-level

- [ ] `cluster_labels_*.parquet` đúng schema, đúng shape.
- [ ] `algorithm_output_*.parquet` (nếu applicable) đúng schema.
- [ ] `experiment_log_*.json` đầy đủ metadata.
- [ ] Customer metadata alignment đúng (positional).
- [ ] Cluster labels row order = customer_metadata row order.

### 9.5. Reproducibility

- [ ] Input SHA-256 unchanged sau experiment.
- [ ] Output SHA-256 ghi trong experiment log.
- [ ] Config SHA-256 ghi trong experiment log.
- [ ] Library versions ghi trong experiment log.

### 9.6. Boundary

- [ ] KHÔNG có metric evaluation trong experiment log.
- [ ] KHÔNG có "best algorithm" claim trong code hoặc comments.
- [ ] KHÔNG mutate FE-06 output.
- [ ] KHÔNG visualize research-grade plots (silhouette plot, comparison dashboard).
- [ ] KHÔNG profile / name segments.

### 9.7. Documentation

- [ ] Module docstring đầy đủ (mục đích, scope, references).
- [ ] Function docstring + type hints.
- [ ] Completion summary viết sau khi task xong (KHÔNG phải Mentor document).

---

## 10. Quy tắc cho toàn bộ EPIC-06

Trong suốt ML-01 → ML-06:

1. **KHÔNG** commit / push / PR (AGENTS.md §2.11).
2. **KHÔNG** tự thay đổi FE-06 output.
3. **KHÔNG** tự chọn algorithm "tốt nhất".
4. **KHÔNG** ranking algorithm.
5. **KHÔNG** thực hiện evaluation chính thức (silhouette, DBI, CH, ARI, AMI) — đó là EPIC-07/08.
6. **KHÔNG** thực hiện controlled experiment (sweep nhiều k / seed) — đó là EPIC-07.
7. **KHÔNG** làm customer profiling / segment naming — đó là EPIC-09.
8. **KHÔNG** invent số liệu.
9. **KHÔNG** biến WORKING_ASSUMPTION thành approved methodology.
10. **KHÔNG** viết Mentor document riêng cho từng task trong quá trình triển khai.

---

## 11. Template file paths cho sáu Mentor document

Khi viết Mentor document cuối cùng, sử dụng các đường dẫn sau:

```
docs/research/ML01_Clustering_Experiment_Framework.md
docs/research/ML02_KMeans.md
docs/research/ML03_Hierarchical_Clustering.md
docs/research/ML04_DBSCAN.md
docs/research/ML05_GMM.md
docs/research/ML06_Fuzzy_CMeans_Algorithm_Baseline.md
```

Lưu ý: file `docs/research/ML01_clustering_experiment_framework.md` hiện tại
là **Implementation Notes** (đã có sẵn). Khi viết Mentor document cuối,
file này sẽ được **tái cấu trúc** theo 12-section template trong §2.

---

## 12. Quy trình viết Mentor document cuối cùng

Sau khi cả 6 task xong:

1. Agent thu thập tất cả evidence từ §8.
2. Agent viết 6 file Mentor document theo §2.
3. Agent KHÔNG viết các phần mà không có evidence — bỏ trống và note `OUT_OF_SCOPE`.
4. Agent verify 12 section đầy đủ theo checklist §9.
5. Agent báo cáo theo AGENTS.md §7:
   - Files created / modified
   - Implementation summary
   - Tests
   - Lint
   - Format
   - Assumptions
   - PENDING_REVIEW decisions
   - Remaining issues
   - Scope explicitly NOT performed

**KHÔNG** tự ý gộp / sửa / bỏ qua các quyết định PENDING_REVIEW đã ghi nhận
trong suốt EPIC-06.

---

## 13. Glossary

| Thuật ngữ | Ý nghĩa |
|-----------|----------|
| **Adapter** | Class implement `BaseClusterAlgorithm` cho 1 thuật toán cụ thể (K-Means adapter, DBSCAN adapter, ...). |
| **Algorithm family** | Phân loại thuật toán: hard / density_based / model_based / fuzzy / other. |
| **Algorithm output** | Artifact lưu output đặc thù của thuật toán (soft probability, membership matrix). |
| **Cluster labels** | Vector `(n_samples,)` gán mỗi customer về 1 cluster ID. |
| **ClusterResult** | Dataclass trong ML-01 chứa output của 1 algorithm fit. |
| **ExperimentResult** | Dataclass trong ML-01 chứa toàn bộ metadata của 1 experiment run. |
| **ExperimentRunner** | Class điều phối 1 experiment end-to-end (load → validate → fit → write). |
| **Framework** | Lớp abstraction trong ML-01 cho phép chạy nhiều adapter với cùng schema. |
| **Hard clustering** | Mỗi point thuộc đúng 1 cluster. |
| **Soft clustering** | Mỗi point có probability / membership cho mỗi cluster. |
| **Noise label** | Sentinel value cho noise points (DBSCAN); default `-1`. |
| **Random state** | Seed cho random number generator; một số algorithm consume, một số không. |
| **Reproducibility metadata** | SHA-256, library versions, config SHA, seed. |
| **Soft probabilities** | Posterior probability matrix (GMM). |
| **Soft membership** | Fuzzy membership matrix (Fuzzy C-Means). |

---

## 14. Liên kết với tài liệu khác

| Concern | Source of truth |
|---------|-----------------|
| Global cross-phase rules | `AGENTS.md` |
| Final clustering dataset | `docs/research/FE06_Transformation_Final_Dataset.md` |
| Candidate features | `docs/research/FE05_Customer_Feature_Engineering.md` |
| Customer base | `docs/research/FE04_Customer_Level_Aggregation.md` |
| Framework details (current) | `docs/research/ML01_clustering_experiment_framework.md` |
| Configuration | `configs/clustering.yaml` |
| Reproducibility metadata | `reports/<stage>/<stage>_run.json` |

---

## 15. Versioning

- Contract version: `EPIC06-DOCCONTRACT-v1.0`.
- Status: `ACTIVE` (chưa phải `RESEARCH_APPROVED_FINAL`).
- Promotion sang `RESEARCH_APPROVED_FINAL`: cần mentor review sau khi
  sáu Mentor document được viết.

---

*Documentation Contract này là specification để chuẩn hóa cấu trúc tài liệu
Mentor cho ML-01 → ML-06. Nó KHÔNG phải Mentor document cuối cùng và KHÔNG
thay thế nội dung của các tài liệu research hiện có (FE-04, FE-05, FE-06,
ML-01 implementation notes). Sáu Mentor document sẽ được viết một lần sau
khi toàn bộ EPIC-06 hoàn thành, theo đúng 12-section template và
provenance rule ở đây.*
