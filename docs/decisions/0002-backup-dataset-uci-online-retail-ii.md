# ADR-0002: Backup Dataset — UCI Online Retail II

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho SHA-256, DOI, URL, command, status, identifier theo
> convention hiện có.

## Status

Accepted

## Date

2026-09-18

## Task ID

DS-05 (Dataset Selection) + foundation provenance step

## Deciders

Repository foundation owner; review pending by project lead.

## Context

DS-05 chọn một dataset **backup** cùng với primary (UCI Online Retail,
xem ADR-0001) để nếu primary file trở nên unavailable, corrupted, hoặc
restricted, dự án có thể tiếp tục mà không cần quyết định lại câu hỏi
dataset. Backup phải đến từ cùng provider, có cùng schema, và áp dụng
cho cùng research scope (segmentation cấp customer trên dữ liệu
transactional bán lẻ).

ADR này ghi lại **provenance** của backup dataset và ghim chính xác
local file mà team đang làm việc. Nó **không** ghi lại bất kỳ research
statistic nào về dataset; công việc đó thuộc về FE-01 (Raw Dataset
Audit) và các stage sau.

## Decision

Repository dùng **UCI Online Retail II** làm backup dataset.

Local raw file là:

- **Path**: `data/raw/backup/online_retail_II.xlsx`
- **Verified by**: lệnh `file` (Microsoft Excel 2007+)
- **Size**: 45,622,278 bytes (≈ 44 MB; listing UCI tự thân báo 43.5 MB)
- **SHA-256**: `bcbe73b35f5b7babf197cb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`
- **Provenance check date**: 2026-09-18

## Vai trò của Dataset

- **Vai trò**: Backup
- **Initial unit of observation**: transaction-level
- **Modeling unit**: customer-level, sau aggregation
- **Feature framework**: RFM + Extended Behavioral Features
- **Primary của vai trò này**: UCI Online Retail (xem ADR-0001)

## Provenance

- **Dataset name**: UCI Online Retail II
- **Source provider**: UCI Machine Learning Repository
- **Source URL**: <https://archive.ics.uci.edu/dataset/502/online+retail+ii>
  (đã verify bằng cách fetch trang vào 2026-09-18; URL trỏ đến entry
  dataset UCI chính thức và hiển thị citation block)
- **UCI dataset ID**: 502
- **DOI**: `10.24432/C5CG6D` — đã verify trực tiếp từ UCI citation
  block vào 2026-09-18: *"Chen, D. (2012). Online Retail II [Dataset].
  UCI Machine Learning Repository. <https://doi.org/10.24432/C5CG6D>"*
- **UCI donation date** (hiển thị trên trang dataset): 2019-09-20
- **License**: **CC BY 4.0** (Creative Commons Attribution 4.0
  International). Đã verify trực tiếp từ trang dataset UCI vào
  2026-09-18: *"This dataset is licensed under a Creative Commons
  Attribution 4.0 International (CC BY 4.0) license."*
- **License redistribution note**: CC BY 4.0 cho phép chia sẻ và adapt
  cho bất kỳ mục đích nào với credit phù hợp. Đây là câu hỏi tách
  biệt với việc liệu ta có redistribute file trong Git repository
  này hay không: **ta không** — raw data ở local và git-ignored
  (xem Reproducibility bên dưới).
- **Download date**: Chưa được ghi ở cấp team cho bản copy đầu tiên
  này. Filesystem mtime của file là `2023-05-22 15:20:22 +07:00`. Các
  phiên bản tương lai của ADR này nên ghi lại download date thực sự
  sau mỗi lần refresh.

## Filename Note (canonical vs. on-disk)

`configs/dataset.yaml` khai báo canonical backup filename là
`online_retail_II.xlsx`. File thực tế hiện đang trên đĩa được đặt tên
`online_retail_II.xlsx`, đã khớp với canonical name. Không cần đổi tên.

## Reproducibility

- Raw dataset file **không được commit** vào Git repository. Nó bị
  loại bởi `.gitignore` rule `/data/raw/**`.
- `git check-ignore -v "data/raw/backup/online_retail_II.xlsx"` trả về:
  `.gitignore:90:/data/raw/**   data/raw/backup/online_retail_II.xlsx`
- Mỗi bản local copy của researcher phải tạo ra cùng SHA-256
  (`bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`)
  để kết quả có thể so sánh được giữa các máy.
- Bất kỳ lần re-download dataset nào trong tương lai phải được phản
  ánh trong ADR này với SHA-256 mới, download date mới, và một
  rationale ngắn ghi dưới "Notes".

## Notes

- ADR này ghi **chỉ** những gì đã được verify bên ngoài chính dữ liệu:
  file existence, file format, file size, SHA-256, và metadata trang
  nguồn.
- Những điều sau **nằm ngoài scope** của ADR này và thuộc về FE-01
  (Raw Dataset Audit) và các stage sau:
  - row count, customer count, transaction count
  - missing-value, duplicate, và outlier count
  - data type, date range, distribution của quantity/monetary
  - bất kỳ descriptive statistic nào khác
- Không có claim "best" algorithm nào được ngụ ý bởi việc chọn dataset
  này.
- Primary dataset (UCI Online Retail) được ghi riêng trong ADR-0001.
- Backup dataset chỉ nên được dùng khi primary unavailable. Bất kỳ
  lần chuyển từ primary sang backup phải tự nó được ghi thành một
  ADR mới.
