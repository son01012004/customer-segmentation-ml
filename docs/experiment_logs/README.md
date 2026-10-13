# Nhật ký thí nghiệm (Experiment Logs)

> **Mục đích của tài liệu này.** Mỗi thí nghiệm chạy bởi bất kỳ thành
> viên nào trong nhóm phải được ghi lại ở đây để **kết quả có thể được
> tái lập** bởi bất kỳ thành viên khác hoặc bởi reviewer bên ngoài.
>
> **Ngôn ngữ:** tiếng Việt cho phần diễn giải; giữ nguyên tiếng Anh cho
> tên trường, identifier, command, schema theo convention hiện có.
>
> **Quy tắc provenance:** Mọi con số, ID, hash trong các file log
> phải truy xuất được về run thực tế. KHÔNG suy đoán hoặc copy từ
> file khác. Xem `AGENTS.md` §2.1, §2.7.

---

## 1. Các trường bắt buộc cho mỗi thí nghiệm

| Trường | Mô tả |
|---|---|
| Experiment ID | `EXP-001`, `EXP-002`, ... (khớp với `experiment.name`). |
| Date | Ngày chạy thí nghiệm theo chuẩn ISO-8601. |
| Author | Tên và (tuỳ chọn) email của người chạy. |
| Task ID | Mã task trong pipeline (ví dụ: `FE-01`, `CL-02`). |
| Git commit | Commit hash của repository tại thời điểm chạy. |
| Config hash | SHA-256 của các file YAML config đã được resolve. |
| Random seed | Số nguyên dùng cho tất cả RNG. |
| Environment | Phiên bản Python, OS, model CPU, RAM. |
| Raw dataset | `primary` hoặc `backup`, kèm filename và SHA-256. |
| Preprocessing | Các quy tắc làm sạch nào đã được áp dụng. |
| Feature version | Bộ feature RFM / extended nào đã được dùng. |
| Clustering setup | Các thuật toán và hyperparameters. |
| Evaluation | Internal metrics, stability, runtime. |
| Artifacts | Đường dẫn tới các hình và bảng đã sinh. |
| Notes | Quan sát và cảnh báo dạng tự do. |

---

## 2. Quy ước đặt tên file

```
NNNN-<task-id>-<short-name>.md
```

Ví dụ:

```
0001-FE-01-rfm-baseline.md
```

---

## 3. Checklist tái lập (Reproducibility)

Trước khi công bố:

- [ ] Các file config được tham chiếu bởi thí nghiệm đã được commit.
- [ ] Random seed được lưu trong log.
- [ ] Thông tin môi trường được lưu trong log.
- [ ] Mọi dataset bên ngoài được dùng có SHA-256 được ghi.
- [ ] Hình và bảng được sinh có tham chiếu tới experiment ID.

---

## 4. Lưu ý về trạng thái nghiên cứu

- File này chỉ là **template hướng dẫn**. KHÔNG tự tạo file log giả
  hoặc điền số liệu mà chưa chạy thí nghiệm thực tế.
- Mỗi thí nghiệm khi chạy phải đi kèm:
  - File log riêng (theo template trên).
  - Manifest JSON trong `reports/<stage>/<stage>_manifest.json` (xem
    `AGENTS.md` §2.7).
  - Nếu là experiment thuộc EPIC-07/08, kết quả phải được tổng hợp
    vào `reports/exp0X/exp0X_*.csv` và `exp0X_manifest.json`.
- Trạng thái methodology vẫn còn `WORKING_ASSUMPTION` / `PENDING_REVIEW`
  ở một số điểm (xem `docs/research/review/METHODOLOGY_LOCK_STATUS.md`).
  Log phải trích dẫn đúng trạng thái tại thời điểm chạy.

---

**Hết template.** File log thực tế sẽ được tạo khi thí nghiệm chạy.
