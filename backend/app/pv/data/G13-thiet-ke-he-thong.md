---
group: G13
title: Thiết kế hệ thống (tình huống)
part: II
---

# Nhóm 13 — Thiết kế hệ thống

## G13-T01 · "AI thông minh biết hết mọi thứ về công ty tôi"
Lớp: T
Nguồn: gốc
Tags: discovery, requirements

### Sếp hỏi
Khách giao đề mơ hồ: "Làm cho tôi một AI thông minh biết hết mọi thứ về công ty tôi." Liệt kê giả định cần làm rõ (quy mô dữ liệu, người dùng, ngân sách, SLA, độ nhạy cảm, deadline) và câu hỏi cụ thể cho buổi họp đầu.

### Chốt kỹ thuật
- Mục tiêu: "Ai sẽ dùng, để làm việc gì, đo thành công bằng gì? Kể 3 câu hỏi cụ thể nhân viên hay hỏi nhất." Chọn 1–2 use case đầu.
- Dữ liệu: "Tài liệu nằm ở đâu (Drive, SharePoint, ERP, email)? Bao nhiêu, định dạng gì, cập nhật bao lâu một lần? Ai sở hữu?"
- Quyền: "Nhân viên nào được xem tài liệu nào? Hệ thống phân quyền hiện tại là gì?"
- Người dùng: "Bao nhiêu người, dùng lúc nào, qua kênh nào (web, Zalo, Teams)?"
- Độ nhạy cảm và tuân thủ: "Có dữ liệu cá nhân, tài chính, hợp đồng không? Có yêu cầu dữ liệu ở Việt Nam không?"
- Chất lượng và rủi ro: "Trả lời sai thì hậu quả gì? Có cần trích nguồn không? Có được tự thực hiện hành động không?"
- Ngân sách và deadline: "Ngân sách xây dựng và vận hành hàng tháng? Có mốc sự kiện nào cố định?"
- Kết buổi bằng đề xuất pilot 4–6 tuần với một phòng ban, một nguồn dữ liệu, tiêu chí nghiệm thu đo được.

### Ví dụ tư vấn
"Để AI hữu ích thật, mình bắt đầu từ một việc cụ thể, ví dụ trả lời câu hỏi chính sách nhân sự cho 200 nhân viên, làm tốt trong 6 tuần, rồi mở rộng."

### Ví dụ đàm phán
"Pilot có giá cố định và tiêu chí nghiệm thu rõ. Anh/chị chỉ mở rộng khi thấy kết quả."

## G13-T02 · Startup 15 triệu/tháng, 50.000 tin nhắn/ngày
Lớp: T
Nguồn: gốc
Tags: cost-design, minimal-architecture

### Sếp hỏi
Startup ngân sách 15 triệu/tháng muốn trợ lý xử lý 50.000 tin nhắn/ngày, "chất lượng tốt nhất có thể". Đề xuất kiến trúc tối giản, nêu hy sinh gì trong tam giác chất lượng-chi phí-độ trễ, và lộ trình nâng cấp theo mốc doanh thu.

### Chốt kỹ thuật
- Ngân sách mỗi tin: 15 triệu / 1,5 triệu tin mỗi tháng = khoảng 10 đồng/tin cho mọi chi phí. Rất chặt.
- Kiến trúc: model nhỏ, rẻ (flash/mini/lite) làm mặc định; cache mạnh cho câu hỏi lặp (FAQ); rule và template cho ý định phổ biến; prompt ngắn với prompt caching; giới hạn output; RAG trên Postgres + pgvector (không thêm service); một server nhỏ.
- Hy sinh: chất lượng ở câu phức tạp (trả lời ngắn, chuyển người khi khó), không có rerank, không kiểm chứng hai lần.
- Đo: chi phí mỗi tin theo ngày, phần trăm câu chuyển người.
- Lộ trình: doanh thu tăng thì thêm rerank, router lên model mạnh cho câu khó, eval tự động, rồi kênh và tính năng.

### Ví dụ tư vấn
"Với ngân sách này, mỗi tin nhắn chỉ được khoảng 10 đồng. Bên em dùng AI nhỏ cho câu phổ biến, trả lời sẵn cho câu lặp lại, câu khó chuyển người. Doanh thu tăng thì mình nâng cấp từng phần."

### Ví dụ đàm phán
"'Tốt nhất có thể' trong ngân sách này nghĩa là tốt ở 80% câu hỏi phổ biến. Bên em ghi rõ trong phạm vi để không có kỳ vọng sai."

