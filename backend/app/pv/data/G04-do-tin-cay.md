---
group: G04
title: Độ tin cậy
part: I
---

# Nhóm 4 — Độ tin cậy

## G04-A01 · Ngưỡng "không biết thì nói không biết"
Lớp: A
Nguồn: gốc
Tags: abstention, confidence, calibration

### Sếp hỏi
"Không biết thì nói không biết": ngưỡng dựa trên cái gì, điểm similarity retrieval, số nguồn đồng thuận, hay confidence của chính model? Rủi ro của từng cách?

### Chốt kỹ thuật
- Similarity retrieval: rẻ, tất định. Rủi ro: điểm cosine không hiệu chỉnh giữa các câu (câu ngắn và câu dài có phân phối khác), đoạn giống về từ nhưng không trả lời được câu hỏi vẫn điểm cao.
- Số nguồn đồng thuận: tốt cho câu hỏi sự kiện. Rủi ro: nhiều bản sao của cùng một nguồn sai, hoặc câu hỏi chỉ có một nguồn hợp lệ duy nhất (luật thường vậy).
- Confidence tự báo của model: dễ lấy. Rủi ro: thường không hiệu chỉnh, model tự tin cả khi sai.
- Cách tốt hơn: kết hợp nhiều tín hiệu (điểm rerank, model có trích dẫn được nguồn hợp lệ không, kiểm tra hỗ trợ bằng NLI) và hiệu chỉnh ngưỡng trên bộ eval có câu không trả lời được: chọn ngưỡng theo đánh đổi precision của câu đã trả lời và tỷ lệ từ chối.
- Dự án luật lao động: điều kiện trả lời là model phải đưa ra trích dẫn nằm trong tập truy hồi; không có thì từ chối hoặc đề xuất viết lại câu hỏi.

### Ví dụ tư vấn
"Hệ thống chỉ trả lời khi tìm được văn bản làm căn cứ và chỉ ra được căn cứ đó. Không có căn cứ thì nói rõ là chưa đủ thông tin."

### Ví dụ đàm phán
"Bên em có thể chỉnh để hệ thống trả lời nhiều hơn hoặc thận trọng hơn. Mỗi mức có số đo tỷ lệ đúng tương ứng để anh/chị chọn."

## G04-A02 · Ba tầng validation
Lớp: A
Nguồn: gốc
Tags: validation, sla

### Sếp hỏi
Ba tầng validation (schema, business rule, sanity-check bằng số liệu thực tế): tầng nào chạy trước, tầng nào tốn thời gian nhất, tầng nào bạn sẵn sàng bỏ qua khi SLA căng?

### Chốt kỹ thuật
- Thứ tự từ rẻ tới đắt: schema (micro giây) → business rule (mili giây, có thể cần đọc DB) → sanity check với dữ liệu thực tế (gọi hệ thống khác, so lịch sử, có thể gọi model).
- Tốn nhất: sanity check, vì cần dữ liệu ngoài.
- Không bao giờ bỏ schema và business rule cho hành động ghi. Sanity check có thể chuyển sang hậu kiểm bất đồng bộ cho hành động đảo ngược được, giá trị thấp; giữ đồng bộ cho hành động giá trị cao.
- Ghi lại mỗi lần bỏ qua tầng nào để audit.

### Ví dụ tư vấn
"Kiểm tra mẫu đơn trước, rồi kiểm tra đúng quy định, cuối cùng mới đối chiếu với số liệu thực tế. Khi đông khách, bước cuối có thể làm sau cho đơn nhỏ, nhưng không bao giờ bỏ hai bước đầu."

### Ví dụ đàm phán
"Bên em cam kết thời gian phản hồi dựa trên việc giữ hai tầng đầu. Muốn nhanh hơn nữa thì chỉ nới tầng thứ ba cho giao dịch nhỏ."

## G04-A03 · Circuit breaker mở giữa luồng nhiều bước
Lớp: A
Nguồn: gốc
Tags: circuit-breaker, saga, consistency

