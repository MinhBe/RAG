# 0005. Tự viết code; chưa dùng LangGraph ở mốc 1

Ngày: 2026-10-26 · Trạng thái: Chấp nhận

## Tự viết, không fork template

Các template FastAPI + LangGraph (wassim249, vstorm-co, nicholasgoh) chỉ dùng để tham khảo cấu trúc. Code trong repo này viết mới, lịch sử commit phản ánh đúng quá trình làm. Nếu sau này chép đoạn code nào từ repo MIT, giữ thông báo bản quyền và ghi nguồn trong README mục "Ghi công".

## Chưa dùng LangGraph

Mốc 1 chỉ có một agent chạy tuyến tính: tìm tài liệu → soạn câu trả lời. Dùng LangGraph lúc này chỉ thêm lớp trừu tượng mà chưa có lợi ích. Lớp `KnowledgeAgent` phát ra chuỗi sự kiện (`step`, `sources`, `token`, `done`) đúng hình dạng mà một node LangGraph sẽ stream, nên ở mốc 2 nó trở thành một node dưới Supervisor mà UI không phải sửa.

LangGraph sẽ vào ở mốc 2 vì lúc đó cần thật: định tuyến giữa 5 agent, checkpointer cho memory ngắn hạn, và `interrupt` cho bước người duyệt.
