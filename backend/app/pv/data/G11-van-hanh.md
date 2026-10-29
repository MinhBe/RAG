---
group: G11
title: Vận hành (tình huống)
part: II
---

# Nhóm 11 — Vận hành

## G11-T01 · Chi phí API tăng gấp 3 tối thứ Sáu
Lớp: T
Nguồn: gốc
Tags: incident, cost-spike

### Sếp hỏi
8 giờ tối thứ Sáu, dashboard báo chi phí API tăng gấp 3 trong 1 giờ, không có deploy nào gần đây, sếp sắp gọi hỏi. Liệt kê giả định cần kiểm chứng, thứ tự kiểm tra, và với mỗi nguyên nhân: hành động chặn máu và sửa gốc rễ.

### Chốt kỹ thuật
- Thứ tự kiểm tra (nhanh và có khả năng cao trước): (1) chi phí tăng theo lưu lượng hay theo chi phí mỗi request; (2) phân tách theo khách/tenant, endpoint, model, API key; (3) top phiên tốn nhất đang chạy.
- Lưu lượng tăng thật (viral, chiến dịch marketing): chặn máu bằng rate limit, cache; gốc rễ là capacity plan và ngân sách theo khách.
- Một khách hoặc một key bị lạm dụng (bot, key lộ): chặn máu là khóa key, rate limit theo khách; gốc rễ là xoay key, giới hạn theo key.
- Vòng lặp agent hoặc retry storm (nhà cung cấp lỗi làm retry dồn dập): chặn máu bằng kill switch, giảm retry, circuit breaker; gốc rễ là trần bước và trần retry.
- Prompt phình (context không được dọn ở phiên dài, cache prompt bị vô hiệu): chặn máu bằng cắt lịch sử; gốc rễ là compaction.
- Nhà cung cấp đổi giá hoặc model alias trỏ sang model đắt hơn, hoặc fallback đang dùng model đắt vì model chính lỗi: kiểm tra model id thực tế.
- Báo sếp ngay trong 15 phút đầu: hiện trạng, đã chặn gì, ước tính thiệt hại, giờ cập nhật tiếp.

### Ví dụ tư vấn
"Bên em đã tìm ra chi phí tăng do một khách gửi yêu cầu tự động liên tục, đã giới hạn tần suất của tài khoản đó, chi phí trở lại bình thường. Thứ Hai bên em gửi báo cáo và thêm giới hạn mặc định cho mọi tài khoản."

### Ví dụ đàm phán
Khi khách lớn là nguyên nhân: "Lưu lượng của anh/chị vượt mức thỏa thuận gấp 5 lần trong 1 giờ. Bên em đã giới hạn tạm để bảo vệ hệ thống, và đề xuất nâng gói hoặc thống nhất mức trần."

## G11-T02 · AI trả lời sai giá dù tool trả đúng
Lớp: T
Nguồn: gốc
Tags: debugging, generation, tool-output

### Sếp hỏi
Merchant báo "AI trả lời sai giá sản phẩm liên tục từ sáng". Log cho thấy agent gọi đúng tool, tool trả đúng dữ liệu, nhưng câu trả lời cuối vẫn sai. Liệt kê ít nhất 4 giả định, mỗi giả định kèm bước kiểm tra, sắp theo xác suất.

### Chốt kỹ thuật
- Model đọc nhầm trong output tool lớn (nhiều sản phẩm, nhiều giá: giá gốc, giá khuyến mãi, giá theo biến thể): kiểm tra output tool của các ca sai, có nhiều trường giá không; sửa bằng output gọn, trường rõ nghĩa.
- Nguồn khác lấn át tool: RAG trả tài liệu cũ có giá cũ, hoặc cache ngữ nghĩa trả câu trả lời cũ: kiểm tra context đầy đủ và cache hit của ca sai.
- Định dạng số: dấu chấm/phẩy hàng nghìn, đơn vị (nghìn đồng vs đồng), model chuyển đổi sai: so giá trị sai với giá đúng có quan hệ ×1000 không.
- Thay đổi từ sáng: prompt, model (nhà cung cấp cập nhật), dữ liệu đầu vào đổi định dạng: xem lịch thay đổi và model id.
- Lịch sử hội thoại có giá cũ (khách hỏi lại sau khi giá đổi): kiểm tra phiên dài.
- Chặn ngay: hậu kiểm số trong câu trả lời phải xuất hiện trong output tool, nếu không thì chèn giá trực tiếp từ dữ liệu (template) thay vì để model viết.