## G13-T03 · Ngân hàng: tự host, 99,95%, p95 dưới 2 giây, 1 triệu user
Lớp: T
Nguồn: gốc
Tags: banking, self-hosting, sla, compliance

### Sếp hỏi
Ngân hàng yêu cầu AI trả lời khách hàng, tuyệt đối không dùng API nước ngoài, tự host, SLA 99,95%, p95 dưới 2 giây, 1 triệu user. Kiến trúc tổng thể, 5 quyết định quan trọng nhất, và khi nào buộc chọn phương án đắt hơn vì compliance.

### Chốt kỹ thuật
- Quyết định 1: hạ tầng tại data center của ngân hàng hoặc nhà cung cấp trong nước đạt chuẩn, tối thiểu 2 vùng/2 data center (99,95% là khoảng 22 phút ngừng mỗi tháng, không đạt với một cụm).
- Quyết định 2: p95 dưới 2 giây cho toàn bộ là khó với LLM sinh dài; định nghĩa SLA theo TTFT (chữ đầu tiên dưới 1–2 giây) với streaming, câu trả lời ngắn, model kích thước vừa (7B–14B quantize FP8) trên GPU đủ mạnh.
- Quyết định 3: phân luồng: ý định phổ biến bằng rule/template + dữ liệu core banking qua API (tất định, nhanh), LLM cho phần diễn đạt và câu mở; hành động giao dịch không do LLM thực hiện trực tiếp.
- Quyết định 4: bảo mật: xác thực khách, phân quyền, mask dữ liệu nhạy cảm trong log, audit đầy đủ, guardrail đầu vào và đầu ra, red-team trước launch.
- Quyết định 5: vận hành: capacity N+1 mỗi vùng, autoscale với warm pool, chế độ suy giảm (degraded mode) về FAQ tĩnh khi LLM lỗi, eval và giám sát liên tục.
- Phương án đắt bắt buộc: GPU dư cho dự phòng nhiều vùng, không dùng API ngoài làm overflow (phải tự host toàn bộ dư thừa), lưu trữ và mã hóa theo quy định, kiểm toán bên thứ ba.

### Ví dụ tư vấn
"Toàn bộ chạy trong hạ tầng của ngân hàng tại Việt Nam, hai trung tâm dữ liệu dự phòng cho nhau. Thông tin tài khoản lấy trực tiếp từ hệ thống lõi, AI chỉ diễn đạt. Khi AI gặp sự cố, hệ thống vẫn trả lời các câu phổ biến."

### Ví dụ đàm phán
"Cam kết 2 giây bên em đề xuất tính theo thời điểm chữ đầu tiên hiện ra. Cam kết toàn bộ câu trả lời dưới 2 giây sẽ buộc dùng model nhỏ, chất lượng thấp hơn."

## G13-T04 · AI tự quyết hoàn tiền dưới 500 nghìn
Lớp: T
Nguồn: gốc
Tags: automation, fraud, guardrails

### Sếp hỏi
Hệ thống chạy 6 tháng, khách muốn "AI tự động quyết định hoàn tiền dưới 500 nghìn mà không cần người duyệt". Giả định rủi ro cần làm rõ và thiết kế guardrail kèm ngưỡng dừng tự động.

### Chốt kỹ thuật
- Giả định: tổng giá trị hoàn tiền mỗi ngày dự kiến; tỷ lệ gian lận lịch sử; dữ liệu 6 tháng: AI đề xuất đúng với quyết định của người bao nhiêu %; chính sách hoàn tiền có rõ ràng thành rule không.
- Guardrail: quyết định dựa trên rule chính sách kiểm tra bằng code (đơn có tồn tại, trong hạn, chưa hoàn), LLM chỉ đọc lý do và phân loại.
- Hạn mức: mỗi khách mỗi tháng (số lần và tổng tiền), mỗi ngày toàn hệ thống.
- Phát hiện bất thường: tài khoản mới, nhiều yêu cầu từ một thiết bị/IP, lý do lặp lại giống nhau, tăng đột biến; chuyển người.
- Ngưỡng dừng tự động: tổng hoàn tiền ngày vượt X lần trung bình, tỷ lệ hoàn tiền vượt ngưỡng, hoặc hậu kiểm mẫu phát hiện sai trên Y% thì tự tắt tự động hóa và chuyển người duyệt.
- Hậu kiểm ngẫu nhiên 5% và báo cáo tuần.

