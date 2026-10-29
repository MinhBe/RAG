---
group: G09
title: Eval
part: I
---

# Nhóm 9 — Eval

## G09-A01 · Tỷ lệ câu dễ và câu cần LLM-judge trong 100 câu đầu
Lớp: A
Nguồn: gốc
Tags: eval-design, ci

### Sếp hỏi
Bộ test 100 câu đầu tiên xây từ 0: tỷ lệ câu "dễ" (exact match được) so với câu "khó, cần LLM-judge" nên là bao nhiêu để vừa chạy nhanh trong CI vừa phản ánh thực tế?

### Chốt kỹ thuật
- Không có con số chung; xuất phát từ phân phối câu hỏi thật. Điểm khởi đầu hợp lý: khoảng 60–70% câu kiểm được bằng code (đáp án có cấu trúc: số, ngày, id điều luật, tool được gọi, JSON hợp lệ), 30–40% cần judge (chất lượng diễn đạt, đầy đủ, đúng giọng).
- Biến câu khó thành kiểm được bằng code khi có thể: kiểm tra trích dẫn đúng id, chứa con số đúng, không chứa thông tin cấm.
- Thêm nhóm câu cần từ chối (ngoài phạm vi, chèn lệnh) khoảng 10–15%.
- CI chạy phần kiểm bằng code mỗi PR (nhanh, rẻ, tất định); phần judge chạy khi thay prompt/model hoặc hằng đêm.

### Ví dụ tư vấn
"Phần lớn câu hỏi có đáp án kiểm tra tự động được như con số, điều luật. Phần còn lại cần chấm chất lượng diễn đạt, bên em dùng AI chấm có kiểm tra lại bằng người."

### Ví dụ đàm phán
"Bộ 100 câu đầu là khoản đầu tư khoảng một tuần, sau đó mỗi thay đổi đều có điểm số trong vài phút."

## G09-A02 · Ground truth do LLM sinh bị lệch thiên kiến
Lớp: A
Nguồn: gốc
Tags: synthetic-data, bias, labeling

### Sếp hỏi
Ground truth do LLM sinh có thể lệch theo đúng thiên kiến của chính LLM đó. Kiểm tra chéo bằng cách nào mà không tốn như thuê người gán nhãn toàn bộ?

### Chốt kỹ thuật
- Sinh bằng model khác họ với model đang được đánh giá.
- Neo vào nguồn: câu hỏi sinh từ một đoạn tài liệu cụ thể, đáp án phải trích được từ đoạn đó (kiểm tra bằng code hoặc NLI).
- Hai model sinh độc lập, chỉ giữ mục đồng thuận; mục bất đồng đưa người xem.
- Người kiểm tra mẫu ngẫu nhiên 10–20% và toàn bộ mục bất đồng; đo tỷ lệ lỗi của bộ sinh, nếu vượt ngưỡng thì xem lại quy trình.
- Bổ sung câu thật từ log production đã được người gán nhãn để chống lệch phân phối.

### Ví dụ tư vấn
"Đề kiểm tra do AI soạn nhưng đáp án phải chỉ ra được trong tài liệu gốc, được một AI khác soát lại, và chuyên viên của anh/chị duyệt ngẫu nhiên một phần."

### Ví dụ đàm phán
"Cách này giảm khoảng 80% công gán nhãn so với làm tay toàn bộ mà vẫn giữ độ tin cậy."

## G09-A03 · Thiên kiến còn lại của LLM-judge khi chấm đạt/không đạt
Lớp: A
Nguồn: gốc
Tags: llm-as-judge, bias, rubric

### Sếp hỏi
LLM-as-judge thiên vị câu dài, thiên vị vị trí đầu khi so cặp. Với rubric chấm đạt/không đạt (không so cặp), thiên kiến nào vẫn còn và cách giảm?

### Chốt kỹ thuật
- Còn: thiên vị độ dài và giọng tự tin (câu dài, trình bày đẹp dễ được chấm đạt); self-preference (ưu ái output của cùng họ model); dễ dãi với lỗi thực tế tinh vi; nhạy với cách viết rubric; không ổn định giữa các lần chạy.
- Giảm: rubric tách tiêu chí nhị phân cụ thể ("có nêu đúng thời hạn 30 ngày không"), bắt judge trích bằng chứng trước khi kết luận, cung cấp đáp án tham chiếu, judge khác họ model, temperature 0 và chạy nhiều lần lấy đa số cho mục quan trọng.
- Hiệu chỉnh judge trên 100–200 mẫu người chấm, đo agreement; theo dõi agreement theo thời gian.