### Ví dụ tư vấn
"Hệ thống lấy đúng giá nhưng AI diễn đạt nhầm. Bên em đã chuyển phần hiển thị giá sang lấy trực tiếp từ dữ liệu, không qua AI viết lại, nên giá luôn khớp."

### Ví dụ đàm phán
"Lỗi này bên em chịu trách nhiệm và đã sửa trong ngày. Bên em gửi danh sách các cuộc trò chuyện bị ảnh hưởng để anh/chị liên hệ khách nếu cần."

## G11-T03 · Model mới: completion giảm 2%, chi phí giảm 30%
Lớp: T
Nguồn: gốc
Tags: rollout, tradeoff, decision

### Sếp hỏi
Rollout model mới cho 10% traffic, sau 24 giờ: task completion giảm 81% → 79% nhưng chi phí giảm 30%. PM hỏi có nên đẩy lên 100% không. Cần biết thêm gì, và điều kiện nào cho từng kịch bản (đẩy, không đẩy, đẩy một phần)?

### Chốt kỹ thuật
- Cần biết: chênh lệch có ý nghĩa thống kê không (cỡ mẫu 24 giờ của 10%); giảm tập trung ở phân khúc nào (khách VIP, loại tác vụ có giá trị cao); lỗi mới có nghiêm trọng không (sai tiền vs diễn đạt kém); giá trị kinh doanh của 2% completion so với 30% chi phí; độ trễ thay đổi thế nào; ngày đo có điển hình không.
- Đẩy 100%: giảm không có ý nghĩa thống kê hoặc chỉ ở tác vụ giá trị thấp, không lỗi nghiêm trọng mới, tiết kiệm lớn hơn giá trị mất.
- Không đẩy: giảm tập trung ở tác vụ giá trị cao hoặc có lỗi nghiêm trọng mới.
- Đẩy một phần: route theo loại tác vụ, model mới cho tác vụ đơn giản, model cũ cho tác vụ phức tạp; thường cho cả lợi ích chi phí lẫn chất lượng.
- Đề xuất kéo dài canary thêm vài ngày để đủ dữ liệu nếu không gấp.

### Ví dụ tư vấn
"Bên em đề xuất dùng model mới cho khoảng 70% câu hỏi đơn giản, giữ model cũ cho câu phức tạp. Tiết kiệm khoảng 20% mà tỷ lệ hoàn thành gần như không đổi."

### Ví dụ đàm phán
Với PM: "Mất 2% hoàn thành trên 1 triệu yêu cầu là 20 nghìn ca chuyển người. Nếu mỗi ca tốn 10 nghìn đồng xử lý thì đã ngang phần tiết kiệm. Cần tính trên số thật trước khi quyết."

## G11-T04 · Nhà cung cấp chính sập giữa 11/11
Lớp: T
Nguồn: gốc
Tags: failover, incident, decision

### Sếp hỏi
Nhà cung cấp LLM chính sập hoàn toàn giữa giờ cao điểm 11/11. Có model dự phòng của hãng khác nhưng chưa test kỹ. Chuyển ngay hay chờ? Giả định rủi ro mỗi lựa chọn và tiêu chí quyết định trong 5 phút.

