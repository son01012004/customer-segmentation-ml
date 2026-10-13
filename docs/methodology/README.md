# Methodology — Chỉ mục

> **Mục đích của tài liệu này.** Đây là chỉ mục cho `docs/methodology/`.
> Thư mục này chứa **các tài liệu methodology nghiên cứu** của dự án:
> research questions, giả thuyết, study design, unit of analysis, và
> benchmarking protocol.
>
> **Ngôn ngữ:** tiếng Việt cho phần diễn giải; giữ nguyên tiếng Anh
> cho tên file, identifier, RQ ID, ADR ID, schema theo convention hiện có.
>
> **Ngày tạo index:** 2026-10-12.
> **Cập nhật:** Phase 2B.4 — bổ sung phần này để thống nhất ngôn ngữ.
> **Phạm vi:** navigation + chính sách cập nhật methodology. KHÔNG tự ý
> sửa methodology; mọi thay đổi phải qua PR + review + ADR mới.

---

## 1. Quy tắc cố định

Các tài liệu trong thư mục này **được project lead cố định** và KHÔNG
được contributor tự ý sửa. Mọi thay đổi đối với research question hoặc
benchmarking protocol phải:

1. Được đề xuất qua Pull Request kèm lý do rõ ràng.
2. Được project lead review và phê duyệt.
3. Được ghi lại thành Architecture Decision Record trong
   [`../decisions/`](../decisions/).

Lý do: methodology là phần **ảnh hưởng trực tiếp đến kết quả nghiên cứu**.
Mọi thay đổi phải có audit trail đầy đủ (xem `AGENTS.md` §2.1, §2.9,
§2.10).

---

## 2. Danh sách tài liệu hiện có

| File | Trạng thái | Mô tả |
|---|---|---|
| `research_questions.md` | ✅ ACTIVE | RQ1, RQ2, RQ3 — định nghĩa chính thức |
| `methodology_overview.md` | ✅ ACTIVE | Study design, benchmarking protocol, experiment pipeline |
| `TODO_unit_of_analysis.md` | ⏳ PENDING | Unit of analysis rationale (sẽ thêm nếu cần) |

---

## 3. Quyết định chính (ADR liên quan)

| ADR | Quyết định |
|---|---|
| ADR-0001 | Primary dataset = UCI Online Retail |
| ADR-0002 | Backup dataset = UCI Online Retail II |
| ADR-0003 | Algorithm scope = 5 thuật toán (K-Medoids OUT OF SCOPE) |
| ADR-0004 | Research Questions RQ1, RQ2, RQ3 — định nghĩa chính thức |

Xem [`../decisions/`](../decisions/) để có nguyên văn ADR.

---

## 4. Trạng thái methodology ở Phase 2B.4

- **Algorithm scope**: ✅ LOCKED qua ADR-0003 (5 thuật toán,
  K-Medoids OUT OF SCOPE).
- **RQ1, RQ2, RQ3**: ✅ LOCKED qua ADR-0004.
- **Feature set & preprocessing config**: ⚠️ WORKING_ASSUMPTION
  (xem `docs/research/review/METHODOLOGY_LOCK_STATUS.md`).
- **Cross-algorithm ranking / "best" claim**: ⚠️ PENDING, KHÔNG được
  phép cho tới khi EPIC-08 Phase B + mentor approval
  (xem `AGENTS.md` §2.5, §2.6, §2.10).

Index này **không** tự ý nâng trạng thái methodology lên mức cao hơn
header đã ghi rõ trong từng file. Quyết định methodology thuộc về
project lead / mentor.

---

## 5. Phạm vi của index này

- KHÔNG sửa nội dung bất kỳ file methodology nào.
- KHÔNG thay đổi RQ1/RQ2/RQ3 đã được lock.
- KHÔNG suy diễn `WORKING_ASSUMPTION` thành `LOCKED` / `APPROVED`.
- KHÔNG tự ý thêm file mới vào đây (ví dụ: thay thế `TODO_*` bằng
  nội dung khác) — cần owner quyết định trước.

---

**Hết chỉ mục methodology.**