### Sếp hỏi
Circuit breaker mở sau 5 lỗi liên tiếp của một tool nội bộ. Trong lúc mở, agent xử lý thế nào với các luồng đang dở (đã trừ kho nhưng chưa tạo hóa đơn)?

### Chốt kỹ thuật
- Luồng nhiều bước phải được thiết kế như saga: mỗi bước có hành động bù (hoàn kho, hủy giữ chỗ).
- Khi breaker mở: luồng dở chuyển trạng thái "chờ" (lưu bền), đưa vào hàng đợi retry với backoff; nếu quá hạn (ví dụ giữ hàng 30 phút) thì chạy hành động bù.
- Không để agent "tự sáng tạo" cách xử lý: trạng thái và hành động bù do code quyết định.
- Thông báo người dùng trạng thái thật ("đơn đang chờ xác nhận"), không nói đã xong.
- Half-open: thử một vài request trước khi mở lại hoàn toàn; ưu tiên chạy tiếp luồng dở trước luồng mới.

### Ví dụ tư vấn
"Nếu phần mềm hóa đơn tạm ngừng, đơn đang làm dở được giữ ở trạng thái chờ và tự làm tiếp khi phần mềm chạy lại. Quá thời gian thì hệ thống tự trả hàng về kho."

### Ví dụ đàm phán
"Thiết kế hoàn tác cho từng bước là phần đắt nhất của tích hợp nhiều hệ thống, nhưng là thứ ngăn kho và sổ sách lệch nhau."

## G04-A04 · Tool đã idempotent, retry vẫn sai ở đâu
Lớp: A
Nguồn: gốc
Tags: idempotency, stale-state, ordering

### Sếp hỏi
Tool "chuyển tiền" đã idempotent. Vậy việc agent retry vẫn có thể sai ở đâu ngoài tool?

### Chốt kỹ thuật
- Key sinh sai: agent retry nhưng tạo key mới (ví dụ key sinh mỗi lần gọi model) thì idempotency vô nghĩa. Key phải sinh từ ý định nghiệp vụ (mã đơn + bước), không từ lần gọi.
- State cũ: agent quyết định dựa trên số dư đọc 5 phút trước; retry sau khi số dư đổi vẫn dùng dữ liệu cũ.
- Thứ tự: retry bước chuyển tiền nhưng bước trước (khóa đơn, kiểm hạn mức) không chạy lại.
- Model đổi tham số giữa hai lần thử (số tiền khác) → cùng key khác payload.
- Bước sau (gửi thông báo) không idempotent nên khách nhận 2 tin.
- Xử lý: idempotency ở mức luồng nghiệp vụ, kiểm tra lại điều kiện ngay trước khi ghi, khóa tham số sau khi đã duyệt.

### Ví dụ tư vấn
"Chống chuyển tiền hai lần chưa đủ. Hệ thống còn kiểm tra lại số dư và điều kiện ngay trước khi chuyển, và không cho đổi số tiền sau khi đã duyệt."

### Ví dụ đàm phán
"Bên em kiểm thử riêng các kịch bản lặp lại và mất kết nối cho luồng tiền. Đây là phần không thể cắt."

## G04-A05 · 429 có Retry-After
Lớp: A
Nguồn: gốc
Tags: rate-limit, backoff

### Sếp hỏi
Với lỗi 429 có header Retry-After rõ ràng, bạn vẫn áp dụng backoff theo công thức riêng hay tôn trọng tuyệt đối header đó? Vì sao?

### Chốt kỹ thuật
- Tôn trọng Retry-After làm cận dưới: không thử lại sớm hơn (thử sớm hơn chỉ tốn quota và có thể bị phạt).
- Thêm jitter để nhiều worker không cùng ùa lại một thời điểm.
- Nếu Retry-After vượt ngân sách thời gian của request (SLA), không chờ: chuyển nhà cung cấp hoặc model dự phòng, hoặc trả lỗi có kiểm soát.
- Không có header thì exponential backoff + full jitter, có trần.
- Phía hệ thống: token bucket chủ động theo quota để giảm 429 ngay từ đầu.
- Dự án luật lao động: Dahl trả 429 rất nhanh khi model hết chỗ nên router thử lại dày hơn và đua nhiều model song song, Gemini vào đua sau 15 giây.

