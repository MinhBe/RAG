---
group: G12
title: Hạ tầng và serving (tình huống)
part: II
---

# Nhóm 12 — Hạ tầng và serving

## G12-T01 · Chuyển từ API sang tự host trong 1 tháng, 50 triệu/tháng
Lớp: T
Nguồn: gốc
Tags: self-hosting, requirements, assumptions

### Sếp hỏi
Sếp giao: "Chuyển từ API sang tự host model trong 1 tháng để tiết kiệm, ngân sách hạ tầng 50 triệu/tháng." Liệt kê ít nhất 6 giả định phải làm rõ, và phương án rủi ro thấp nhất cho mỗi giả định nếu không được trả lời rõ.

### Chốt kỹ thuật
- Chất lượng chấp nhận được so với API hiện tại (giảm bao nhiêu % là chấp nhận)? Không rõ thì đặt mục tiêu "không giảm quá 3% trên bộ eval" và giữ API cho tác vụ khó.
- Lưu lượng và độ trễ: request/giây cao điểm, p95 cần đạt? Không rõ thì đo từ log 30 ngày gần nhất và thiết kế cho cao điểm × 1,5.
- 50 triệu gồm những gì (GPU, lưu trữ, mạng, nhân sự vận hành)? Không rõ thì tính riêng GPU và báo nhân sự là chi phí phát sinh.
- Có yêu cầu dữ liệu không rời Việt Nam không (ảnh hưởng chọn nhà cung cấp GPU)? Không rõ thì chọn nhà cung cấp trong nước.
- Tất cả tác vụ hay một phần? Không rõ thì chuyển tác vụ đơn giản, khối lượng lớn trước (phân loại, tóm tắt).
- Ai vận hành 24/7, SLA thế nào? Không rõ thì giữ API làm fallback.
- Ước tính sơ bộ: 50 triệu/tháng khoảng 1–2 GPU 80 GB thuê theo tháng; chạy được model 14B–32B quantize với throughput nhất định. So với hóa đơn API hiện tại để xem có thật sự tiết kiệm không.
- Lộ trình 1 tháng: tuần 1 benchmark model ứng viên trên eval; tuần 2 dựng serving (vLLM) và load test; tuần 3 shadow traffic; tuần 4 chuyển dần với fallback API.

### Ví dụ tư vấn
Với sếp: "Em làm được trong 1 tháng cho phần tác vụ đơn giản, giữ API cho phần khó và làm dự phòng. Em cần anh xác nhận mức giảm chất lượng chấp nhận được và ai trực vận hành."

### Ví dụ đàm phán
"Nếu chuyển 100% trong 1 tháng mà không có dự phòng, rủi ro sự cố cao. Em đề xuất chuyển 60% khối lượng, tiết kiệm phần lớn chi phí với rủi ro thấp."

## G12-T02 · Từ 100 lên 500 user đồng thời trong 2 tuần, không thêm GPU
Lớp: T
Nguồn: gốc
Tags: capacity, scaling, tradeoff

### Sếp hỏi
Hệ thống tự host 14B ổn với 100 user đồng thời, khách lớn sẽ đẩy lên 500 trong 2 tuần, không có ngân sách thêm GPU. Ít nhất 3 phương án (không chỉ mua GPU), đánh đổi, và phương án chọn nếu deadline tuyệt đối không đổi.

### Chốt kỹ thuật
- Tối ưu serving: continuous batching, PagedAttention (vLLM), prefix caching cho system prompt chung, giới hạn max_tokens, tăng batch size. Thường tăng throughput 2–4 lần. Rủi ro thấp, làm nhanh.
- Quantize (AWQ/GPTQ INT4 hoặc FP8): tăng số request đồng thời nhờ giảm VRAM cho weights, dành cho KV cache. Giảm chất lượng cần đo.
- Model nhỏ hơn cho tác vụ dễ (router theo độ khó), hoặc speculative decoding.
- Giảm tải: cache câu trả lời, rút ngắn prompt và context, hàng đợi có ưu tiên, giới hạn tần suất.
- Overflow sang API (trả theo dùng) cho phần vượt công suất: không cần đầu tư cố định.
- Lưu ý "500 user đồng thời" khác "500 request đồng thời": đo tỷ lệ thật (thường chỉ 10–30% user đang chờ phản hồi cùng lúc).
- Deadline cứng: tối ưu serving + prefix caching (tuần 1), overflow sang API cho phần vượt (tuần 2), load test với 600 user giả lập.