### Ví dụ tư vấn
"AI chấm bài cũng có thói quen chấm dễ cho bài dài. Bên em cho nó chấm theo từng ý cụ thể, bắt chỉ ra bằng chứng, và định kỳ so với người chấm."

### Ví dụ đàm phán
"Hiệu chỉnh người chấm AI là việc định kỳ nhỏ, đảm bảo điểm chất lượng báo cho anh/chị là đáng tin."

## G09-A04 · Faithfulness và recall cao nhưng task completion không tăng
Lớp: A
Nguồn: gốc
Tags: metrics, business-alignment

### Sếp hỏi
Faithfulness cao, recall@5 cao, nhưng task completion rate kinh doanh không tăng. "Cái thước đo" của bạn đang đo sai thứ gì?

### Chốt kỹ thuật
- Đo trên bộ câu không đại diện cho phân phối thật (câu dễ, viết chuẩn, không có câu nhiều lượt).
- Faithfulness đo trung thành với tài liệu, không đo tài liệu có đúng và đủ để hoàn thành việc.
- Đo câu trả lời, không đo hành động tiếp theo của người dùng (họ vẫn phải gọi tổng đài).
- Đơn vị sai: đo từng lượt, trong khi việc cần cả hội thoại.
- Sửa: định nghĩa task completion theo hành vi (không quay lại hỏi trong 24 giờ, không chuyển người, hoàn tất đơn), xây eval theo hội thoại, lấy mẫu từ production.

### Ví dụ tư vấn
"Điểm thi cao nhưng khách vẫn phải gọi tổng đài nghĩa là đề thi chưa giống việc thật. Bên em sửa đề theo các cuộc trò chuyện thật."

### Ví dụ đàm phán
"Bên em gắn chỉ số chất lượng vào chỉ số kinh doanh anh/chị quan tâm, để không tối ưu nhầm hướng."

## G09-A05 · Thay đổi nào vào tầng regression nhanh
Lớp: A
Nguồn: gốc
Tags: regression, ci, tiering

### Sếp hỏi
Chia tầng regression "nhanh" (CI, vài chục câu) và "đầy đủ" (nightly, 1.000 câu). Tiêu chí nào quyết định một câu được gộp vào tầng nhanh?

### Chốt kỹ thuật
- Câu bao phủ đường đi quan trọng nhất (theo lưu lượng hoặc theo rủi ro).
- Câu từng phát hiện bug thật (regression case).
- Câu kiểm được bằng code, tất định, chạy nhanh.
- Câu đại diện cho mỗi nhánh của router và mỗi tool chính.
- Câu an toàn (chèn lệnh, ngoài phạm vi) vì lỗi ở đây nghiêm trọng.
- Loại khỏi tầng nhanh câu không ổn định (flaky) hoặc cần judge đắt.
- Thay đổi chạm prompt, model, retrieval thì bắt buộc chạy tầng đầy đủ trước khi merge.

### Ví dụ tư vấn
"Mỗi thay đổi nhỏ chạy bài kiểm tra nhanh vài phút. Thay đổi lớn chạy bài đầy đủ trước khi đưa lên."

### Ví dụ đàm phán
"Hai tầng giúp giữ tốc độ phát triển mà không bỏ kiểm tra."

## G09-A06 · A/B tăng 2% nhưng chưa có ý nghĩa thống kê
Lớp: A
Nguồn: gốc
Tags: ab-testing, statistics, decision

### Sếp hỏi
A/B test prompt mới: tăng 2% tỷ lệ hoàn thành task nhưng p-value chưa đủ sau 2 tuần. Chờ thêm, deploy luôn, hay bỏ? Dựa trên tiêu chí nào?

### Chốt kỹ thuật
- Tính power: với cỡ mẫu hiện tại, muốn phát hiện 2% cần bao nhiêu mẫu, mất bao lâu. Nếu cần hàng tháng thì chờ không thực tế.
- Xem guardrail metric: chi phí, độ trễ, tỷ lệ lỗi, an toàn. Nếu không xấu đi và chi phí đổi thấp, đảo ngược dễ thì có thể deploy (quyết định kinh doanh, không phải kết luận thống kê).
- Nếu prompt mới đắt hơn hoặc rủi ro cao hơn thì không deploy khi chưa chắc.
- Kết hợp eval offline: nếu offline cũng cải thiện thì tăng niềm tin.
- Cách khác: giảm phương sai (CUPED, phân tầng), metric nhạy hơn.

### Ví dụ tư vấn
"Thay đổi có vẻ tốt hơn một chút nhưng chưa đủ dữ liệu để chắc. Vì nó không làm tăng chi phí và dễ quay lại, bên em đề xuất áp dụng và tiếp tục theo dõi."