### Ví dụ tư vấn
"Nhà cung cấp báo 'quay lại sau 20 giây' thì hệ thống chờ đúng như vậy. Nếu chờ lâu quá mức cho phép, nó chuyển sang nhà cung cấp khác."

### Ví dụ đàm phán
"Có nhà cung cấp dự phòng làm tăng chút chi phí cố định, nhưng giữ được thời gian phản hồi khi nhà cung cấp chính quá tải."

## G04-A06 · Budget thời gian và tiền mâu thuẫn
Lớp: A
Nguồn: gốc
Tags: budget, cost-control

### Sếp hỏi
Thiết kế budget cho agent giới hạn cả wall-clock và chi phí USD. Khi hai giới hạn mâu thuẫn, agent ưu tiên dừng theo cái nào?

### Chốt kỹ thuật
- Dừng khi chạm bất kỳ giới hạn nào (giới hạn nào tới trước). Cả hai là trần cứng.
- Mâu thuẫn thật nằm ở chiến lược: muốn nhanh thì song song hóa và hedging (tốn tiền), muốn rẻ thì tuần tự (chậm). Chọn theo loại tác vụ: tương tác thời gian thực ưu tiên thời gian, tác vụ nền ưu tiên tiền.
- Theo dõi ngân sách còn lại để điều chỉnh: còn ít tiền thì chuyển model nhỏ; còn ít thời gian thì bỏ bước phụ (rerank, tự kiểm).
- Khi dừng: trả kết quả tốt nhất hiện có kèm trạng thái chưa hoàn thành.

### Ví dụ tư vấn
"Mỗi việc có hai giới hạn: thời gian và tiền. Chạm cái nào trước thì dừng và báo lại. Việc khách đang chờ thì ưu tiên nhanh, việc chạy nền thì ưu tiên tiết kiệm."

### Ví dụ đàm phán
"Anh/chị chọn mức ưu tiên cho từng loại việc, bên em cấu hình theo đó và báo cáo chi phí thực tế hàng tuần."

## G04-A07 · Trích đúng điều khoản đã hết hiệu lực
Lớp: A
Nguồn: gốc
Tags: grounding, retrieval, data-quality, legal

### Sếp hỏi
Agent trích đúng "Điều 5 Thông tư X" nhưng Thông tư X đã hết hiệu lực 3 tháng (tài liệu RAG chưa cập nhật). Đây là lỗi grounding, retrieval hay dữ liệu nguồn? Sửa khác nhau thế nào?

### Chốt kỹ thuật
- Grounding đúng: model trung thành với nguồn được đưa.
- Retrieval đúng về mặt tìm kiếm, nhưng thiếu lọc hiệu lực nếu metadata có sẵn mà không dùng.
- Gốc rễ là lỗi dữ liệu nguồn và quy trình cập nhật: kho không biết văn bản đã hết hiệu lực.
- Sửa dữ liệu: quy trình theo dõi văn bản mới thay thế/bãi bỏ, cập nhật effective_to, liên kết văn bản thay thế.
- Sửa retrieval: lọc hiệu lực bắt buộc ở truy vấn.
- Sửa trình bày: hiển thị ngày hiệu lực và ngày cập nhật kho cạnh trích dẫn, cảnh báo nếu văn bản sắp hoặc đã có văn bản sửa đổi.
- Dự án luật lao động: node có effective_to, tìm kiếm mặc định lọc effective_to IS NULL; điểm yếu là phải tự nạp văn bản mới.

### Ví dụ tư vấn
"Câu trả lời đọc đúng văn bản, nhưng văn bản đó đã hết hiệu lực mà kho chưa cập nhật. Bên em sửa quy trình cập nhật và hiện ngày hiệu lực cạnh mỗi trích dẫn."