### Ví dụ tư vấn
"Bên em đẩy công suất máy hiện có lên bằng tối ưu cách chạy, phần vượt tạm chuyển sang dịch vụ AI thuê ngoài. Khách mới vẫn được phục vụ đúng hẹn."

### Ví dụ đàm phán
Với sếp: "Phương án này không cần mua GPU ngay, chi phí overflow trả theo dùng. Sau 1 tháng có số liệu thật mình mới quyết có mua GPU hay không."

## G12-T03 · INT4 giảm 4% chất lượng tiếng Việt phức tạp
Lớp: T
Nguồn: gốc
Tags: quantization, routing, quality

### Sếp hỏi
Quantize FP16 xuống INT4 tiết kiệm 60% VRAM, nhưng chất lượng giảm 4% trên câu hỏi tiếng Việt phức tạp (1% trên câu tiếng Anh đơn giản). Áp dụng toàn bộ, theo luồng, hay không? Khi nào 4% chấp nhận được?

### Chốt kỹ thuật
- Xem 4% rơi vào đâu: lỗi diễn đạt hay lỗi sai thông tin, tác vụ giá trị cao hay thấp.
- Thử phương án quantize khác trước khi kết luận: AWQ vs GPTQ, INT8 hoặc FP8 (thường giảm dưới 1%), quantize với dữ liệu hiệu chỉnh tiếng Việt.
- Route theo độ phức tạp: INT4 cho câu đơn giản (khối lượng lớn), FP16/FP8 cho câu phức tạp; cần router và hai deployment.
- Chấp nhận khi: tác vụ có hậu kiểm hoặc người duyệt, sai ít hậu quả, tiết kiệm giúp phục vụ được nhiều người hơn.
- Không chấp nhận khi: pháp lý, tài chính, y tế, hoặc 4% đó là sai thông tin.

### Ví dụ tư vấn
"Bản nén nhẹ chạy nhanh và rẻ cho câu hỏi đơn giản, câu hỏi phức tạp vẫn dùng bản đầy đủ."

### Ví dụ đàm phán
"Bên em đo cụ thể trên câu hỏi của anh/chị. Nếu phần giảm rơi vào câu quan trọng, bên em không áp dụng, dù tiết kiệm."

## G12-T04 · Pod GPU cần 4 phút khởi động, traffic tăng trong 90 giây
Lớp: T
Nguồn: gốc
Tags: autoscaling, cold-start, burst

### Sếp hỏi
Pod GPU mới cần 4 phút để tải model, nhưng traffic tăng đột biến trong 90 giây. Kiến trúc để không chết đứng khi scale-up, ít nhất 2 phương án, kèm chi phí ngày thường.

### Chốt kỹ thuật
- Giữ máy ấm (warm pool): luôn có N pod dư. Phản ứng tức thì, chi phí cố định cao mỗi ngày.
- Hàng đợi + giới hạn tải: chấp nhận request vào hàng đợi có ưu tiên, trả 429 hoặc thông báo chờ khi đầy. Chi phí ngày thường thấp, trải nghiệm kém khi đỉnh.
- Overflow sang API bên ngoài khi hàng đợi vượt ngưỡng. Chi phí chỉ phát sinh khi có đỉnh.
- Rút ngắn khởi động: image có sẵn model, tải từ ổ local/NVMe hoặc snapshot thay vì kéo mạng, dùng định dạng load nhanh (safetensors), giữ node GPU sẵn chỉ chưa chạy pod.
- Scale dự báo theo lịch hoặc tín hiệu sớm (lượt truy cập trang tăng trước lượt chat).
- Kết hợp thường hợp lý nhất: warm pool nhỏ + hàng đợi + overflow API.

### Ví dụ tư vấn
"Lúc đột ngột đông khách, hệ thống tạm chuyển phần vượt sang dịch vụ thuê ngoài trong vài phút trong khi máy mới khởi động, khách không phải chờ."

### Ví dụ đàm phán
"Giữ sẵn máy chờ tốn khoảng X triệu mỗi tháng kể cả khi không có đỉnh. Phương án chuyển tạm ra ngoài chỉ tốn khi có đỉnh."

## G12-T05 · Dữ liệu không rời Việt Nam, ngân sách GPU tầm trung
Lớp: T
Nguồn: gốc
Tags: data-residency, self-hosting, expectations

