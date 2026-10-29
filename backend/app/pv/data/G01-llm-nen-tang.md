---
group: G01
title: LLM nền tảng, prompt và context
part: I
---

# Nhóm 1 — LLM nền tảng, prompt và context

## G01-A01 · Token, context window và chi phí
Lớp: A
Nguồn: bổ sung
Tags: tokens, cost, context-window

### Sếp hỏi
Giải thích token và context window ảnh hưởng tới chi phí và độ trễ thế nào. Tiếng Việt có gì đặc biệt?

### Chốt kỹ thuật
- Giá tính theo token vào và token ra (token ra thường đắt gấp 3–5 lần token vào).
- Độ trễ: TTFT tăng theo token vào (prefill), thời gian sinh tăng tuyến tính theo token ra (decode tuần tự).
- Tiếng Việt có dấu thường tốn nhiều token hơn tiếng Anh cho cùng nội dung với nhiều tokenizer (có thể 1,5–3 lần), nên chi phí và giới hạn context thực tế khác.
- Context dài làm chất lượng giảm ở thông tin nằm giữa (lost in the middle) và tốn tiền; không nên nhồi.
- Đo bằng tokenizer thật của model trên dữ liệu thật trước khi ước tính chi phí.

### Ví dụ tư vấn
"AI tính tiền theo lượng chữ đọc và viết. Tiếng Việt tốn nhiều hơn tiếng Anh một chút, bên em đã tính vào báo giá dựa trên dữ liệu thật của anh/chị."

### Ví dụ đàm phán
"Câu trả lời ngắn gọn hơn không chỉ dễ đọc mà còn rẻ hơn, vì phần AI viết ra đắt nhất."

## G01-A02 · Temperature và tính tất định
Lớp: A
Nguồn: bổ sung
Tags: sampling, determinism

### Sếp hỏi
Đặt temperature 0 có làm output tất định không? Khi nào dùng temperature cao?

### Chốt kỹ thuật
- Temperature 0 (greedy) giảm biến thiên nhưng không đảm bảo tất định tuyệt đối: batching, phần cứng, phép cộng dấu phẩy động không kết hợp, cập nhật model ở phía nhà cung cấp.
- Dùng thấp cho trích xuất, phân loại, JSON, trả lời có căn cứ. Dùng cao hơn cho sáng tạo nội dung, sinh nhiều phương án, sinh dữ liệu eval đa dạng.
- Tính tất định trong hệ thống nên đến từ thiết kế: validate, rule, cache, không từ temperature.
- Eval phải chạy lặp nhiều lần với tác vụ quan trọng để đo độ ổn định.

### Ví dụ tư vấn
"Bên em đặt AI ở chế độ ít ngẫu hứng nhất cho việc tra cứu, và vẫn có các bước kiểm tra vì AI không bao giờ hoàn toàn giống nhau mỗi lần."

### Ví dụ đàm phán
"Muốn cùng câu hỏi luôn ra cùng câu trả lời, bên em dùng bộ nhớ đệm cho câu hỏi phổ biến."

## G01-A03 · Viết system prompt cho production
Lớp: A
Nguồn: bổ sung
Tags: prompt-engineering, structure

### Sếp hỏi
Cấu trúc một system prompt production tốt gồm những phần gì? Bạn quản lý phiên bản prompt thế nào?

### Chốt kỹ thuật
- Phần: vai trò và phạm vi; nguồn dữ liệu được dùng; quy tắc theo thứ tự ưu tiên (an toàn > đúng căn cứ > định dạng > giọng văn); cách xử lý khi không chắc (từ chối, hỏi lại); định dạng output (schema); ví dụ ngắn cho ca khó; chỉ dẫn về dữ liệu không tin cậy.
- Viết cụ thể và có thể kiểm tra ("cite đúng Khoản chứa con số") thay vì chung chung ("trả lời chính xác").
- Quản lý: prompt trong code (version control), có id phiên bản ghi vào trace, mỗi thay đổi chạy eval, ghi lý do mỗi quy tắc.
- Phần cố định đặt đầu để tận dụng prompt caching; phần biến đổi (ngữ cảnh, câu hỏi) đặt cuối.