### Ví dụ đàm phán
"Theo dõi văn bản mới là việc vận hành liên tục. Bên em đưa vào gói duy trì hàng tháng với cam kết thời gian cập nhật."

## G04-A08 · Self-consistency check cho lớp câu hỏi nào
Lớp: A
Nguồn: gốc
Tags: self-consistency, cost, risk-based

### Sếp hỏi
Self-consistency check (render lại bằng model rẻ hơn) tốn gấp đôi chi phí. Áp dụng cho toàn bộ traffic hay chỉ một lớp câu hỏi? Lớp nào?

### Chốt kỹ thuật
- Chỉ áp dụng cho lớp rủi ro cao: câu trả lời có con số (tiền, thời hạn, tỷ lệ), dẫn tới hành động, lĩnh vực pháp lý/y tế/tài chính, khách VIP, hoặc khi các tín hiệu tin cậy khác ở mức trung bình.
- Lớp câu hỏi thông tin chung, có thể kiểm tra dễ thì bỏ qua.
- Kiểm tra có mục tiêu thay vì sinh lại toàn bộ: chỉ trích các con số và đối chiếu nguồn, rẻ hơn nhiều.
- Đo giá trị: tỷ lệ lỗi bắt được trên lớp đó; nếu dưới mức chi phí cho phép thì tắt.

### Ví dụ tư vấn
"Câu trả lời có con số tiền hay thời hạn thì hệ thống kiểm tra lại lần hai. Câu hỏi chung chung thì không cần."

### Ví dụ đàm phán
"Áp kiểm tra kép cho khoảng 15–25% câu quan trọng nhất, chi phí tăng ít mà vẫn bắt được phần lớn lỗi nguy hiểm."

## G04-A09 · Năm tín hiệu tự escalate ngoài độ tin cậy thấp
Lớp: A
Nguồn: gốc
Tags: escalation, signals

### Sếp hỏi
Ngoài "độ tin cậy thấp", liệt kê ít nhất 5 tín hiệu để hệ thống tự phát hiện cần chuyển người.

### Chốt kỹ thuật
- Cảm xúc tiêu cực tăng dần hoặc từ ngữ bức xúc, đe dọa khiếu nại, nhắc tới luật sư hay báo chí.
- Người dùng hỏi lại cùng một ý 2–3 lần (câu trả lời không giải quyết được).
- Người dùng yêu cầu gặp người thật.
- Chủ đề nhạy cảm: sức khỏe, an toàn, pháp lý cá nhân nghiêm trọng, tranh chấp tiền.
- Giá trị giao dịch vượt ngưỡng hoặc khách VIP.
- Agent chạm giới hạn bước, lặp tool, hoặc lỗi tool liên tiếp.
- Câu hỏi nằm ngoài phạm vi kho (out of corpus) lặp lại.
- Bất thường hành vi: dấu hiệu gian lận, tài khoản mới với yêu cầu lớn.
- Dự án luật lao động: câu bị từ chối có nút chuyển chuyên gia, câu ngoài kho được ghi log.

### Ví dụ tư vấn
"Hệ thống tự nhận ra khi khách đang bực, hỏi đi hỏi lại, hoặc chuyện có giá trị lớn, và chuyển cho nhân viên kèm tóm tắt cuộc trò chuyện để khách không phải kể lại."

### Ví dụ đàm phán
"Chuyển đúng lúc giúp giữ khách. Bên em báo cáo hằng tháng số ca chuyển và lý do để anh/chị điều chỉnh."

## G04-A10 · Agent lặp 4 giờ mới bị phát hiện: observability hỏng ở đâu
Lớp: A
Nguồn: gốc
Tags: observability, alerting

### Sếp hỏi
Agent lặp vô hạn 4 giờ trước khi bị phát hiện. Điều gì trong hệ thống giám sát đã thất bại, không phải "agent thất bại" mà "observability thất bại ở đâu"?