### Ví dụ đàm phán
"Bên em trình bày rõ đây là quyết định có rủi ro thấp, không phải kết luận chắc chắn, để anh/chị cùng quyết."

## G09-A07 · Canary: task completion giảm nhưng thumbs không đổi
Lớp: A
Nguồn: gốc
Tags: canary, feedback, metrics

### Sếp hỏi
Canary 10%: task completion giảm 3 điểm % nhưng 👍/👎 không đổi. Tin số liệu nào hơn, vì sao hai tín hiệu mâu thuẫn?

### Chốt kỹ thuật
- Tin task completion hơn: đo hành vi trên toàn bộ người dùng; 👍/👎 chỉ vài phần trăm người bấm và thiên lệch.
- Giải thích mâu thuẫn: người dùng không biết câu trả lời sai (không bấm 👎), hoặc người gặp lỗi bỏ đi không bấm; nhóm bấm không đại diện.
- Kiểm tra: phân tách theo loại câu hỏi, kiểm tra instrument của metric (định nghĩa completion có bị ảnh hưởng bởi thay đổi UI không), đọc mẫu hội thoại thất bại.
- Dừng mở rộng canary cho tới khi giải thích được.

### Ví dụ tư vấn
"Ít người bấm thích hay không thích, nên đó không phải thước đo đầy đủ. Số người hoàn thành việc giảm là tín hiệu thật, bên em tạm dừng mở rộng để tìm nguyên nhân."

### Ví dụ đàm phán
"Quy trình phát hành từng phần giúp phát hiện vấn đề khi chỉ 10% người dùng bị ảnh hưởng."

## G09-A08 · Eval trạng thái hệ thống sau khi agent chạy
Lớp: A
Nguồn: gốc
Tags: agent-eval, sandbox, state

### Sếp hỏi
Eval agent ở cấp "trạng thái hệ thống sau khi chạy" (đơn hàng có thật sự được tạo đúng trong database không): khác eval câu trả lời văn bản thế nào, tốn thêm hạ tầng gì?

### Chốt kỹ thuật
- Đo kết quả thật thay vì lời nói: đối chiếu trạng thái DB sau khi chạy với trạng thái mong đợi (đơn có tạo, số tiền đúng, không tạo thừa).
- Cần: môi trường sandbox (DB riêng, mock API bên thứ ba có trạng thái), fixture khởi tạo trạng thái đầu cho mỗi case, rollback/reset sau mỗi case (transaction hoặc snapshot container), cách ly để chạy song song.
- Chấm cả side effect không mong muốn (gửi email thừa, ghi sai bảng).
- Chi phí: hạ tầng và thời gian chạy lâu hơn nhiều, nên số case ít hơn eval văn bản.

### Ví dụ tư vấn
"Thay vì hỏi nhân viên 'em làm xong chưa', bên em kiểm tra kho và sổ sách xem việc đã thật sự xong đúng chưa."

### Ví dụ đàm phán
"Môi trường kiểm thử riêng là hạng mục cho các luồng có ghi dữ liệu, cần thiết trước khi cho AI tự thao tác."

## G09-A09 · Rủi ro tập trung ở khách VIP
Lớp: A
Nguồn: gốc
Tags: segmentation, tail-risk

### Sếp hỏi
Tool-call accuracy 95% nhưng 2 lần gọi sai cùng rơi vào 1 khách VIP. Điểm trung bình có che giấu rủi ro tập trung không? Thiết kế eval theo phân khúc thế nào?

### Chốt kỹ thuật
- Có. Trung bình che phân phối; lỗi có thể tập trung theo phân khúc (khách lớn có nghiệp vụ phức tạp hơn).
- Báo cáo theo lát cắt: phân khúc khách, loại tác vụ, giá trị giao dịch, ngôn ngữ, kênh.
- Trọng số theo giá trị (lỗi trên giao dịch lớn đếm nặng hơn).
- Ngưỡng riêng cho phân khúc quan trọng; eval set riêng xây từ dữ liệu của khách VIP.
- Cảnh báo khi một khách có nhiều lỗi trong một cửa sổ thời gian.

### Ví dụ tư vấn
"Điểm trung bình tốt chưa đủ. Bên em xem riêng từng nhóm khách và loại việc, để không có nhóm nào chịu lỗi dồn."

### Ví dụ đàm phán
"Báo cáo theo nhóm khách là phần bên em cung cấp hằng tháng cho khách doanh nghiệp."

## G09-A10 · Model đổi ngầm không đổi version
Lớp: A
Nguồn: gốc
Tags: drift, monitoring