### Chốt kỹ thuật
- Giả định cần biết nhanh: trang status nhà cung cấp có ETA không; lịch sử sự cố tương tự kéo dài bao lâu; thiệt hại mỗi phút không có AI (doanh thu, tổng đài quá tải); model dự phòng đã chạy eval tối thiểu nào chưa; luồng nào có hành động rủi ro (tạo đơn, hoàn tiền).
- Chuyển ngay khi: thiệt hại mỗi phút lớn, không có ETA hoặc ETA dài, model dự phòng đã qua smoke test cơ bản.
- Cách giảm rủi ro khi chuyển: chỉ chuyển luồng chỉ đọc (tư vấn, tra cứu); tắt hoặc yêu cầu duyệt người cho luồng có hành động; bật thêm kiểm tra định dạng; theo dõi sát và có người đọc mẫu hội thoại.
- Chờ khi: ETA ngắn, thiệt hại nhỏ, hoặc model dự phòng có hành vi nguy hiểm đã biết; trong lúc chờ hiện thông báo và chuyển tổng đài.
- Bài học: model dự phòng phải được eval và chạy shadow định kỳ trước mùa cao điểm.

### Ví dụ tư vấn
"Nhà cung cấp AI chính đang sự cố. Bên em đã chuyển phần tư vấn sang nhà cung cấp dự phòng, phần đặt hàng tạm chuyển cho nhân viên xác nhận, cho tới khi nhà cung cấp chính phục hồi."

### Ví dụ đàm phán
"Bên em đề xuất trước mỗi mùa cao điểm có một buổi diễn tập chuyển dự phòng, chi phí nhỏ so với rủi ro ngày 11/11."

## G11-T05 · Semantic cache trả nhầm câu trả lời giữa hai khách
Lớp: T
Nguồn: gốc
Tags: cache, privacy, incident

### Sếp hỏi
Semantic cache trúng 45% nhưng có ca khách phàn nàn "AI trả lời nhầm câu hỏi của người khác", nghi cache trả nhầm giữa hai khách. Quy trình điều tra, phương án sửa kèm đánh đổi, khi nào chọn phương án quyết liệt nhất?

### Chốt kỹ thuật
- Điều tra: lấy các ca phàn nàn, kiểm tra cache hit, so khóa cache (có tenant/user không), so câu hỏi gốc của entry cache với câu hỏi hiện tại; quét toàn bộ cache tìm entry chứa dữ liệu cá nhân.
- Phân biệt mức độ: nhầm nghĩa (câu hỏi gần giống) hay rò dữ liệu (câu trả lời chứa thông tin cá nhân của khách khác). Rò dữ liệu là sự cố bảo mật, có nghĩa vụ báo cáo.
- Phương án: siết ngưỡng (rẻ, không giải quyết rò rỉ); thêm khóa theo tenant và loại câu (giải quyết rò rỉ, hit rate giảm); tắt cache hoàn toàn (an toàn nhất, chi phí tăng ngay).
- Chọn tắt ngay khi có bất kỳ bằng chứng rò dữ liệu cá nhân giữa khách; flush toàn bộ cache, bật lại sau khi đã thêm khóa và không cache câu có dữ liệu cá nhân.

### Ví dụ tư vấn
"Bên em đã tắt tính năng dùng lại câu trả lời ngay khi phát hiện, xóa toàn bộ dữ liệu tạm, và chỉ bật lại sau khi tách riêng theo từng khách."

### Ví dụ đàm phán
"Chi phí tăng khoảng 40% trong vài ngày tắt cache, bên em chịu phần đó vì lỗi thuộc thiết kế của bên em."

## G11-T06 · Dùng chung tài khoản admin, không có audit log
Lớp: T
Nguồn: gốc
Tags: access-control, audit, process

### Sếp hỏi
Phát hiện nhân viên vận hành dùng chung 1 tài khoản admin để debug production, không có audit log riêng. Sự cố vừa xảy ra, không biết ai làm gì. Giải pháp ngắn hạn và dài hạn; khi nào chậm lại để làm đúng quy trình, khi nào làm nhanh?