### Chốt kỹ thuật
- Không có metric theo phiên: thời lượng, số bước, token, chi phí mỗi phiên; chỉ có metric tổng.
- Không có cảnh báo bất thường: phiên vượt p99 lịch sử, chi phí theo giờ vượt baseline.
- Không có trần cứng ở runtime (lỗi thiết kế) và không có giám sát việc trần đó hoạt động.
- Trace không được lấy mẫu hoặc không theo dõi được phiên đang chạy (chỉ ghi khi kết thúc).
- Cảnh báo có nhưng gửi vào kênh không ai đọc, hoặc quá nhiều cảnh báo nhiễu.
- Sửa: metric và trace theo phiên real-time, cảnh báo theo ngưỡng tuyệt đối và bất thường, kill switch, dashboard top phiên tốn nhất đang chạy.

### Ví dụ tư vấn
"Lỗi không chỉ là AI chạy vòng vòng, mà là hệ thống theo dõi không báo động khi một việc chạy lâu bất thường. Bên em đặt chuông báo cho từng việc, không chỉ cho tổng."

### Ví dụ đàm phán
"Giám sát theo từng phiên là phần bên em không cắt, vì một sự cố như vậy có thể tốn bằng chi phí giám sát cả năm."

## G04-A11 · Trajectory đúng đáp án sai vs trajectory sai đáp án đúng
Lớp: A
Nguồn: gốc
Tags: eval, trajectory

### Sếp hỏi
Trajectory đúng mà đáp án sai, so với trajectory sai mà đáp án đúng (may mắn): bạn trừ điểm case nào nặng hơn trong eval nội bộ, vì sao rủi ro hơn về lâu dài?

### Chốt kỹ thuật
- Trừ nặng hơn trajectory sai đáp án đúng. Nó che giấu lỗi quy trình (gọi sai tool, bỏ bước kiểm tra, dựa vào nguồn không hợp lệ) sẽ gây sai khi dữ liệu đổi; khó tái hiện; và tạo cảm giác an toàn giả.
- Trajectory đúng đáp án sai thường do bước cuối (tổng hợp, diễn giải), dễ khu trú và sửa.
- Eval nên chấm cả quá trình: đúng tool, đúng thứ tự bắt buộc, đúng nguồn, không bước thừa nguy hiểm.

### Ví dụ tư vấn
"Nhân viên làm sai quy trình mà tình cờ ra kết quả đúng còn đáng lo hơn người làm đúng quy trình nhưng tính nhầm ở bước cuối. Lần sau người thứ nhất có thể gây ra sai lớn."

### Ví dụ đàm phán
"Báo cáo chất lượng của bên em chấm cả cách làm, không chỉ kết quả, để anh/chị thấy rủi ro trước khi nó xảy ra."

## G04-A12 · Khu trú lỗi "AI sai" trong 15 phút
Lớp: A
Nguồn: gốc
Tags: incident-response, layers, tracing

### Sếp hỏi
Độ tin cậy của agent production gồm bao nhiêu lớp (model, tool, hạ tầng, dữ liệu, con người vận hành)? Khi khách báo "AI sai", quy trình nào giúp xác định lỗi ở lớp nào trong 15 phút?

### Chốt kỹ thuật
- Lớp: đầu vào (người dùng, phân loại), dữ liệu (kho, hiệu lực), retrieval, model và prompt (phiên bản), tool và hệ thống ngoài, hạ tầng (timeout, retry), trình bày (UI), vận hành (cấu hình, thay đổi gần đây).
- Điều kiện: mỗi câu trả lời có trace id hiển thị hoặc tra được từ thời gian và người dùng; trace ghi phiên bản prompt, model, tài liệu truy hồi, tool call và kết quả.
- Quy trình: lấy trace → xem tài liệu truy hồi có đúng không (retrieval/dữ liệu) → xem câu trả lời có trung thành tài liệu không (generation) → xem tool result (tool/hệ thống ngoài) → xem lịch thay đổi gần đây (vận hành).
- Mẫu báo cáo sự cố ghi lớp lỗi để thống kê lỗi theo lớp.

