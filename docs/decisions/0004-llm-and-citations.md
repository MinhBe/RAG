# 0004. LLM và cách trích dẫn nguồn

Ngày: 2026-10-26 · Trạng thái: Chấp nhận

## LLM

Gọi Claude qua Anthropic Python SDK (`AsyncAnthropic.messages.stream`). Mặc định `claude-opus-5-5` với `effort: low`, đổi bằng biến môi trường `LLM_MODEL`, `LLM_EFFORT`. Định tuyến model rẻ/đắt để dành cho mốc 7, khi đã có eval để biết model rẻ có giữ được chất lượng không.

Khi không có `ANTHROPIC_API_KEY`, hệ thống chạy **chế độ offline**: trả lời bằng cách trích nguyên văn các dòng trong nguồn trùng từ khóa với câu hỏi. Mục đích: ai clone repo cũng chạy được demo, test và CI không tốn tiền, không phụ thuộc mạng. UI ghi rõ khi đang ở chế độ này.

## Trích dẫn

1. **Thẻ đánh số trong prompt** (`<tai_lieu id="1">`) và yêu cầu model ghi `[1]`: chạy được với mọi model, kể cả Qwen tự host sau này. Server kiểm tra số trích dẫn có nằm trong danh sách nguồn không (`invalid_citations`), đây là tín hiệu hallucination đầu tiên đưa vào eval.
2. **Citations API của Claude** (document block có `citations.enabled`): trả về đoạn trích chính xác theo ký tự, chất lượng tốt hơn, nhưng gắn chặt với một nhà cung cấp.

Chọn phương án 1 vì lộ trình có bước chạy model mở (Qwen qua vLLM). Sẽ thử phương án 2 như một biến thể A/B ở mốc 6–7 và so bằng số đo faithfulness.

## Chống prompt injection (bước đầu)

System prompt nói rõ nội dung trong `<tai_lieu>` là dữ liệu, không phải chỉ dẫn; tiêu đề nguồn được escape HTML. Bộ test tài liệu chứa lệnh độc để ở mốc 7.

## Từ chối khi không có thông tin

Nếu không chunk nào khớp từ khóa và độ tương đồng vector cao nhất dưới `MIN_DENSE_SCORE`, agent trả lời "chưa tìm thấy" mà không gọi LLM: vừa tránh bịa, vừa không tốn token.
