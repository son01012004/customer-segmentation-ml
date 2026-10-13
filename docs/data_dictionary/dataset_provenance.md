# Dataset Provenance

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho tên cột, identifier, SHA-256, DOI, URL, file path,
> command, status enum theo convention hiện có. Mọi con số (file size,
> SHA-256) truy xuất được về raw file trong `data/raw/`.

Tài liệu này ghi lại **provenance** của mọi raw dataset hiện có trong
repository. Nó là một **structural reference** — chỉ ghi lại những gì đã
được verify từ bên ngoài chính dữ liệu (file existence, file format,
size, SHA-256, source URL, license). Nó **không** ghi lại bất kỳ research
statistic nào (row count, customer count, date range, distribution, ...);
những thứ đó thuộc về FE-01 (Raw Dataset Audit) và các stage sau.

Nếu một giá trị trong bảng dưới đây là **`Chưa xác minh`**, nghĩa là
thông tin chưa được verify từ nguồn chính thức. **Không** điền research
estimate ở đây — hãy tạo ADR thay thế.

## Bảng tóm tắt

| Dataset               | Vai trò | Local Path                  | Actual Filename           | File Size (bytes) | File Size (human) | SHA-256                                                              | Source                                                                                                  | License    | Trạng thái                                |
| --------------------- | ------- | --------------------------- | ------------------------- | ----------------- | ----------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------- |
| UCI Online Retail     | Primary | `data/raw/primary/`         | `Online Retail.xlsx`      | 23,715,344        | ≈ 23 MB           | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`   | UCI Machine Learning Repository — <https://archive.ics.uci.edu/dataset/352/online+retail> (verified 2026-09-18) | CC BY 4.0  | Verified (filename khác canonical, xem Notes) |
| UCI Online Retail II  | Backup  | `data/raw/backup/`          | `online_retail_II.xlsx`   | 45,622,278        | ≈ 44 MB           | `bcbe73b35f5b7babf197cb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`   | UCI Machine Learning Repository — <https://archive.ics.uci.edu/dataset/502/online+retail+ii> (verified 2026-09-18) | CC BY 4.0  | Verified                              |

### Identifiers

| Dataset               | UCI Dataset ID | DOI                                                  |
| --------------------- | -------------- | --------------------------------------------------- |
| UCI Online Retail     | 352            | Article DOI: `10.1057/dbm.2012.17`. UCI dataset DOI: Chưa xác minh trực tiếp từ trang UCI. |
| UCI Online Retail II  | 502            | `10.24432/C5CG6D` (verified from UCI citation block) |

### Kiểm tra file format

| Dataset               | Output của lệnh `file`     |
| --------------------- | -------------------------- |
| UCI Online Retail     | `Microsoft Excel 2007+`    |
| UCI Online Retail II  | `Microsoft Excel 2007+`    |

### File mtime trên đĩa (filesystem metadata, không phải provenance)

| Dataset               | Filesystem mtime          |
| --------------------- | ------------------------- |
| UCI Online Retail     | `2023-05-22 15:20:26 +07:00` |
| UCI Online Retail II  | `2023-05-22 15:20:22 +07:00` |

Mtime phản ánh thời điểm file đến máy này. Nó **không** phải download
timestamp; ngày download thực sự cho các bản copy này là
**Chưa xác minh** ở cấp team.

## Verification commands

Các giá trị trong file này được lấy bằng các lệnh sau, thực thi ngày
2026-09-18 từ repository root. Chúng là **non-mutating** và có thể được
re-run bởi bất kỳ reviewer nào.

```bash
# Format check
file "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# Size
du -b "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# SHA-256
sha256sum "data/raw/primary/Online Retail.xlsx" "data/raw/backup/online_retail_II.xlsx"

# Git-ignore check
git check-ignore -v "data/raw/primary/Online Retail.xlsx"
git check-ignore -v "data/raw/backup/online_retail_II.xlsx"
```

## Git safety

Cả hai file bị loại khỏi version control bởi rule `/data/raw/**` trong
`.gitignore`. Các placeholder `.gitkeep` tương ứng trong `data/raw/`,
`data/raw/primary/`, và `data/raw/backup/` vẫn được tracked để giữ cấu
trúc thư mục.

| File                                       | `git check-ignore` exit | Trạng thái |
| ------------------------------------------ | ----------------------- | ---------- |
| `data/raw/primary/Online Retail.xlsx`      | 0 (ignored)             | PASS       |
| `data/raw/backup/online_retail_II.xlsx`    | 0 (ignored)             | PASS       |
| `data/raw/primary/.gitkeep`                | 1 (tracked)             | PASS       |
| `data/raw/backup/.gitkeep`                 | 1 (tracked)             | PASS       |

## Ghi chú

- **Canonical filename mismatch (Primary only)**:
  `configs/dataset.yaml` khai báo canonical primary filename là
  `online_retail.xlsx`, nhưng file thực tế trên đĩa là
  `Online Retail.xlsx`. File **chưa được đổi tên**. Điều này sẽ được
  reconcile qua một ADR trong dataset audit (FE-01).
- **Filename agreement (Backup)**: file backup
  `online_retail_II.xlsx` đã khớp với canonical name trong
  `configs/dataset.yaml`.
- **Cách hiểu license**: CC BY 4.0 cho phép chia sẻ và adapt cho bất kỳ
  mục đích nào với credit phù hợp. Điều này **không** có nghĩa là raw data
  nên được commit vào repository — raw data ở local và git-ignored theo
  data-privacy rule của dự án.
- **Cái KHÔNG có trong file này**: row count, customer count, transaction
  count, missing-value, duplicate, hoặc outlier count, data type, date
  range, và bất kỳ descriptive statistic nào khác. Những thứ đó thuộc về
  FE-01 và không được thêm vào đây.

## ADR liên quan

- `docs/decisions/0001-primary-dataset-uci-online-retail.md`
- `docs/decisions/0002-backup-dataset-uci-online-retail-ii.md`