### Ví dụ tư vấn
"Mỗi câu trả lời có mã tra cứu. Anh/chị gửi mã đó, bên em mở lại toàn bộ quá trình: tìm thấy tài liệu gì, AI đọc gì, gọi phần mềm nào, và chỉ ra lỗi nằm ở đâu."

### Ví dụ đàm phán
"Cam kết thời gian chẩn đoán ban đầu chỉ làm được khi có hệ thống truy vết. Đó là lý do phần này nằm trong gói vận hành."

## G04-B13 · "Sao AI lúc đúng lúc sai?"
Lớp: B
Nguồn: gốc
Tags: probabilistic, client

### Sếp hỏi
Khách hỏi: "Sao AI lúc đúng lúc sai, công ty anh không kiểm soát được à?" Giải thích đặc tính xác suất mà vẫn trấn an rủi ro đã được quản lý.

### Chốt kỹ thuật
- AI tạo câu trả lời theo xác suất, không chạy theo lệnh cố định như phần mềm thường; cùng câu hỏi có thể ra cách diễn đạt khác.
- Kiểm soát nằm ở các lớp xung quanh: căn cứ bắt buộc, kiểm tra tự động, giới hạn hành động, đo tỷ lệ đúng liên tục.

### Ví dụ tư vấn
"AI giống một chuyên viên giỏi hơn là máy tính bỏ túi: phần lớn đúng nhưng không tuyệt đối. Bên em không trông vào việc nó không bao giờ sai, mà đặt các lớp kiểm tra để cái sai bị chặn trước khi tới khách, và đo tỷ lệ đúng hằng tuần."

### Ví dụ đàm phán
"Bên em cam kết tỷ lệ đúng trên bộ câu hỏi hai bên cùng chọn, và có quy trình xử lý khi xuống dưới ngưỡng."

## G04-B14 · "Tôi muốn AI đúng 100%"
Lớp: B
Nguồn: gốc
Tags: expectations, client

### Sếp hỏi
Khách yêu cầu: "Tôi muốn AI đúng 100%, có làm được không?" Trả lời trung thực mà không làm khách mất niềm tin hay bỏ dự án.

### Chốt kỹ thuật
- Không hệ thống nào đúng 100%, kể cả con người. Mục tiêu đúng là: biết khi nào không chắc và không trả lời bừa; với việc quan trọng có người duyệt.
- Đề xuất chỉ số thực tế: tỷ lệ đúng trên câu đã trả lời, tỷ lệ từ chối hợp lý, tỷ lệ lỗi nghiêm trọng gần 0 nhờ guardrail.

### Ví dụ tư vấn
"Không ai, kể cả chuyên viên giỏi nhất, đúng 100%. Bên em làm cho hệ thống biết nói 'chưa chắc' thay vì đoán, và những việc quan trọng luôn có người duyệt. So với hiện tại, anh/chị có thể đặt mục tiêu giảm X% sai sót."

### Ví dụ đàm phán
"Bên em không ký cam kết 100%, nhưng ký cam kết theo từng chỉ số cụ thể và có cơ chế xử lý khi vi phạm."

## G04-B15 · "Agent chuyển nhầm tiền thì ai đền?"
Lớp: B
Nguồn: gốc
Tags: financial-risk, controls, client

### Sếp hỏi
Khách hỏi: "Nếu agent chuyển nhầm tiền thì sao, ai đền?" Trình bày các lớp bảo vệ bằng ngôn ngữ rủi ro tài chính.

### Chốt kỹ thuật
- Lớp: hạn mức mỗi giao dịch và mỗi ngày, danh sách người nhận đã xác minh, chống làm hai lần, người duyệt trên ngưỡng, đối soát cuối ngày, khả năng tạm khóa toàn bộ.
- Phân định trách nhiệm theo hợp đồng và bảo hiểm (nếu có).