### Sếp hỏi
Khách yêu cầu dữ liệu tuyệt đối không rời Việt Nam, ngân sách chỉ đủ GPU tầm trung. Đề xuất cấu hình cụ thể (GPU, quantize, kích thước model) và những điều cần thông báo rõ trước khi ký.

### Chốt kỹ thuật
- Cấu hình ví dụ: 1–2 GPU 48 GB (L40S/A6000) hoặc 24 GB (L4/RTX 4090) tại data center trong nước; model open-weight 7B–14B (Qwen, Llama, Gemma, hoặc model tiếng Việt fine-tune) quantize AWQ INT4 hoặc FP8; vLLM; embedding model tiếng Việt tự host.
- Bù chất lượng: RAG tốt, prompt chặt, output có cấu trúc, phạm vi tác vụ hẹp, fine-tune LoRA cho tác vụ chính.
- Thông báo trước khi ký: chất lượng thấp hơn model thương mại lớn ở câu suy luận phức tạp (đưa số eval cụ thể); độ trễ và số người dùng đồng thời tối đa; phạm vi tác vụ phù hợp; chi phí nâng cấp nếu muốn chất lượng cao hơn.
- Cam kết bằng bộ eval do khách duyệt thay vì so với ChatGPT.

### Ví dụ tư vấn
"Toàn bộ chạy trên máy chủ đặt tại Việt Nam. Bên em nói trước: với câu hỏi phức tạp, chất lượng sẽ kém các dịch vụ lớn khoảng X% trên bộ kiểm tra này. Bên em tập trung làm thật tốt các việc chính của anh/chị."

### Ví dụ đàm phán
"Bên em cam kết theo bộ câu hỏi hai bên thống nhất. Muốn tăng chất lượng thì có các mức nâng cấp GPU với chi phí tương ứng."

## G12-T06 · Nhà cung cấp GPU tăng giá 25%, hợp đồng đã cố định
Lớp: T
Nguồn: gốc
Tags: cost, vendor, decision

### Sếp hỏi
Nhà cung cấp GPU cloud tăng giá 25% từ tháng sau, hợp đồng với khách cố định giá 1 năm. Phương án ứng phó và tiêu chí chọn trong 1 tuần.

### Chốt kỹ thuật
- Tối ưu hạ tầng bù chi phí: tăng tận dụng GPU (batching, quantize, prefix cache), tắt máy giờ thấp điểm, gộp workload. Thường bù được 15–30%.
- Đàm phán với nhà cung cấp: cam kết dài hạn (reserved) đổi lấy giá; dùng báo giá đối thủ làm đòn bẩy.
- Chuyển nhà cung cấp: chi phí migrate, rủi ro, yêu cầu dữ liệu trong nước; kiến trúc có portable không (container, không phụ thuộc dịch vụ riêng).
- Hybrid: overflow sang API khi rẻ hơn ở mức tải thấp.
- Chấp nhận lỗ ngắn hạn nếu hợp đồng chiến lược.
- Tiêu chí: tổng chi phí 12 tháng còn lại của từng phương án, rủi ro gián đoạn dịch vụ, công sức đội ngũ, điều khoản hợp đồng (có điều khoản điều chỉnh giá theo chi phí đầu vào không).

### Ví dụ tư vấn
Với sếp: "Em đề xuất làm song song: tối ưu hạ tầng để bù khoảng 20% trong 3 tuần, và đàm phán gói cam kết 12 tháng. Phương án chuyển nhà cung cấp chỉ dùng nếu hai cách trên không đủ."

### Ví dụ đàm phán
Với nhà cung cấp GPU: "Bên em cam kết dùng 12 tháng với mức tối thiểu, đổi lại giữ giá cũ hoặc tăng không quá 10%."

## G12-T07 · LLM gateway là điểm chịu tải duy nhất cho 5 sản phẩm
Lớp: T
Nguồn: gốc
Tags: gateway, spof, architecture

### Sếp hỏi
LLM gateway đang là điểm chịu tải duy nhất cho 5 sản phẩm. Sếp hỏi có cần tách ra không, tốn bao lâu. Tiêu chí khi nào bắt buộc tách, khi nào trì hoãn an toàn?

