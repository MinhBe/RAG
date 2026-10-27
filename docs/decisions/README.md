# Nhật ký quyết định kỹ thuật (ADR)

Mỗi file ghi một quyết định: bối cảnh, các phương án đã cân nhắc, lựa chọn và cái giá phải trả. Quyết định bị thay thế thì không xóa, chỉ đổi trạng thái và trỏ sang ADR mới.

| # | Quyết định | Trạng thái |
|---|---|---|
| [0001](0001-fastapi-sse.md) | FastAPI async + Server-Sent Events cho chat streaming | Chấp nhận |
| [0002](0002-hybrid-retrieval.md) | Hybrid search BM25 + vector, gộp bằng RRF, tách từ tiếng Việt kiểu âm tiết | Chấp nhận |
| [0003](0003-embeddings-and-vector-store.md) | Embedding baseline không cần tải model, bge-m3 bật bằng cờ; index trong bộ nhớ ở mốc 1 | Chấp nhận, xem lại ở mốc 2 |
| [0004](0004-llm-and-citations.md) | Claude qua Anthropic SDK, chế độ offline, trích dẫn bằng thẻ đánh số | Chấp nhận |
| [0005](0005-no-template-no-langgraph-yet.md) | Tự viết, không fork template; chưa dùng LangGraph ở mốc 1 | Chấp nhận |
