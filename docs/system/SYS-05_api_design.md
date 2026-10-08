# SYS-05 — API Design

> **Mã tài liệu:** SYS-05
> **Tên:** **API Design**
> **Trạng thái:** `WORKING_DRAFT v0.1`
> **Ngày:** 2026-10-07
> **Phạm vi:** Đặc tả contract API cho **Customer Segmentation ML**.
> **Đối tượng đọc:** Backend engineer, ML engineer, FE developer (sau này), reviewer nghiên cứu.
> **Người chịu trách nhiệm:** Architecture owner (Human researcher).
> **Tài liệu liên quan:**
> - [`SYS-01_requirements.md`](./SYS-01_requirements.md) — yêu cầu sản phẩm & phi chức năng.
> - [`SYS-02_architecture.md`](./SYS-02_architecture.md) — kiến trúc tổng thể, runtime view.
> - [`SYS-03_data_model.md`](./SYS-03_data_model.md) — schema dữ liệu.
> - [`SYS-04_ml_processing_pipeline.md`](./SYS-04_ml_processing_pipeline.md) — pipeline xử lý ML.

> **Quy ước ngôn ngữ**
> - Tiếng Việt cho mô tả, tiếng Anh cho identifier / endpoint / schema.
> - Mọi thuật ngữ ML giữ nguyên tên gốc (K-Means, silhouette, elbow, Davies-Bouldin, Calinski-Harabasz, Fuzzy C-Means, ...).
> - Mọi số liệu / range / policy phải có nguồn trỏ về `SYS-01` / `SYS-03` / `SYS-04` / config. Không invent.

---

## Mục lục