### Ví dụ tư vấn
"AI chỉ tự hoàn tiền khi đơn thỏa đủ điều kiện chính sách, trong hạn mức mỗi khách, và không có dấu hiệu bất thường. Tổng tiền hoàn trong ngày vượt ngưỡng thì hệ thống tự dừng chờ người."

### Ví dụ đàm phán
"Bên em đề xuất bắt đầu ngưỡng 200 nghìn trong 1 tháng, dựa trên số liệu thực tế nâng lên 500 nghìn."

## G13-T05 · Thiết kế trước chế độ suy giảm khi LLM sập 2 giờ
Lớp: T
Nguồn: gốc
Tags: graceful-degradation, resilience

### Sếp hỏi
Nhà cung cấp LLM sập 2 tiếng giữa giờ cao điểm. Thiết kế trước chế độ suy giảm theo tầng: tính năng nào tắt trước, tính năng nào giữ đến cùng, người dùng thấy thông báo gì ở mỗi tầng.

### Chốt kỹ thuật
- Tầng 0 (bình thường).
- Tầng 1 (nhà cung cấp chính chậm/lỗi một phần): chuyển model dự phòng; tắt tính năng đắt và không thiết yếu (tóm tắt dài, báo cáo, soạn thảo); người dùng không cần biết hoặc thấy "trả lời có thể ngắn hơn".
- Tầng 2 (mọi LLM lỗi): tìm kiếm thuần trả về tài liệu liên quan nhất (không sinh câu trả lời), FAQ và template cho ý định phổ biến, nút chuyển người; thông báo "Trợ lý AI đang bảo trì, đây là các tài liệu liên quan".
- Tầng 3 (hệ thống lõi lỗi): trang tĩnh, kênh liên hệ.
- Giữ đến cùng: tra cứu thông tin quan trọng, kênh liên hệ người.
- Chuyển tầng tự động theo health check, có kill switch thủ công, diễn tập định kỳ.

### Ví dụ tư vấn
"Khi AI gặp sự cố, khách vẫn tìm được tài liệu và câu trả lời có sẵn cho câu hỏi phổ biến, và luôn có nút gặp nhân viên."

### Ví dụ đàm phán
"Chế độ suy giảm là phần nằm trong cam kết độ sẵn sàng, bên em diễn tập mỗi quý."

## G13-T06 · RAG multi-tenant 300 nghìn merchant chậm dần
Lớp: T
Nguồn: gốc
Tags: multi-tenant, vector-db, architecture-options

### Sếp hỏi
Thiết kế lại hệ thống RAG multi-tenant cho 300 nghìn merchant, hệ thống cũ dùng một index chung lọc metadata đang chậm dần. 2–3 phương án, đánh đổi, tiêu chí chọn.

### Chốt kỹ thuật
- Phương án A: một index, partition theo tenant (Postgres partition by hash tenant, hoặc engine có tenant-aware index như Qdrant multitenancy với payload index). Vận hành đơn giản; hiệu năng tốt nếu engine hỗ trợ lọc theo tenant hiệu quả.
- Phương án B: phân tầng theo kích thước: tenant lớn (top 1%) có collection/index riêng; tenant nhỏ gộp chung và quét tuần tự trong partition (dữ liệu nhỏ quét nhanh). Hiệu năng ổn định nhất, cần lớp định tuyến.
- Phương án C: index riêng mỗi tenant (300 nghìn index): cô lập tốt nhưng overhead metadata và vận hành rất lớn, chỉ hợp với serverless index trả theo dùng.
- Tiêu chí: phân phối kích thước tenant (thường lệch mạnh), p95 latency mục tiêu, chi phí, yêu cầu cô lập dữ liệu, tần suất cập nhật, công sức migrate. Benchmark trên mẫu tenant lớn, vừa, nhỏ.

### Ví dụ tư vấn
"Merchant lớn có kho riêng, merchant nhỏ dùng chung kho nhưng chia ngăn. Tìm kiếm của ai cũng nhanh mà chi phí không bùng nổ."

### Ví dụ đàm phán
"Bên em chọn phương án theo đo đạc trên dữ liệu thật của anh/chị, không theo công nghệ mới nhất."

## G13-T07 · Chi phí API gấp đôi dự kiến sau 3 tháng
Lớp: T
Nguồn: gốc
Tags: cost-investigation

### Sếp hỏi
Sau 3 tháng launch, chi phí API thực tế gấp đôi dự kiến dù traffic đúng kế hoạch. Ít nhất 5 nguyên nhân và bước điều tra bằng dữ liệu cho mỗi nguyên nhân.

