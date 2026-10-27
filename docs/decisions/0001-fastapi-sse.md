# 0001. FastAPI async + Server-Sent Events cho chat streaming

Ngày: 2026-10-26 · Trạng thái: Chấp nhận

## Bối cảnh

UI cần hiện từng token và từng bước agent đang làm (tìm tài liệu, soạn câu trả lời; sau này là gọi tool, chờ duyệt). Phía server phải chịu được nhiều request chờ LLM cùng lúc.

## Phương án

1. **SSE qua `StreamingResponse`**: một chiều server → client, chạy trên HTTP thường, dễ đi qua proxy và dễ debug bằng `curl -N`.
2. **WebSocket**: hai chiều, nhưng phải tự quản lý kết nối, reconnect, và khó cache/log hơn.
3. **Polling**: đơn giản nhưng độ trễ cao, tốn request.

## Quyết định

Chọn SSE. Mỗi sự kiện có `event:` riêng (`step`, `sources`, `token`, `done`, `error`) để UI xử lý theo loại thay vì đoán từ nội dung. Endpoint là `POST /api/chat` vì cần gửi body JSON (lịch sử hội thoại), nên client dùng `fetch` + parser SSE tự viết (`frontend/lib/sse.ts`), không dùng `EventSource` (chỉ hỗ trợ GET).

## Hệ quả

- Duyệt bởi người (mốc 2) sẽ là request riêng (`POST /api/approvals/{id}`), không cần kênh hai chiều.
- Sự kiện `done` mang luôn độ trễ, token, chi phí, nên UI và log có cùng một nguồn số liệu, chuẩn bị cho Langfuse ở mốc 6.
- Header `X-Accel-Buffering: no` để nginx không gom buffer khi triển khai sau proxy.