1. [Mục đích & Phạm vi](#1-mục-đích--phạm-vi)
2. [Nguyên tắc thiết kế API](#2-nguyên-tắc-thiết-kế-api)
3. [Mô hình giao tiếp tổng thể](#3-môi-giao-tiếp-tổng-thể)
4. [Quy ước chung](#4-quy-ước-chung)
5. [Nhóm A — Admin & Configuration](#5-nhóm-a--admin--configuration)
6. [Nhóm B — Dataset Management](#6-nhóm-b--dataset-management)
7. [Nhóm C — Preprocessing & Feature Engineering](#7-nhóm-c--preprocessing--feature-engineering)
8. [Nhóm D — Clustering & Model Registry](#8-nhóm-d--clustering--model-registry)
9. [Nhóm E — Evaluation](#9-nhóm-e--evaluation)
10. [Nhóm F — Profiling & Reporting](#10-nhóm-f--profiling--reporting)
11. [Nhóm G — Telemetry & System](#11-nhóm-g--telemetry--system)
12. [Phiên bản hoá & tương thích](#12-phiên-bản-hoá--tương-thích)
13. [Bảo mật & xác thực](#13-bảo-mật--xác-thực)
14. [Lỗi & mã lỗi chuẩn](#14-lỗi--mã-lỗi-chuẩn)
15. [PENDING_REVIEW & open questions](#15-pending_review--open-questions)

> **Mẹo đọc:** mỗi quyết định trong tài liệu này gán nhãn theo §2.11 —
> `CONTRACT_REQUIRED` / `WORKING_ASSUMPTION` / `REVIEW_REQUIRED` /
> `IMPLEMENTATION_OPTION`. Đọc §2.11 trước khi dùng tài liệu.

---

## 1. Mục đích & Phạm vi

### 1.1 Mục đích

Tài liệu này đặc tả **API contract** cho toàn bộ hệ thống Customer Segmentation ML
bao gồm:

- REST API do backend service cung cấp.
- Command-line / internal API do Cổ CLI / worker sử dụng.
- Boundary giữa frontend (sau này), backend, ML core, storage layer.

Mục tiêu:

1. Cho phép frontend (Phase sau) và operator tương tác với hệ thống thông qua
   REST/HTTP + tệp dữ liệu theo một contract duy nhất.
2. Đảm bảo mọi thao tác nghiên cứu (training, evaluation, profiling) đều được
   **audit được**, **reproducible được** và **không silent override methodology**
   (xem `AGENTS.md` §2.1, §2.7).
3. Cho phép frontend / script tự động hoá đầy đủ quy trình từ
   **upload dataset → run preprocessing → train → evaluate → profile → report**
   mà không cần SSH vào worker.

### 1.2 Phạm vi (in-scope)

- API cho **admin / configuration** (xem Nhóm A).
- API cho **dataset management**: upload, validate, list, version, schema check
  (xem Nhóm B).
- API cho **preprocessing** và **feature engineering** (xem Nhóm C).
- API cho **clustering** + **model registry / load** (xem Nhóm D).
- API cho **evaluation** (xem Nhóm E).
- API cho **profiling** + **report generation** (xem Nhóm F).
- API cho **telemetry** (health, jobs, logs, lineage) (xem Nhóm G).

### 1.3 Ngoài phạm vi (out-of-scope)

- **Thiết kế UI/UX** chi tiết của frontend — chỉ đặc tả contract.
- **Thay đổi methodology ML** — API phải trung hoà về methodology; mọi tham số
  đều tới từ `configs/*.yaml` (xem `SYS-04`).
- **Các thuật toán ngoài scope nghiên cứu** (K-Medoids, HDBSCAN, ...) — không
  expose qua API.
- **Streaming inference online** — sản phẩm là batch research tool, không phải
  online serving. Mọi endpoint "predict" ở đây là predict-theo-batch.

---

## 2. Nguyên tắc thiết kế API

1. **Resource-oriented.** URL xác định resource, HTTP method xác định hành động.
2. **Idempotency.** `GET`, `PUT`, `DELETE` phải idempotent. `POST` chỉ dùng cho
   hành động tạo mới hoặc trigger job.
3. **Stateless HTTP API; ML state được externalize.** HTTP API không lưu
   state ML trong bộ nhớ process. Mọi state ML (model artifact, transform
   state, dataset version, config hash, run metadata) được externalize vào
   artifact storage + metadata store. Server chỉ là coordinator (xem
   `SYS-02` §5).
4. **Job-based long-running.** Các thao tác nặng (preprocess full, train, evaluate)
   là **async job** trả về `job_id`, polling `/jobs/{id}` để lấy kết quả.
5. **Repro by reference.** Mọi request chạy ML phải kèm `config_id` hoặc
   `config_snapshot_id`. Không nhận config inline để ghi đè policy.
6. **Standard error envelope.** Mọi lỗi trả về theo cùng một schema (xem
   §14).
7. **Versioned URL.** Mọi endpoint prefix với `/api/v1`. Không breaking change
   trong v1, đổi contract → v2 (xem §12).
8. **Pagination + filtering chuẩn.** Mọi list endpoint dùng cursor-based hoặc
   offset-based pagination với filter chuẩn.
9. **OpenAPI-first.** Mọi endpoint phải khai báo trong OpenAPI 3.1 schema
   (`openapi/api_v1.yaml`). Backend xanh demo generate code cung cấp client.
10. **Audit + lineage.** Mọi mutation tạo ra một entry in `data/input/audit/`
    hoặc storage tương đương (xem `SYS-03` §13).

### 2.11 Decision classification (đọc kỹ trước khi dùng)

Mỗi quyết định trong tài liệu này phải được gán **một trong bốn nhãn**
sau. Nhãn xuất hiện ngay tại mục/endpoint/quy tắc liên quan. Endpoint
không mang nhãn nào → mặc định hiểu là `CONTRACT_REQUIRED` ở mức đặc
tả resource, **chưa** bao gồm bất kỳ parameter ML cụ thể nào.

| Nhãn                  | Ý nghĩa                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| `CONTRACT_REQUIRED`   | Phần này là một phần bắt buộc của API contract; cần có khi triển khai. Không chứa quyết định methodology. |
| `WORKING_ASSUMPTION`  | Đề xuất tạm thời của architecture owner. Có thể thay đổi khi mentor/researcher review; chưa lock.          |
| `REVIEW_REQUIRED`     | Có nhiều cách làm hợp lý; hiện chưa đủ evidence để chốt một lựa chọn. Cần mentor quyết.                    |
| `IMPLEMENTATION_OPTION`| Là lựa chọn công nghệ/cách triển khai, không phải quyết định methodology; Phase sau được quyền thay đổi.  |

> Nhãn không thay thế `WORKING_ASSUMPTION` / `PENDING_REVIEW` / `FINAL` của
> methodology (xem `AGENTS.md` §2.1, §2.5). Khi một endpoint đụng methodology
> → methodology status vẫn do plan/ADR quyết, không phải do API contract.

---

## 3. Mô hình giao tiếp tổng thể

```
┌────────────┐   HTTPS/JSON    ┌──────────────────┐
│  Frontend  │ ──────────────▶ │  Backend (REST)  │
│ (sau này)  │ ◀────────────── │  /api/v1/...     │
└────────────┘                 └────────┬─────────┘
                                         │
                                         ▼
                                ┌──────────────────┐
                                │   Job queue      │
                                │   (kind: TBD)    │
                                └────────┬─────────┘
                                         │
                                         ▼
                ┌────────────────────────────────────────┐
                │           ML Worker                   │
                │   (customer_segmentation.*)           │
                │                                        │
                │   - preprocess                         │
                │   - feature_eng                        │
                │   - clustering                         │
                │   - evaluation                         │
                │   - profiling                          │
                │   - reporting                          │
                └─────┬─────────────────────────┬───────┘
                      │                         │
                      ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │   Artifact       │      │  Metadata store  │
              │   store          │      │  (DB)            │
              │ (FS / Storage)   │      │  lineage + runs  │
              └──────────────────┘      └──────────────────┘
```

> Hình này là diễn giải trực quan. Nguồn runtime view: `SYS-02` §5.

Mọi thành phần giao tiếp với worker thông qua **internal Python API**
(`customer_segmentation.*`) và job queue. Boundary HTTP chỉ có ở
frontend ↔ backend.

---

## 4. Quy ước chung

### 4.1 URL & version

- Base URL: `/api/v1`
- Ví dụ: `POST /api/v1/datasets`, `GET /api/v1/jobs/{job_id}`

### 4.2 Content-Type

- Request: `application/json` cho mọi endpoint trừ `POST /datasets/{id}/file`
  (multipart/form-data) và `GET /config/publish` (`application/x-yaml`).
- Response: `application/json; charset=utf-8` cho mọi endpoint trừ
  download artifact (`application/octet-stream` hoặc `application/zip`).

### 4.3 Request ID & tracing

- Mọi request phải mang header `X-Request-Id` (UUID v4). Server có thể sinh
  nếu thiếu.
- Mọi job chạy ML phải ghi `request_id` vào run metadata.

### 4.4 Datetime

- Tất cả timestamp trả về ở **UTC ISO-8601** (`2026-10-07T03:12:45Z`).

### 4.5 Pagination

- Query: `?page=1&page_size=50` (default `page=1`, `page_size=50`,
  max `page_size=200`).
- Response envelope:
  ```json
  {
    "items": [...],
    "page": 1,
    "page_size": 50,
    "total": 1234
  }
  ```

### 4.6 Filter / sort

- Query: `?sort=created_at:desc&filter[status]=SUCCEEDED`.
- Filter là object JSON-encoded trong query string; syntax đơn giản
  `key=value` cho giá trị primitive, `key__in=a,b,c` cho list.

### 4.7 Standard success envelope

Mọi response thành công trả về resource trực tiếp hoặc theo envelope:

```json
{
  "data": <resource>,
  "meta": {
    "request_id": "uuid",
    "server_time": "2026-10-07T03:12:45Z"
  }
}
```

### 4.8 Standard error envelope

Xem §14.

### 4.9 Authentication

Xem §13. Trạng thái hiện tại: `WORKING_ASSUMPTION`. Cấu hình authentication
mặc định mọi endpoint ngoại trừ `/healthz`, `/readyz`, `/openapi.json` yêu
cầu xác thực là `CONTRACT_REQUIRED`; cơ chế xác thực cụ thể (Bearer + JWT,
session, hoặc cơ chế khác) là `REVIEW_REQUIRED` / `IMPLEMENTATION_OPTION`.

### 4.10 Rate limit

> **`WORKING_ASSUMPTION`** — giá trị khởi điểm. Cần calibrate khi có
> usage pattern thật và mentor review. Nguồn tham chiếu: `SYS-01` §7.5.

- Giá trị khởi điểm: `60 req/min/user`, `600 req/min/global`.
- Backend triển khai có thể chọn cơ chế giới hạn khác (token bucket,
  leaky bucket, ...) thuộc `IMPLEMENTATION_OPTION`.

---

## 5. Nhóm A — Admin & Configuration

### A.1 `GET /api/v1/admin/configs`

Mô tả: liệt kê tất cả config (`configs/*.yaml` + custom user config) đang có.

Response 200:

```json
{
  "items": [
    {
      "config_id": "preprocess_default",
      "kind": "preprocess",
      "version": "v1",
      "checksum_sha256": "abc123...",
      "created_at": "2026-10-07T03:00:00Z",
      "updated_at": "2026-10-07T03:00:00Z",
      "is_default": true
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 5
}
```

Trường `kind` ∈ `{preprocess, feature_eng, transform, clustering, evaluation,
profiling, pipeline, dataset}`.

### A.2 `GET /api/v1/admin/configs/{config_id}`

Mô tả: lấy full config của một config_id.

Response 200:

```json
{
  "config_id": "preprocess_default",
  "kind": "preprocess",
  "version": "v1",
  "checksum_sha256": "abc123...",
  "yaml": "<raw YAML string>",
  "parsed": { ... },
  "created_at": "...",
  "updated_at": "..."
}
```

### A.3 `PUT /api/v1/admin/configs/{config_id}`

Mô tả: cập nhật config. Tạo version mới, **không** ghi đè version cũ.
Yêu cầu quyền `CONFIG_EDIT`.

Request body:

```json
{
  "yaml": "<new yaml>",
  "changelog": "..."
}
```

Response 200: trả về config mới với `version: v2`.

### A.4 `GET /api/v1/admin/configs/{config_id}/history`

Mô tả: liệt kê các version trước của config.

Response 200: `{ items: [...], total, page, page_size }`.

### A.5 `POST /api/v1/admin/configs/{config_id}/revert`

> **`WORKING_ASSUMPTION` / `REVIEW_REQUIRED`:** nguyên tắc tạo version mới
> copy từ `target_version` được giữ. Cơ chế bảo vệ (audit-only hay cần
> 2FA) là `REVIEW_REQUIRED`; quyết định cuối thuộc mentor.

Mô tả: revert config về version chỉ định. Tạo version mới copy từ
`target_version`.

Request body:

```json
{ "target_version": "v1" }
```

Response 200: trả về config sau revert.

### A.6 `POST /api/v1/admin/policies/reset`

> **`REVIEW_REQUIRED`** — endpoint này hiện chưa lock. Cả ba khía cạnh
> (cơ chế xác thực, phạm vi reset, audit) đều cần mentor quyết. Hiện đang
> chỉ được liệt kê là candidate để đảm bảo tài liệu API surface đầy đủ;
> **không** coi là requirement triển khai ở Phase này.

Mô tả (candidate): reset toàn bộ custom config về default shipped.

Response 200 (candidate):

```json
{ "status": "RESET", "reset_at": "..." }
```

---

## 6. Nhóm B — Dataset Management

### B.1 `POST /api/v1/datasets`

Mô tả: tạo dataset record mới (metadata + checksum) trước khi upload file.

> **Chú thích:** `expected_rows` ở đây là kỳ vọng ban đầu do caller cung
> cấp; server sẽ so sánh với `actual_rows` lúc validate (§B.3). Cột
> `expected_schema_version` phải trỏ đến schema version đã được publish
> trong data dictionary. Ví dụ dưới dùng dataset primary tham chiếu; giá
> trị cụ thể là placeholder minh hoạ.

Request body:

```json
{
  "name": "<dataset_name>",
  "kind": "primary",
  "expected_rows": 0,
  "expected_schema_version": "v1",
  "source": {
    "url": "https://...",
    "license": "...",
    "provenance_notes": "..."
  }
}
```

Response 201:

```json
{
  "dataset_id": "ds_8c1e...",
  "upload_url": "https://.../datasets/ds_8c1e.../file",
  "upload_method": "PUT",
  "upload_expires_in": "PENDING_REVIEW"
}
```

### B.2 `PUT /api/v1/datasets/{dataset_id}/file`

Mô tả: upload raw file (multipart hoặc stream). Backend lưu file theo
content-addressed path (xem `SYS-03` §6).

- Content-Type: `multipart/form-data` hoặc `application/octet-stream`.
- Yêu cầu header `Content-MD5` (hoặc `X-Content-SHA256`).

Response 200:

```json
{
  "dataset_id": "ds_8c1e...",
  "size_bytes": 15382968,
  "checksum_sha256": "...",
  "rows_counted": 0,
  "status": "UPLOADED"
}
```

`rows_counted` mặc định `0` cho đến khi validate.

### B.3 `POST /api/v1/datasets/{dataset_id}/validate`

Mô tả: chạy schema + row count + null + duplicate check. Trả job_id
vì có thể lâu với dataset lớn. **Validation không mutate file** (nguồn
policy: `SYS-04` §4, `SYS-03` §6).

Response 202:

```json
{
  "job_id": "job_...",
  "status": "PENDING",
  "poll_url": "/api/v1/jobs/job_..."
}
```

Sau khi job hoàn thành, kết quả validate được lưu vào dataset record.
Schema trả về là `CONTRACT_REQUIRED` cho cấu trúc; giá trị cụ thể do
config dataset quyết:

```json
{
  "validation": {
    "schema_match": true,
    "actual_rows": 0,
    "expected_rows": 0,
    "null_counts": {...},
    "duplicate_invoice_count": 0,
    "duplicate_customer_count": 0,
    "cancellation_ratio": 0.0,
    "warnings": [],
    "errors": []
  }
}
```

### B.4 `GET /api/v1/datasets`

Mô tả: list dataset. Filter: `?filter[kind]=primary`, `?filter[status]=VALID`.

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "items": [
    {
      "dataset_id": "...",
      "name": "...",
      "kind": "primary",
      "version": "v1",
      "checksum_sha256": "...",
      "rows": 0,
      "status": "VALID",
      "uploaded_at": "...",
      "uploaded_by": "..."
    }
  ],
  "total": 0
}
```

### B.5 `GET /api/v1/datasets/{dataset_id}`

Mô tả: lấy chi tiết dataset + lịch sử sử dụng.

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "dataset_id": "...",
  "name": "...",
  "kind": "primary",
  "version": "v1",
  "checksum_sha256": "...",
  "size_bytes": 0,
  "rows": 0,
  "status": "VALID",
  "schema": { "columns": ["..."] },
  "provenance": { "url": "...", "license": "...", "notes": "..." },
  "usage": [
    {
      "run_id": "run_...",
      "stage": "preprocess",
      "config_id": "preprocess_default",
      "config_version": "v1",
      "ran_at": "..."
    }
  ]
}
```

### B.6 `POST /api/v1/datasets/{dataset_id}/promote`

> **`REVIEW_REQUIRED`** — endpoint candidate. Việc dataset version nào
> "active" cho phase tiếp theo hiện chưa có cơ chế chốt. Phase trước có
> thể dùng cách khác (config reference, dataset mặc định, ...). Endpoint
> này liệt kê để đảm bảo surface đầy đủ; **không** coi là requirement
> triển khai Phase này. Nguồn: `AGENTS.md` §2.10, §2.11.

Mô tả (candidate): promote dataset version thành `ACTIVE` cho phase tiếp theo.

Response 200 (candidate):

```json
{ "dataset_id": "...", "status": "ACTIVE", "promoted_at": "..." }
```

### B.7 `DELETE /api/v1/datasets/{dataset_id}`

> **`REVIEW_REQUIRED`** — chính sách xoá dataset (soft vs hard, role cần
> thiết, có cần ADR) chưa được lock. Mặc định dự kiến là soft-delete với
> audit, nhưng đây là `WORKING_ASSUMPTION`. Nguồn: `AGENTS.md` §2.12.

Response 200 (candidate):

```json
{ "dataset_id": "...", "status": "DELETED", "deleted_at": "..." }
```

---

## 7. Nhóm C — Preprocessing & Feature Engineering

> Mọi endpoint trong nhóm này là **async job**. Request body phải reference
> `dataset_id` + `config_id`. Không nhận config inline để tránh silent policy
> override. Nguồn: `AGENTS.md` §2.9, `SYS-04` §3.

### C.1 `POST /api/v1/preprocess/runs`

Mô tả: chạy preprocessing pipeline trên dataset. Trả job_id.

Request body (cấu trúc `CONTRACT_REQUIRED`; mọi policy/ngưỡng từ config):

```json
{
  "dataset_id": "ds_...",
  "config_id": "preprocess_default",
  "config_version": "v1",
  "output_kind": "interim",
  "notes": "..."
}
```

Trường `output_kind` ∈ `{interim, processed}`. Phase preprocessing mặc định
ghi ra `data/interim/...`. Phase sau có thể ghi ra `data/processed/...`.

Response 202:

```json
{
  "job_id": "job_...",
  "run_id": "run_...",
  "status": "PENDING",
  "poll_url": "/api/v1/jobs/job_...",
  "expected_outputs": [
    "data/interim/preprocess/<dataset_name>__<config_id>__<config_version>.parquet"
  ]
}
```

### C.2 `GET /api/v1/preprocess/runs/{run_id}`

Mô tả: lấy chi tiết 1 run.

> **Chú thích:** tên metric trong block `metrics` là `CONTRACT_REQUIRED`
> ở mức danh sách key (để UI/operator biết có gì để xem). **Giá trị**
> từng metric, ngưỡng, quy tắc drop… đều đến từ config `preprocess` và
> `AGENTS.md` §2.3, §2.9. Tài liệu này không chốt con số cụ thể.

Response 200:

```json
{
  "run_id": "run_...",
  "dataset_id": "ds_...",
  "config_id": "preprocess_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "output_sha256": "...",
  "output_artifacts": [
    {
      "path": "data/interim/preprocess/<dataset_name>__<config_id>__<config_version>.parquet",
      "kind": "interim_dataset",
      "checksum_sha256": "...",
      "size_bytes": 0,
      "rows": 0
    }
  ],
  "metrics": {
    "rows_in": 0,
    "rows_out": 0,
    "rows_dropped": {
      "<rule_name>": 0
    },
    "duplicates_dropped": 0
  },
  "warnings": []
}
```

> Cấu trúc `metrics` tham chiếu `SYS-04` §6; tên rule cụ thể do config quyết.

### C.3 `GET /api/v1/preprocess/runs`

Mô tả: list runs. Filter: `?filter[dataset_id]=...`, `?filter[config_id]=...`,
`?filter[status]=SUCCEEDED`.

Response 200: `{ items: [...], total, page, page_size }`.

### C.4 `POST /api/v1/feature-eng/runs`

Mô tả: chạy feature engineering trên interim dataset đã được preprocess.

> **Chú thích về baseline hiện tại:** current working baseline là
> **RFM Extended 14-feature** (FE-06 C7) với ~4,371 unique customers.
> `C7 = WORKING_ASSUMPTION`. **RFM-only = FUTURE_WORK**, không coi là
> current contract. Endpoint này **không** chốt danh sách cột; cột do
> config `feature_eng_default` quyết (xem `AGENTS.md` §2.6, `SYS-04` §8).

Request body (cấu trúc `CONTRACT_REQUIRED`; mọi tham số từ config):

```json
{
  "interim_run_id": "run_...",
  "config_id": "feature_eng_default",
  "config_version": "v1",
  "output_kind": "processed",
  "notes": "..."
}
```

> **NOTE:** `reference_date` (nếu cần) phải đến từ config `feature_eng`.
> Nếu client truyền giá trị khác config → server từ chối với lỗi
> `REFERENCE_DATE_NOT_IN_CONFIG` (xem §14). `REVIEW_REQUIRED` cho
> trường hợp cần cơ chế reference date linh hoạt.

Response 202: `{ job_id, run_id, status, poll_url, expected_outputs }`.

### C.5 `GET /api/v1/feature-eng/runs/{run_id}`

> **Chú thích:** danh sách cột trong `output_artifacts[].columns` do
> config quyết; tài liệu này chỉ đặc tả schema trả về. Số dòng, số
> customer… là kết quả thực thi, không phải tham số API.

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "run_id": "run_...",
  "interim_run_id": "run_...",
  "config_id": "feature_eng_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "output_sha256": "...",
  "output_artifacts": [
    {
      "path": "data/processed/feature_eng/<dataset_name>__<config_id>__<config_version>.parquet",
      "kind": "processed_dataset",
      "checksum_sha256": "...",
      "size_bytes": 0,
      "rows": 0,
      "columns": ["..."]
    }
  ],
  "metrics": {
    "unique_entities": 0,
    "feature_columns": ["..."],
    "null_cells_total": 0,
    "null_cells_by_column": {}
  },
  "warnings": []
}
```

### C.6 `GET /api/v1/feature-eng/runs`

Response 200: `{ items: [...], total, page, page_size }`.

### C.7 `POST /api/v1/transform/runs`

Mô tả: chạy transformation (scaler / log / robust / …) trên processed
features. **Tên scaler, danh sách cột log-transform, các tham số
transformation đều đến từ config `transform`** (`AGENTS.md` §2.6,
`SYS-04` §9). Không nhận inline.

Request body (cấu trúc `CONTRACT_REQUIRED`):

```json
{
  "feature_eng_run_id": "run_...",
  "config_id": "transform_default",
  "config_version": "v1",
  "output_kind": "ml_ready",
  "notes": "..."
}
```

Response 202: `{ job_id, run_id, status, poll_url, expected_outputs }`.

### C.8 `GET /api/v1/transform/runs/{run_id}`

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "run_id": "run_...",
  "feature_eng_run_id": "run_...",
  "config_id": "transform_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "output_sha256": "...",
  "transform_state_id": "ts_...",
  "output_artifacts": [
    {
      "path": "data/processed/transform/<dataset_name>__<config_id>__<config_version>/ml_ready.parquet",
      "kind": "ml_ready_dataset",
      "checksum_sha256": "...",
      "size_bytes": 0,
      "rows": 0,
      "columns": ["..."]
    }
  ],
  "metrics": {
    "feature_count_in": 0,
    "feature_count_out": 0,
    "transformer_kinds": {}
  },
  "warnings": []
}
```

> Transform state (`ts_...`) là artifact cần song song **ml_ready_dataset**
> (xem `SYS-04` §9) để inverse transform khi profiling. Có/không có state
> này là `CONTRACT_REQUIRED`; cấu trúc state là `IMPLEMENTATION_OPTION`.

### C.9 `GET /api/v1/transform/runs`

Response 200: `{ items: [...], total, page, page_size }`.

---

## 8. Nhóm D — Clustering & Model Registry

> Theo `SYS-01` §5.2 và `AGENTS.md` §3, các thuật toán trong scope nghiên
> cứu: **K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means**. K-Medoids
> **OUT OF SCOPE** (xem ADR-0003).
>
> Mọi clustering run là async job, tham chiếu `ml_ready_run_id` + `config_id`.

### D.1 `POST /api/v1/clustering/runs`

> **Nguyên tắc config-only (CONTRACT_REQUIRED, nguồn: `AGENTS.md` §2.6,
> §2.7, §2.9, `SYS-04` §10):** mọi tham số ML (`k_range`, `eps`,
> `min_samples`, `linkage`, `covariance_type`, `fuzziness`, `n_init`,
> `max_iter`, `random_seed`, ...) **đều phải đến từ config** `clustering_*`.
> Request body mặc định **không** chứa bất kỳ tham số ML nào.
>
> Cơ chế override `random_seed` qua request (nếu có) là `REVIEW_REQUIRED` /
> `WORKING_ASSUMPTION` và chỉ được kích hoạt khi config có cờ rõ ràng
> cho phép. Khi chưa lock, mặc định cấm override → lỗi
> `SEED_NOT_OVERRIDABLE` (§14).

Request body (`CONTRACT_REQUIRED`):

```json
{
  "ml_ready_run_id": "run_...",
  "algorithm": "kmeans",
  "config_id": "clustering_kmeans_default",
  "config_version": "v1",
  "notes": "..."
}
```

Trường `algorithm` ∈ `{kmeans, agglomerative, dbscan, gmm, fcm}`.

Response 202:

```json
{
  "job_id": "job_...",
  "run_id": "run_...",
  "status": "PENDING",
  "poll_url": "/api/v1/jobs/job_..."
}
```

### D.2 `GET /api/v1/clustering/runs/{run_id}`

> **Chú thích về khảo sát elbow / silhouette:**
>
> - Tập `k_tested` (hoặc tương đương cho thuật toán không dùng `k`) **đến
>   từ config**, không phải request. Tài liệu này đặc tả schema; giá
>   trị cụ thể do config + phase plan quyết.
> - Các metric internal (`silhouette`, `davies_bouldin`,
>   `calinski_harabasz`, `inertia`, ...) là `CONTRACT_REQUIRED` ở mức
>   schema; **một số metric chỉ áp dụng cho một số thuật toán** (vd.
>   `inertia` cho K-Means; `log_likelihood` cho GMM; `fpc` cho FCM).
>   Field nào không áp dụng → trả `null`, không tự ý đặt bằng 0.
> - Endpoint này **không** trả `best_k` / `optimal_k` /
>   `recommended_k` (xem `AGENTS.md` §2.5).

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "run_id": "run_...",
  "algorithm": "kmeans",
  "ml_ready_run_id": "run_...",
  "config_id": "clustering_kmeans_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "artifacts": {
    "model_artifact_id": "ma_...",
    "labels_artifact_id": "la_...",
    "centroids_artifact_id": "ca_...",
    "transform_state_ref": "ts_..."
  },
  "metrics": {
    "k_tested": [0],
    "inertia": [0.0],
    "silhouette": [0.0],
    "davies_bouldin": [0.0],
    "calinski_harabasz": [0.0],
    "fit_seconds_per_k": [0.0]
  },
  "warnings": []
}
```

### D.3 `GET /api/v1/clustering/runs`

Filter: `?filter[algorithm]=kmeans`, `?filter[ml_ready_run_id]=...`.

Response 200: `{ items: [...], total, page, page_size }`.

### D.4 `GET /api/v1/clustering/runs/{run_id}/model`

Mô tả: tải model artifact (`pickle` hoặc `joblib`). Trả binary stream.

Response 200: `application/octet-stream`, header
`X-Model-Checksum-SHA256: ...`.

### D.5 `GET /api/v1/clustering/runs/{run_id}/labels`

Mô tả: trả DataFrame label (`<entity_id>, cluster`) dưới dạng CSV stream
hoặc JSON. Mặc định JSON streaming. Tên cột `<entity_id>` đến từ
dataset / feature_eng config (vd. `CustomerID` nếu đơn vị phân tích là
customer); tài liệu này không chốt tên cột.

Response 200: NDJSON, mỗi dòng:

```json
{"<entity_id>": "...", "cluster": 0}
```

### D.6 `POST /api/v1/clustering/predict`

> **`WORKING_ASSUMPTION` / `REVIEW_REQUIRED`** — endpoint candidate. Có
> nhiều câu hỏi chưa đóng: (a) feature lookup dựa trên model fingerprint
> (lineage về feature_eng run) có khả thi với dataset lớn không, (b) phạm
> vi "predict" (per-entity vs per-batch), (c) trả về distance/medoid/prob
> tuỳ thuật toán, (d) tương tác với transform state. Endpoint này chỉ
> liệt kê để đảm bảu API surface đầy đủ; **chưa** coi là requirement
> triển khai Phase này. Nguồn: `AGENTS.md` §2.10, §2.11.

Mô tả (candidate): predict cluster cho 1 batch entities dựa trên
model + transform state đã chọn. Đây là **predict-theo-batch**, không
phải online serving.

Request body (candidate):

```json
{
  "model_artifact_id": "ma_...",
  "transform_state_id": "ts_...",
  "entities": [
    { "id": "..." }
  ]
}
```

Response 200 (candidate, cấu trúc có thể thay đổi sau review):

```json
{
  "predictions": [
    { "id": "...", "cluster": 0, "score": null }
  ]
}
```

> **Lưu ý:** chỗ này **không** chốt `distance_to_centroid`,
> `distance_to_medoid`, `membership_probability`. Mỗi thuật toán có
> khái niệm khác nhau:
>
> - K-Means / GMM: có centroid khoảng cách / xác suất thành viên.
> - DBSCAN: không có centroid; "score" có thể là core distance /
>   `None` cho noise.
> - Agglomerative: khái niệm `medoid` chưa được chốt trong methodology
>   hiện tại → `REVIEW_REQUIRED`. **Không** mặc định trả
>   `distance_to_medoid` trong contract.
>
> Cấu trúc cuối của `predictions[].score` thuộc `REVIEW_REQUIRED` và
> phải được chốt bằng ADR trước khi implement.

### D.7 `POST /api/v1/clustering/explain`

> **`REVIEW_REQUIRED`** — endpoint candidate cho explainability batch
> (cluster centroid profile, feature importance permutation, ...). Hiện
> chưa có plan chốt nội dung; **không** coi là requirement Phase này.
> Liệt kê để đảm bảo surface đầy đủ.

### D.8 `GET /api/v1/models`

> **`WORKING_ASSUMPTION`** — cụm model registry (D.8–D.12) được liệt kê
> đầy đủ vì lý do kiến trúc (lineage, audit, reproducibility), nhưng
> **một số endpoint trong cụm có thể chưa cần ở Phase prototype**:
>
> - `D.8 GET /models`, `D.9 GET /models/{id}`, `D.12 GET
>   /models/{id}/lineage` → `CONTRACT_REQUIRED` (cần cho audit + lineage).
> - `D.10 POST /models/{id}/tag` → `WORKING_ASSUMPTION`.
> - `D.11 POST /models/{id}/promote` → `REVIEW_REQUIRED` (workflow release
>   của model thuộc methodology governance, chưa chốt).

Mô tả: list model artifact trong registry. Filter:
`?filter[algorithm]=kmeans`, `?filter[created_by]=...`.

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder):

```json
{
  "items": [
    {
      "model_artifact_id": "ma_...",
      "algorithm": "kmeans",
      "k": 0,
      "clustering_run_id": "run_...",
      "config_id": "...",
      "config_version": "v1",
      "config_checksum_sha256": "...",
      "input_sha256": "...",
      "size_bytes": 0,
      "checksum_sha256": "...",
      "created_at": "...",
      "created_by": "...",
      "tags": ["..."]
    }
  ],
  "total": 0
}
```

### D.9 `GET /api/v1/models/{model_artifact_id}`

Response 200: chi tiết một model artifact. Cấu trúc mirror D.8 item.

### D.10 `POST /api/v1/models/{model_artifact_id}/tag`

> **`WORKING_ASSUMPTION`** — schema request là `CONTRACT_REQUIRED`; tập
> tag được phép và quyền truy cập do governance quyết (xem `AGENTS.md`
> §2.10).

Request body:

```json
{
  "add": ["..."],
  "remove": ["..."]
}
```

### D.11 `POST /api/v1/models/{model_artifact_id}/promote`

> **`REVIEW_REQUIRED`** — workflow release/stage model hiện chưa được
> chốt trong methodology. Liệt kê đầy đủ để đảm bảo API surface;
> **chưa** coi là requirement triển khai. Quyết định thuộc mentor +
> `AGENTS.md` §2.10.

Mô tả (candidate): đánh dấu model là `STAGED_FOR_EVAL` hoặc `RELEASE`.

Request body (candidate):

```json
{ "stage": "STAGED_FOR_EVAL", "note": "..." }
```

### D.12 `GET /api/v1/models/{model_artifact_id}/lineage`

`CONTRACT_REQUIRED` — cần cho audit + reproducibility. Cấu trúc envelope
do config lineage quyết ở mức tổng quát:

Response 200 (cấu trúc `CONTRACT_REQUIRED`):

```json
{
  "model_artifact_id": "ma_...",
  "lineage": {
    "clustering_run_id": "run_...",
    "ml_ready_run_id": "run_...",
    "feature_eng_run_id": "run_...",
    "interim_run_id": "run_...",
    "dataset_id": "ds_...",
    "configs": [
      { "config_id": "clustering_kmeans_default", "version": "v1" },
      { "config_id": "transform_default", "version": "v1" },
      { "config_id": "feature_eng_default", "version": "v1" },
      { "config_id": "preprocess_default", "version": "v1" }
    ]
  }
}
```

---

## 9. Nhóm E — Evaluation

> **Tình trạng methodology của evaluation framework hiện tại**
> (`SYS-01` §6, `SYS-04` §11):
>
> - **Internal metrics (silhouette, Davies-Bouldin, Calinski-Harabasz,
>   inertia, log-likelihood, FPC, partition coefficient, partition
>   entropy):** `CONTRACT_REQUIRED` ở mức schema (key trả về). Các
>   metric có thể `null` tuỳ thuật toán. **Một số** (vd. inertia cho
>   K-Means) chỉ áp dụng cho một số thuật toán.
> - **Stability evidence (ARI / NMI / AMI / Hungarian matching /
>   permutation test / confidence interval / bootstrap):** chưa có
>   quyết định methodology cuối. Cả ba nhãn sau đều đang mở:
>   `WORKING_ASSUMPTION` / `REVIEW_REQUIRED` / chưa chốt thư viện.
>   Endpoint này **chỉ** đặc tả schema **generic** (status, evidence
>   reference, config snapshot), không chốt một phép đo stability
>   cụ thể. Khi methodology chốt, sẽ cập nhật schema mà không phá v1
>   (chỉ thêm field optional, xem §12).
> - **API không trả `winner` / `best` / `recommended`** (xem
>   `AGENTS.md` §2.5, §2.6).

### E.1 `POST /api/v1/evaluation/runs`

Request body (cấu trúc `CONTRACT_REQUIRED`; mọi tham số ML từ config):

```json
{
  "model_artifact_id": "ma_...",
  "transform_state_id": "ts_...",
  "ml_ready_run_id": "run_...",
  "config_id": "evaluation_default",
  "config_version": "v1",
  "notes": "..."
}
```

> **Chú thích:** mọi tham số stability (`n_bootstrap`,
> `random_seed_base`, loại metric stability, loại test thống kê, …)
> đều đến từ config `evaluation_default` (`AGENTS.md` §2.6). Request
> body **không** chứa `n_bootstrap`, `random_seed_base` hoặc bất kỳ
> tham số stability nào ở mức mặc định. Mọi thay đổi sau này phải
> thông qua config + ADR.

Response 202: `{ job_id, run_id, status, poll_url }`.

### E.2 `GET /api/v1/evaluation/runs/{run_id}`

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder;
metric không áp dụng cho thuật toán đang chạy → `null`):

```json
{
  "run_id": "run_...",
  "model_artifact_id": "ma_...",
  "algorithm": "kmeans",
  "k": 0,
  "config_id": "evaluation_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "metrics_internal": {
    "silhouette": 0.0,
    "davies_bouldin": 0.0,
    "calinski_harabasz": 0.0,
    "inertia": null,
    "log_likelihood": null,
    "fpc": null,
    "partition_coefficient": null,
    "partition_entropy": null,
    "n_iter": 0,
    "converged": true
  },
  "metrics_stability": {
    "status": "NOT_REQUESTED",
    "evidence_ref": null,
    "details": null
  },
  "metrics_runtime": {
    "fit_seconds_total": 0.0,
    "fit_seconds_per_k": [0.0],
    "n_samples": 0,
    "n_features": 0
  },
  "per_cluster": {
    "0": {
      "size": 0,
      "share": 0.0,
      "centroid_untransformed": {},
      "centroid_feature_contrib": {},
      "top_features_by_abs_z": ["..."]
    }
  },
  "warnings": []
}
```

> **Chú thích về `metrics_stability`:**
>
> - `status ∈ {NOT_REQUESTED, RUNNING, SUCCEEDED, FAILED, SKIPPED}`.
> - Khi methodology stability được chốt (bằng ADR), các field sau
>   sẽ được thêm dưới `details` mà không bump version (xem §12):
>   `metric_kind`, `n_bootstrap`, `random_seed_base`, summary
>   statistics, … Hiện **không** chốt.
> - ARI / NMI / AMI / Hungarian matching / statistical test /
>   confidence interval đều **chưa** được phép như API contract
>   mặc định; thuộc `REVIEW_REQUIRED` (xem §15).

### E.3 `GET /api/v1/evaluation/runs`

Filter: `?filter[algorithm]=kmeans`, `?filter[k]=0`.

Response 200: `{ items: [...], total, page, page_size }`.

### E.4 `GET /api/v1/evaluation/runs/{run_id}/report.csv`

Mô tả: trả báo cáo evaluation dạng CSV. Cấu trúc cột do config
`evaluation_default.report_columns` quyết; tài liệu này chỉ chốt
`Content-Type`.

Response 200: `text/csv`.

### E.5 `POST /api/v1/evaluation/compare`

Mô tả: so sánh nhiều evaluation runs. Trả về bảng side-by-side.
**API không trả `winner` / `best` / `recommended`** (xem
`AGENTS.md` §2.5, §2.6). Frontend có thể sort/filter; API chỉ cung
cấp evidence.

Request body:

```json
{
  "evaluation_run_ids": ["run_e1", "run_e2", "run_e3"],
  "config_id": "evaluation_default",
  "config_version": "v1"
}
```

> **Chú thích:** các field so sánh (internal metrics, runtime,
> stability evidence reference) đều từ `evaluation_default`. Không
> chốt cột stability cụ thể (ARI / NMI / …) ở contract vì
> `REVIEW_REQUIRED`.

Response 200 (cấu trúc `CONTRACT_REQUIRED`):

```json
{
  "items": [
    {
      "evaluation_run_id": "run_e1",
      "algorithm": "kmeans",
      "k": 0,
      "silhouette": 0.0,
      "davies_bouldin": 0.0,
      "calinski_harabasz": 0.0,
      "fit_seconds": 0.0,
      "stability_status": "NOT_REQUESTED"
    }
  ],
  "compare_metadata": {
    "compared_at": "...",
    "config_evaluation_id": "evaluation_default",
    "config_evaluation_version": "v1",
    "ml_ready_run_id": "run_..."
  }
}
```

---

## 10. Nhóm F — Profiling & Reporting

> Nguồn: `SYS-04` §12. Mọi segment name + (chú thích segment) phải tới từ
> ADR được mentor approve. Mặc định endpoint này trả về **profile numeric**
> chưa gắn nhãn business.

### F.1 `POST /api/v1/profiling/runs`

Request body (cấu trúc `CONTRACT_REQUIRED`):

```json
{
  "model_artifact_id": "ma_...",
  "transform_state_id": "ts_...",
  "ml_ready_run_id": "run_...",
  "evaluation_run_id": "run_...",
  "config_id": "profiling_default",
  "config_version": "v1",
  "notes": "..."
}
```

> **Chú thích:** có/không breakdown theo category (vd. country, channel)
> là policy từ `profiling_default` (`AGENTS.md` §2.6). Mặc định API
> **không** nhận `include_country_breakdown` inline. Nếu sau này cần
> toggle, đưa vào config + ADR.

Response 202: `{ job_id, run_id, status, poll_url }`.

### F.2 `GET /api/v1/profiling/runs/{run_id}`

Response 200 (cấu trúc `CONTRACT_REQUIRED`; giá trị placeholder;
`country_top` chỉ xuất hiện nếu config `profiling` bật:

```json
{
  "run_id": "run_...",
  "model_artifact_id": "ma_...",
  "evaluation_run_id": "run_...",
  "config_id": "profiling_default",
  "config_version": "v1",
  "config_checksum_sha256": "...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "input_sha256": "...",
  "output_sha256": "...",
  "report_artifact_id": "ra_...",
  "per_cluster": {
    "0": {
      "size": 0,
      "share": 0.0,
      "stats": {
        "<feature_name>": {"mean": 0.0, "median": 0.0, "std": 0.0,
                           "p25": 0.0, "p75": 0.0, "min": 0.0, "max": 0.0}
      },
      "breakdown_by_category": null,
      "nominal_label": null,
      "candidate_label": null
    }
  },
  "warnings": []
}
```

> L`nominal_label` / `candidate_label` chỉ fill khi ADR profile-mapping đã
> được approve. Mặc định `null`. Nguồn: `AGENTS.md` §2.5, §3.
> Tên segment ("Champions", "Loyal", ...) là `REVIEW_REQUIRED` và **không**
> tự gán.

### F.3 `GET /api/v1/profiling/runs/{run_id}/report`

Mô tả: tải report artifact (PDF/HTML/Markdown tuỳ theo config
`profiling_default.report_format`). Default Markdown.

Response 200: `text/markdown` hoặc `application/pdf`.

### F.4 `GET /api/v1/profiling/runs`

Response 200: `{ items: [...], total, page, page_size }`.

### F.5 `POST /api/v1/reports/build`

Mô tả: aggregate nhiều evaluation + profiling runs thành một report cuối
của phase / experiment. Report này **không** chứa khẳng định "best", chỉ
tổng hợp evidence.

Request body (cấu trúc `CONTRACT_REQUIRED`; tiêu đề do caller cung cấp,
không chứa khẳng định "best"/"recommended"):

```json
{
  "title": "<experiment_title>",
  "include_evaluation_run_ids": ["run_e1", "run_e2"],
  "include_profiling_run_ids": ["run_p1", "run_p2"],
  "config_id": "report_default",
  "config_version": "v1",
  "format": "markdown"
}
```

Response 202: `{ job_id, report_id, poll_url }`.

### F.6 `GET /api/v1/reports/{report_id}`

Response 200:

```json
{
  "report_id": "...",
  "title": "...",
  "format": "markdown",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "artifacts": [
    {
      "path": "reports/phase7/report_phase7.md",
      "checksum_sha256": "...",
      "size_bytes": 45678
    }
  ],
  "inputs": {
    "evaluation_run_ids": [...],
    "profiling_run_ids": [...]
  }
}
```

### F.7 `GET /api/v1/reports`

Response 200: `{ items: [...], total, page, page_size }`.

### F.8 `GET /api/v1/reports/{report_id}/download`

Response 200: stream file report.

---

## 11. Nhóm G — Telemetry & System

### G.1 `GET /healthz`

Mô tả: liveness probe. Trả `200 OK` khi process còn sống.

Response 200:

```json
{ "status": "ok", "version": "0.1.0" }
```

### G.2 `GET /readyz`

Mô tả: readiness probe. Kiểm tra DB, storage, queue.

Response 200:

```json
{
  "status": "ok",
  "checks": {
    "db": "ok",
    "storage": "ok",
    "queue": "ok"
  }
}
```

Response 503: bất kỳ check nào fail, trả envelope lỗi (xem §14) với
`error.code = "NOT_READY"`.

### G.3 `GET /api/v1/jobs/{job_id}`

Mô tả: lấy trạng thái một job.

Response 200:

```json
{
  "job_id": "job_...",
  "kind": "clustering.run",
  "status": "RUNNING",
  "started_at": "...",
  "finished_at": null,
  "progress": {
    "step": "fitting",
    "step_index": 3,
    "step_total": 7,
    "percent": 42
  },
  "logs_url": "/api/v1/jobs/job_.../logs",
  "result_url": null
}
```

Các trạng thái: `PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, TIMEOUT`.

### G.4 `GET /api/v1/jobs/{job_id}/logs`

Mô tả: stream log của job (text hoặc NDJSON).

Response 200: `text/plain` (log streaming) hoặc `application/x-ndjson`.

### G.5 `POST /api/v1/jobs/{job_id}/cancel`

Mô tả: huỷ job nếu job đang PENDING hoặc RUNNING.

Response 200:

```json
{ "job_id": "...", "status": "CANCELLED", "cancelled_at": "..." }
```

Response 409: nếu job đã ở terminal state.

### G.6 `GET /api/v1/lineage/{run_id}`

Mô tả: lấy lineage của bất kỳ run nào (preprocess / feature_eng / transform /
clustering / evaluation / profiling).

Response 200:

```json
{
  "run_id": "run_...",
  "kind": "clustering",
  "lineage": {
    "upstream": [
      { "run_id": "run_ml_ready", "kind": "transform" },
      { "run_id": "run_features", "kind": "feature_eng" },
      { "run_id": "run_interim", "kind": "preprocess" },
      { "run_id": "ds_...", "kind": "dataset" }
    ],
    "downstream": [
      { "run_id": "run_eval", "kind": "evaluation" },
      { "run_id": "run_profile", "kind": "profiling" }
    ],
    "configs": [
      { "config_id": "clustering_kmeans_default", "version": "v1" },
      ...
    ],
    "checksums": {
      "input_sha256": "...",
      "output_sha256": "..."
    }
  }
}
```

### G.7 `GET /api/v1/audit`

Mô tả: list audit entries. Filter:
`?filter[actor]=...`, `?filter[action]=CONFIG_EDIT`.

Response 200: `{ items: [...], total, page, page_size }`.

Mỗi item:

```json
{
  "audit_id": "...",
  "actor": "user:hoangson301223",
  "action": "CONFIG_EDIT",
  "target": "config:preprocess_default",
  "before_sha256": "...",
  "after_sha256": "...",
  "request_id": "...",
  "ip": "10.0.0.1",
  "timestamp": "..."
}
```

### G.8 `GET /openapi.json`

Mô tả: trả OpenAPI 3.1 schema cho toàn bộ API.

### G.9 `GET /api/v1/system/info`

Response 200:

```json
{
  "version": "0.1.0",
  "git_sha": "abc123",
  "python_version": "3.11.4",
  "platform": "linux",
  "config": {
    "log_level": "INFO",
    "max_upload_size_bytes": 52428800,
    "rate_limit_per_minute_user": 60,
    "rate_limit_per_minute_global": 600
  },
  "storage": {
    "kind": "fs",
    "root": "/srv/customer-segmentation-ml/storage"
  }
}
```

---

## 12. Phiên bản hoá & tương thích

- URL prefix `/api/v1` đánh version. Không breaking change trong v1.
- Khi cần đổi schema response, endpoint mới sẽ đặt ở `/api/v2` và v1 giữ
  nguyên trong ít nhất **6 tháng** kể từ ngày phát hành v2.
- Các field mới (optional) có thể thêm vào response mà không bump version.
- Khi **bỏ field**, đổi kiểu field, đổi enum → bump version.
- Mọi config (`config_id` + `version`) reference trong run metadata phải
  resolve được vĩnh viễn (không xoá config cũ).

---

## 13. Bảo mật & xác thực

> **Tổng quan trạng thái:**
>
> - Việc **mọi endpoint (trừ `/healthz`, `/readyz`, `/openapi.json`) yêu
>   cầu xác thực** là `CONTRACT_REQUIRED`.
> - **Cơ chế xác thực cụ thể** (Bearer + JWT, session, mTLS, …) là
>   `IMPLEMENTATION_OPTION`; tài liệu này đề xuất Bearer + JWT vì
>   phù hợp với frontend SPA / CLI client. Phase sau được quyền chọn
>   cơ chế khác nếu mentor approve.
> - **Mô hình role** (bảng §13.2) là `WORKING_ASSUMPTION`. Tên role và
>   mapping quyền chưa được chốt bằng ADR; coi là candidate.
> - **2FA / dual-control** cho thao tác nhạy cảm (reset, hard-delete,
>   model promote) là `REVIEW_REQUIRED` (xem §15).
> - **Audit log** append-only là `CONTRACT_REQUIRED` (`AGENTS.md` §2.7).

### 13.1 Authentication

- `CONTRACT_REQUIRED`: request phải mang credential trừ các endpoint
  public liệt kê ở §4.9.
- `IMPLEMENTATION_OPTION`: cơ chế cụ thể. Đề xuất:
  - Header: `Authorization: Bearer <token>`.
  - Token chứa `sub`, `roles`, `exp` (nếu dùng JWT).

### 13.2 Roles

> **`WORKING_ASSUMPTION`** — bảng dưới là candidate mapping. Tên role và
> quyền chưa được chốt bằng ADR; được phép điều chỉnh khi implement.

| Role (candidate)   | Quyền                                                  |
| ------------------ | ------------------------------------------------------ |
| `VIEWER`           | Đọc mọi resource; chạy evaluation/profiling read-only. |
| `OPERATOR`         | Upload dataset, chạy preprocess/feature/clustering/eval. |
| `CONFIG_EDIT`      | Sửa config (xem A.3).                                  |
| `DATA_STEWARD`     | Promote dataset (xem B.6, nếu endpoint được chốt).      |
| `MODEL_REVIEWER`   | Promote model (xem D.11, nếu endpoint được chốt).       |
| `ADMIN`            | Toàn quyền (xem A.6, soft-delete).                     |

### 13.3 Audit

- `CONTRACT_REQUIRED`: mọi mutation tạo audit entry (`G.7`).
- `CONTRACT_REQUIRED`: audit log append-only; không sửa, không xoá.

### 13.4 Secrets

- `CONTRACT_REQUIRED`: raw dataset, model artifact, report không public.
- `CONTRACT_REQUIRED`: token / secret lưu ở env / secret manager; không
  commit vào repo.

### 13.5 Data privacy

- `CONTRACT_REQUIRED` (theo `AGENTS.md` §2.12): không commit raw / interim
  / processed / external data vào repo.
- `CONTRACT_REQUIRED`: API không bao giờ trả raw dataset qua response;
  chỉ trả metadata, summary, checksum.
- `REVIEW_REQUIRED`: cơ chế download raw / interim / model artifact qua
  pre-signed URL có TTL. TTL cụ thể và cách sinh URL thuộc ADR sau.

---

## 14. Lỗi & mã lỗi chuẩn

### 14.1 Error envelope

Mọi response lỗi (4xx, 5xx) trả về:

```json
{
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset ds_xxx not found.",
    "details": {
      "dataset_id": "ds_xxx"
    },
    "request_id": "uuid"
  }
}
```

### 14.2 Mã lỗi chuẩn (đề xuất)

> **Chú thích:** bảng dưới là `CONTRACT_REQUIRED` ở mức **danh sách mã lỗi
> có thể xuất hiện**. Một số mã chỉ phát sinh nếu endpoint liên quan
> được chốt triển khai (xem chú thích cuối bảng).

| HTTP | code                       | Ý nghĩa                                                          |
| ---- | -------------------------- | ---------------------------------------------------------------- |
| 400  | `BAD_REQUEST`             | Request body không hợp lệ.                                       |
| 400  | `INVALID_CONFIG_REFERENCE`| config_id hoặc config_version không tồn tại.                    |
| 400  | `REFERENCE_DATE_NOT_IN_CONFIG` | `reference_date` truyền vào không khớp policy trong config. |
| 400  | `SEED_NOT_OVERRIDABLE`   | random_seed truyền vào không được phép bởi config.                |
| 400  | `INVALID_PAGINATION`     | page hoặc page_size không hợp lệ.                                |
| 401  | `UNAUTHENTICATED`        | Thiếu hoặc sai credential.                                       |
| 403  | `FORBIDDEN`               | Không đủ quyền.                                                  |
| 404  | `NOT_FOUND`              | Resource không tồn tại.                                          |
| 404  | `DATASET_NOT_FOUND`      | Dataset không tồn tại.                                           |
| 404  | `CONFIG_NOT_FOUND`       | Config không tồn tại.                                            |
| 404  | `RUN_NOT_FOUND`          | Run không tồn tại.                                               |
| 404  | `MODEL_NOT_FOUND`        | Model artifact không tồn tại.                                    |
| 409  | `CONFLICT`               | Trạng thái resource xung đột (vd. job đã terminal).               |
| 409  | `JOB_ALREADY_TERMINAL`   | Cancel job đã ở trạng thái cuối.                                 |
| 413  | `PAYLOAD_TOO_LARGE`      | Upload vượt `max_upload_size_bytes`.                             |
| 415  | `UNSUPPORTED_MEDIA_TYPE`  | Content-Type không hỗ trợ.                                       |
| 422  | `SCHEMA_VALIDATION_FAILED`| Schema không khớp expected_schema_version.                     |
| 422  | `ROW_COUNT_MISMATCH`     | Số dòng không khớp expected_rows.                                |
| 422  | `CHECKSUM_MISMATCH`      | SHA-256 không khớp.                                              |
| 429  | `RATE_LIMITED`          | Vượt rate limit.                                                 |
| 500  | `INTERNAL_ERROR`        | Lỗi server không phân loại được.                                 |
| 503  | `NOT_READY`              | Service chưa sẵn sàng (xem G.2).                                 |
| 504  | `JOB_TIMEOUT`           | Job chạy quá thời gian cho phép.                                  |

> **Chú thích điều kiện phát sinh mã lỗi:**
>
> - `SEED_NOT_OVERRIDABLE`: chỉ phát sinh nếu endpoint `D.1` được chốt có
>   hỗ trợ override `random_seed` qua request. Hiện `REVIEW_REQUIRED`
>   (xem §15).
> - `REFERENCE_DATE_NOT_IN_CONFIG`: chỉ phát sinh nếu endpoint `C.4`
>   chốt cho phép client truyền `reference_date`. Hiện `REVIEW_REQUIRED`.
> - `JOB_TIMEOUT`: timeout giá trị cụ thể thuộc `WORKING_ASSUMPTION` và
>   hiện chưa chốt.
> - Mã lỗi mới có thể được thêm (bump minor) mà không phá v1 (xem §12).

---

## 15. PENDING_REVIEW & open questions

Các điểm dưới đây cần mentor/human researcher review trước khi đưa vào
implementation phase. Mỗi mục kèm nhãn `WORKING_ASSUMPTION` / `REVIEW_REQUIRED`
/ `IMPLEMENTATION_OPTION` đã được dùng trong tài liệu để chỉ các quyết
định chưa lock.

1. **AuthN/AuthZ implementation.** Cơ chế xác thực cụ thể (Bearer + JWT,
   session, mTLS, ...) là `IMPLEMENTATION_OPTION` (§13.1). Mapping role
   → quyền là `WORKING_ASSUMPTION` (§13.2).
2. **`POST /admin/configs/{config_id}/revert` & `POST /admin/policies/reset`.**
   Quy trình 2FA / dual-control cho revert + reset hiện `REVIEW_REQUIRED`.
   Cần mentor confirm: (a) có cần 2FA cho cả hai endpoint, (b) chỉ `revert`
   mới cần 2FA, (c) workflow khác.
3. **`POST /datasets/{id}/promote`.** Endpoint candidate. Cơ chế dataset
   "active" cho phase tiếp theo chưa được chốt; có thể dùng config
   reference hoặc dataset mặc định. `REVIEW_REQUIRED`.
4. **`DELETE /datasets/{id}`.** Chính sách xoá (soft vs hard, role,
   ADR) chưa chốt. `REVIEW_REQUIRED`. Nguồn: `AGENTS.md` §2.12.
5. **`POST /clustering/predict` & `POST /clustering/explain`.** Cả hai là
   `REVIEW_REQUIRED` ở Phase này. Câu hỏi mở: feature lookup theo model
   fingerprint, phạm vi predict, schema `predictions[].score` cho từng
   thuật toán (đặc biệt `distance_to_medoid` cho Agglomerative — **không
   tự chốt** trong contract).
6. **`POST /models/{id}/promote`.** Workflow release/stage model thuộc
   methodology governance, chưa chốt. `REVIEW_REQUIRED`.
7. **Stability metrics (ARI / NMI / AMI / Hungarian matching / permutation
   test / confidence interval / bootstrap).** Methodology evaluation
   framework chưa chốt các phép đo stability cụ thể. API hiện chỉ trả
   `metrics_stability.status` + `evidence_ref`; khi chốt, sẽ thêm field
   optional mà không bump v1 (§12). Nguồn: `SYS-01` §6, `SYS-04` §11.
8. **Random seed override trong clustering request.** Hiện `REVIEW_REQUIRED`
   (`SEED_NOT_OVERRIDABLE` chỉ phát sinh nếu override được chốt). Cần
   mentor confirm: cấm hoàn toàn, hay cho phép qua config flag, hay
   cho phép qua env-level override.
9. **Rate limit value & mechanism.** 60 req/min/user là
   `WORKING_ASSUMPTION`; cơ chế (token bucket / leaky bucket) là
   `IMPLEMENTATION_OPTION`. Cần calibrate khi có usage pattern thật.
10. **Audit retention & storage.** Audit log giữ bao lâu? Có cần WORM
    storage không? Cần ADR. (`CONTRACT_REQUIRED`: append-only đã chốt.)
11. **Long-running job timeout.** Default timeout cụ thể cho
    `JOB_TIMEOUT` chưa lock; `WORKING_ASSUMPTION`.
12. **Pre-signed URL TTL.** Download raw / interim / model artifact qua
    pre-signed URL có TTL bao lâu? Cần ADR. `REVIEW_REQUIRED`.
13. **Tech stack cho backend service.** FastAPI / Pydantic / job queue
    (RQ / Celery / custom) / DB đều là `IMPLEMENTATION_OPTION`. Tài liệu
    này **không** chốt lựa chọn; Phase sau chọn với mentor.
14. **OpenAPI generation.** Tài liệu này dùng OpenAPI 3.1 như **mục tiêu
    schema** (`CONTRACT_REQUIRED`); cơ chế sinh (Pydantic, manual YAML,
    …) là `IMPLEMENTATION_OPTION`.

---

**Hết SYS-05.**