### Chốt kỹ thuật
- Bắt buộc khi: sự cố gateway đã từng làm sập nhiều sản phẩm; một sản phẩm làm nghẽn sản phẩm khác (noisy neighbor); các sản phẩm có SLA rất khác nhau; yêu cầu cô lập dữ liệu hoặc tuân thủ khác nhau; đội deploy gateway bị nghẽn vì nhiều team cùng cần thay đổi.
- Trì hoãn được khi: gateway stateless, chạy nhiều replica, có giới hạn và quota theo sản phẩm, uptime đạt yêu cầu, thay đổi ít.
- Bước trung gian rẻ: nhiều replica + quota theo sản phẩm + deployment riêng (cùng code) cho sản phẩm quan trọng nhất. Thường vài ngày đến 2 tuần.

### Ví dụ tư vấn
Với sếp: "Chưa cần tách hoàn toàn. Em đề xuất chạy riêng một bản cho sản phẩm quan trọng nhất và đặt hạn mức cho từng sản phẩm, khoảng 1–2 tuần, giải quyết phần lớn rủi ro."

### Ví dụ đàm phán
"Tách hoàn toàn tốn 1–2 tháng và tăng chi phí vận hành. Mình làm khi có dấu hiệu bắt buộc như danh sách trên."

## G12-T08 · Không được cache dữ liệu tài chính của một khách
Lớp: T
Nguồn: gốc
Tags: cache-policy, multi-tenant, compliance

### Sếp hỏi
Semantic cache tiết kiệm 35% chi phí, nhưng một khách enterprise yêu cầu không cache câu trả lời liên quan số liệu tài chính của họ. Kiến trúc đáp ứng mà không tắt cache toàn hệ thống, và chi phí cụ thể?

### Chốt kỹ thuật
- Chính sách cache theo tenant: cấu hình cho phép/không cho phép theo loại dữ liệu.
- Phân loại câu hỏi và câu trả lời (classifier hoặc rule) có chứa số liệu tài chính của tenant đó; nếu có thì bỏ qua đọc và ghi cache.
- Đơn giản và chắc chắn hơn: tắt cache hoàn toàn cho tenant đó (cô lập theo tenant), các tenant khác giữ nguyên.
- Đảm bảo không lưu ở nơi khác: log, trace (mask), backup.
- Chi phí: phần lưu lượng của khách đó × tỷ lệ hit đã mất × chi phí mỗi lượt; đưa vào báo giá của khách.

### Ví dụ tư vấn
"Với riêng công ty anh/chị, mọi câu trả lời liên quan số liệu tài chính luôn được tạo mới và không lưu lại, các phần khác của hệ thống vẫn chạy như cũ."

### Ví dụ đàm phán
"Yêu cầu này làm chi phí xử lý của anh/chị tăng khoảng X%, bên em đưa vào phụ lục hợp đồng."

## G12-T09 · Driver GPU/CUDA mới nhanh hơn 15%
Lớp: T
Nguồn: gốc
Tags: change-management, testing

### Sếp hỏi
Bản cập nhật driver GPU/CUDA mới tăng tốc inference 15% theo benchmark nhà sản xuất, đội vận hành chưa test kỹ. Quy trình đánh giá và triển khai an toàn, khi nào chấp nhận rủi ro áp dụng ngay?

### Chốt kỹ thuật
- Test trên staging với đúng model và workload thật: throughput, p95, VRAM, độ ổn định chạy dài (24–48 giờ), và kiểm tra output tất định so với bản cũ (eval).
- Kiểm tra tương thích: phiên bản vLLM/PyTorch, kernel, container base image.
- Canary một node, theo dõi lỗi CUDA, OOM, crash, sau đó rolling từng node; giữ image cũ để rollback nhanh.
- Áp dụng nhanh khi: bản vá bảo mật nghiêm trọng, hoặc tiết kiệm lớn và có rollback nhanh đã được kiểm chứng. Không áp dụng ngay trước mùa cao điểm.

### Ví dụ tư vấn
"Bên em thử bản mới trên một máy trước, chạy liên tục hai ngày với lưu lượng thật, ổn mới cập nhật dần."

### Ví dụ đàm phán
Với sếp: "15% là số của nhà sản xuất, mình cần số của mình. Một tuần thử nghiệm là đủ."

## G12-T10 · Hai sản phẩm chung cụm GPU, một sản phẩm tăng 10 lần
Lớp: T
Nguồn: gốc
Tags: isolation, fairness, quota

### Sếp hỏi
Hai sản phẩm dùng chung cụm GPU tự host, một sản phẩm tăng traffic 10 lần làm sản phẩm kia chậm nghiêm trọng. Đề xuất cơ chế cô lập tài nguyên và chính sách ưu tiên công bằng.