### Chốt kỹ thuật
- Prompt phình do thêm tính năng: so token vào trung bình mỗi lời gọi theo tuần.
- Số lời gọi mỗi yêu cầu cao hơn ước tính (agent nhiều bước, phân loại, viết lại, tự kiểm): đếm lời gọi theo yêu cầu, phân rã theo bước.
- Cache hit thấp hơn ước tính hoặc prompt cache bị vô hiệu (phần đầu prompt thay đổi mỗi request, ví dụ chèn thời gian): đo hit rate, kiểm tra phần prefix.
- Retry dư thừa và hedging: đếm lời gọi bị hủy hoặc trùng; trong hedging, nhiều model cùng tính tiền.
- Model bị đổi hoặc fallback sang model đắt: phân phối chi phí theo model id.
- Context không được dọn (lịch sử hội thoại dài): token theo số lượt.
- Output dài hơn ước tính: token ra trung bình.
- Ước tính ban đầu sai (dựa trên câu mẫu ngắn): so phân phối độ dài câu thật với câu mẫu.

### Ví dụ tư vấn
"Bên em đã phân tích chi phí theo từng thành phần và tìm ra hai nguyên nhân chính, kèm kế hoạch giảm 40% trong 3 tuần."

### Ví dụ đàm phán
"Phần chênh lệch do ước tính sai của bên em, bên em chia sẻ chi phí trong thời gian tối ưu."

## G13-T08 · Interviewer đổi yêu cầu giữa buổi thiết kế
Lớp: T
Nguồn: gốc
Tags: interview-skills, adaptability

### Sếp hỏi
Trong buổi phỏng vấn thiết kế hệ thống 45 phút, interviewer đưa đề mơ hồ và liên tục thêm ràng buộc sau khi bạn đã vẽ xong. Vẽ lại từ đầu hay điều chỉnh phần nào, và nói gì để thể hiện tư duy linh hoạt?

### Chốt kỹ thuật
- Không vẽ lại: xác định ràng buộc mới ảnh hưởng thành phần nào, giữ phần không bị ảnh hưởng.
- Nói to quy trình: "Ràng buộc này ảnh hưởng tới lưu trữ và độ trễ, phần ingest giữ nguyên. Em có hai lựa chọn, A và B, đánh đổi là… Với ràng buộc anh vừa nêu em chọn B."
- Ghi giả định ra bảng từ đầu để khi đổi chỉ cần đánh dấu giả định nào thay đổi.
- Hỏi ưu tiên khi ràng buộc mâu thuẫn ("chi phí hay độ trễ quan trọng hơn?").
- Quản lý thời gian: chừa 5 phút cuối tóm tắt kiến trúc cuối, rủi ro, việc làm tiếp.

### Ví dụ tư vấn
Câu nói mẫu: "Cảm ơn anh, ràng buộc này thay đổi phần lưu trữ. Em giữ nguyên luồng xử lý, đổi phần lưu trữ sang phương án phân vùng theo khách, và chấp nhận đánh đổi là chi phí vận hành cao hơn."

### Ví dụ đàm phán
Nếu ràng buộc không thực tế: "Với ba ràng buộc này cùng lúc em không đạt được cả ba. Nếu phải chọn, em giữ X và Y, nới Z, vì…"

## G13-T09 · Build hay buy hệ thống đánh giá chất lượng
Lớp: T
Nguồn: gốc
Tags: build-vs-buy, eval-platform

### Sếp hỏi
Khách cần quyết định build vs buy cho hệ thống đánh giá chất lượng câu trả lời tự động. Khung quyết định, một kịch bản nên buy dù có thể build, và một kịch bản nên build dù có giải pháp buy sẵn.

### Chốt kỹ thuật
- Khung: đây có phải lợi thế cạnh tranh không; tổng chi phí sở hữu 2–3 năm (build gồm cả duy trì); time to value; yêu cầu dữ liệu (có được gửi dữ liệu ra ngoài không); mức tùy biến cần; rủi ro khóa vào nhà cung cấp; năng lực đội.
- Nên buy: đội nhỏ, cần ngay, nhu cầu chuẩn (tracing, dataset, LLM-judge, dashboard) như Langfuse, Braintrust, LangSmith; dữ liệu được phép đưa lên (hoặc bản self-host).
- Nên build: tiêu chí chấm rất đặc thù domain (pháp lý cần đối chiếu hiệu lực văn bản, đúng Điều Khoản), dữ liệu không được rời hạ tầng và công cụ không có bản self-host, hoặc eval gắn chặt với hệ thống nội bộ (eval trạng thái DB).
- Thường lai: buy nền tảng (tracing, lưu dataset, UI), build phần chấm đặc thù như plugin.