### Ví dụ tư vấn
"Hướng dẫn cho AI được viết như quy trình làm việc cho nhân viên mới: rõ phạm vi, rõ thứ tự ưu tiên, rõ phải làm gì khi không chắc."

### Ví dụ đàm phán
"Mỗi lần chỉnh hướng dẫn đều được lưu phiên bản và kiểm tra lại, nên luôn quay lại được bản cũ."

## G01-A04 · Few-shot, chain-of-thought và model suy luận
Lớp: A
Nguồn: bổ sung
Tags: few-shot, reasoning, cot

### Sếp hỏi
Khi nào dùng few-shot, khi nào yêu cầu model suy nghĩ từng bước, khi nào dùng model có chế độ suy luận (reasoning)? Chi phí đánh đổi?

### Chốt kỹ thuật
- Few-shot: hiệu quả để dạy định dạng và ranh giới phân loại; rủi ro model bắt chước sát ví dụ (thiên lệch theo ví dụ), tốn token mỗi request (giảm nhờ caching).
- Suy nghĩ từng bước: giúp tác vụ nhiều bước (tính toán, so sánh điều kiện); tăng token ra và độ trễ; với output có cấu trúc, đặt trường lý luận trước trường kết luận.
- Model reasoning: tốt cho bài toán khó (lập kế hoạch, phân tích phức tạp); đắt và chậm hơn nhiều; không cần cho tra cứu, phân loại đơn giản.
- Quyết định bằng eval: đo chất lượng và chi phí từng cấu hình trên tác vụ cụ thể, dùng route theo độ khó.

### Ví dụ tư vấn
"Việc đơn giản dùng AI nhanh và rẻ. Việc cần cân nhắc nhiều điều kiện mới dùng chế độ suy nghĩ kỹ, chậm hơn và đắt hơn."

### Ví dụ đàm phán
"Bên em chỉ bật chế độ suy nghĩ kỹ cho loại câu hỏi được lợi rõ ràng, để giữ chi phí."

## G01-A05 · Fine-tune hay RAG hay prompt
Lớp: A
Nguồn: bổ sung
Tags: fine-tuning, rag, decision

### Sếp hỏi
Khách muốn "huấn luyện AI trên tài liệu công ty". Khi nào fine-tune, khi nào RAG, khi nào chỉ cần prompt?

### Chốt kỹ thuật
- Prompt: khi yêu cầu là hành vi, định dạng, giọng văn đơn giản. Rẻ nhất, thử trước.
- RAG: khi cần kiến thức cụ thể, thay đổi theo thời gian, cần trích nguồn, cần phân quyền. Kiến thức không nên đưa vào trọng số.
- Fine-tune: khi cần hành vi hoặc định dạng nhất quán mà prompt không đạt, thuật ngữ và văn phong chuyên ngành, giảm chi phí bằng model nhỏ thay model lớn cho tác vụ hẹp (distillation), hoặc giảm độ dài prompt. Cần dữ liệu chất lượng (vài trăm đến vài nghìn mẫu), eval, và vận hành mỗi lần model nền đổi.
- Thường kết hợp: RAG cho kiến thức, fine-tune nhẹ (LoRA) cho định dạng nếu cần.

### Ví dụ tư vấn
"Muốn AI biết tài liệu công ty thì cho nó tra tài liệu mỗi lần trả lời, cập nhật dễ và trích được nguồn. Huấn luyện lại chỉ cần khi muốn nó viết theo một phong cách rất riêng."

### Ví dụ đàm phán
"Huấn luyện lại tốn chi phí và phải làm lại khi tài liệu đổi. Bên em chỉ đề xuất khi cách tra cứu không đạt yêu cầu."