### Sếp hỏi
Nhà cung cấp LLM tự cập nhật model ngầm khiến hành vi đổi. Pipeline giám sát hành vi nào chạy liên tục, không chỉ khi có pull request?

### Chốt kỹ thuật
- Canary eval theo lịch (hằng giờ/ngày) với bộ câu cố định, temperature 0; so với baseline bằng kiểm định thống kê và theo từng metric.
- Giám sát production: phân phối độ dài, tỷ lệ từ chối, tỷ lệ parse fail, tỷ lệ tool call, độ trễ, token.
- Fingerprint: lưu output của câu cố định, theo dõi tỷ lệ thay đổi.
- Pin snapshot có ngày; đọc changelog nhà cung cấp.
- Cảnh báo đi vào kênh có người trực.

### Ví dụ tư vấn
"Mỗi ngày hệ thống tự làm cùng một bài kiểm tra. Kết quả đổi bất thường là bên em biết nhà cung cấp đã thay đổi gì đó."

### Ví dụ đàm phán
"Khoản giám sát này nhỏ và cố định hằng tháng."

## G09-B11 · "Có bằng chứng gì AI đang hoạt động tốt?"
Lớp: B
Nguồn: gốc
Tags: reporting, client

### Sếp hỏi
Khách hỏi: "Sao các anh biết AI của tôi đang hoạt động tốt, có bằng chứng gì không?" Trình bày report eval bằng ngôn ngữ kinh doanh.

### Chốt kỹ thuật
- Chỉ số kinh doanh: tỷ lệ yêu cầu được xử lý trọn vẹn không cần người, thời gian phản hồi, tỷ lệ chuyển người và lý do, số lỗi nghiêm trọng, chi phí mỗi yêu cầu, xu hướng theo tháng.
- Kèm 3–5 ví dụ hội thoại tốt và xấu đã xử lý.
- Bộ câu kiểm tra hai bên cùng duyệt, điểm theo tháng.

### Ví dụ tư vấn
"Tháng này 82% yêu cầu được xử lý trọn vẹn, tăng 4% so với tháng trước, thời gian phản hồi trung bình 3 giây, có 2 lỗi nghiêm trọng đã được sửa, đây là chi tiết. Anh/chị cũng có thể tự kiểm tra trên bộ 200 câu hai bên đã thống nhất."

### Ví dụ đàm phán
"Báo cáo hằng tháng nằm trong gói vận hành và là căn cứ cho điều khoản cam kết chất lượng."

## G09-B12 · "Đổi prompt có ảnh hưởng chất lượng, tôi có phải trả thêm?"
Lớp: B
Nguồn: gốc
Tags: regression, client, pricing

### Sếp hỏi
Khách hỏi: "Sao thỉnh thoảng các anh đổi prompt, có ảnh hưởng chất lượng không, tôi có phải trả thêm tiền kiểm tra lại không?"

### Chốt kỹ thuật
- Mỗi thay đổi đều chạy bộ kiểm tra tự động, chỉ phát hành khi không giảm điểm; phát hành từng phần và có thể quay lại.
- Phân định: thay đổi để duy trì và sửa lỗi nằm trong phí vận hành; thay đổi theo yêu cầu mới của khách là phát sinh.

### Ví dụ tư vấn
"Mỗi lần chỉnh, hệ thống tự làm lại bài kiểm tra mấy trăm câu. Điểm không giảm mới được áp dụng, và áp cho một phần nhỏ người dùng trước."

### Ví dụ đàm phán
"Kiểm tra lại khi bên em chủ động cải tiến hay sửa lỗi là trong phí vận hành. Chỉ khi anh/chị yêu cầu tính năng mới mới tính riêng."

## G09-C13 · "Đổi prompt nhỏ xíu, cần gì chạy eval"
Lớp: C
Nguồn: gốc
Tags: regression, negotiation

### Sếp hỏi
Khách nói: "Sao phải chạy eval tốn tiền token mỗi lần đổi prompt nhỏ xíu, cứ đổi rồi dùng thử xem sao?" Thuyết phục bằng ví dụ thiệt hại cụ thể.

### Chốt kỹ thuật
- Ví dụ: thêm một câu "trả lời ngắn gọn" làm model bỏ phần ngoại lệ của điều luật; thêm một ví dụ mẫu làm model bắt chước sai định dạng JSON làm hỏng parse 5% câu.
- Chi phí eval: vài trăm câu × chi phí mỗi câu, thường nhỏ hơn nhiều so với một ngày lỗi trên production.