### Ví dụ tư vấn
"Giống hạn mức chi tiêu của thẻ công ty: AI chỉ chuyển trong hạn mức, chỉ cho người nhận đã được duyệt, mọi lệnh trên ngưỡng phải có người ký. Cuối ngày có đối soát, sai lệch được phát hiện trong ngày."

### Ví dụ đàm phán
"Hợp đồng ghi rõ: lỗi vượt qua lớp kiểm soát bên em cam kết là trách nhiệm bên em. Hạn mức do anh/chị quyết định."

## G04-C16 · "Lỗi 2% là chấp nhận được, sao tính thêm guardrail?"
Lớp: C
Nguồn: gốc
Tags: cost-of-failure, negotiation

### Sếp hỏi
Khách nói: "Tỷ lệ lỗi 2% chấp nhận được rồi, sao vẫn tính thêm phí cho guardrail, retry, fallback?" Giải thích bằng kịch bản chi phí nếu không có chúng.

### Chốt kỹ thuật
- 2% trung bình che giấu phân phối: lỗi không đều, một số lỗi nhỏ, một số rất đắt.
- Tính: số giao dịch mỗi tháng × 2% × chi phí trung bình mỗi lỗi (xử lý khiếu nại, hoàn tiền, mất khách) so với chi phí guardrail.
- Nhà cung cấp sập vài giờ không có fallback = toàn bộ dịch vụ ngừng.

### Ví dụ tư vấn
"100 nghìn yêu cầu mỗi tháng, 2% là 2.000 lỗi. Nếu mỗi lỗi tốn 15 phút nhân viên xử lý thì đã là 500 giờ công. Lớp kiểm soát nhắm vào giảm phần lỗi đắt nhất trong số đó."

### Ví dụ đàm phán
"Bên em tính cùng anh/chị chi phí mỗi lỗi trên số liệu thật. Nếu lớp nào không tự hoàn vốn, bên em bỏ lớp đó."

## G04-C17 · "Cắt human-in-the-loop cho nhanh"
Lớp: C
Nguồn: gốc
Tags: human-in-the-loop, negotiation

### Sếp hỏi
Khách ép: "Cắt bớt human-in-the-loop cho nhanh và rẻ." Bạn đồng ý, từ chối, hay đưa phương án trung gian? Điều kiện cụ thể nào khiến bạn chọn từng hướng?

### Chốt kỹ thuật
- Đồng ý: hành động đảo ngược được, giá trị thấp, agent có lịch sử đúng cao trên đủ mẫu.
- Từ chối: hành động không đảo ngược, giá trị cao, yêu cầu pháp lý, hoặc chưa có số đo.
- Trung gian: chuyển từ duyệt trước sang hậu kiểm lấy mẫu; nâng ngưỡng giá trị cần duyệt; duyệt theo lô thay vì từng cái.

### Ví dụ tư vấn
"Bên em đề xuất bỏ duyệt cho đơn dưới X đồng và chuyển sang kiểm tra ngẫu nhiên 5%, giữ duyệt cho đơn lớn."

### Ví dụ đàm phán
"Phương án này giảm khoảng 70–80% khối lượng duyệt. Phần còn lại bên em giữ vì một lỗi ở đó có thể vượt tổng chi phí tiết kiệm được."

## G04-C18 · "Bên kia không có mục độ tin cậy"
Lớp: C
Nguồn: gốc
Tags: competition, negotiation

### Sếp hỏi
Khách so sánh: "Bên kia báo giá không có mục độ tin cậy nào, sao bên anh tính riêng?" Trả lời không dìm đối thủ nhưng làm rõ rủi ro khách đang gánh.

### Chốt kỹ thuật
- Có thể bên kia gộp vào giá khác, hoặc không làm. Đề nghị khách hỏi họ các câu cụ thể: xử lý thế nào khi nhà cung cấp AI sập, khi AI làm sai, có đo tỷ lệ đúng không.
- Tách riêng để minh bạch, khách thấy mình trả cho cái gì.