## G01-A06 · Prompt caching
Lớp: A
Nguồn: bổ sung
Tags: prompt-caching, cost, latency

### Sếp hỏi
Prompt caching hoạt động thế nào và bạn thiết kế prompt để tận dụng nó ra sao?

### Chốt kỹ thuật
- Nhà cung cấp lưu trạng thái tính toán của phần đầu prompt (prefix) giống hệt nhau giữa các request trong một khoảng thời gian; request sau đọc lại với giá rẻ hơn nhiều và TTFT thấp hơn.
- Thiết kế: phần cố định (system prompt, mô tả tool, tài liệu dùng chung, ví dụ) đặt đầu và không đổi; phần biến đổi (thời gian, tên người dùng, câu hỏi, tài liệu truy hồi) đặt cuối.
- Tránh vô hiệu cache vô tình: chèn timestamp vào đầu prompt, đổi thứ tự tool, thay đổi nhỏ trong system prompt.
- Đo cache hit rate từ thông tin usage trả về.
- Với tự host: prefix caching trong vLLM/SGLang cùng nguyên lý.

### Ví dụ tư vấn
"Phần hướng dẫn chung AI chỉ cần đọc kỹ một lần, những lần sau đọc lại với giá rẻ, nên chi phí mỗi câu hỏi giảm đáng kể."

### Ví dụ đàm phán
"Tối ưu này giảm chi phí đọc hướng dẫn lên tới khoảng 90%, bên em làm mặc định."

## G01-A07 · Hallucination: nguyên nhân và cách giảm
Lớp: A
Nguồn: bổ sung
Tags: hallucination, grounding

### Sếp hỏi
Vì sao LLM bịa thông tin? Liệt kê các biện pháp giảm theo hiệu quả và chi phí.

### Chốt kỹ thuật
- Nguyên nhân: model tối ưu để sinh văn bản hợp lý, không để biết khi nào mình không biết; câu hỏi ngoài kiến thức hoặc ngữ cảnh thiếu; prompt ép phải trả lời; tài liệu truy hồi sai.
- Biện pháp: cho phép và khuyến khích từ chối (giảm áp lực phải trả lời); RAG với căn cứ; bắt trích dẫn và kiểm tra trích dẫn bằng code; output có cấu trúc; kiểm tra hỗ trợ từng ý (NLI/LLM); số liệu lấy trực tiếp từ dữ liệu thay vì để model viết; self-consistency cho câu quan trọng; người duyệt cho ca rủi ro cao.
- Đo: tỷ lệ câu có ý không được nguồn hỗ trợ trên bộ eval.

### Ví dụ tư vấn
"AI đôi khi tự tin nói điều không có thật. Bên em buộc nó chỉ nói những gì có trong tài liệu, chỉ rõ nguồn, và tự kiểm tra nguồn đó có thật."

### Ví dụ đàm phán
"Mỗi lớp chống bịa có chi phí. Bên em chọn số lớp theo mức rủi ro của từng loại câu hỏi."

## G01-A08 · Chọn model cho từng tác vụ
Lớp: A
Nguồn: bổ sung
Tags: model-selection, routing, cost

### Sếp hỏi
Bạn có 5 loại tác vụ: phân loại, viết lại câu hỏi, trả lời có trích dẫn, soạn thảo văn bản dài, xử lý dữ liệu hàng loạt. Chọn model cho mỗi loại thế nào?

### Chốt kỹ thuật
- Nguyên tắc: model rẻ nhất đạt ngưỡng chất lượng trên eval của tác vụ đó.
- Phân loại, viết lại: model nhỏ/nhanh (flash-lite, mini), độ trễ thấp quan trọng.
- Trả lời có trích dẫn: model tầm trung có structured output tốt, hiểu tiếng Việt tốt.
- Soạn thảo dài: model mạnh về viết dài và tuân thủ định dạng.
- Hàng loạt: model rẻ, batch API (giảm giá, chấp nhận trễ), hoặc tự host.
- Danh sách fallback theo tác vụ, mỗi model trong danh sách đã qua eval.
- Dự án luật lao động: router có bảng task → danh sách nhà cung cấp (route/lite dùng flash-lite, answer dùng flash, draft/report dùng Claude, bulk dùng FPT), Dahl đua trước.