### Ví dụ tư vấn
"Phần khung theo dõi và lưu trữ có sẵn trên thị trường thì dùng luôn. Phần chấm điểm đặc thù nghiệp vụ của anh/chị thì bên em viết riêng và gắn vào."

### Ví dụ đàm phán
"Bên em không tính công xây lại thứ đã có sẵn tốt. Báo giá chỉ gồm phần đặc thù."

## G13-T10 · ADR chọn pgvector giờ chạm giới hạn
Lớp: T
Nguồn: gốc
Tags: adr, migration, communication

### Sếp hỏi
ADR 4 tháng trước chọn pgvector thay vì Qdrant, giờ chạm giới hạn hiệu năng. Sếp hỏi "lúc đó sao không chọn Qdrant luôn?". Trả lời bảo vệ quyết định cũ mà không chống chế, và lộ trình migrate.

### Chốt kỹ thuật
- Dựa vào ADR: bối cảnh lúc đó (quy mô dữ liệu, team, deadline, cần JOIN và transaction với dữ liệu nghiệp vụ, ít service), các phương án đã cân nhắc, điều kiện xem xét lại đã ghi.
- Thừa nhận dữ kiện mới: tăng trưởng nhanh hơn dự kiến, ngưỡng xem xét lại đã chạm.
- Kiểm tra trước khi migrate: đã tối ưu pgvector chưa (HNSW, tham số m/ef, halfvec, partition, iterative scan, máy lớn hơn, read replica).
- Lộ trình: benchmark Qdrant trên dữ liệu thật; dual-write; backfill; shadow read so kết quả; chuyển đọc theo phần trăm; giữ pgvector làm fallback; giữ dữ liệu nghiệp vụ ở Postgres.

### Ví dụ tư vấn
Với sếp: "Lúc đó dữ liệu 500 nghìn vector, pgvector đủ và giúp mình ra mắt sớm hơn 3 tuần với ít hạ tầng hơn. ADR có ghi khi vượt 10 triệu vector thì xem lại, giờ mình đã tới mốc đó. Em đề xuất tối ưu trong 1 tuần, nếu không đủ thì migrate trong 4 tuần theo lộ trình này."

### Ví dụ đàm phán
"Chi phí migrate bây giờ thấp hơn chi phí phải duy trì thêm một hệ thống trong 4 tháng đầu khi chưa cần."

## G13-T11 · Khách đòi SLA p95 dưới 1 giây cho mọi tính năng
Lớp: T
Nguồn: gốc
Tags: sla, negotiation, contract-risk

### Sếp hỏi
Khách đồng ý ký nhưng yêu cầu SLA p95 dưới 1 giây cho toàn bộ tính năng, kể cả RAG + rerank + gọi tool real-time. Có nên ký? Đàm phán SLA theo từng loại tính năng thế nào, rủi ro pháp lý và tài chính nếu ký mà không làm rõ?

### Chốt kỹ thuật
- Không nên ký con số chung. Đo phân rã: retrieval 50–150 ms, rerank 50–200 ms, tool bên khách tùy hệ thống, LLM TTFT 300–1.500 ms và thời gian sinh theo độ dài.
- Đề xuất SLA theo loại: tra cứu đơn giản/FAQ p95 dưới 1 giây; hỏi đáp RAG: TTFT p95 dưới 1,5 giây, hoàn tất dưới 6 giây; luồng có tool bên ngoài: loại trừ thời gian hệ thống của khách hoặc cam kết riêng.
- Định nghĩa rõ: đo ở đâu (server hay client), loại trừ gì (sự cố nhà cung cấp, hệ thống khách, bất khả kháng), cửa sổ đo, chế tài và giới hạn bồi thường.
- Rủi ro nếu ký mơ hồ: vi phạm liên tục, phạt hợp đồng, quyền chấm dứt hợp đồng của khách.

### Ví dụ tư vấn
"Câu trả lời có tra cứu tài liệu và hỏi hệ thống kho không thể dưới 1 giây mà vẫn chính xác. Bên em đề xuất cam kết riêng cho từng loại: câu hỏi thường gặp dưới 1 giây, câu cần tra cứu thì chữ đầu tiên hiện dưới 1,5 giây."