### Ví dụ tư vấn
"Có thể bên kia đã tính trong giá chung. Anh/chị hỏi họ ba câu này. Nếu họ có câu trả lời rõ thì hai bên tương đương; nếu không, phần rủi ro đó anh/chị đang tự gánh."

### Ví dụ đàm phán
"Bên em tách riêng để anh/chị chọn mức phù hợp, không phải để tính thêm. Có gói tối thiểu nếu anh/chị chấp nhận rủi ro cao hơn."

## G04-A19 · Thiết kế fallback đa nhà cung cấp LLM
Lớp: A
Nguồn: bổ sung
Tags: fallback, multi-provider, hedging

### Sếp hỏi
Thiết kế lớp gọi LLM có fallback giữa nhiều nhà cung cấp. Những gì có thể sai khi chuyển nhà cung cấp, và bạn kiểm soát thế nào?

### Chốt kỹ thuật
- Khác biệt hành vi: prompt tối ưu cho model A chưa chắc tốt với model B; khả năng structured output, độ dài context, tokenizer, giới hạn an toàn khác nhau.
- Kiểm soát: mỗi cặp (task, model) có bộ eval riêng; chỉ đưa vào danh sách fallback những model đạt ngưỡng; prompt riêng theo model nếu cần.
- Phân loại lỗi để quyết định: lỗi tạm thời (429, 5xx, timeout) thì retry hoặc chuyển; lỗi nội dung (bị chặn an toàn) không nên chuyển tự động; lỗi parse coi như lỗi nhà cung cấp.
- Hedging: gửi song song hoặc gửi trễ cho nhà cung cấp thứ hai để giảm độ trễ đuôi, đổi lấy chi phí.
- Ghi model thực sự trả lời vào trace để phân tích chất lượng theo model.
- Dự án luật lao động: router chọn danh sách theo task, đua mọi model Dahl song song, Gemini vào đua sau 15 giây, bỏ qua nhà cung cấp chưa cấu hình key.

### Ví dụ tư vấn
"Hệ thống có nhà cung cấp AI dự phòng đã được kiểm tra trước, tự chuyển khi nhà cung cấp chính gặp sự cố, nên dịch vụ của anh/chị không ngừng."

### Ví dụ đàm phán
"Dự phòng tăng chi phí kiểm thử và chút chi phí vận hành, đổi lại tránh được những giờ ngừng dịch vụ hoàn toàn."

## G04-A20 · Giám sát drift của nhà cung cấp model
Lớp: A
Nguồn: bổ sung
Tags: drift, monitoring, canary

### Sếp hỏi
Không có thay đổi gì phía bạn, nhưng chất lượng câu trả lời giảm dần trong 2 tuần. Bạn phát hiện và xử lý thế nào?

### Chốt kỹ thuật
- Canary eval định kỳ (hằng giờ hoặc hằng ngày) với bộ câu hỏi cố định, so phân phối điểm với baseline; cảnh báo khi giảm vượt ngưỡng thống kê.
- Theo dõi tín hiệu production: tỷ lệ từ chối, tỷ lệ parse fail, độ dài câu trả lời, phân phối token, tỷ lệ escalate, feedback.
- Ghi đầy đủ model id và tham số mỗi lời gọi; pin phiên bản model có ngày (snapshot) thay vì alias "latest".
- Phân biệt: dữ liệu người dùng thay đổi (câu hỏi mới) hay model thay đổi (eval cố định giảm).
- Xử lý: chuyển sang snapshot cũ hoặc nhà cung cấp khác, điều chỉnh prompt, báo nhà cung cấp.

### Ví dụ tư vấn
"Mỗi ngày hệ thống tự làm một bài kiểm tra cố định. Điểm giảm là bên em biết ngay, kể cả khi nhà cung cấp AI âm thầm thay đổi."

### Ví dụ đàm phán
"Bài kiểm tra hằng ngày tốn một khoản nhỏ cố định, là cách duy nhất phát hiện chất lượng giảm trước khi khách của anh/chị phàn nàn."
