# 0003. Embedding và nơi lưu vector ở mốc 1

Ngày: 2026-10-26 · Trạng thái: Chấp nhận, xem lại ở mốc 2

## Bối cảnh

Đề xuất ban đầu là bge-m3 + Qdrant/pgvector. Nhưng bge-m3 kéo theo PyTorch và ~2,3 GB model, làm CI chậm và người clone repo phải tải nặng mới chạy được demo. Corpus mốc 1 chỉ có 5 tài liệu, 23 chunk.

## Quyết định

- Giao diện `Embedder` với hai bản: `HashingEmbedder` (n-gram ký tự 3–5 trên văn bản bỏ dấu, băm vào vector 2048 chiều, không cần tải gì) là mặc định; `BgeM3Embedder` bật bằng `EMBEDDER=bge-m3` sau khi cài `requirements-ml.txt`.
- Index để trong bộ nhớ (numpy), dựng lại lúc khởi động. Với vài chục chunk, tìm kiếm mất khoảng 1–2 ms.

## Cái giá

- Hashing embedder không hiểu nghĩa: "không vừa" và "đổi ý" không gần nhau. Số đo ở ADR 0002 cho thấy vector hashing yếu hơn BM25 rõ rệt.
- Chưa có số đo cho bge-m3. Việc cần làm: chạy `eval_retrieval.py --embedder bge-m3` và ghi kết quả vào README trước khi chọn mặc định.

## Khi nào đổi

Chuyển sang pgvector ở mốc 2, vì Postgres đã có trong Docker Compose cho DB đơn hàng, đỡ thêm một dịch vụ (Qdrant). Điều kiện: corpus vượt vài nghìn chunk hoặc cần cập nhật tài liệu mà không khởi động lại.
