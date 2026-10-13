# Data Dictionary — UCI Online Retail (Primary, FE-01)

Data dictionary này là **canonical reference** cho raw primary dataset
được dùng trong nghiên cứu customer-segmentation. Nó document mọi cột ở
mức mà team đã thống nhất (theo quyết định DS-05 và audit FE-01).

- **Dataset**: UCI Online Retail (Primary) — xem
  [`docs/decisions/0001-primary-dataset-uci-online-retail.md`](../decisions/0001-primary-dataset-uci-online-retail.md).
- **File**: `data/raw/primary/Online Retail.xlsx` (xem thêm
  [`dataset_provenance.md`](./dataset_provenance.md) cho SHA-256 và
  source URL).
- **Sheet**: `Online Retail` (file có 1 sheet).
- **Rows**: **541,909**
- **Columns**: **8**

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho tên cột, identifier, dtype, value, range theo convention
> hiện có của repository. Các con số (row count, missing count/rate,
> range) truy xuất được về `reports/fe01/primary_*.csv` (xem cuối file).

## Ghi chú về canonical filename

`configs/dataset.yaml` khai báo canonical primary filename là
`online_retail.xlsx`, nhưng file thực tế trên đĩa là
`Online Retail.xlsx`. File **chưa được đổi tên** (xem
[`dataset_provenance.md`](./dataset_provenance.md) cho thảo luận đầy
đủ). Schema và ý nghĩa cột dưới đây mô tả các cột **đúng theo file
thực tế trên đĩa**.

## Tham chiếu cột

| Cột | Data Type | Vai trò | Ý nghĩa | Đơn vị | Nguồn | Missing Count | Missing Rate | Unique Values | Expected Range | Business Meaning |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `InvoiceNo` | `object` | Identifier (transaction) | 6-digit integral invoice number. Leading 'C' đánh dấu cancellation theo convention UCI. | code | UCI Online Retail (raw primary file) | 0 | 0.0000 | 25,900 | [N/A (mixed types), N/A (mixed types)] | Dùng để nhóm các transaction line vào một purchase event và để nhận diện cancellation (tiền tố 'C'). |
| `StockCode` | `object` | Identifier (product) | 5-digit integral product (item) code. Có thể là alphanumeric (vd. '85123A'). | code | UCI Online Retail (raw primary file) | 0 | 0.0000 | 4,070 | [N/A (mixed types), N/A (mixed types)] | Dùng để phân biệt sản phẩm và tính các feature product-level diversity cho mỗi customer. |
| `Description` | `object` | Categorical Feature (text) | Product (item) name như ghi trong invoice line. | text | UCI Online Retail (raw primary file) | 1,454 | 0.2683 | 4,223 | [N/A (mixed types), N/A (mixed types)] | Free-text product label. Hữu ích cho product taxonomy, nhưng **không** dùng trực tiếp làm clustering feature. |
| `Quantity` | `int64` | Numerical Feature (transaction-line) | Số lượng sản phẩm (item) trên mỗi transaction. | items | UCI Online Retail (raw primary file) | 0 | 0.0000 | 722 | [-80995.0, 80995.0] | Dùng (sau preprocessing) để derive monetary value và basket-size features. |
| `InvoiceDate` | `datetime64[us]` | Date Feature (transaction) | Ngày và giờ khi transaction được sinh ra. | datetime | UCI Online Retail (raw primary file) | 0 | 0.0000 | 23,260 | [2010-12-01 08:26:00, 2011-12-09 12:50:00] | Dùng để tính Recency và purchase-cadence features ở customer level. |
| `UnitPrice` | `float64` | Numerical Feature (transaction-line) | Giá sản phẩm trên mỗi đơn vị, tính bằng sterling (£). | GBP (£) | UCI Online Retail (raw primary file) | 0 | 0.0000 | 1,630 | [-11062.06, 38970.0] | Dùng (sau preprocessing) để tính Monetary (= sum(Quantity * UnitPrice)) cho mỗi customer. |
| `CustomerID` | `float64` | Identifier (customer) | 5-digit integral customer number, unique per customer. Missing ở ~24.93% row trong raw primary file. | code | UCI Online Retail (raw primary file) | 135,080 | 24.9267 | 4,372 | [12346.0, 18287.0] | Customer-level join key cho modelling unit. Không thể aggregate customer nếu thiếu cột này. |
| `Country` | `str` | Categorical Feature | Tên quốc gia nơi customer cư trú. | category | UCI Online Retail (raw primary file) | 0 | 0.0000 | 38 | [Australia, Unspecified] | Behavioural attribute dùng để segment theo geography. Chủ yếu là UK trong raw data (~91.4%). |

## Phân cấp identifier

Unit of observation của dataset là **transaction-line**. Modelling unit
dự kiến là **customer**.

| Cấp | Cột | Ghi chú |
| --- | --- | --- |
| Transaction | `InvoiceNo` | Một invoice có nhiều row (mỗi row một sản phẩm). Tiền tố `C` đánh dấu cancellation. |
| Product | `StockCode` | Mã sản phẩm riêng biệt. Có thể là alphanumeric. |
| Customer | `CustomerID` | Missing ở ≈ 24.93% raw row — phải xử lý trong preprocessing. |

## Nguồn của mọi con số trong file này

Mọi con số trong tài liệu này đến từ
[`reports/fe01/primary_missing.csv`](../../reports/fe01/primary_missing.csv),
[`reports/fe01/primary_numerical.csv`](../../reports/fe01/primary_numerical.csv),
và [`reports/fe01/primary_schema.csv`](../../reports/fe01/primary_schema.csv).
Chúng được tính live bởi
[`scripts/run_fe01_audit.py`](../../scripts/run_fe01_audit.py) và docs
được sinh lại bởi
[`scripts/generate_fe01_docs.py`](../../scripts/generate_fe01_docs.py).