### Chốt kỹ thuật
- Ngay lập tức: đổi mật khẩu và khóa tài khoản chung, cấp tài khoản cá nhân với quyền tối thiểu, bật log ở tầng DB và hạ tầng (cloud audit log thường có sẵn), thu thập mọi log hiện có để tái dựng sự cố.
- Tuần này: truy cập production qua bastion/SSO có ghi phiên, quyền ghi chỉ cấp theo yêu cầu có thời hạn (just-in-time), hai người cho thao tác nguy hiểm.
- Trong quý: quy trình change management, runbook, công cụ debug chỉ đọc để giảm nhu cầu quyền ghi, review quyền định kỳ.
- Khi sự cố đang diễn ra và gây thiệt hại: được phép làm nhanh bằng quyền khẩn cấp (break-glass) nhưng phải ghi lại và review sau. Khi không khẩn cấp: không được bỏ quy trình.

### Ví dụ tư vấn
"Bên em đã chuyển sang mỗi kỹ sư một tài khoản riêng có ghi lại thao tác. Thao tác khẩn cấp vẫn làm được nhưng luôn có người thứ hai xác nhận và có biên bản."

### Ví dụ đàm phán
Với sếp: "Làm đúng quy trình làm mỗi lần debug chậm thêm vài phút, nhưng lần sự cố sau mình biết ngay ai làm gì thay vì mất hai ngày đoán."

## G11-T07 · Đoạn system prompt kỳ lạ tồn tại 6 tháng
Lớp: T
Nguồn: gốc
Tags: prompt-maintenance, chesterton-fence

### Sếp hỏi
Một đoạn hướng dẫn kỳ lạ trong system prompt tồn tại 6 tháng, không ai nhớ lý do, hệ thống vẫn chạy ổn. Có nên xóa để gọn và tiết kiệm token không? Quy trình kiểm chứng an toàn, khi nào chấp nhận rủi ro, khi nào tuyệt đối không động?

### Chốt kỹ thuật
- Tìm lý do trước: git blame, PR, ticket, chat thời điểm đó, hỏi người đã thêm.
- Kiểm chứng: chạy eval đầy đủ có và không có đoạn đó; tìm trong log các câu hỏi liên quan tới chủ đề đoạn đó và replay; thêm case đặc thù vào eval.
- Tính lợi ích thật: số token tiết kiệm × số request (với prompt caching, lợi ích có thể rất nhỏ).
- Xóa khi: eval không đổi, lợi ích đáng kể, rollout từng phần có theo dõi.
- Không động khi: đoạn đó liên quan an toàn, pháp lý, bảo mật, hoặc lĩnh vực rủi ro cao mà eval không phủ được; lợi ích nhỏ.
- Sau cùng: ghi chú lý do cho mọi đoạn prompt (comment hoặc tài liệu đi kèm).

### Ví dụ tư vấn
"Trước khi bỏ một quy tắc cũ, bên em tìm hiểu vì sao có nó và kiểm tra lại trên các câu hỏi liên quan. Không chắc thì giữ, vì tiết kiệm được rất ít."

### Ví dụ đàm phán
"Phần tiết kiệm từ việc rút gọn hướng dẫn này chỉ vài trăm nghìn đồng một tháng, không đáng rủi ro nếu chưa rõ lý do."

## G11-T08 · Dùng tỷ lệ 👍/👎 2% để báo cáo hài lòng
Lớp: T
Nguồn: gốc
Tags: metrics, reporting, bias

### Sếp hỏi
Chỉ 2% người dùng bấm 👍/👎, dữ liệu thiên lệch, nhưng sếp muốn dùng số này báo cáo "tỷ lệ hài lòng" lên ban giám đốc hàng tháng. Từ chối, dùng kèm cảnh báo, hay xây thêm tín hiệu khác?

### Chốt kỹ thuật
- Không nên từ chối thẳng: có số liệu kèm cảnh báo tốt hơn không có gì.
- Báo cáo kèm: tỷ lệ người bấm, cỡ mẫu, khoảng tin cậy, xu hướng (xu hướng đáng tin hơn giá trị tuyệt đối).
- Xây thêm tín hiệu hành vi: tỷ lệ hoàn thành việc, tỷ lệ hỏi lại, tỷ lệ chuyển người, tỷ lệ quay lại dùng; khảo sát ngẫu nhiên một mẫu nhỏ người dùng để có ước lượng không thiên lệch; chấm chất lượng tự động trên mẫu hội thoại.
- Lộ trình: tháng này dùng kèm cảnh báo, 2–3 tháng sau thay bằng chỉ số tổng hợp.