### Ví dụ tư vấn
"Một câu chữ nhỏ trong hướng dẫn có thể làm AI bỏ mất phần 'trừ trường hợp…' trong mọi câu trả lời. Bài kiểm tra bắt được lỗi đó trong 10 phút, thay vì để khách hàng phát hiện."

### Ví dụ đàm phán
"Chi phí mỗi lần kiểm tra khoảng X nghìn đồng tiền AI. Bên em sẵn sàng ghi vào báo cáo để anh/chị thấy nó nhỏ thế nào."

## G09-C14 · "Bớt giám sát hàng tháng, AI chạy ổn rồi"
Lớp: C
Nguồn: gốc
Tags: drift, negotiation

### Sếp hỏi
Khách ép: "Bớt khoản giám sát và đánh giá hàng tháng, AI chạy ổn rồi cần gì giám sát?" Giải thích rủi ro drift mà không nghe như vẽ việc.

### Chốt kỹ thuật
- Các thứ thay đổi dù không ai đụng vào hệ thống: nhà cung cấp cập nhật model, câu hỏi khách thay đổi theo mùa và sản phẩm mới, tài liệu và chính sách đổi, hệ thống tích hợp đổi API.
- Đề xuất gói giám sát tối thiểu tự động + báo cáo quý thay vì tháng nếu cần giảm chi phí.

### Ví dụ tư vấn
"Hệ thống không đổi nhưng thế giới xung quanh đổi: nhà cung cấp AI cập nhật, khách hỏi về sản phẩm mới, chính sách đổi. Giám sát là để biết sớm."

### Ví dụ đàm phán
"Bên em có gói giám sát tự động tối thiểu, chỉ cảnh báo khi có vấn đề, chi phí thấp hơn khoảng một nửa."

## G09-A15 · Eval cho hội thoại nhiều lượt
Lớp: A
Nguồn: bổ sung
Tags: multi-turn, simulation

### Sếp hỏi
Eval một lượt không bắt được lỗi trong hội thoại nhiều lượt (quên ngữ cảnh, mâu thuẫn với câu trước). Bạn dựng eval nhiều lượt thế nào?

### Chốt kỹ thuật
- Kịch bản cố định: chuỗi câu hỏi viết sẵn có câu nối tiếp, câu đổi chủ đề, câu sửa lại thông tin; chấm từng lượt và chấm toàn hội thoại.
- User simulator: LLM đóng vai người dùng với mục tiêu và tính cách, chạy nhiều lần; chấm đạt mục tiêu, số lượt, có mâu thuẫn không.
- Kiểm tra đặc thù: câu nối tiếp có truy hồi đúng không ("còn lao động nữ thì sao"), có giữ ràng buộc người dùng nêu từ đầu không.
- Replay hội thoại thật từ log (ẩn danh hóa) làm case.
- Dự án luật lao động có test riêng cho câu nối tiếp và script probe đo hạng của điều đúng trong kết quả khi hỏi nối tiếp.

### Ví dụ tư vấn
"Bên em không chỉ kiểm tra từng câu hỏi lẻ mà cho AI trò chuyện cả đoạn như khách thật, xem nó có nhớ đúng và không tự mâu thuẫn không."

### Ví dụ đàm phán
"Kiểm tra hội thoại nhiều lượt tốn hơn kiểm tra từng câu, bên em áp cho các luồng chính."

## G09-A16 · Đo chi phí và độ trễ trong eval
Lớp: A
Nguồn: bổ sung
Tags: cost, latency, pareto

### Sếp hỏi
Một thay đổi tăng điểm chất lượng 3% nhưng tăng chi phí 40% và độ trễ p95 thêm 2 giây. Eval của bạn trình bày quyết định này thế nào?

### Chốt kỹ thuật
- Eval luôn báo cáo đồng thời chất lượng, chi phí mỗi yêu cầu, độ trễ p50/p95, tỷ lệ lỗi.
- Đặt quyết định trên biên Pareto: các cấu hình không bị cấu hình khác vượt trội ở mọi chiều.
- Quy đổi về giá trị kinh doanh: 3% chất lượng tương ứng bao nhiêu ca phải chuyển người ít hơn, giá trị mỗi ca.
- Áp dụng có chọn lọc: chỉ bật cấu hình đắt cho lớp câu hỏi được lợi nhiều nhất.

### Ví dụ tư vấn
"Bên em đưa bảng so sánh: phương án A rẻ và nhanh, phương án B đúng hơn 3% nhưng đắt hơn 40%. Anh/chị chọn theo giá trị của 3% đó với doanh nghiệp."

### Ví dụ đàm phán
"Bên em đề xuất dùng phương án B chỉ cho loại câu hỏi quan trọng, giữ chi phí tổng tăng dưới 10%."
