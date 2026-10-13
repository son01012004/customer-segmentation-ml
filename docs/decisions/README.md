# Decisions — Architecture Decision Records (Chỉ mục)

> **Mục đích của tài liệu này.** Đây là chỉ mục cho `docs/decisions/`.
> Thư mục này ghi lại **các quyết định nghiên cứu và kỹ thuật** được
> đưa ra trong dự án, theo template ADR nhẹ bên dưới.
>
> **Ngôn ngữ:** tiếng Việt cho phần diễn giải; giữ nguyên tiếng Anh
> cho tên ADR, identifier, status, command theo convention hiện có.
>
> **Ngày tạo index:** 2026-10-12.
> **Cập nhật:** Phase 2B.4 — bổ sung phần này để thống nhất ngôn ngữ.
> **Phạm vi:** navigation + chính sách ADR. KHÔNG tự ý đổi status ADR
> đã Accepted; mọi đảo ngược phải qua ADR mới supersede.

---

## 1. Quy tắc bất biến của ADR

- ADR là **bất biến một khi đã Accepted**. Không sửa nội dung ADR đã
  Accepted.
- Nếu quyết định bị đảo ngược, viết **ADR mới** supersede cái cũ; không
  sửa file cũ.
- ADR ở trạng thái `Proposed` / `WORKING_ASSUMPTION` có thể được cập
  nhật (ví dụ: thêm context, bổ sung evidence), nhưng KHÔNG tự ý đổi
  sang `Accepted` mà không có review từ project lead.

---

## 2. Quy ước đặt tên file

Sử dụng số thứ tự bốn chữ số tiếp theo và tiêu đề kebab-case ngắn:

```
NNNN-short-kebab-title.md
```

Ví dụ (đã có trong repo):

- `0001-primary-dataset-uci-online-retail.md`
- `0002-backup-dataset-uci-online-retail-ii.md`
- `0003-algorithm-scope.md`
- `0004-research-questions.md`
- `0005-prototype-architecture-option-a.md`
- `0006-dev05-prototype-noise-policy.md`
- `0008-dev07-version-pattern.md`
- `0009-prototype-storage-layout.md`

Lưu ý: hiện KHÔNG có `0007`; số tiếp theo được dùng là `0010` trở đi
(tuỳ theo quyết định của owner).

---

## 3. Template ADR

```markdown
# NNNN — <short title>

- **Status**: Proposed | Accepted | Superseded by NNNN
- **Date**: YYYY-MM-DD
- **Deciders**: <names>
- **Task ID**: <DS-05 | FE-01 | ...>

## Context

Tình huống nào đòi hỏi phải đưa ra quyết định?

## Decision

Chúng ta đã quyết định gì?

## Consequences

Điều gì trở nên dễ hơn? Điều gì khó hơn hoặc rủi ro hơn?

## Alternatives considered

Những lựa chọn khác đã được cân nhắc, và vì sao bị loại?
```

---

## 4. Danh sách ADR hiện có

| ADR | Trạng thái | Chủ đề |
|---|---|---|
| `0001-primary-dataset-uci-online-retail.md` | Accepted | Dataset chính = UCI Online Retail |
| `0002-backup-dataset-uci-online-retail-ii.md` | Accepted | Dataset backup = UCI Online Retail II |
| `0003-algorithm-scope.md` | Accepted | 5 thuật toán (K-Medoids OUT OF SCOPE) |
| `0004-research-questions.md` | Accepted | RQ1, RQ2, RQ3 |
| `0005-prototype-architecture-option-a.md` | (untracked, xem status trong file) | Prototype architecture: file-based batch / offline (Option A) |
| `0006-dev05-prototype-noise-policy.md` | (untracked, xem status trong file) | DEV-05 noise policy cho prototype scope |
| `0008-dev07-version-pattern.md` | (untracked, xem status trong file) | DEV-07 canonical version pattern |
| `0009-prototype-storage-layout.md` | (untracked, xem status trong file) | Prototype storage layout |

Lưu ý: 4 ADR `0005 / 0006 / 0008 / 0009` hiện là **untracked file** (chưa
được commit). Xem `docs/README.md` §3.1 và §5.1 để biết phạm vi xử lý.

---

## 5. Phạm vi của index này

Index này:

- KHÔNG tự ý nâng trạng thái ADR từ `Proposed` / `WORKING_ASSUMPTION`
  lên `Accepted`.
- KHÔNG sửa nội dung bất kỳ ADR nào.
- KHÔNG thay đổi numbering.
- KHÔNG đảo ngược quyết định đã lock trong ADR-0003 / ADR-0004 (5
  algorithms + RQ1/RQ2/RQ3).

Mọi thay đổi đối với ADR đã Accepted chỉ có thể thông qua **ADR mới
supersede** và phải được review bởi project lead.

---

**Hết chỉ mục ADR.**
