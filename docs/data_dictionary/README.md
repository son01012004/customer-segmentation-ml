# Data Dictionary — Chỉ mục

> **Mục đích của tài liệu này.** Đây là chỉ mục cho `docs/data_dictionary/`.
> Data dictionary mô tả schema cột cho mọi dataset trong pipeline
> (raw, processed, clustering-output) — KHÔNG phải implementation note
> và KHÔNG phải research result.
>
> **Ngôn ngữ:** tiếng Việt cho phần diễn giải; giữ nguyên tiếng Anh
> cho tên cột, identifier, schema theo convention hiện có của repository.
>
> **Ngày tạo index:** 2026-10-12.
> **Cập nhật:** Phase 2B.4 — bổ sung phần này để thống nhất ngôn ngữ.
> **Phạm vi:** navigation + chính sách cập nhật data dictionary. KHÔNG
> tự ý thêm cột mới; mọi cột mới phải qua `data_dictionary.md` và
> `AGENTS.md` §5 (data dictionary update).

---

## 1. Cấu trúc thư mục

```
docs/data_dictionary/
├── README.md                     ← file này (chỉ mục)
├── data_dictionary.md            ← schema cột (tất cả các dataset)
├── dataset_provenance.md         ← nguồn gốc, SHA-256, license
├── dataset_schema.csv            ← schema dạng bảng (cho tool tiêu thụ)
└── initial_data_profile.md       ← audit raw dataset lúc đầu (FE-01)
```

---

## 2. Quy tắc cập nhật

Mọi cột mới xuất hiện trong bất kỳ dataset nào (raw, interim, processed,
clustering output) phải:

1. Được thêm vào `data_dictionary.md` (mục tương ứng).
2. Được liệt kê trong `dataset_schema.csv` (nếu áp dụng cho pipeline).
3. Có ghi chú provenance trong `dataset_provenance.md` (nếu là dataset
   mới hoặc thay đổi nguồn).
4. Đi kèm ADR tương ứng trong `docs/decisions/` nếu thay đổi **ảnh hưởng
   methodology** (xem `AGENTS.md` §2.9).

Vi phạm "skipped data dictionary update" là một **forbidden shortcut**
theo `AGENTS.md` §5.

---

## 3. Trạng thái ban đầu (FE-01)

| Mục | Người chịu trách nhiệm | Trạng thái |
|---|---|---|
| Cột transactional-level (raw primary) | TBD | Đã audit trong `initial_data_profile.md` |
| Cột transactional-level (raw backup) | TBD | Đã audit trong `initial_data_profile.md` |
| Cột customer-level feature (FE-01) | TBD | Chi tiết trong `docs/research/FE05_*.md` |
| Cột clustering-output (cluster label, ...) | TBD | Chi tiết trong `docs/research/ML01_*.md` |

Cho đến khi các mục trên được cập nhật đầy đủ, KHÔNG tham chiếu semantics
cột trong tài liệu downstream mà không có ADR tường minh trong
`docs/decisions/`.

---

## 4. Liên kết nhanh

- `data_dictionary.md` — schema cột.
- `dataset_provenance.md` — SHA-256, nguồn, license.
- `dataset_schema.csv` — bảng schema cho pipeline.
- `initial_data_profile.md` — audit raw dataset (FE-01).
- `AGENTS.md` §5 — forbidden shortcuts (skipped data dictionary update).
- `AGENTS.md` §2.12 — data privacy (KHÔNG commit raw/interim/processed).

---

**Hết chỉ mục data dictionary.**
