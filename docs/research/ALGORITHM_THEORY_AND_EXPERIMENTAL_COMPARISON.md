# Algorithm Theory, Application và Experimental Comparison
## Tổng hợp 5 thuật toán clustering trong nghiên cứu Customer Segmentation

> **Loại tài liệu:** Research synthesis / Documentation.
> **Phạm vi:** EPIC-06 (adapters), EPIC-07 (controlled experiments), EPIC-08 (evaluation), EPIC-09 (profiling).
> **Trạng thái methodology:** `METHODOLOGY_LOCKED` (per ADR-0003, ADR-0004).
> **Nguồn evidence:** EXP-01 → EXP-05, EVA-01 → EVA-05, CP-01 → CP-05.
> **Ngôn ngữ:** Tiếng Việt. Code/identifier/file name giữ nguyên convention English hiện có của repository.

Tài liệu này tổng hợp lý thuyết, cách áp dụng vào bài toán customer segmentation và số liệu thực nghiệm đã có cho 5 thuật toán:

1. K-Means
2. Agglomerative Clustering (Hierarchical)
3. DBSCAN
4. Gaussian Mixture Model (GMM)
5. Fuzzy C-Means (FCM)

K-Medoids **không** nằm trong phạm vi tài liệu này (xem ADR-0003 — `OUT OF SCOPE` cho phase hiện tại).

---

## 1. Mục đích và phạm vi

### 1.1. Mục đích

Tài liệu này phục vụ ba mục tiêu rõ ràng:

- **Tổng hợp lý thuyết** đủ chiều sâu để hiểu cơ chế hoạt động và giả định của từng thuật toán đang được benchmark trong project.
- **Cầu nối lý thuyết → bài toán**: làm rõ từng giả định lý thuyết được "kích hoạt" như thế nào khi áp dụng lên không gian 14-chiều RFM Extended (4,371 customer).
- **Trình bày evidence thực nghiệm** từ EPIC-06/07/08/09 với số liệu lấy thẳng từ artifact đã có, không suy diễn và không bịa.

### 1.2. Phạm vi và không phạm vi

**Trong phạm vi tài liệu:**
- Lý thuyết cơ bản của 5 thuật toán đã đăng ký trong `AlgorithmRegistry`.
- Cấu hình và kết quả baseline (EXP-01), K-sweep (EXP-02), hyperparameter sensitivity (EXP-03), preprocessing sensitivity (EXP-04 Family B), reproducibility + stability evidence (EXP-05).
- So sánh lý thuyết và thực nghiệm giữa 5 thuật toán, ở mức observation.

**NGOÀI phạm vi tài liệu:**
- Đánh giá "best algorithm", "winner", "optimal algorithm", "recommended algorithm" (vi phạm AGENTS.md §2.5).
- Tạo ranking tổng thể, composite score, weighted ranking (vi phạm AGENTS.md §2.5, §2.6, §2.10).
- K-Medoids (đã được ADR-0003 xác nhận OUT OF SCOPE).
- Thay đổi methodology, research questions, RFM-only artifact (không thuộc scope documentation synthesis).
- Customer profiling / segment naming (thuộc EPIC-09, xem CP-05.md).

### 1.3. Bối cảnh methodology

Các quyết định sau đã khóa (KHÔNG thay đổi trong tài liệu này):

| Quyết định | Nguồn | Trạng thái |
|---|---|---|
| 5 algorithms in scope (K-Medoids OUT) | ADR-0003 | Accepted |
| 3 RQs (RQ1/RQ2/RQ3) theo formulation trong ADR-0004 | ADR-0004 | Accepted |
| Final dataset = FE-06 v1.0, 4,371 customers × 14 features | methodology_overview.md | METHODOLOGY_LOCKED |
| Internal metrics (silhouette primary, DBI, CH, WCSS diagnostic) | methodology_overview.md §3.6 | METHODOLOGY_LOCKED |
| K-Means chỉ làm single-algorithm reference cho RQ2 | ADR-0004 RQ2 | Accepted |

---

## 2. Bài toán Customer Segmentation trong nghiên cứu

### 2.1. Dataset

| Trường | Giá trị |
|---|---|
| Source | UCI Online Retail (primary, ADR-0001) |
| Raw file | `data/raw/primary/Online Retail.xlsx` |
| Raw SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Cleaning | FE-02 (invalid records, duplicates) |
| Customer aggregation | FE-04 (customer-level base) |
| Feature engineering | FE-05 (RFM + extended behavioral features) |
| Transformation + scaling | FE-06 (median imputation + Yeo-Johnson + RobustScaler) |
| Final matrix | `data/processed/final_clustering_dataset.parquet` |
| Final matrix dimensions | 4,371 customers × 14 features (R¹⁴) |
| Final matrix SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Customer metadata | `data/processed/customer_metadata.parquet` (4,371 × 1, CustomerID) |

### 2.2. Customer-level unit of analysis

Mỗi customer được biểu diễn bằng **một vector duy nhất** trong không gian R¹⁴. Cột `CustomerID` nằm trong `customer_metadata.parquet` riêng biệt; feature matrix 14 cột không chứa CustomerID. Tất cả 5 adapter (ML-02 → ML-06) đều enforce positional alignment (row `i` của cluster labels ↔ row `i` của customer metadata).

### 2.3. Feature representation: 14-feature RFM Extended working baseline

| # | Feature | FE-06 Status |
|---|---|---|
| 1 | Recency | ELIGIBLE |
| 2 | Frequency | ELIGIBLE_WORKING_ASSUMPTION |
| 3 | Monetary | ELIGIBLE |
| 4 | TotalQuantity | ELIGIBLE |
| 5 | AverageQuantity | ELIGIBLE_WORKING_ASSUMPTION |
| 6 | BasketSize | ELIGIBLE_WORKING_ASSUMPTION |
| 7 | TenureDays | ELIGIBLE |
| 8 | PurchaseIntervalMean | ELIGIBLE |
| 9 | PurchaseIntervalStd | ELIGIBLE |
| 10 | ActiveDays | ELIGIBLE_WORKING_ASSUMPTION |
| 11 | AverageInvoiceValue | ELIGIBLE |
| 12 | ProductsPerInvoice | ELIGIBLE |
| 13 | CancellationRate | ELIGIBLE_WORKING_ASSUMPTION |
| 14 | ReturnRate | ELIGIBLE_WORKING_ASSUMPTION |

Sáu feature nằm trong `ELIGIBLE_WORKING_ASSUMPTION` (xem FE-06 §13). Feature set này là working baseline; nó được chấp nhận cho phase hiện tại và **không** được thay đổi trong tài liệu này.

### 2.4. Preprocessing pipeline (FE-06 C7 — WORKING_ASSUMPTION)

| Bước | Phương pháp | Ghi chú |
|---|---|---|
| Imputation | Median | PurchaseIntervalMean (41.0), PurchaseIntervalStd (32.585) |
| Transformation | Yeo-Johnson | Per-feature lambda, fitted by sklearn |
| Scaling | RobustScaler | median=0, IQR=1 |

Trạng thái pipeline C7: `WORKING_ASSUMPTION`. Đây là configuration mặc định được EPIC-07 sử dụng để chạy 5 thuật toán trên cùng một input.

### 2.5. Clustering input và evaluation boundary

Tất cả 5 thuật toán nhận cùng một input: ma trận `(4371, 14)` đã được impute / transform / scale. Evaluation sử dụng **internal metrics only** (silhouette, DBI, CH, WCSS), WCSS ở chế độ diagnostic. DBSCAN noise points (label = -1) được loại khỏi internal metric computation theo policy trong `configs/clustering.yaml`.

---

## 3. Tổng quan 5 thuật toán — Taxonomy

| Algorithm | Paradigm | Yêu cầu K | Xử lý noise | Membership | Cluster representation | Đặc điểm chính |
|---|---|---|---|---|---|---|
| **K-Means** | Partitional, centroid-based | Bắt buộc K | Không có khái niệm noise chính thức (mọi điểm được assign) | Hard | Centroid (mean của cluster) | Lloyd's algorithm; Euclidean; nhạy centroid khởi tạo |
| **Agglomerative (Hierarchical)** | Hierarchical, bottom-up | Bắt buộc K (chọt cắt dendrogram) | Không có khái niệm noise | Hard | Tập điểm trong cluster | Tính khoảng cách pairwise; linkage ward/average/complete |
| **DBSCAN** | Density-based | Không cần K (realized K từ density) | Có, label = -1 | Hard (kèm noise flag) | Tập density-reachable points | Core / border / noise; không giả định cluster convex |
| **GMM** | Probabilistic, model-based | Bắt buộc K (n_components) | Không có noise flag (mọi điểm đều có responsibility > 0) | Soft (responsibility matrix), hard nếu lấy argmax | Phân phối Gaussian với mean/covariance | EM algorithm; covariance type full/tied/diag/spherical |
| **Fuzzy C-Means** | Fuzzy / soft partition | Bắt buộc K (n_clusters) | Không có noise flag | Soft (membership matrix U ∈ [0,1]), hard nếu argmax | Centroid cộng với membership weights | Bezdek update; fuzziness parameter m |

