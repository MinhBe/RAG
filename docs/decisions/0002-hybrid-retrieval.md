# 0002. Hybrid search BM25 + vector, gộp bằng RRF

Ngày: 2026-10-26 · Trạng thái: Chấp nhận

## Bối cảnh

Câu hỏi chính sách có hai kiểu: kiểu chứa từ khóa cụ thể ("MoMo", "Visa", "2.000.000", "sofa") và kiểu diễn đạt lại ("gửi trả vì không vừa thì mất phí không"). Người dùng Việt còn hay gõ không dấu ("hoan tien ve vi momo").

## Phương án

1. Chỉ vector: tốt với diễn đạt lại, yếu với số tiền, mã, tên riêng.
2. Chỉ BM25: tốt với từ khóa, yếu khi khách dùng từ khác tài liệu.
3. **Hybrid, gộp bằng Reciprocal Rank Fusion (RRF, k=60)**: RRF chỉ dùng thứ hạng nên không phải chuẩn hóa thang điểm của hai bên.
4. Hybrid gộp theo trọng số điểm: phải tinh chỉnh trọng số, thang điểm BM25 thay đổi theo kích thước corpus.

## Tách từ tiếng Việt

Không dùng bộ tách từ (pyvi, underthesea) ở mốc 1. Thay vào đó index âm tiết + cặp âm tiết liền nhau (bigram, xấp xỉ từ ghép như "hoàn_tiền") + bản bỏ dấu có tiền tố `~`. Câu hỏi có dấu vẫn ưu tiên khớp chính xác, câu hỏi không dấu vẫn tìm được. Lý do: không thêm phụ thuộc nặng, và với corpus chính sách ngắn thì bigram đã đủ. Sẽ đo lại khi corpus lớn hơn.

## Số đo (bộ 24 câu hỏi tự soạn, embedder hashing)

| Chế độ | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| BM25 | 0,83 | 0,88 | 0,96 | 0,87 |
| Vector (hashing) | 0,50 | 0,83 | 0,88 | 0,66 |
| Hybrid RRF | 0,79 | 0,96 | 0,96 | 0,85 |

Hybrid tăng R@3 (chỉ số quan trọng vì LLM nhận top 5) nhưng giảm nhẹ R@1 so với BM25. Bộ câu hỏi còn nhỏ và do chính người viết tài liệu soạn nên có thiên lệch; số này để so sánh tương đối giữa các phương án, không phải chất lượng tuyệt đối. Chạy lại: `python backend/scripts/eval_retrieval.py`.

## Hệ quả

- Rerank (AITeamVN/Vietnamese_Reranker) để sau khi có bộ eval 150–200 câu, chỉ thêm nếu đo thấy tăng.
- Hàm `search(mode=...)` giữ cả ba chế độ để eval so sánh trong CI.