### Ví dụ tư vấn
"Việc dễ dùng AI nhỏ và rẻ, việc khó dùng AI mạnh. Không dùng AI đắt nhất cho mọi việc."

### Ví dụ đàm phán
"Phân công model theo việc thường giảm 40–70% chi phí so với dùng một model mạnh cho tất cả."

## G01-A09 · Embedding hoạt động thế nào
Lớp: A
Nguồn: bổ sung
Tags: embedding, cosine, fundamentals

### Sếp hỏi
Giải thích embedding và cosine similarity cho một kỹ sư backend chưa làm AI. Bi-encoder khác cross-encoder thế nào?

### Chốt kỹ thuật
- Embedding: model biến văn bản thành vector số cố định chiều (ví dụ 1024), huấn luyện sao cho văn bản cùng nghĩa có vector gần nhau.
- Cosine similarity: đo góc giữa hai vector, 1 là cùng hướng; với vector đã chuẩn hóa độ dài 1, cosine bằng tích vô hướng. pgvector dùng toán tử <=> cho khoảng cách cosine.
- Bi-encoder: encode câu hỏi và tài liệu độc lập, tài liệu encode sẵn một lần, tìm nhanh trên hàng triệu tài liệu; kém tinh tế hơn.
- Cross-encoder: đưa cặp (câu hỏi, tài liệu) vào cùng model chấm điểm, chính xác hơn nhưng phải chạy cho từng cặp, nên chỉ dùng để rerank vài chục ứng viên.
- Giới hạn: không phân biệt tốt số, phủ định, tên riêng hiếm; độ dài tối đa đầu vào.

### Ví dụ tư vấn
"Mỗi đoạn văn được đổi thành một tọa độ trên bản đồ ý nghĩa. Câu hỏi cũng có tọa độ, hệ thống lấy những đoạn ở gần nhất."

### Ví dụ đàm phán
"Phần đổi văn bản thành tọa độ chạy trên máy chủ của mình, không tốn phí theo lượt."

## G01-A10 · Đo và giảm độ trễ end-to-end
Lớp: A
Nguồn: bổ sung
Tags: latency, ttft, optimization

### Sếp hỏi
Trợ lý RAG mất 8 giây mỗi câu. Bạn phân rã và giảm độ trễ thế nào?

### Chốt kỹ thuật
- Đo từng bước bằng trace: embedding câu hỏi, truy vấn DB, rerank, các lượt gọi LLM (TTFT và thời gian sinh), tool, mạng.
- Song song hóa bước độc lập (phân loại chạy song song với truy hồi và soạn trả lời; bỏ kết quả nếu phân loại loại câu đó).
- Stream để giảm thời gian cảm nhận.
- Giảm token vào (ít chunk hơn, chunk gọn), giới hạn token ra, prompt caching.
- Model nhanh hơn cho bước phụ; nạp sẵn model embedding khi khởi động (tránh cold start).
- Hedging khi nhà cung cấp có đuôi chậm.
- Dự án luật lao động: phân loại và soạn trả lời chạy song song trong ThreadPoolExecutor, model embedding nạp khi API khởi động, router đua nhiều model.

### Ví dụ tư vấn
"Bên em đo từng bước mất bao lâu, cho các bước không phụ thuộc nhau chạy cùng lúc, và hiện chữ ngay khi có."

### Ví dụ đàm phán
"Giảm từ 8 xuống 3–4 giây thường làm được bằng tối ưu, không cần đổi model đắt hơn."