### Chốt kỹ thuật
- Ngắn hạn: quota và rate limit theo sản phẩm ở gateway; hàng đợi riêng và weighted fair queuing; giới hạn số request đồng thời mỗi sản phẩm.
- Ưu tiên theo SLA: sản phẩm có SLA chặt được đảm bảo phần công suất tối thiểu (reserved), phần dư dùng chung (burst).
- Cô lập cứng: chia GPU (node pool riêng, MIG trên A100/H100) cho sản phẩm quan trọng.
- Overflow sang API cho phần vượt quota.
- Đo: latency theo sản phẩm, tỷ lệ bị throttle.

### Ví dụ tư vấn
"Mỗi sản phẩm có phần máy chủ được đảm bảo, phần dư mới chia sẻ. Một sản phẩm đột ngột đông không làm sản phẩm kia chậm."

### Ví dụ đàm phán
Nội bộ: "Sản phẩm tăng 10 lần cần ngân sách thêm hoặc chấp nhận giới hạn. Mình không để nó lấy phần của sản phẩm khác."

## G12-T11 · Chọn engine serving cho model tự host
Lớp: T
Nguồn: bổ sung
Tags: vllm, tgi, serving

### Sếp hỏi
Bạn phải chọn engine serving cho model 14B tự host (vLLM, TGI, SGLang, TensorRT-LLM, Ollama). Tiêu chí và lựa chọn?

### Chốt kỹ thuật
- Tiêu chí: throughput với batching ở tải thật, TTFT và tốc độ sinh token, hỗ trợ model và quantize cần dùng, structured output, prefix caching, LoRA nhiều adapter, API tương thích OpenAI, độ ổn định và cộng đồng, công sức vận hành.
- vLLM: lựa chọn mặc định phổ biến, PagedAttention, continuous batching, hỗ trợ rộng.
- SGLang: mạnh với prefix caching (RadixAttention) và structured output, tốt cho agent nhiều lượt chung prefix.
- TensorRT-LLM: hiệu năng cao nhất trên NVIDIA nhưng build phức tạp.
- Ollama/llama.cpp: tiện cho dev và máy đơn, không cho tải production cao.
- Quyết định bằng benchmark trên workload thật (độ dài prompt, độ dài output, số đồng thời).

### Ví dụ tư vấn
"Bên em chọn phần mềm chạy model dựa trên thử nghiệm với lưu lượng giống của anh/chị, không theo xu hướng."

### Ví dụ đàm phán
"Lựa chọn phổ biến giúp anh/chị dễ tìm người vận hành sau này, bên em ưu tiên điều đó trừ khi số đo chênh lệch lớn."

## G12-T12 · Tính số GPU cần cho một lưu lượng
Lớp: T
Nguồn: bổ sung
Tags: capacity-planning, kv-cache

### Sếp hỏi
Ước lượng số GPU cần cho 50 request/giây cao điểm, prompt trung bình 2.000 token, output 300 token, model 8B. Bạn tính thế nào?

### Chốt kỹ thuật
- VRAM: weights 8B FP16 khoảng 16 GB (INT4 khoảng 5 GB); KV cache mỗi token phụ thuộc số layer, số head KV, head dim (với GQA khoảng 0,1–0,13 MB/token cho model 8B FP16); 2.300 token × số request đồng thời quyết định VRAM KV.
- Số request đồng thời ≈ request/giây × thời gian mỗi request (Little's law). Thời gian ≈ TTFT (prefill 2.000 token) + 300 token / tốc độ sinh mỗi stream.
- Throughput thực tế lấy từ benchmark engine trên GPU cụ thể (token/giây tổng ở batch size nhất định), không tính lý thuyết.
- Chia tổng token cần mỗi giây (prefill + decode) cho throughput một GPU, cộng 30–50% dư cho đỉnh và sự cố, và N+1 để chịu lỗi một node.
- Prefix caching giảm prefill nếu prompt có phần chung lớn.

### Ví dụ tư vấn
"Bên em tính dựa trên đo thực tế số câu một máy xử lý được mỗi giây với câu hỏi giống của anh/chị, rồi cộng dư phòng giờ cao điểm."

### Ví dụ đàm phán
"Bên em đưa ba mức cấu hình kèm số người dùng đồng thời tối đa của từng mức để anh/chị chọn theo ngân sách."