### Ví dụ đàm phán
"Bên em sẵn sàng ký phạt nếu vi phạm cam kết theo từng loại. Con số chung dưới 1 giây cho tất cả thì bên em không ký được, vì sẽ phải bỏ tra cứu và kiểm tra, chất lượng giảm."

## G13-T12 · 20% tính năng tạo 80% giá trị nhưng tốn 60% chi phí
Lớp: T
Nguồn: gốc
Tags: product-strategy, cost

### Sếp hỏi
Dữ liệu cho thấy 80% giá trị đến từ 20% tính năng, nhưng 20% đó tốn 60% chi phí vận hành. Sếp hỏi có nên cắt phần còn lại không. Khung phân tích và câu hỏi cần làm rõ.

### Chốt kỹ thuật
- Lưu ý: 80% tính năng còn lại chỉ tốn 40% chi phí; cắt chúng tiết kiệm tối đa 40%, và có thể mất giá trị ẩn.
- Câu hỏi: "giá trị" đo thế nào (doanh thu trực tiếp, giữ chân, chuyển đổi)? Tính năng nào là cửa vào (ít dùng nhưng người dùng nó là khách lớn)? Tính năng nào có hợp đồng cam kết? Chi phí là biến đổi hay cố định (cắt có thật sự tiết kiệm không)?
- Phân tích theo từng tính năng: giá trị, chi phí biên, số khách phụ thuộc, chi phí duy trì kỹ thuật.
- Phương án ngoài cắt: tối ưu chi phí 20% tính năng chính (vì chúng tốn 60%), đưa tính năng ít dùng vào gói trả phí, tắt dần có thông báo.

### Ví dụ tư vấn
Với sếp: "Đòn bẩy lớn nhất là tối ưu 20% tính năng đang tốn 60% chi phí. Phần còn lại em đề xuất xem từng tính năng, cắt những cái không có khách lớn phụ thuộc."

### Ví dụ đàm phán
"Trước khi cắt, mình kiểm tra hợp đồng xem có tính năng nào đã cam kết với khách, để không vi phạm."

## G13-T13 · Thiết kế trợ lý hỏi đáp pháp luật có trích dẫn
Lớp: T
Nguồn: bổ sung
Tags: legal-rag, design, citations

### Sếp hỏi
Thiết kế từ đầu một trợ lý hỏi đáp pháp luật lao động Việt Nam: yêu cầu trích dẫn tới Điều, Khoản, Điểm, xử lý luật hết hiệu lực, chống bịa. Trình bày kiến trúc và các quyết định chính.

### Chốt kỹ thuật
- Ingest: parser theo cấu trúc pháp lý (Chương, Mục, Điều, Khoản, Điểm) bằng regex + máy trạng thái, kiểm tra bất biến; node_id tất định (văn bản-điều-khoản-điểm).
- Lưu trữ: Postgres với bảng văn bản, node (cây cha-con, effective_from/to, embedding), quan hệ thay thế giữa node và giữa văn bản; pgvector cho vector.
- Truy hồi: embedding tiếng Việt tự host, lọc hiệu lực ở SQL, tìm kép cho câu nối tiếp; hướng nâng cấp: hybrid với full-text và rerank.
- Sinh: model trả JSON với citation id; code loại id không nằm trong tập truy hồi; không có căn cứ thì từ chối hoặc gợi ý câu hỏi chuẩn thuật ngữ.
- Phân loại câu hỏi song song: luật, mơ hồ, ngoài kho, lạc đề, chèn lệnh; regex chặn chèn lệnh trước LLM.
- Trình bày: SSE theo bước, thẻ trích dẫn hiện nguyên văn, ngày hiệu lực.
- Vận hành: router nhiều nhà cung cấp, rate limit demo, log câu ngoài kho để mở rộng kho.
- Đây chính là kiến trúc dự án của tôi; điểm còn thiếu tôi tự nêu: eval tự động, hybrid search thật, kiểm tra hỗ trợ từng ý.

### Ví dụ tư vấn
"Mỗi câu trả lời dẫn tới đúng Điều, Khoản, Điểm, bấm vào xem nguyên văn, chỉ dùng điều luật còn hiệu lực, và hệ thống nói 'chưa đủ căn cứ' thay vì đoán."

### Ví dụ đàm phán
"Phạm vi văn bản là yếu tố chính quyết định chi phí. Bên em bắt đầu với bộ văn bản cốt lõi và mở rộng theo câu hỏi thực tế người dùng hỏi nhiều nhất."