### Ví dụ tư vấn
Với ban giám đốc: "Trong số 2% người dùng có phản hồi, 85% hài lòng. Con số này thiên về người rất thích hoặc rất không thích. Từ tháng sau bên em bổ sung chỉ số tỷ lệ hoàn thành việc trên toàn bộ người dùng."

### Ví dụ đàm phán
Với sếp: "Mình báo cáo được ngay, nhưng ghi rõ giới hạn. Nếu sau này số thật thấp hơn, mình không bị coi là báo cáo sai."

## G11-T09 · Đồng nghiệp đề xuất đổi toàn bộ hệ thống logging
Lớp: T
Nguồn: gốc
Tags: tooling, migration, decision

### Sếp hỏi
Đồng nghiệp mới đề xuất đổi toàn bộ hệ thống logging sang công cụ "tốt hơn" đang hot, trong khi hệ thống hiện tại chạy ổn dù không hoàn hảo. Hỏi gì trước khi đồng ý, và khi nào thật sự nên đổi?

### Chốt kỹ thuật
- Hỏi: vấn đề cụ thể nào đang gặp mà công cụ hiện tại không giải quyết được (có sự cố nào bị chậm vì thiếu log không)? Chi phí migrate (người, thời gian, dữ liệu cũ)? Chi phí vận hành mới? Ai duy trì? Rủi ro khóa vào nhà cung cấp? Có thể cải thiện công cụ hiện tại không?
- Nên đổi khi: chi phí hiện tại tăng không bền vững, thiếu năng lực quan trọng (trace phân tán, truy vấn theo phiên), công cụ cũ ngừng hỗ trợ, hoặc yêu cầu tuân thủ.
- Cách làm an toàn: thử song song trên một service, đo lợi ích, rồi quyết định.

### Ví dụ tư vấn
"Bên em đánh giá đổi công cụ dựa trên vấn đề cụ thể và chi phí, không vì công cụ mới đang thịnh hành."

### Ví dụ đàm phán
Với đồng nghiệp: "Ý tưởng hay. Mình thử trên một service trong 2 tuần và đo xem tìm lỗi nhanh hơn bao nhiêu, có số thì dễ thuyết phục cả team."

## G11-T10 · Chi phí tăng 15%/tháng khi traffic chỉ tăng 5%
Lớp: T
Nguồn: gốc
Tags: cost-analysis, investigation

### Sếp hỏi
Chi phí vận hành agent của một khách lớn tăng đều 15%/tháng suốt 3 tháng dù traffic chỉ tăng 5%/tháng. Liệt kê ít nhất 5 nguyên nhân, kế hoạch điều tra và mốc báo cáo cho khách.

### Chốt kỹ thuật
- Prompt phình dần (thêm quy tắc, ví dụ, tool mới): đo token vào trung bình theo tháng.
- Lịch sử hội thoại dài hơn (người dùng dùng lâu hơn, không compaction): đo token theo số lượt.
- Số bước agent mỗi tác vụ tăng (tác vụ phức tạp hơn, retry, tự sửa): đo số lời gọi LLM mỗi tác vụ.
- Cache hit giảm (dữ liệu thay đổi, prompt đổi làm vô hiệu prompt cache): đo hit rate.
- Fallback sang model đắt hơn nhiều hơn (model chính lỗi): đo phân phối model thực tế.
- Kho tài liệu lớn lên, đưa nhiều chunk hơn vào context.
- Thay đổi hành vi người dùng (câu hỏi dài, tải tài liệu).
- Kế hoạch: tuần 1 phân rã chi phí = traffic × lời gọi/tác vụ × token/lời gọi × giá; tìm thành phần tăng. Báo cáo sơ bộ cho khách sau 1 tuần, kế hoạch tối ưu sau 2 tuần.

