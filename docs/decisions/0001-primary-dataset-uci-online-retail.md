# ADR-0001: Primary Dataset — UCI Online Retail

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

Dự án customer-segmentation cần một transactional dataset duy nhất, có
thẩm quyền, hỗ trợ aggregation cấp customer cho các feature kiểu RFM.
DS-05 chọn **UCI Online Retail** làm dataset **primary** và
**UCI Online Retail II** làm dataset **backup**. ADR này ghi lại
**provenance** của primary dataset và ghim chính xác file mà team đang
làm việc. Nó **không** ghi lại bất kỳ research statistic nào về
dataset; công việc đó thuộc về FE-01 (Raw Dataset Audit) và các stage
sau.

## Decision

Repository dùng **UCI Online Retail** làm primary dataset.

Local raw file là:

- **Path**: `data/raw/primary/Online Retail.xlsx`
- **Verified by**: lệnh `file` (Microsoft Excel 2007+)
- **Size**: 23,715,344 bytes (≈ 23 MB)
- **SHA-256**: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`
- **Provenance check date**: 2026-09-18

## Vai trò của Dataset

- **Vai trò**: Primary
- **Initial unit of observation**: transaction-level
- **Modeling unit**: customer-level, sau aggregation
- **Feature framework**: RFM + Extended Behavioral Features
- **Backup của vai trò này**: UCI Online Retail II (xem ADR-0002)

## Provenance

- **Dataset name**: UCI Online Retail
- **Source provider**: UCI Machine Learning Repository
- **Source URL**: <https://archive.ics.uci.edu/dataset/352/online+retail>
  (đã verify bằng cách fetch trang vào 2026-09-18; URL trỏ đến entry
  dataset UCI chính thức)
- **UCI dataset ID**: 352
- **Article DOI** (bài báo published đi kèm dataset):
  `10.1057/dbm.2012.17` — Daqing Chen, Sai Liang Sain, Kun Guo,
  *"Data mining for the online retail industry: A case study of RFM
  model-based customer segmentation using data mining"*, Journal of
  Database Marketing and Customer Strategy Management, Vol. 19, No. 3,
  pp. 197–208, 2012 (đã verify bằng web search vào 2026-09-18).
- **UCI-assigned dataset DOI**: Chưa xác minh trực tiếp từ trang UCI
  ID 352. (Công cụ fetch chỉ trả về bảng biến; block citation/DOI
  không hiển thị trên trang rendered. Sẽ điền sau khi kiểm tra thủ
  công trang UCI. Dataset backup ID 502 có DOI `10.24432/C5CG6D` hiển
  thị để tham chiếu.)
- **License**: **CC BY 4.0** (Creative Commons Attribution 4.0
  International). Đã verify bằng web search hiển thị license footer
  UCI cho dataset này vào 2026-09-18.
- **License redistribution note**: CC BY 4.0 cho phép chia sẻ và adapt
  cho bất kỳ mục đích nào với credit phù hợp. Đây là câu hỏi tách
  biệt với việc liệu ta có redistribute file trong Git repository
  này hay không: **ta không** — raw data ở local và git-ignored
  (xem Reproducibility bên dưới).
- **Download date**: Chưa được ghi ở cấp team cho bản copy đầu tiên
  này. Filesystem mtime của file là `2023-05-22 15:20:26 +07:00`. Các
  phiên bản tương lai của ADR này nên ghi lại download date thực sự
  sau mỗi lần refresh.

## Filename Note (canonical vs. on-disk)

`configs/dataset.yaml` khai báo canonical primary filename là
`online_retail.xlsx`. File thực tế hiện đang trên đĩa là
`Online Retail.xlsx` (chữ cái đầu viết hoa và có dấu cách). File
**chưa được đổi tên** — team lead sẽ quyết định canonical filename
policy như một phần của dataset audit (FE-01). Sự không khớp được ghi ở
đây để minh bạch và sẽ được reconcile bằng một ADR khi audit hoàn tất.

## Reproducibility

- Raw dataset file **không được commit** vào Git repository. Nó bị
  loại bởi `.gitignore` rule `/data/raw/**`.
- `git check-ignore -v "data/raw/primary/Online Retail.xlsx"` trả về:
  `.gitignore:90:/data/raw/**   data/raw/primary/Online Retail.xlsx`
- Mỗi bản local copy của researcher phải tạo ra cùng SHA-256
  (`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`)
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
- Dataset backup (UCI Online Retail II) được ghi riêng trong ADR-0002.
