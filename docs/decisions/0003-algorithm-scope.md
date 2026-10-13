# ADR-0003 — Algorithm Scope: Five-Algorithm Benchmark

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, command, file path, status, EPIC ID theo
> convention hiện có.

## Status

Accepted

## Date

2026-09-22

## Task ID

EPIC-06 / EPIC-07 / EPIC-08

## Deciders

Researcher / Mentor

## Context

Tài liệu repository (README.md, AGENTS.md, FE-05, FE-06, và các tài
liệu methodology liên quan) trước đây claim rằng benchmark scope gồm
bốn thuật toán clustering: **K-Means, K-Medoids, Agglomerative
Clustering, và DBSCAN**.

Điều tra implementation thực tế phát hiện:

1. `src/customer_segmentation/clustering/kmedoids.py` chỉ chứa
   `raise NotImplementedError("fit_kmedoids is not implemented yet.")`
   — không có implementation chức năng.
2. `configs/clustering.yaml` có `kmedoids: enabled: true` nhưng với
   `metric: "TODO"` và `init: "TODO"`.
3. `AlgorithmRegistry.list_registered()` trả về chính xác năm tên:
   `kmeans`, `agglomerative`, `dbscan`, `gmm`, `fuzzy_cmeans`.
   K-Medoids **không** được registered.
4. EXP-01 đến EXP-05 chạy chính xác **năm** thuật toán: K-Means,
   Agglomerative, DBSCAN, GMM, Fuzzy C-Means.
5. EPIC-06 documentation contract mô tả sáu tài liệu ML (ML-01 đến
   ML-06), trong đó ML-06 bao trùm Fuzzy C-Means và "Algorithm Baseline"
   — nhất quán với năm adapter hoạt động.
6. Bảng `AGENTS.md` §3 liệt kê "4 fixed algorithms" bao gồm K-Medoids,
   tạo ra mâu thuẫn document với hệ thống đã implement.

Không có evidence thực nghiệm nào cho thấy K-Medoids từng được chạy
trong bất kỳ experiment nào. Claim bốn thuật toán trong AGENTS.md và tài
liệu liên quan không nhất quán với implementation năm thuật toán.

## Decision

Benchmark algorithm scope là **năm thuật toán**:

1. **K-Means** (`kmeans`) — hard centroid-based clustering.
2. **Agglomerative Clustering** (`agglomerative`) — hierarchical clustering
   với Ward linkage.
3. **DBSCAN** (`dbscan`) — density-based clustering.
4. **Gaussian Mixture Model** (`gmm`) — probabilistic model-based clustering.
5. **Fuzzy C-Means** (`fuzzy_cmeans`) — soft/fuzzy clustering với Bezdek
   update equations.

**K-Medoids** được tường minh **DEFERRED / OUT OF SCOPE** cho research
phase hiện tại (EPIC-06 đến EPIC-08).

Quyết định này áp dụng cho:

- EPIC-06 (clustering experiment framework và adapters).
- EPIC-07 (controlled experiments: EXP-01 đến EXP-05).
- EPIC-08 (stability và evaluation).

K-Medoids có thể được reconsider cho một research phase trong tương lai
(vd. EPIC-X) qua một ADR mới.

## Consequences

### Dễ hơn

- Tài liệu giờ nhất quán với hệ thống đã implement (185 run qua 5
  thuật toán).
- Không còn claim gây hiểu nhầm rằng thuật toán thứ tư đã được
  benchmark trong khi thực tế không phải.
- EPIC-08 có thể tiến hành với algorithm scope rõ ràng, đã được
  verify.
- RQ1 evaluation bao trùm chính xác các thuật toán có experimental
  evidence.

### Khó hơn hoặc rủi ro hơn

- Người đọc kỳ vọng benchmark bốn thuật toán theo tài liệu trước có
  thể bị bối rối. Điều này được giảm thiểu bằng document tường minh
  về thay đổi.
- Bất kỳ claim tương lai nào so sánh với K-Medoids literature sẽ
  không đầy đủ. Điều này chấp nhận được trong research scope hiện tại.

## Alternatives Considered

### Option A: Implement K-Medoids + Rerun EXP-01 đến EXP-05

- **Estimated impact**: ~70–90 experimental run mới qua 5 experiment.
- **Additional dependency**: `scikit-learn-extra` (yêu cầu ADR cho
  dependency mới).
- **Test mới**: ~15–20 test trong `tests/test_ml07_kmedoids.py`.
- **Timeline**: ~2–4 tuần cho implementation, testing, và rerun.
- **Decision**: Bị reject cho phase hiện tại. Implementation cost mất
  cân đối so với research benefit, vì 185 run trên 5 thuật toán đã
  cung cấp evidence đáng kể cho RQ1. K-Medoids có thể được thêm vào
  một phase tương lai.

### Option B: Cập nhật tài liệu để phản ánh Five-Algorithm Scope (ĐÃ CHỌN)

- **Estimated impact**: Chỉ cập nhật tài liệu; không rerun thí nghiệm.
- **Additional dependency**: Không có.
- **Timeline**: ~2–3 ngày cho tài liệu.
- **Decision**: Được chấp nhận. Cách này align tài liệu với hệ thống
  đã implement và loại bỏ K-Medoids claim gây hiểu nhầm mà không phá
  vỡ evidence base hiện tại.

## Scope of This Decision

ADR này bao trùm:

- EPIC-06 (ML-01 đến ML-06 algorithm adapters).
- EPIC-07 (EXP-01 đến EXP-05).
- EPIC-08 (stability và evaluation).

ADR này KHÔNG:

- Ngăn cản implementation K-Medoids trong tương lai ở một research
  phase riêng.
- Thay đổi ranh giới diễn giải cho RQ1 (không có claim "best algorithm").
- Ảnh hưởng tới tính hợp lệ của kết quả thí nghiệm hiện tại
  (185 run trên 5 thuật toán vẫn hợp lệ).

## References

- `src/customer_segmentation/clustering/kmedoids.py` — placeholder only.
- `src/customer_segmentation/clustering/registry.py` — `list_registered()`
  loại trừ kmedoids.
- `configs/clustering.yaml` — `kmedoids: enabled: true` với
  `metric: "TODO"`.
- EXP-01 đến EXP-05 manifests — tất cả tham chiếu chính xác 5 thuật toán.
- `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis
  dẫn đến quyết định này.