### Ví dụ tư vấn
"Bên em đã tách chi phí thành bốn phần và thấy phần tăng chủ yếu do hướng dẫn cho AI dài thêm sau các tính năng mới. Bên em sẽ tối ưu và báo lại mức tiết kiệm sau 2 tuần."

### Ví dụ đàm phán
"Phần tăng do thiết kế bên em thì bên em tối ưu không tính phí. Phần tăng do anh/chị dùng nhiều hơn thì bên em đề xuất các lựa chọn giảm."

## G11-T11 · Rollback dữ liệu agent ghi sai (50 hóa đơn nhầm)
Lớp: T
Nguồn: gốc
Tags: data-repair, governance

### Sếp hỏi
Rollback prompt thì dễ, nhưng agent đã tạo nhầm 50 hóa đơn thì sao? Đề xuất quy trình, và ai có quyền quyết định "sửa trực tiếp trong database" trong tình huống khẩn cấp?

### Chốt kỹ thuật
- Dừng nguồn lỗi trước: tắt tính năng hoặc chuyển sang duyệt người.
- Xác định phạm vi: truy vết từ audit log mọi bản ghi agent tạo trong khoảng thời gian, kèm trace id.
- Sửa qua nghiệp vụ thay vì sửa DB: hủy hóa đơn bằng chức năng hủy chính thức (sinh chứng từ điều chỉnh, giữ dấu vết kế toán), không xóa thẳng.
- Nếu buộc sửa DB: script được review bởi người thứ hai, chạy trong transaction, có bản sao lưu trước, ghi biên bản.
- Quyền quyết định: chủ sở hữu nghiệp vụ (kế toán trưởng với hóa đơn) cùng kỹ thuật trưởng; quy trình break-glass được định nghĩa trước.
- Thông báo khách bị ảnh hưởng nếu chứng từ đã gửi đi.

### Ví dụ tư vấn
"Bên em đã dừng tính năng, xác định đúng 50 hóa đơn bị ảnh hưởng và hủy bằng quy trình hủy chính thức để sổ sách vẫn đúng luật."

### Ví dụ đàm phán
"Bên em đề xuất thêm bước duyệt cho tạo hóa đơn trong 2 tuần, rồi gỡ dần khi số liệu cho thấy ổn định."

## G11-T12 · Tính năng viral làm chi phí tăng vọt ngày đầu
Lớp: T
Nguồn: gốc
Tags: cost-control, launch, ux

### Sếp hỏi
Tính năng mới launch khiến chi phí API tăng vọt ngày đầu, nhưng đang được PR trên mạng xã hội, tắt đột ngột ảnh hưởng hình ảnh. Phương án cân bằng trong 24 giờ đầu?

### Chốt kỹ thuật
- Giảm chi phí mỗi lượt không làm người dùng thấy: chuyển sang model rẻ hơn cho phần lớn lượt, cache kết quả phổ biến, rút gọn prompt, giới hạn độ dài output.
- Giới hạn có thiết kế: số lượt mỗi người mỗi ngày, hàng đợi với thông báo "nhiều người đang dùng", ưu tiên người dùng đăng nhập hoặc trả phí.
- Ngân sách cứng có cảnh báo theo giờ.
- Truyền thông: biến giới hạn thành thông điệp tích cực ("đang có rất nhiều người dùng, bạn còn 5 lượt hôm nay").
- Sau 24 giờ: đánh giá giá trị (chuyển đổi, đăng ký) so với chi phí để quyết định mô hình lâu dài.

### Ví dụ tư vấn
"Bên em giữ tính năng chạy nhưng chuyển sang chế độ tiết kiệm và giới hạn số lượt mỗi người, người dùng vẫn trải nghiệm được và chi phí trong tầm kiểm soát."

### Ví dụ đàm phán
Với bộ phận marketing: "Mình giữ được hình ảnh, nhưng cần thống nhất ngân sách tối đa mỗi ngày. Vượt ngân sách thì tự chuyển sang hàng đợi."
