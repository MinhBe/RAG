# 0006. Một cổng gọi model theo vai trò (LiteLLM), Gemini khi phát triển

Ngày: 2026-10-27 · Trạng thái: Chấp nhận · Bổ sung cho [0004](0004-llm-and-citations.md)

## Bối cảnh

Trong giai đoạn phát triển, lab dùng Gemini cho rẻ. Khi bộ eval cho thấy hệ thống đã ổn thì mới chạy với Claude. Nếu mỗi chỗ trong code tự gọi SDK của một hãng, việc đổi hãng sẽ phải sửa nhiều nơi, và không so được hai model trên cùng một bộ câu hỏi.

## Quyết định

- Code nghiệp vụ gọi model **theo vai trò** (`answer`, `router`, `extract`). Vai trò nào dùng model nào được ghi trong `config/models.yaml`, theo cú pháp của LiteLLM.
- Tên model Gemini không ghi cứng trong file mà lấy từ `GEMINI_MODEL` trong `.env`. Lý do: danh sách model mà một key gọi được có thể khác với tài liệu, ví dụ một tên đã thấy trong danh sách nhưng gọi thì trả 404. Thiếu biến này thì ứng dụng báo lỗi ngay lúc khởi động.
- **Retry** chỉ áp dụng cho lỗi có thể khỏi khi thử lại: 429, 408, 409 và 5xx. Gặp 429 thì làm theo `Retry-After` nếu nhà cung cấp gửi kèm. Nếu không có thì dùng backoff mũ với full jitter, tối đa 3 lần. Các lỗi 400, 401, 403, 404 không retry.
- Retry và fallback chỉ bọc **bước mở stream**. Khi chữ đã hiện ra cho người dùng thì không chuyển sang model khác, để người dùng không thấy hai câu trả lời khác nhau.
- Chế độ offline vẫn là tầng cuối khi không có key nào.

## Cái giá

- Phụ thuộc thêm LiteLLM, một thư viện lớn và ra phiên bản liên tục. Bản đang dùng được ghim cố định, và bản ghim phải ra đời ít nhất 2 tuần trước khi dùng.
- Các tính năng riêng của từng hãng (ví dụ `effort` hay Citations API của Claude) không đi qua lớp chung này. Muốn dùng thì vẫn gọi `AnthropicLLM` trực tiếp, đặt `LLM_PROVIDER=anthropic`.