---

## 4. K-Means

### 4.1. Lý thuyết

K-Means (Lloyd's algorithm) là **hard centroid-based clustering**. Mỗi observation được assign về centroid gần nhất theo Euclidean distance, centroid sau đó được update là trung bình cộng của các observation trong cluster. Hai bước này lặp cho đến khi centroid không đổi hoặc đạt `max_iter`.

### 4.2. Objective function

K-Means tối thiểu hoá tổng bình phương khoảng cách trong từng cluster (Within-Cluster Sum of Squares, WCSS):

```
WCSS = Σ_{k=1}^{K} Σ_{x ∈ C_k} ||x − μ_k||²
```

trong đó `μ_k = (1/|C_k|) · Σ_{x ∈ C_k} x` là centroid cluster `k`.

Trong ML-02, WCSS được ghi vào `ClusterResult.extra` ở chế độ **diagnostic only**, không dùng để rank algorithm.

### 4.3. Nguyên lý hoạt động

1. Khởi tạo K centroid (mặc định `init="k-means++"`, `n_init=10`).
2. **Assignment step**: mỗi điểm → centroid gần nhất.
3. **Update step**: mỗi centroid = mean các điểm vừa được assign.
4. Lặp (2)-(3) đến khi hội tụ hoặc `max_iter`.

### 4.4. Assumptions và characteristics

- Distance metric: Euclidean (mặc định, không expose metric khác qua ML-02).
- Cluster hình dạng: isotropic, variance tương đương giữa các cluster.
- Cluster sizes: tương đương (K-Means có xu hướng tạo cluster cùng size).
- Nhạy với khởi tạo: `n_init=10` giảm rủi ro bad local minimum.
- Không có noise label.
- Algorithm family: `hard` (mỗi customer thuộc đúng 1 cluster).

### 4.5. Áp dụng vào bài toán Customer Segmentation

- Mỗi customer (4,371 vector trong R¹⁴) được map về một trong K cluster.
- K-Means sử dụng Euclidean distance, nên scaling là bắt buộc. FE-06 C7 đã mitigate bằng RobustScaler trước khi feed vào adapter.
- Working `n_clusters=4` (theo EXP-01 baseline) là WORKING_ASSUMPTION, không phải "best K".
- Adapter dùng `random_state=42`, `n_init=10`, `max_iter=300`, `tol=1e-4` (working config từ `configs/clustering.yaml`).

### 4.6. Experimental configuration (EXP-01 baseline)

- Algorithm: `kmeans`, sklearn_1.9.1
- Hyperparameters: `{n_clusters=4, init="k-means++", n_init=10, max_iter=300, tol=1e-4, random_state=42}`
- Status: SUCCESS

### 4.7. Experimental results (EXP-01, EXP-02, EXP-05 Block R)

| Nguồn | K | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Noise |
|---|---|---|---|---|---|---|---|
| EXP-01 baseline | 4 | 0.5681 | 0.6128 | 4819.08 | 179858.91 | 0.0476 | 0 |
| EXP-02 K=2 | 2 | 0.5839 | 0.6518 | 3331.81 | 439857.24 | 0.0210 | 0 |
| EXP-02 K=3 | 3 | 0.6291 | 0.5881 | 5420.09 | 222674.94 | 0.0296 | 0 |
| EXP-02 K=5 | 5 | 0.5697 | 0.7219 | 4851.72 | 142386.28 | 0.0273 | 0 |
| EXP-02 K=6 | 6 | 0.5740 | 0.6598 | 4663.50 | 122249.01 | 0.0331 | 0 |
| EXP-02 K=7 | 7 | 0.5118 | 0.6894 | 4472.89 | 108436.95 | 0.0433 | 0 |
| EXP-02 K=10 | 10 | 0.4782 | 0.6768 | 4083.96 | 82230.82 | 0.0522 | 0 |
| EXP-05 Block R (5x repeats) | 4 | 0.5681 (std=0) | 0.6128 (std=0) | 4819.08 (std=0) | 179858.91 (std=0) | 0.2321 | 0 |

EXP-03 working selection cho K-Means: `K=3, n_init=1, init=k-means++` với silhouette 0.6291 (TIED_WORKING_SELECTED — có 2 tied alternates).

### 4.8. Interpretation

- K-Means với K=4 đạt silhouette 0.5681 — cao nhất trong 5 algorithm ở baseline cùng K.
- WCSS giảm đơn điệu khi K tăng (chuẩn elbow behavior).
- Silhouette đạt peak ở K=3 (0.6291) trong sweep K ∈ [2,10].
- Reproducibility verified: 5/5 repeats với cùng seed → labels_hash giống hệt.

### 4.9. Limitations

- Giả định cluster isotropic → có thể không phù hợp nếu segment có hình dáng phức tạp.
- Không có soft membership (mỗi customer hard-assigned về 1 cluster).
- Không có noise concept → outlier trong dữ liệu vẫn bị ép vào cluster gần nhất.
- Nhạy với feature scaling và centroid khởi tạo (mitigate bằng `n_init=10`).

---

## 5. Agglomerative (Hierarchical) Clustering

### 5.1. Lý thuyết

Agglomerative clustering là **bottom-up hierarchical clustering**: ban đầu mỗi điểm là một cluster riêng lẻ, sau đó lặp đi lặp lại việc merge hai cluster gần nhất cho đến khi còn đúng K cluster (hoặc 1 cluster duy nhất).

### 5.2. Nguyên lý hoạt động

1. Khởi tạo: mỗi điểm = 1 cluster. Tính ma trận khoảng cách pairwise.
2. **Merge step**: tìm cặp cluster (C_a, C_b) có linkage distance nhỏ nhất → merge thành C_ab.
3. Cập nhật ma trận khoảng cách theo linkage rule.
4. Lặp đến khi còn K cluster.

### 5.3. Linkage

Khoảng cách giữa hai cluster được xác định bởi linkage rule:

- **Ward linkage**: minimize tổng variance trong cluster sau merge. `d(C_a, C_b) = Δ(ESS)` trong đó ESS = Error Sum of Squares. Đây là working default trong ML-03.
- **Average linkage**: trung bình khoảng cách pairwise giữa mọi cặp điểm trong C_a × C_b.
- **Complete linkage**: max khoảng cách giữa một điểm trong C_a và một điểm trong C_b.
- **Single linkage**: min khoảng cách.

Trong ML-03, metric mặc định là `euclidean`. Working config trong EXP-01 dùng `linkage="ward"`.

### 5.4. Assumptions và characteristics

- Distance metric: Euclidean (working default), `metric="euclidean"`.
- Không có khái niệm noise.
- Deterministic: Agglomerative với linkage ward/average/complete trên Euclidean không có random axis → cùng input + cùng `n_clusters` + cùng `linkage` → cùng output.
- Algorithm family: `hard`.

### 5.5. Áp dụng vào bài toán Customer Segmentation

- Dendrogram có thể được dựng (với `compute_distances=True`) nhưng ML-03 chỉ output cluster labels sau khi cắt ở `n_clusters=K`.
- Với 4,371 customer và 14 features, distance matrix có kích thước (4371×4370)/2 ≈ 9.5M cặp.
- Phù hợp với cấu trúc phân cấp nếu segment thực sự nested; trên RFM Extended, kết quả EXP-01 cho thấy silhouette rất gần K-Means (0.5657 vs 0.5681).

### 5.6. Experimental configuration (EXP-01 baseline)

- Algorithm: `agglomerative`, sklearn_1.9.1
- Hyperparameters: `{n_clusters=4, linkage="ward", metric="euclidean", compute_distances=True}`
- Status: SUCCESS

### 5.7. Experimental results

| Nguồn | K | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Noise |
|---|---|---|---|---|---|---|---|
| EXP-01 baseline | 4 | 0.5657 | 0.7360 | 4578.83 | 187019.54 | 0.5663 | 0 |
| EXP-02 K=2 | 2 | 0.6103 | 0.5655 | 3148.99 | 450553.83 | 0.6389 | 0 |
| EXP-02 K=3 | 3 | 0.5904 | 0.6388 | 5029.13 | 234744.25 | 0.5367 | 0 |
| EXP-02 K=5 | 5 | 0.5446 | 0.7438 | 4266.60 | 157935.11 | 0.4352 | 0 |
| EXP-02 K=10 | 10 | 0.4432 | 0.7037 | 3720.43 | 89339.74 | 0.4890 | 0 |
| EXP-03 (linkage=average, K=3) | 3 | 0.8033 | 0.2714 | 77.15 | 748840.46 | 0.4887 | 0 |
| EXP-05 Block R (5x repeats) | 4 | 0.5657 (std=0) | 0.7360 (std=0) | 4578.83 (std=0) | 187019.54 (std=0) | 0.7806 | 0 |

EXP-03 working selection cho Agglomerative: `K=3, linkage=average` với silhouette 0.8033 (WORKING_SELECTED).

### 5.8. Interpretation

- Ở baseline K=4 với linkage ward, Agglomerative cho silhouette gần bằng K-Means (chênh 0.0024) nhưng DBI cao hơn (~0.12).
- EXP-03 stage C cho thấy linkage=average với K=3 đạt silhouette 0.8033 — cao nhất trong tất cả (algorithm × config) đã chạy trong EPIC-07. Tuy nhiên đây là `WORKING_SELECTED` trong search space của algorithm đó, không phải claim về algorithm nào tốt hơn algorithm nào.
- Agglomerative ward cho runtime cao hơn K-Means ~12x ở cùng K=4 (0.5663s vs 0.0476s).

### 5.9. Limitations

- Không scale tốt với N rất lớn (distance matrix O(N²)).
- Deterministic → không có seed axis → không có "seed stability" khái niệm.
- Không có noise handling (mọi điểm phải thuộc một cluster).
- Linkage choice có ảnh hưởng mạnh đến cấu trúc cluster (xem EXP-03 sensitivity).

---

## 6. DBSCAN

### 6.1. Lý thuyết

DBSCAN (Density-Based Spatial Clustering of Applications with Noise, Ester et al., 1996) là **density-based clustering**. Thuật toán parameterized bởi hai hyperparameter:

- `eps` — neighborhood radius.
- `min_samples` — minimum số điểm để form dense region.

### 6.2. Epsilon-neighborhood

```
N_eps(x) = { x_j | d(x, x_j) ≤ eps }
```

### 6.3. Khái niệm core / border / noise

- **Core point**: `|N_eps(x)| ≥ min_samples`. Điểm này nằm trong vùng dense đủ để làm hạt nhân cluster.
- **Border point**: `|N_eps(x)| < min_samples` NHƯNG nằm trong eps-neighborhood của ít nhất một core point.
- **Noise point**: `|N_eps(x)| < min_samples` VÀ không nằm trong eps-neighborhood của core point nào. Trong sklearn convention, noise được gán `label = -1`.

### 6.4. Density connectivity

Hai điểm `x`, `y` được gọi là **density-connected** nếu tồn tại chuỗi `x = p_0, p_1, ..., p_n = y` sao cho mỗi `p_{i+1} ∈ N_eps(p_i)` và `p_i` là core point. Một DBSCAN cluster = một maximal tập density-connected core points + các border points của chúng.

### 6.5. Realized K

DBSCAN **không yêu cầu K trước**. Số cluster `K` là **realized outcome** từ density structure của dữ liệu. Trên RFM Extended, baseline cho K=17, noise=3177.

### 6.6. Assumptions và characteristics

- Distance metric: Euclidean (working default), có thể đổi sang manhattan/cosine nhưng không phải trong baseline.
- Deterministic: cùng input + cùng `(eps, min_samples, metric)` → cùng output.
- Algorithm family: `density_based` (hard labels + dedicated noise label -1).
- Không giả định cluster convex → phát hiện được cluster hình thù bất kỳ.

### 6.7. Áp dụng vào bài toán Customer Segmentation

- Working hyperparameters: `eps=0.5`, `min_samples=5`, `metric="euclidean"`. Đây là WORKING_ASSUMPTION.
- Sau FE-06 RobustScaler, `eps=0.5` mang nghĩa "bán kính 0.5 đơn vị scale".
- Trên 4,371 customer × 14 features (đã scaled), DBSCAN baseline phát hiện 17 cluster và **3,177 noise points (≈72.7% tổng số customer)**.

### 6.8. Experimental configuration (EXP-01 baseline)

- Algorithm: `dbscan`, sklearn_1.9.1
- Hyperparameters: `{eps=0.5, min_samples=5, metric="euclidean"}`
- Status: SUCCESS
- Realized K: 17
- Noise count: 3177
- Noise ratio: 0.7268 (≈72.7%)

### 6.9. Experimental results

| Nguồn | eps | min_samples | Realized K | Noise count | Noise ratio | Silhouette | DBI | CH | WCSS | Runtime mean (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| EXP-01 baseline | 0.5 | 5 | 17 | 3177 | 0.7268 | -0.1041 | 0.7721 | 49.18 | 2125.13 | 0.1083 |
| EXP-03 min_samples=10 | 0.5 | 10 | 5 | 3360 | 0.7687 | 0.1598 | 0.7687 | 54.22 | 1739.80 | 0.1100 |
| EXP-03 eps=0.3 | 0.3 | 5 | NOT_AVAILABLE (chi tiết trong exp03_report) | — | — | -0.1713 | — | 17.78 | — | — |
| EXP-03 eps=0.7 | 0.7 | 5 | — | — | — | — | — | — | — | — |
| EXP-05 Block R (5x repeats) | 0.5 | 5 | 17 | 3177 | 0.7268 | -0.1041 (std=0) | 0.7721 (std=0) | 49.18 (std=0) | 2125.13 (std=0) | 0.1110 |
| EXP-05 Block N (sigma=0.01, 3 seeds) | 0.5 | 5 | n_clusters_unique_count=3 | — | — | 0.0227 (cv=6.625) | 0.6960 | 49.80 | 2054.96 | 0.1403 |
| EXP-05 Block N (sigma=0.05, 3 seeds) | 0.5 | 5 | n_clusters_unique_count=2 | — | — | -0.0662 (cv=-0.797) | 1.0038 | 25.98 | 458.44 | 0.1056 |

EXP-03 working selection cho DBSCAN: `min_samples=10, eps=0.5, metric=euclidean` với silhouette 0.1598 (WORKING_SELECTED).

### 6.10. Interpretation

- **Noise là kết quả của DBSCAN, không phải bug.** Với working `eps=0.5`, baseline nhãn 72.7% customer là noise. Điều này phản ánh rằng sau khi scale bằng RobustScaler và nén vào 14 chiều, RFM Extended KHÔNG tạo thành 17 vùng dense rõ ràng — phần lớn customer nằm "lưng chừng" giữa các vùng.
- Silhouette -0.1041 (ở baseline) có status `VALID_VALUE` theo schema, không phải MISSING hay ERROR. Nhưng theo AGENTS.md §3 (Evaluation row) và ML-04 doc: silhouette KHÔNG có ý nghĩa cho density-based clusters vì noise label -1 không có ground truth centroid. Việc silhouette = -0.1041 vẫn được ghi nhận nhưng không nên dùng để đánh giá chất lượng.
- DBI=0.7721, CH=49.18 (rất thấp so với các thuật toán khác) — phản ánh việc có 17 cluster nhỏ + 3177 noise point làm cho dispersion ratio lệch.
- DBSCAN rất nhạy với feature perturbation: sigma=0.01 cho silhouette cv = 6.625 (cao nhất trong 5 thuật toán) và `n_clusters_unique_count=3` (realized K dao động giữa 3 giá trị khác nhau). Ở sigma=0.05, `n_clusters_unique_count=2` và WCSS giảm mạnh xuống 458.44 (so với baseline 2125.13) → nhiều core point bị mất khi noise tăng.

### 6.11. Limitations

- `eps` và `min_samples` cực kỳ nhạy với scaling → RobustScaler trong FE-06 là cần thiết nhưng vẫn không đảm bảo DBSCAN phát hiện được cluster có ý nghĩa thương mại.
- Với 14-dimensional scaled feature space, khái niệm "neighborhood" trở nên counter-intuitive (curse of dimensionality).
- Noise ratio rất cao (72.7%) ở baseline → segment profile rất ít.
- Working selection (min_samples=10) chỉ giảm noise xuống ~76.9% (vẫn rất cao).

---

## 7. Gaussian Mixture Model (GMM)

### 7.1. Lý thuyết

GMM giả định dữ liệu được sinh ra từ hỗn hợp (mixture) của K phân phối Gaussian. Mỗi component `k` có:
- Mean vector `μ_k ∈ R^D`
- Covariance matrix `Σ_k ∈ R^{D×D}`
- Mixing weight `π_k`, với `Σ π_k = 1`.

### 7.2. Mixture model

Probability density function:

```
p(x) = Σ_{k=1}^{K} π_k · N(x | μ_k, Σ_k)
```

trong đó `N(x | μ, Σ)` là multivariate Gaussian density.

### 7.3. Covariance types

Trong sklearn, `covariance_type` có 4 lựa chọn:
- `full` — mỗi component có covariance matrix riêng, tổng quát nhất.
- `tied` — tất cả component dùng chung 1 covariance matrix.
- `diag` — mỗi component có diagonal covariance (axis-aligned ellipsoid).
- `spherical` — mỗi component có variance scalar (giống K-Means spherical assumption).

Working config trong EXP-01 dùng `covariance_type="full"`. EXP-03 working selection chọn `covariance_type="tied"`.

### 7.4. Soft assignment và responsibility

Với mỗi điểm `x_i`, GMM tính posterior probability (responsibility) của component `k`:

```
γ(z_{ik}) = π_k · N(x_i | μ_k, Σ_k) / Σ_{j=1}^{K} π_j · N(x_i | μ_j, Σ_j)
```

Đây là **soft membership**: một điểm có thể có responsibility > 0 cho nhiều component.

### 7.5. Hard label convention

Trong implementation của project, sklearn GMM được dùng ở chế độ `predict()` — tức là lấy `argmax_k γ(z_{ik})` để ra hard label. Adapter cũng có thể expose `predict_proba()` để lấy soft membership matrix. Trong EPIC-07 metrics, internal metric sử dụng **hard label** (sau argmax).

### 7.6. Expectation-Maximization (EM)

MLE của mixture model không có closed-form. EM lặp:
- **E-step**: tính responsibility `γ(z_{ik})` cho mọi (i, k) với current (π, μ, Σ).
- **M-step**: update (π, μ, Σ) bằng weighted MLE sử dụng `γ` làm weight.

Hội tụ khi log-likelihood thay đổi dưới `tol=0.001` hoặc đạt `max_iter=100`.

### 7.7. Assumptions và characteristics

- Distance metric: implicit qua covariance structure của Gaussian.
- Mỗi customer có soft probability cho mọi component (không có noise label).
- Algorithm family: `probabilistic` (soft by construction, hard by argmax).
- Random axis: `init_params="kmeans"` cho phép seed-controlled initialization.
- Nhạy với `covariance_type`: full quá tổng quát, spherical quá hạn chế. Tied là một trade-off.

### 7.8. Áp dụng vào bài toán Customer Segmentation

- Mỗi customer có một vector responsibility `(γ_1, ..., γ_K)` mô tả mức độ thuộc về từng latent Gaussian component.
- Adapter cho phép access `responsibility matrix` (qua `predict_proba()`) nếu EPIC-09 cần soft assignment cho segment profiling.
- Working `n_components=4`, `covariance_type="full"` ở EXP-01 là WORKING_ASSUMPTION.

### 7.9. Experimental configuration (EXP-01 baseline)

- Algorithm: `gmm`, sklearn_1.9.1
- Hyperparameters: `{n_components=4, covariance_type="full", init_params="kmeans", tol=0.001, reg_covar=1e-06, max_iter=100, n_init=1, random_state=42}`
- Status: SUCCESS

### 7.10. Experimental results

| Nguồn | n_components | Covariance | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Noise |
|---|---|---|---|---|---|---|---|---|
| EXP-01 baseline | 4 | full | 0.1843 | 3.7486 | 131.73 | 710957.20 | 0.5189 | 0 |
| EXP-02 K=2 | 2 | full | 0.0222 | 3.8192 | 118.77 | 754775.21 | 0.6092 | 0 |
| EXP-02 K=3 | 3 | full | 0.2047 | 3.5978 | 245.01 | 697090.23 | 0.4812 | 0 |
| EXP-02 K=5 | 5 | full | 0.1946 | 12.7203 | 153.29 | 679821.48 | 0.4636 | 0 |
| EXP-02 K=10 | 10 | full | 0.1528 | 8.5950 | 141.02 | 600519.58 | 2.0167 | 0 |
| EXP-03 covariance=tied, K=4 | 4 | tied | 0.5702 | 0.6167 | 4481.99 | 190069.74 | 0.1495 | 0 |
| EXP-05 Block R (5x repeats) | 4 | full | 0.1843 (std=0) | 3.7486 (std=0) | 131.73 (std=0) | 710957.20 (std=0) | 0.3908 | 0 |
| EXP-05 Block S (5 seeds) | 4 | full | 0.1844 (cv=0.0006) | 3.7917 (cv=0.0254) | 132.41 (cv=0.0116) | 710649.68 (cv=0.0009) | 0.5627 | 0 |
| EXP-05 Block N (sigma=0.05, 3 seeds) | 4 | full | 0.1708 (cv=0.0055) | 3.9400 (cv=0.0148) | 121.29 (cv=0.0084) | 716738.00 | 0.3013 | 0 |

EXP-03 working selection cho GMM: `n_components=4, covariance_type=tied` với silhouette 0.5702 (WORKING_SELECTED).

### 7.11. Interpretation

- Ở working config `covariance_type="full"` với K=4, silhouette = 0.1843 — thấp nhất trong 5 thuật toán cùng K. DBI = 3.7486 cao bất thường.
- EXP-03 cho thấy switching sang `covariance_type="tied"` cải thiện silhouette từ 0.1843 → 0.5702 và DBI từ 3.7486 → 0.6167. Lý do: với 14 features × 4371 customers, full covariance có quá nhiều parameter (14×15/2 = 105 per component × 4 = 420 parameters) → dễ overfit / under-constrain. Tied covariance chỉ có 105 parameters total → robust hơn cho dataset này.
- WCSS = 710,957 (cao nhất trong 5 algorithm) — đây là **WCSS với arithmetic centroid**, không phải Mahalanobis distance. WCSS không phải metric phù hợp để đánh giá GMM vì GMM không tối ưu WCSS; nó tối ưu log-likelihood. Đây là limitation đã được ghi trong AGENTS.md §3 và methodology_overview.md §3.6.
- GMM có seed sensitivity (5 seeds → labels_hash_unique_count = 5) — đây là dấu hiệu EM khởi tạo khác nhau cho các local optimum khác nhau.

### 7.12. Limitations

- Số component (K) cố định trước.
- Với D lớn, full covariance có quá nhiều parameter.
- Có thể hội tụ về local optimum khác nhau tùy initialization.
- WCSS không phải metric phù hợp cho GMM (chỉ là diagnostic theo working config).
- soft membership bị "bỏ qua" khi compute hard silhouette — đây là limitation của methodology hiện tại, không phải limitation thuật toán.

---

## 8. Fuzzy C-Means (FCM)

### 8.1. Lý thuyết

FCM (Bezdek, 1981) là phiên bản soft của K-Means: thay vì mỗi điểm thuộc đúng 1 cluster, mỗi điểm thuộc về tất cả các cluster với một **membership degree** ∈ [0, 1], tổng membership trên các cluster bằng 1.

### 8.2. Membership matrix

Ma trận `U ∈ [0,1]^(N×K)`, với `U[i, k]` = membership của điểm `x_i` trong cluster `k`. Constraint:

```
Σ_{k=1}^{K} U[i, k] = 1, ∀ i
U[i, k] ≥ 0, ∀ (i, k)
```

### 8.3. Fuzziness parameter m

`m > 1` là fuzziness parameter. Khi `m → 1+`, FCM tiệm cận K-Means (hard). Khi `m → ∞`, membership tiệm cận `1/K` cho mọi cluster (maximum fuzziness). Working default `m=2.0`; EXP-03 working selection chọn `m=1.5`.

### 8.4. Objective function

FCM tối thiểu hoá weighted sum of squared distances:

```
J_m = Σ_{i=1}^{N} Σ_{k=1}^{K} (U[i, k])^m · ||x_i − c_k||²
```

trong đó `c_k` là centroid của cluster `k` và `m` là fuzziness parameter.

### 8.5. Centroid update và membership update (Bezdek update equations)

```
c_k = (Σ_i (U[i, k])^m · x_i) / (Σ_i (U[i, k])^m)

U[i, k] = 1 / (Σ_{j=1}^{K} (||x_i − c_k|| / ||x_i − c_j||)^(2/(m−1)))
```

Hai bước lặp đến khi `||U_new − U_old|| < error = 0.0001` hoặc `max_iter=300`.

### 8.6. Hard label convention

Trong implementation hiện tại (`custom_v1`, NumPy), adapter expose:
- Soft membership matrix `U` (qua `predict_proba()` analog).
- Hard label = `argmax_k U[i, k]` (qua `predict()`).

Trong EPIC-07 metrics, internal metrics dùng hard label (sau argmax).

### 8.7. Assumptions và characteristics

- Distance metric: Euclidean.
- Không có noise label.
- Algorithm family: `fuzzy` (soft by construction, hard by argmax).
- Random axis: `random_state=42` cho Dirichlet initialization.
- Nhạy với `m`: `m` nhỏ → gần hard; `m` lớn → gần uniform.

### 8.8. Áp dụng vào bài toán Customer Segmentation

- Mỗi customer có một vector membership `(u_1, ..., u_K)` ∈ [0,1]^K.
- Working config trong EXP-01: `n_clusters=4, m=2.0, max_iter=300, error=0.0001, random_state=42`.
- Implementation: custom NumPy (không dùng sklearn).

### 8.9. Experimental configuration (EXP-01 baseline)

- Algorithm: `fuzzy_cmeans`, `custom_v1` (NumPy)
- Hyperparameters: `{n_clusters=4, m=2.0, max_iter=300, error=0.0001, random_state=42}`
- Status: SUCCESS

### 8.10. Experimental results

| Nguồn | K | m | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Noise |
|---|---|---|---|---|---|---|---|---|
| EXP-01 baseline | 4 | 2.0 | 0.2691 | 1.3709 | 3869.05 | 211949.22 | 0.0658 | 0 |
| EXP-02 K=2 | 2 | 2.0 | 0.5696 | 0.6835 | 3315.16 | 440810.14 | 0.0191 | 0 |
| EXP-02 K=3 | 3 | 2.0 | 0.6271 | 0.5938 | 5413.69 | 222862.69 | 0.0211 | 0 |
| EXP-02 K=5 | 5 | 2.0 | 0.5560 | 0.7262 | 4805.42 | 143504.11 | 0.0794 | 0 |
| EXP-02 K=10 | 10 | 2.0 | 0.1914 | 1.5919 | 2957.31 | 109148.16 | 0.3965 | 0 |
| EXP-03 K=3, m=1.5 | 3 | 1.5 | 0.6296 | 0.5869 | 5419.61 | 222689.21 | 0.0251 | 0 |
| EXP-05 Block R (5x repeats) | 4 | 2.0 | 0.2691 (std=0) | 1.3709 (std=0) | 3869.05 (std=0) | 211949.22 (std=0) | 0.0720 | 0 |
| EXP-05 Block S (5 seeds) | 4 | 2.0 | 0.3230 (cv=0.374) | 1.2255 (cv=0.265) | 4047.51 (cv=0.099) | 205864.98 | 0.0855 | 0 |
| EXP-05 Block N (sigma=0.05, 3 seeds) | 4 | 2.0 | 0.3915 (cv=0.317) | 0.9126 (cv=0.253) | 4329.82 (cv=0.080) | 195812.44 | 0.2818 | 0 |

EXP-03 working selection cho FCM: `K=3, m=1.5` với silhouette 0.6296 (WORKING_SELECTED).

### 8.11. Interpretation

- Ở working config `m=2.0` với K=4, silhouette = 0.2691 — cao hơn GMM full (0.1843) nhưng thấp hơn K-Means (0.5681) và Agglomerative (0.5657).
- Khi sweep K với `m=2.0` cố định: silhouette peak ở K=3 (0.6271). Pattern này giống K-Means (peak 0.6291 ở K=3) → gợi ý rằng working `m=2.0` không đủ "soft" để phân biệt behavior so với K-Means.
- EXP-03 working selection `m=1.5` gần với K-Means hơn (m → 1+). Việc tăng silhouette nhẹ từ 0.6271 → 0.6296 khi giảm m từ 2.0 → 1.5 phù hợp với lý thuyết.
- FCM có seed sensitivity cao hơn K-Means/GMM: silhouette cv = 0.374 ở Block S (so với K-Means cv = 0.0 và GMM cv = 0.0006). Cluster size distribution ở 5 seeds cũng khác biệt rõ rệt → EM/Dirichlet initialization không stable như K-Means++.
- Runtime nhanh (0.066s baseline) — nhẹ hơn K-Means dù cùng N.

### 8.12. Limitations

- Membership interpretation phụ thuộc vào `m`: `m` quá lớn → membership không phân biệt.
- Working config `m=2.0` chưa được so sánh với `m=1.5` (EXP-03 working selection) trong full evaluation.
- Custom NumPy implementation (`custom_v1`) không phải từ thư viện chuẩn → reproducibility phải dựa vào `random_state` protocol.
- Internal metric (silhouette/DBI/CH) dùng hard label (sau argmax) → soft information bị mất trong EPIC-07 evaluation.

---

## 9. Từ lý thuyết đến bài toán Customer Segmentation

### 9.1. Mapping "input feature space → algorithm mechanism → cluster structure → observed behavior"

| Algorithm | Feature space assumption | Algorithm mechanism | Resulting cluster structure | Observed experimental behavior |
|---|---|---|---|---|
| K-Means | Euclidean, isotropic clusters | Lloyd iteration; centroid = mean | K spherical clusters (mean-based) | Silhouette ~0.57 ở K=4; peak 0.63 ở K=3; runtime nhanh nhất |
| Agglomerative | Euclidean, no shape assumption | Greedy merge theo linkage | Hierarchical → cắt ở K cluster | Silhouette ~0.57 ở K=4 với ward; peak 0.80 với linkage=average ở K=3 |
| DBSCAN | Euclidean density reachable | Density expansion từ core points | Variable-K clusters + noise label | K=17, noise=72.7% ở baseline; silhouette -0.10 (không informative cho density-based) |
| GMM | Multivariate Gaussian per component | EM trên log-likelihood | K ellipsoidal clusters; soft responsibility | Silhouette thấp 0.18 với full; cải thiện lên 0.57 với tied |
| FCM | Euclidean, fuzzy partition | Bezdek update trên membership matrix | K centroid + soft membership matrix | Silhouette 0.27 ở K=4 với m=2.0; peak 0.63 với K=3, m=2.0 |

### 9.2. Cụ thể từng bước

**K-Means trên R¹⁴:**
- 14-feature scaled → centroid trong R¹⁴.
- Mỗi customer thuộc cluster có centroid gần nhất theo Euclidean.
- Kết quả: K cluster có mean gần tâm R¹⁴ nhất → silhouette ~0.57 cho thấy clusters tương đối tách biệt và compact.

**Agglomerative trên R¹⁴:**
- Tính full distance matrix giữa 4371 customer → greedy merge theo ward.
- Cắt dendrogram ở K=4 → silhouette gần bằng K-Means.
- Khi đổi linkage sang average ở K=3 → silhouette tăng đáng kể lên 0.80. Đây là evidence rằng linkage rule có ảnh hưởng rất mạnh.

**DBSCAN trên R¹⁴:**
- 14D scaled space → eps-ball neighborhood.
- Phát hiện 17 cluster rất nhỏ + 3177 noise → 72.7% customer không đạt density threshold.
- Phản ánh: R¹⁴ (post-robust-scale) không có 17 vùng dense rõ ràng; customer phân tán.

**GMM trên R¹⁴:**
- Mỗi component = multivariate Gaussian trong R¹⁴.
- `covariance_type=full` → mỗi component có 105 covariance parameters → quá nhiều, dễ fit noise.
- `covariance_type=tied` → chỉ 105 parameters total → cải thiện silhouette gấp 3 lần.

**FCM trên R¹⁴:**
- Centroid trong R¹⁴ + membership matrix.
- `m=2.0` (default) → khá gần K-Means vì `(U)^2` weighting vẫn dominant ở cluster gần nhất.
- `m=1.5` → dominant hơn → silhouette tăng nhẹ.

---

## 10. So sánh lý thuyết (không ranking)

### 10.1. Bảng so sánh

| Tiêu chí | K-Means | Agglomerative | DBSCAN | GMM | FCM |
|---|---|---|---|---|---|
| Paradigm | Partitional centroid | Hierarchical | Density-based | Probabilistic | Fuzzy partition |
| Yêu cầu K | Bắt buộc | Bắt buộc (cắt dendrogram) | Không cần | Bắt buộc | Bắt buộc |
| Noise handling | Không | Không | Có (label -1) | Không (soft) | Không (soft) |
| Membership | Hard | Hard | Hard + noise | Soft (responsibility) | Soft (membership U) |
| Cluster shape | Isotropic | Tùy linkage | Bất kỳ (density-defined) | Ellipsoidal | Isotropic |
| Sensitivity | Init, n_init | Linkage rule, metric | eps, min_samples | covariance_type, init_params | m, init |
| Interpretability | Trung bình (centroid trong R¹⁴) | Cao (dendrogram) | Thấp (nhiều cluster rất nhỏ) | Cao (responsibility matrix) | Cao (membership vector) |
| Computational | O(NKdT) | O(N² log N) hoặc O(N²) | O(N log N) với index | O(NKDT) per iteration | O(NKDT) per iteration |
| Reproducibility (cùng seed) | Có (nếu n_init=1) | Deterministic | Deterministic | Có (random_state) | Có (random_state) |
| Soft information | Không | Không | Không | Có (responsibility) | Có (membership) |

### 10.2. Limitations lý thuyết

| Algorithm | Limitation chính |
|---|---|
| K-Means | Isotropic assumption; nhạy outlier; không có soft assignment |
| Agglomerative | O(N²) memory; linkage choice có ảnh hưởng lớn; không có noise |
| DBSCAN | Nhạy eps/min_samples; không scale tốt trong high-D; "neighborhood" trở nên mơ hồ trong R¹⁴ |
| GMM | Full covariance có quá nhiều parameter; local optimum; WCSS không phù hợp |
| FCM | m parameter subjective; custom NumPy impl có reproducibility dependency |

---

## 11. So sánh thực nghiệm

### 11.1. Bảng EXP-01 baseline (5 algorithm × cùng input, K=4 hoặc realized K)

| Algorithm | K (realized) | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Noise count |
|---|---|---|---|---|---|---|---|
| K-Means | 4 | 0.5681 | 0.6128 | 4819.08 | 179858.91 | 0.0476 | 0 |
| Agglomerative (ward) | 4 | 0.5657 | 0.7360 | 4578.83 | 187019.54 | 0.5663 | 0 |
| DBSCAN | 17 | -0.1041 | 0.7721 | 49.18 | 2125.13 | 0.1083 | 3177 |
| GMM (full) | 4 | 0.1843 | 3.7486 | 131.73 | 710957.20 | 0.5189 | 0 |
| FCM (m=2.0) | 4 | 0.2691 | 1.3709 | 3869.05 | 211949.22 | 0.0658 | 0 |

### 11.2. Bảng EXP-02 K-sweep (K=2..10, 5 algorithm × K subset)

Chỉ liệt kê một số K quan trọng (xem `reports/exp02/exp02_cluster_number_summary.csv` cho đầy đủ):

**K-Means silhouette (K ∈ {2,3,4,5,6,7,8,9,10}):**
0.5839, **0.6291 (peak)**, 0.5681, 0.5697, 0.5740, 0.5118, 0.5033, 0.4983, 0.4782

**Agglomerative silhouette (K ∈ {2,3,4,5,6,7,8,9,10}):**
**0.6103 (peak)**, 0.5904, 0.5657, 0.5446, 0.4556, 0.4574, 0.4405, 0.4424, 0.4432

**DBSCAN** ở baseline chỉ có 1 diagnostic row (eps=0.5, min_samples=5) → 17 cluster, noise=3177.

**GMM silhouette (K ∈ {2,3,4,5,6,7,8,9,10}):**
0.0222, **0.2047 (peak)**, 0.1843, 0.1946, 0.1387, 0.1489, 0.1544, 0.1604, 0.1528

**FCM silhouette (K ∈ {2,3,4,5,6,7,8,9,10}):**
0.5696, **0.6271 (peak)**, 0.2691, 0.5560, 0.2711, 0.2681, 0.2047, 0.2455, 0.1914

FCM có "dip" ở K=4 (silhouette 0.27) giữa 2 peak ở K=3 (0.63) và K=5 (0.56) — pattern này không xuất hiện ở K-Means.

### 11.3. Bảng EXP-03 working selection (per-algorithm)

| Algorithm | Selected config | K | Silhouette | DBI | CH | WCSS | Status |
|---|---|---|---|---|---|---|---|
| K-Means | n_init=1, init=k-means++ | 3 | 0.6291 | 0.5881 | 5420.09 | 222674.94 | TIED_WORKING_SELECTED |
| Agglomerative | linkage=average | 3 | **0.8033** | 0.2714 | 77.15 | 748840.46 | WORKING_SELECTED |
| DBSCAN | min_samples=10 | 5 | 0.1598 | 0.7687 | 54.22 | 1739.80 | WORKING_SELECTED |
| GMM | covariance_type=tied | 4 | 0.5702 | 0.6167 | 4481.99 | 190069.74 | WORKING_SELECTED |
| FCM | m=1.5 | 3 | 0.6296 | 0.5869 | 5419.61 | 222689.21 | WORKING_SELECTED |

### 11.4. Bảng EXP-05 Block R (reproducibility, 5x repeats với seed=42)

| Algorithm | Labels_hash unique | Silhouette std | DBI std | CH std | Runtime mean (s) |
|---|---|---|---|---|---|
| K-Means | 1 | 0.0 | 0.0 | 0.0 | 0.2321 |
| Agglomerative | 1 | 0.0 | 0.0 | 0.0 | 0.7806 |
| DBSCAN | 1 | 0.0 | 0.0 | 0.0 | 0.1110 |
| GMM | 1 | 0.0 | 0.0 | 0.0 | 0.3908 |
| FCM | 1 | 0.0 | 0.0 | 0.0 | 0.0720 |

5/5 algorithms: `REPRODUCIBILITY_VERIFIED` ở EXP-05 Block R.

### 11.5. Bảng EXP-05 Block S (seed stability, 5 seeds cho K-Means/GMM/FCM)

| Algorithm | Silhouette mean (cv) | DBI mean (cv) | Labels_hash unique (5 seeds) | Cluster size distribution |
|---|---|---|---|---|
| K-Means | 0.5681 (0.0) | 0.6128 (0.0) | 5/5 | 4 distributions khác nhau (permutations của [555, 571, 224, 3021]) |
| GMM | 0.1844 (0.0006) | 3.7917 (0.0254) | 5/5 | 4 distributions khác nhau |
| FCM | 0.3230 (0.374) | 1.2255 (0.265) | 5/5 | 4 distributions khác nhau (một seed có {597, 2904, 579, 291} rất khác) |

**Lưu ý quan trọng về Block S:**
- Tất cả 5 seeds cho mỗi algorithm đều cho `labels_hash_unique_count = 5` → mỗi seed thực sự cho một hard-label set khác nhau.
- Tuy nhiên, **silhouette values lại gần như giống hệt** (cv = 0.0 cho K-Means, 0.0006 cho GMM, 0.374 cho FCM).
- ARI/AMI computation được defer sang EPIC-08 — đây là evidence raw, không phải "stability analysis" đã hoàn thành.

### 11.6. Bảng EXP-05 Block N (perturbation, sigma=0.01 và 0.05)

| Algorithm | sigma | Silhouette (cv) | DBI (cv) | n_clusters_unique_count | WCSS mean |
|---|---|---|---|---|---|
| K-Means | 0.01 | 0.5684 (0.0005) | 0.6135 (0.0020) | 1 | 179859 |
| K-Means | 0.05 | 0.5638 (0.0061) | 0.6135 (0.0027) | 1 | 180727 |
| Agglomerative | 0.01 | 0.5632 (0.0301) | 0.7240 (0.1312) | 1 | 192267 |
| Agglomerative | 0.05 | 0.5625 (0.0282) | 0.6291 (0.0338) | 1 | 188455 |
| DBSCAN | 0.01 | 0.0227 (**6.625**) | 0.6960 (0.0980) | **3** | 2055 |
| DBSCAN | 0.05 | -0.0662 (-0.797) | **1.0038** (0.0512) | 2 | 458 |
| GMM | 0.01 | 0.1818 (0.0014) | 3.8000 (0.0075) | 1 | 709178 |
| GMM | 0.05 | 0.1708 (0.0056) | 3.9400 (0.0148) | 1 | 716738 |
| FCM | 0.01 | 0.2704 (0.0041) | 1.3513 (0.0140) | 1 | 211495 |
| FCM | 0.05 | 0.3915 (0.3173) | 0.9126 (0.2532) | 1 | 195812 |

DBSCAN là algorithm nhạy nhất với perturbation (cv silhouette 6.625 ở sigma=0.01), trong khi K-Means gần như không đổi (cv 0.0005).

### 11.7. Không tạo overall rank

Theo AGENTS.md §2.5 và §2.6, tài liệu này KHÔNG tạo:
- Overall ranking giữa 5 algorithm.
- Composite score có trọng số.
- Best/winner/optimal/recommended claim.
- "Final" recommendation.

Mỗi bảng ở trên là **evidence observed**, không phải comparative conclusion. Cross-algorithm phân tích nằm ở §12.

---

## 12. Cross-metric / structural interpretation

### 12.1. Metric agreement / disagreement

Khi xét 4 internal metrics đồng thời (silhouette, DBI, CH, WCSS) trên cùng một algorithm, ta thấy:

- **K-Means (K=4)**: silhouette = 0.5681 (cao), DBI = 0.6128 (thấp — tốt), CH = 4819.08 (cao — tốt), WCSS = 179858.91 (thấp — tốt). **4 metric đồng thuận** rằng cluster có chất lượng cao.
- **Agglomerative ward (K=4)**: silhouette = 0.5657, DBI = 0.7360, CH = 4578.83, WCSS = 187019.54. DBI cao hơn K-Means (0.736 vs 0.613) trong khi các metric khác tương đương → cluster compactness/separation ratio kém hơn một chút.
- **GMM full (K=4)**: silhouette = 0.1843 (thấp), DBI = 3.7486 (rất cao — xấu), CH = 131.73 (rất thấp — xấu), WCSS = 710957.20 (rất cao — xấu). **4 metric đồng thuận** rằng cluster có chất lượng thấp với config này. Nhưng đây là metric cho **hard label**, không phải log-likelihood — GMM tối ưu log-likelihood, không tối ưu WCSS.
- **FCM (K=4, m=2.0)**: silhouette = 0.2691, DBI = 1.3709, CH = 3869.05, WCSS = 211949.22. Metric tốt hơn GMM nhưng kém hơn K-Means/Agglomerative ở cùng K.
- **DBSCAN (eps=0.5, min_samples=5)**: silhouette = -0.1041 (negative), DBI = 0.7721, CH = 49.18, WCSS = 2125.13. Silhouette và CH thấp vì 17 cluster nhỏ + 3177 noise point tạo ra dispersion ratio cực thấp. **Metric này không nên dùng để đánh giá DBSCAN** (xem AGENTS.md §3).

### 12.2. Cluster structure observation

- **K-Means / Agglomerative / FCM / GMM (hard label)**: tất cả 4 algorithm đều cho K=4 cluster không có noise. Internal structure ở K=3 thường cho silhouette tốt hơn K=4.
- **DBSCAN**: 17 cluster rất nhỏ + 72.7% noise. Đây là cấu trúc fundamentally khác với 4 algorithm còn lại — DBSCAN phát hiện micro-clusters thay vì macro-segments.
- **GMM full vs GMM tied**: cùng K=4 nhưng cấu trúc cluster rất khác (silhouette 0.18 vs 0.57) → covariance type ảnh hưởng mạnh đến EM solution.

### 12.3. Noise behavior

- 4/5 algorithm (K-Means, Agglomerative, GMM, FCM) **không có noise handling** — mọi customer phải thuộc 1 cluster hoặc có responsibility > 0 cho mọi component.
- DBSCAN là duy nhất có noise label. Ở baseline, 72.7% customer bị label là noise → cấu trúc này kém phù hợp nếu mục tiêu là segment profile cho mọi customer.
- Working selection DBSCAN (min_samples=10) tăng noise ratio lên 76.9% → tệ hơn baseline.

### 12.4. Hard vs soft assignment

| Algorithm | Soft assignment? | EPIC-07 evaluation dùng |
|---|---|---|
| K-Means | Không | Hard (only choice) |
| Agglomerative | Không | Hard (only choice) |
| DBSCAN | Không (nhưng có noise flag) | Hard (loại noise khỏi metric) |
| GMM | Có (responsibility matrix) | Hard (sau argmax) |
| FCM | Có (membership matrix U) | Hard (sau argmax) |

EPIC-07 chỉ compute internal metric trên hard label (sau argmax cho soft algorithm). Soft information chưa được khai thác trong evaluation hiện tại.

### 12.5. Computational behavior

| Algorithm | Runtime baseline (s) | Runtime Block R mean (s) | Relative ranking |
|---|---|---|---|
| K-Means | 0.0476 | 0.2321 | Nhanh nhất (cluster center iteration) |
| FCM | 0.0658 | 0.0720 | Nhanh thứ 2 (NumPy vectorized) |
| DBSCAN | 0.1083 | 0.1110 | Trung bình (deterministic sklearn) |
| GMM | 0.5189 | 0.3908 | Chậm (EM iteration) |
| Agglomerative | 0.5663 | 0.7806 | Chậm nhất (O(N²) distance matrix) |

Lưu ý: Block R runtime mean lệch so với EXP-01 baseline vì Block R dùng n_repeat=5 với reload overhead. EXP-02 cho thấy runtime ổn định hơn: K-Means runtime mean 0.037s (k2-k10), Agglomerative 0.504s, GMM 0.882s (cao nhất ở K=7 với 1.83s).

### 12.6. Interpretability

- **Agglomerative ward** có dendrogram → có thể visualize cấu trúc phân cấp. Tuy nhiên ML-03 hiện không output dendrogram visualization.
- **K-Means** centroid trong R¹⁴ → dễ diễn giải (mỗi centroid = mean của customer trong cluster đó).
- **GMM** responsibility matrix → diễn giải được customer thuộc nhiều latent class.
- **FCM** membership matrix → tương tự GMM.
- **DBSCAN**: khó diễn giải khi có nhiều cluster rất nhỏ và noise.

### 12.7. Kết luận cross-metric

Không có metric nào đứng một mình. Từng metric có limitation riêng:

- **Silhouette**: nhạy với cluster shape, không informative cho density-based.
- **DBI**: giả định cluster convex, có thể misleading khi cluster shape phức tạp.
- **CH**: nhạy với cluster density assumption.
- **WCSS**: chỉ áp dụng cho centroid-based (K-Means, FCM); không phù hợp GMM (tối ưu log-likelihood), DBSCAN (không có centroid).

Việc sử dụng multi-metric (silhouette primary + DBI tiebreaker + CH tiebreaker 2 + WCSS diagnostic) trong EPIC-03 selection protocol đã mitigate được limitation từng metric riêng lẻ.

---

## 13. Tổng hợp: Theory → Dataset → Results

### 13.1. Logic tổng hợp

```
Lý thuật (algorithm mechanism)
    ↓
Input: 4,371 customer × 14 feature đã impute / transform / scale (FE-06 C7)
    ↓
Thuật toán chạy với working config (per-algorithm)
    ↓
Cluster labels + soft membership (nếu có) + diagnostics (WCSS, n_iter, ...)
    ↓
Internal metrics (silhouette, DBI, CH, WCSS) trên hard label
    ↓
Multi-metric evidence → observed behavior
    ↓
EPIC-09 sẽ dùng labels + RFM features để segment profile
```

### 13.2. Per-algorithm tổng hợp

**K-Means:**
Lloyd iteration trong R¹⁴ → 4 centroid (working K) hoặc 3 centroid (peak silhouette) → clusters có centroid gần tâm R¹⁴ → observed silhouette 0.57 ở K=4, 0.63 ở K=3 → segments có centroid trung bình → EPIC-09 sẽ map centroid → segment profile.

**Agglomerative ward:**
Bottom-up merge theo ward criterion → dendrogram → cắt ở K=4 (working) → clusters có within-cluster variance nhỏ nhất → silhouette 0.57 ở K=4 → khi đổi linkage sang average ở K=3 → silhouette 0.80 → segments có thể nested.

**DBSCAN:**
Density expansion từ core points trong R¹⁴ scaled → 17 micro-cluster + 3177 noise (baseline) → segments rất nhỏ + 72.7% un-clustered → không phù hợp cho segment profile covering all customer ở baseline.

**GMM full:**
EM trong R¹⁴ với full covariance per component → 4 ellipsoidal latent class → posterior responsibility → hard label qua argmax → silhouette 0.18 vì full covariance overfit trên 4,371 customer × 14 feature. Chuyển sang tied → silhouette 0.57. EPIC-09 có thể khai thác responsibility matrix để soft-segment.

**FCM:**
Bezdek update trong R¹⁴ → 4 centroid + membership matrix → hard label qua argmax → silhouette 0.27 ở K=4 với m=2.0, 0.63 ở K=3 với m=1.5 → EPIC-09 có thể khai thác membership vector để soft-segment (mỗi customer có vector membership trong [0,1]^K).

### 13.3. Observation về dataset-feature space

RFM Extended 14 feature (post-RobustScale) có cấu trúc:
- 4 algorithm (K-Means, Agglomerative, GMM tied, FCM) đều có thể tìm được cấu trúc cluster ổn (silhouette 0.27 - 0.80).
- 1 algorithm (DBSCAN) không tìm được cấu trúc density rõ ràng ở working hyperparameters (72.7% noise).
- 1 algorithm (GMM full) overfit do quá nhiều covariance parameter.

Điều này gợi ý rằng **cấu trúc "tự nhiên" của R¹⁴ là centroid-based / ellipsoidal**, không phải density-based. Tuy nhiên observation này chỉ là evidence observed cho cùng một dataset, không generalize cho dataset khác.

---

## 14. Limitations

### 14.1. Methodology lock limitations

| Limitation | Nguồn | Trạng thái |
|---|---|---|
| RFM-only vs RFM Extended chưa được trả lời | ADR-0004 (RQ2 reformulated) | FUTURE WORK — `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md` |
| K-Medoids chưa được implement | ADR-0003 | OUT OF SCOPE cho phase hiện tại |
| Stability metrics ARI/AMI chưa compute | RQ3 (EPIC-08 owned) | PENDING — raw evidence đã có ở EXP-05 |
| Statistical tests và confidence intervals cho stability chưa chạy | RQ3 (EPIC-08 owned) | PENDING |
| DBSCAN noise handling trong EPIC-09 chưa xác định | CP-05.md scope | PENDING_REVIEW |
| Six feature ở ELIGIBLE_WORKING_ASSUMPTION | FE-06 §13 | PENDING_REVIEW |

### 14.2. Tài liệu / evidence limitations

- **Silhouette cho DBSCAN**: AGENTS.md §3 đã ghi "ignoring silhouette for density-based clusters" — silhouette ở DBSCAN report chỉ là artifact value, không phải quality indicator. Tài liệu này ghi nhận DBSCAN silhouette = -0.1041 ở baseline nhưng KHÔNG dùng nó để so sánh algorithm.
- **WCSS cho GMM**: GMM tối ưu log-likelihood, không phải WCSS. WCSS=710,957 cho GMM full chỉ là diagnostic cho hard-label centroid (arithmetic mean), không phải quality indicator cho Gaussian fit.
- **Soft information chưa khai thác**: GMM responsibility và FCM membership matrix có giá trị thông tin nhưng EPIC-07 evaluation chỉ dùng hard label. EPIC-09 có thể khai thác nhưng chưa được thực hiện.
- **EXP-05 Block S**: ARI/AMI computation defer sang EPIC-08. Raw evidence (5 seeds × 3 algorithms × labels_hash_unique_count=5) cho thấy seed sensitivity có thật, nhưng quantitative stability analysis chưa có.
- **EXP-05 Block N**: DBSCAN rất nhạy với perturbation (cv silhouette = 6.625) nhưng hiện tại chỉ có raw labels_hash. ARI/AMI computation sẽ cung cấp quantitative measure ở EPIC-08.
- **EXP-04 Family A (RFM-only)** đã DEFER. RQ2 chỉ có evidence cho preprocessing sensitivity trên RFM Extended. So sánh RFM-only vs RFM Extended là future work.

### 14.3. Theoretical limitations đã acknowledged

- K-Means isotropic assumption có thể không giữ trong R¹⁴.
- Agglomerative linkage choice rất ảnh hưởng → EXP-03 đã explore nhưng chỉ 3 linkages.
- DBSCAN eps/min_samples không có closed-form selection.
- GMM full covariance overfit trên 4,371 × 14.
- FCM custom NumPy implementation cần `random_state` protocol chặt để reproduce.

### 14.4. Scope NOT performed trong tài liệu này

- **KHÔNG** đánh giá "best algorithm" / "winner" / "optimal" / "recommended".
- **KHÔNG** tạo overall ranking giữa 5 algorithm.
- **KHÔNG** tạo composite score / weighted ranking.
- **KHÔNG** chạy lại bất kỳ experiment nào.
- **KHÔNG** thay đổi methodology, RQ, hoặc ADR.
- **KHÔNG** đề xuất thay đổi algorithm scope (K-Medoids vẫn OUT OF SCOPE).
- **KHÔNG** segment profile / customer profiling (thuộc EPIC-09).
- **KHÔNG** tạo visualization.

---

## 15. Kết luận có giới hạn

### 15.1. Factual findings

Dựa trên evidence thực nghiệm hiện có (185 runs từ EXP-01 → EXP-05), tài liệu này ghi nhận các sự kiện quan sát được sau:

1. **Cả 5 algorithm đều chạy thành công** trên RFM Extended 14-feature, 4,371 customer, FE-06 C7 preprocessing. Kết quả đều có status `VALID_VALUE` cho tất cả 4 internal metric (silhouette, DBI, CH, WCSS).
2. **5/5 algorithm reproducibility verified** ở EXP-05 Block R (5 repeats × seed=42 → labels_hash giống hệt).
3. **K-Means và Agglomerative ward** cho silhouette cao nhất ở working K=4 (0.5681 và 0.5657).
4. **Agglomerative với linkage=average ở K=3** đạt silhouette 0.8033 — cao nhất trong tất cả (algorithm × config) đã chạy. Đây là evidence trong search space của algorithm đó, không phải claim về algorithm nào tốt hơn algorithm nào.
5. **GMM full covariance** cho silhouette thấp nhất trong 5 algorithm ở baseline (0.1843). Chuyển sang tied covariance cải thiện silhouette lên 0.5702. Đây là evidence về sensitivity của GMM đối với covariance_type.
6. **DBSCAN** ở working hyperparameters cho 17 cluster và 72.7% noise — cấu trúc rất khác 4 algorithm còn lại. Silhouette -0.1041 không nên dùng để đánh giá chất lượng theo AGENTS.md §3.
7. **K-Means runtime nhanh nhất** ở EXP-01 baseline (0.0476s), Agglomerative chậm nhất (0.5663s).
8. **Seed sensitivity** (EXP-05 Block S): K-Means có labels_hash_unique_count=5/5 với silhouette cv = 0.0 (centroid permutation, không thay đổi cluster geometry). GMM cv = 0.0006. FCM cv = 0.374 (cao nhất).
9. **Perturbation sensitivity** (EXP-05 Block N): DBSCAN rất nhạy (cv = 6.625 ở sigma=0.01), các algorithm khác có cv < 0.05.
10. **WCSS không phù hợp cho GMM** (GMM tối ưu log-likelihood); và cho DBSCAN (WCSS chỉ trên 1194 non-noise customer).

### 15.2. Observation về methodology

- Multi-metric protocol (silhouette primary + DBI tiebreaker + CH tiebreaker 2 + WCSS diagnostic) đã mitigate được limitation từng metric riêng lẻ trong EPIC-03 selection.
- EXP-04 Family B (6 preprocessing scenarios × 5 repeats = 30 runs) cho evidence preprocessing sensitivity trên RFM Extended — KHÔNG mở rộng ra RFM-only (đó là future work).
- EPIC-08 sẽ compute ARI/AMI từ EXP-05 raw evidence để có quantitative stability analysis.

### 15.3. Hạn chế của tài liệu này

Tài liệu này:
- Tổng hợp evidence, không phải generate evidence mới.
- KHÔNG đánh giá "best algorithm".
- KHÔNG tạo ranking tổng thể.
- KHÔNG thay đổi methodology.
- KHÔNG đề xuất thay đổi algorithm scope.
- KHÔNG đề cập K-Medoids (đã OUT OF SCOPE theo ADR-0003).

Mọi số liệu đều lấy trực tiếp từ:
- `reports/exp01/exp01_initial_baseline.md`
- `reports/exp02/exp02_cluster_number_summary.csv`
- `reports/exp03/exp03_selected_configurations.csv`
- `reports/exp03/exp03_hyperparameter_analysis.md`
- `reports/exp05/exp05_reproducibility_aggregate.csv`
- `reports/exp05/exp05_seed_sweep_aggregate.csv`
- `reports/exp05/exp05_noise_perturbation_aggregate.csv`
- `reports/evaluation/eva01/eva01_summary.md`
- EPIC-06 mentor documents: `docs/research/ML02_KMeans.md`, `ML03_Hierarchical_Clustering.md`, `ML04_DBSCAN.md`, `ML05_GMM.md`, `ML06_Fuzzy_CMeans.md`
- ADR-0003, ADR-0004, methodology_overview.md, research_questions.md

### 15.4. Final statement

> Việc 5 thuật toán clustering (K-Means, Agglomerative, DBSCAN, GMM, FCM) cho kết quả **khác nhau có hệ thống** trên cùng một customer-level 14-feature space là một observation thực nghiệm. Sự khác biệt này phản ánh giả định lý thuyết khác nhau của từng thuật toán, chứ không phải ranking giữa chúng. Cross-algorithm comparison phải được diễn giải trong phạm vi observed evidence và methodology boundary đã khóa. Mọi quyết định về việc dùng thuật toán nào cho segment profile thuộc về EPIC-09 (CP-05) và mentor approval — nằm ngoài phạm vi tài liệu này.

---

## Phụ lục: Mapping evidence → nguồn artifact

| Evidence | Artifact nguồn |
|---|---|
| EXP-01 baseline (5 runs) | `reports/exp01/exp01_initial_baseline.md` + `exp01_baseline_summary.csv` |
| EXP-02 K-sweep (37 runs) | `reports/exp02/exp02_cluster_number_summary.csv` |
| EXP-03 hyperparameter (38 runs) | `reports/exp03/exp03_selected_configurations.csv` + `exp03_hyperparameter_analysis.md` |
| EXP-04 Family B preprocessing (30 runs) | `reports/exp04/exp04_scenario_results.csv` (RFM Extended only) |
| EXP-05 Block R reproducibility (25 runs) | `reports/exp05/exp05_reproducibility_aggregate.csv` |
| EXP-05 Block S seed stability (15 runs) | `reports/exp05/exp05_seed_sweep_aggregate.csv` |
| EXP-05 Block N perturbation (35 runs) | `reports/exp05/exp05_noise_perturbation_aggregate.csv` |
| 185 rows unified repository | `reports/evaluation/eva01/eva01_experiment_repository.parquet` |
| Algorithm theory | `docs/research/ML02_KMeans.md`, `ML03_Hierarchical_Clustering.md`, `ML04_DBSCAN.md`, `ML05_GMM.md`, `ML06_Fuzzy_CMeans.md` |
| ADR-0003 (algorithm scope) | `docs/decisions/0003-algorithm-scope.md` |
| ADR-0004 (research questions) | `docs/decisions/0004-research-questions.md` |
| RQ definitions | `docs/methodology/research_questions.md` |
| Methodology lock | `docs/methodology/methodology_overview.md` |
