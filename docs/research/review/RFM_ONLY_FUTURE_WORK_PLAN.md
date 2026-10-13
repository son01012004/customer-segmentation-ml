# RFM-Only Materialization — Future Work Plan

> **Trạng thái:** FUTURE_WORK (không nằm trong research scope hiện tại)
> **Ngày:** 2026-09-22
> **Nguồn:** ADR-0004 (RQ2 reformulation)
> **Người chịu trách nhiệm:** Mentor / future researcher

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho identifier, file path, command, status enum theo
> convention hiện có.

---

## Context

Câu hỏi RQ2 ban đầu ("Việc thêm các extended behavioral feature
(RFM Extended, 14 feature) có cải thiện clustering quality so với chỉ
dùng RFM core feature (Recency, Frequency, Monetary) hay không?") yêu
cầu một RFM-only artifact hiện không tồn tại trong repository.

Trong EPIC-07 / EPIC-08 methodology lock, RQ2 đã được reformulate thành:

> **RQ2 (reformulated):** Chiến lược preprocessing ảnh hưởng thế nào đến
> clustering quality dưới một feature representation cấp customer cố
> định?

Reformulated RQ2 này trả lời được với evidence EXP-04 Family B hiện có
(6 preprocessing scenario × 5 repeat = 30 run).

Original RFM-only comparison được document là future work.

---

## RFM-Only Materialization sẽ yêu cầu những gì

### Định nghĩa feature

RFM-only artifact = chỉ 3 feature:

| Feature | Định nghĩa | Nguồn |
|---|---|---|
| `Recency` | Days từ `LastPurchaseDate` đến `ReferenceDate` | Giống FE-06 hiện tại |
| `Frequency` | `nunique(InvoiceNo)` (FREQ-01) | Giống FE-06 hiện tại |
| `Monetary` | `MonetarySigned` = `sum(LineRevenue)` | Giống FE-06 hiện tại |

### Các bước implementation

| # | Bước | Chi tiết | Effort ước tính |
|---|---|---|---|
| 1 | Viết ADR | `docs/decisions/0005-rfm-only-materialization.md` | 1 ngày |
| 2 | Implement pipeline | Hàm mới trong `src/customer_segmentation/transformation/` — đọc 3 feature từ `customer_candidates.parquet`, áp dụng FE-06 C7 pipeline độc lập (fit trên 3 feature only) | 1-2 ngày |
| 3 | Tests | `tests/test_pipeline_rfm_only.py` (~5-10 test) | 1 ngày |
| 4 | Config | Cập nhật `configs/transformation.yaml` với entry RFM-only | 1 giờ |
| 5 | Execute | Sinh `data/processed/final_clustering_dataset_rfmonly.parquet` | 1 giờ |
| 6 | Verify | SHA-256, shape (4371, 3), no NaN, no Inf | 1 giờ |
| 7 | EXP-04 Family A | 6 scenario × 5 repeat = 30 run | 1-2 ngày |
| 8 | Cập nhật RQ2 | Revert RQ2 về framing ban đầu (RFM-only vs RFM Extended) | 1 ngày |
| 9 | Reports | Cập nhật RQ2 section trong methodology docs và thesis | 1 ngày |
| **Tổng** | | | **~1-2 tuần** |

### Ràng buộc chính

1. **Independent preprocessing pipeline**: RFM-only phải có Yeo-Johnson +
   RobustScaler fit riêng (fit trên 3 feature only; KHÔNG reuse FE-06 C7
   lambda value từ 14-feature fit).
2. **Same ReferenceDate**: `2011-12-10T12:50:00` (giống FE-05/FE-06).
3. **Same Frequency definition**: `nunique(InvoiceNo)` (FREQ-01, current
   default).
4. **Same Monetary definition**: `MonetarySigned` (current default).
5. **READ-ONLY input**: `customer_candidates.parquet` SHA không đổi.
6. **Artifact riêng**: `final_clustering_dataset_rfmonly.parquet` (KHÔNG
   overwrite `final_clustering_dataset.parquet`).
7. **Không rerun FE-01 đến FE-06**: RFM-only derivation là downstream
   từ FE-05 candidates.

### EXP-04 Family A Scenario Matrix

Giống Family B (6 full-matrix scenario):

| Scenario | Transformation | Scaling | Vai trò |
|---|---|---|---|
| A-S01 | none | none | A baseline |
| A-S02 | none | standard | Candidate |
| A-S03 | none | minmax | Candidate |
| A-S04 | none | robust | Candidate |
| A-S05 | yeo_johnson | standard | Candidate |
| A-S06 | yeo_johnson | robust | Candidate |

Control: K-Means, K=4, median imputation, seed=42.

Tổng: 30 run.

### Kết quả mong đợi

Nếu RFM-only được materialize và Family A được execute:

- RFM-only metric cho từng scenario (silhouette, DBI, CH, WCSS).
- Cross-comparison: RFM-only vs RFM Extended cho từng scenario.
- Δ-metric (chênh lệch quality metric giữa RFM-only và RFM Extended).
- ARI/AMI giữa RFM-only clustering và RFM Extended clustering cho cùng
  customer set.

### Khi nào quyết định

Đây là **mentor decision**. Nếu thesis reviewer hoặc publication review
yêu cầu RFM-only comparison, plan này có thể được execute. Cho tới
khi đó, nó là future work.

---

## Checklist

- [ ] Viết `docs/decisions/0005-rfm-only-materialization.md` ADR
- [ ] Implement `src/customer_segmentation/transformation/rfm_only_pipeline.py`
- [ ] Thêm `configs/transformation.yaml` entry cho RFM-only
- [ ] Viết `tests/test_pipeline_rfm_only.py`
- [ ] Execute pipeline: `final_clustering_dataset_rfmonly.parquet`
- [ ] Verify SHA-256, shape, no NaN, no Inf
- [ ] Chạy EXP-04 Family A (30 run)
- [ ] Cập nhật `docs/methodology/research_questions.md` RQ2 section
- [ ] Cập nhật ADR-0004 với RQ2 completion status
- [ ] Cập nhật thesis / paper với RFM-only evidence

---

## References

- ADR-0004: `docs/decisions/0004-research-questions.md`
- FE-06 documentation: `docs/research/FE06_Transformation_Final_Dataset.md`
- EXP-04 review: `docs/research/review/EXP04_PREPROCESSING_FEATURE_REVIEW.md`
