---
group: G05
title: Giao tiếp — function calling, MCP, A2A, streaming
part: I
---

# Nhóm 5 — Giao tiếp: function calling, MCP, A2A, streaming

## G05-A01 · Chuỗi trách nhiệm thực thi tool
Lớp: A
Nguồn: gốc
Tags: function-calling, error-handling

### Sếp hỏi
Model "gọi tool" không thực sự chạy code. Chuỗi trách nhiệm thực thi nằm ở đâu, và nếu một khâu (ví dụ cổng xác thực) chết, model có biết không hay sẽ ảo giác rằng tool đã chạy?

### Chốt kỹ thuật
- Model chỉ sinh JSON (tên tool + tham số). Ứng dụng parse, validate, kiểm quyền, gọi API thật, rồi đưa kết quả về model dưới dạng tool result.
- Model chỉ biết những gì nằm trong tool result. Nếu executor nuốt lỗi và trả chuỗi rỗng hay "ok", model sẽ kết luận đã thành công.
- Thiết kế: tool result luôn có trạng thái tường minh (status: success/error, error_code, retryable), không bao giờ trả rỗng; lỗi hạ tầng (timeout, 401, 503) được phân loại để model biết nên thử lại, báo người dùng hay dừng.
- Câu trả lời cuối về hành động ("đã hủy đơn") phải dựa trên trạng thái xác nhận từ hệ thống đích, có thể kiểm tra lại bằng một lần đọc.
- Log mỗi tool call kèm request id để đối chiếu với log hệ thống đích.

### Ví dụ tư vấn
"AI chỉ viết phiếu yêu cầu. Phần mềm của mình mới là bên thực hiện và phải báo lại rõ 'đã làm' hay 'không làm được, vì sao'. AI chỉ được nói với khách là đã xong khi nhận được xác nhận."

### Ví dụ đàm phán
"Phần xử lý lỗi rõ ràng chiếm khoảng 20% công tích hợp mỗi hệ thống. Bỏ đi thì sẽ có lúc AI báo khách 'đã hoàn tiền' trong khi thực tế chưa."

## G05-A02 · Đặt tên và mô tả tham số optional
Lớp: A
Nguồn: gốc
Tags: tool-schema, prompt-design

### Sếp hỏi
Tool schema có một tham số optional dễ gây hiểu nhầm. Viết lại nguyên tắc đặt tên và mô tả tham số để giảm tỷ lệ model gọi sai, không chỉ dựa vào "mô tả dài hơn".

### Chốt kỹ thuật
- Tên nói lên ngữ nghĩa và đơn vị: `amount_vnd`, `start_date_iso`, `include_cancelled_orders` thay vì `amount`, `date`, `flag`.
- Mô tả theo khuôn: dùng khi nào, không dùng khi nào, mặc định khi bỏ trống là gì, ví dụ giá trị đúng.
- Dùng kiểu chặt: enum thay vì chuỗi tự do, format date, pattern regex, min/max.
- Tránh tham số optional làm thay đổi hành vi lớn: tách thành hai tool rõ nghĩa (`search_orders` và `search_cancelled_orders`).
- Đo: tỷ lệ tool call fail validation và tỷ lệ gọi sai trên bộ eval trước và sau khi sửa schema.

### Ví dụ tư vấn
"Giống thiết kế biểu mẫu cho người mới: mỗi ô có tên rõ, có ví dụ điền mẫu, và ô nào để trống thì ghi rõ hệ thống sẽ hiểu là gì."

### Ví dụ đàm phán
"Rà soát và chuẩn hóa mô tả công cụ là việc làm một lần, giảm lỗi gọi sai rõ rệt, nên bên em luôn đưa vào giai đoạn tích hợp."

## G05-A03 · Ba quyết định kiến trúc MCP ảnh hưởng bảo mật nhất
Lớp: A
Nguồn: gốc
Tags: mcp, security, least-privilege

### Sếp hỏi
MCP giải quyết bài toán "M tool × N agent" nhưng tạo bề mặt tấn công mới. Với MCP server cho khách doanh nghiệp, đâu là 3 quyết định kiến trúc ảnh hưởng nhiều nhất đến bảo mật?

### Chốt kỹ thuật
- Danh tính và ủy quyền: server chạy với quyền của ai? Ưu tiên ủy quyền theo người dùng cuối (OAuth, token phạm vi hẹp) thay vì một service account toàn quyền; xác thực client gọi tới server.
- Phạm vi tool: least privilege, tách tool đọc và ghi, tool ghi có xác nhận; không có tool kiểu "chạy SQL bất kỳ" hay "chạy lệnh shell".
- Ranh giới tin cậy của nội dung: mô tả tool và kết quả tool có thể chứa prompt injection (tool poisoning); pin phiên bản server, review khi mô tả tool thay đổi, coi kết quả tool là dữ liệu không tin cậy.
- Thêm: audit log mọi lời gọi, rate limit, chạy server trong sandbox mạng hạn chế.

### Ví dụ tư vấn
"Cổng kết nối chung giúp AI dùng được nhiều phần mềm, nên phải kiểm soát như cửa ra vào tòa nhà: ai được vào, vào phòng nào, và ghi sổ mọi lượt ra vào."

### Ví dụ đàm phán
"Phần phân quyền và nhật ký là bắt buộc với dữ liệu doanh nghiệp. Bên em không triển khai cổng kết nối nào dùng một tài khoản toàn quyền, kể cả khi làm vậy rẻ hơn."

## G05-A04 · Một MCP server phân quyền hay năm server riêng
Lớp: A
Nguồn: gốc
Tags: mcp, isolation, operations

### Sếp hỏi
Một MCP server phục vụ 5 agent của 5 phòng ban, mỗi phòng chỉ nên thấy tool của mình. Chọn 1 server phân quyền theo client hay 5 server riêng? Đánh đổi vận hành?

### Chốt kỹ thuật
- 1 server: một chỗ deploy, vá lỗi, giám sát; logic chung không lặp. Rủi ro: lỗi ở lớp phân quyền làm lộ tool hoặc dữ liệu sang phòng khác; một sự cố ảnh hưởng cả 5 phòng.
- 5 server: cô lập rõ (mạng, credential, dữ liệu), lỗi khu trú, review bảo mật đơn giản theo từng server. Chi phí: 5 lần deploy, đồng bộ phiên bản code chung.
- Trung gian: một codebase, 5 deployment với cấu hình tool và credential riêng; hoặc gateway phía trước lọc tool theo danh tính.
- Chọn theo độ nhạy dữ liệu: phòng nhân sự, tài chính tách riêng; phòng ít nhạy cảm dùng chung.

### Ví dụ tư vấn
"Có thể làm một tòa nhà với thẻ từ phân tầng, hoặc mỗi phòng ban một tòa riêng. Phòng nhân sự và kế toán bên em đề xuất tòa riêng, các phòng khác dùng chung."

### Ví dụ đàm phán
"Tách riêng cho phòng nhạy cảm tăng chi phí vận hành khoảng X mỗi tháng. Đổi lại một sự cố ở phòng kinh doanh không bao giờ chạm được dữ liệu lương."

## G05-A05 · Agent card A2A công khai gì
Lớp: A
Nguồn: gốc
Tags: a2a, interoperability, disclosure

### Sếp hỏi
Agent card trong A2A công khai thông tin gì là đủ để hai công ty tin tưởng hợp tác, và thông tin gì tuyệt đối không nên public?

### Chốt kỹ thuật
- Công khai: tên, mô tả năng lực, danh sách skill và loại tác vụ, định dạng input/output, phương thức xác thực được hỗ trợ (không phải credential), endpoint công khai, phiên bản, hỗ trợ streaming hay xử lý dài, thông tin liên hệ và chính sách.
- Không public: endpoint nội bộ, credential, chi tiết hạ tầng, prompt và logic nghiệp vụ, tên model và nhà cung cấp nếu là lợi thế cạnh tranh, giới hạn nội bộ có thể bị khai thác.
- Card mở rộng (đầy đủ hơn) chỉ trả sau khi đã xác thực.

### Ví dụ tư vấn
"Giống danh thiếp và bảng dịch vụ: nói mình làm được gì và liên hệ thế nào, không ghi mật khẩu kho hay công thức nội bộ."

### Ví dụ đàm phán
"Bên em soạn bản mô tả công khai và bản cho đối tác đã ký thỏa thuận, để hợp tác dễ mà không lộ bí quyết."

## G05-A06 · Parse JSON đang stream bị cắt giữa chừng
Lớp: A
Nguồn: gốc
Tags: streaming, json, frontend

### Sếp hỏi
Model stream JSON có cấu trúc nhưng bị cắt giữa chừng ở client. Bạn parse JSON chưa hoàn chỉnh để hiển thị tạm UI bằng kỹ thuật gì mà không crash?

### Chốt kỹ thuật
- Partial JSON parser: tự đóng ngoặc, chuỗi đang mở để có object tạm (các thư viện kiểu partial-json, hoặc parser trạng thái tự viết).
- Chỉ render trường đã hoàn chỉnh (chuỗi đã đóng ngoặc kép, mảng phần tử đã xong), đánh dấu trạng thái "đang nhận".
- Tách thành các sự kiện ngữ nghĩa ở server thay vì stream JSON thô: server parse và gửi event `section`, `citation`… từng phần hoàn chỉnh, client không phải parse JSON dở.
- Khi stream đứt: giữ phần đã có, hiện nút thử lại, không ghi đè bằng lỗi.
- Dự án luật lao động: backend nhận JSON đầy đủ từ LLM rồi phát các sự kiện SSE `token`, `section`, `citation` từng phần, nên frontend không cần parse JSON dở.

### Ví dụ tư vấn
"Màn hình hiện dần từng phần câu trả lời đã hoàn chỉnh. Nếu mạng chập chờn, phần đã hiện vẫn giữ nguyên và có nút tải lại phần còn lại."

### Ví dụ đàm phán
"Trải nghiệm hiện dần làm người dùng cảm thấy nhanh gấp nhiều lần dù tổng thời gian như nhau. Đó là phần nằm trong gói giao diện chuẩn."

## G05-A07 · UI khi 3 tool chạy song song khác tốc độ
Lớp: A
Nguồn: gốc
Tags: ux, streaming, progress

### Sếp hỏi
Agent gọi 3 tool song song: 1 trả sau 200 ms, 1 sau 2 s, 1 timeout sau 10 s. UI hiển thị trạng thái "đang chờ" thế nào để người dùng không nghĩ hệ thống treo?

### Chốt kỹ thuật
- Server phát sự kiện tiến độ theo từng tool: started, done, failed, kèm nhãn dễ hiểu ("Đang tra đơn hàng").
- UI hiện danh sách bước với trạng thái riêng; bước xong đánh dấu, bước chậm hiện thời gian đã chờ.
- Sau ngưỡng (ví dụ 3 s) hiện thông báo "đang lâu hơn bình thường", sau timeout hiện kết quả từng phần và lựa chọn thử lại.
- Heartbeat định kỳ để kết nối không bị proxy cắt và UI biết server còn sống.
- Có thể trả lời trước bằng dữ liệu đã có, bổ sung khi tool chậm xong.

### Ví dụ tư vấn
"Giống theo dõi đơn giao hàng: thấy từng chặng đã xong và chặng nào đang chậm, thay vì một vòng xoay không biết bao giờ dừng."

### Ví dụ đàm phán
"Hiển thị tiến độ không làm hệ thống nhanh hơn nhưng giảm đáng kể số người bỏ đi giữa chừng."

## G05-A08 · Webhook trễ, trùng hoặc không đến
Lớp: A
Nguồn: gốc
Tags: webhook, idempotency, reliability

### Sếp hỏi
Webhook bên thứ ba (Zalo, ngân hàng) có thể đến trễ, trùng, hoặc không đến. Hệ thống phản ứng thế nào, và test cả 3 trường hợp trước production bằng cách nào?

### Chốt kỹ thuật
- Nhận: xác thực chữ ký, trả 200 nhanh, đẩy vào hàng đợi, xử lý bất đồng bộ.
- Trùng: idempotency theo event id của bên gửi (bảng processed_events có unique constraint).
- Trễ hoặc sai thứ tự: dùng trạng thái và timestamp, chỉ chuyển trạng thái tiến (state machine), bỏ qua sự kiện cũ hơn trạng thái hiện tại.
- Không đến: job đối soát định kỳ gọi API truy vấn trạng thái sau timeout; với thanh toán, đối soát cuối ngày.
- Test: tool giả lập gửi trễ, gửi trùng, đảo thứ tự, bỏ sự kiện; chaos test trên staging; contract test với sandbox của bên thứ ba.

### Ví dụ tư vấn
"Hệ thống không chỉ chờ ngân hàng báo. Nếu sau một thời gian chưa có tin, nó tự hỏi lại ngân hàng. Báo hai lần thì chỉ ghi nhận một lần."

### Ví dụ đàm phán
"Cơ chế đối soát là bắt buộc với mọi luồng liên quan tiền. Không có nó, đơn đã thanh toán có thể bị treo ở trạng thái chưa thanh toán."

## G05-A09 · Idempotency key sinh phía client bị trùng
Lớp: A
Nguồn: gốc
Tags: idempotency, payments

### Sếp hỏi
Idempotency key sinh phía client: rủi ro gì nếu client bị bug sinh trùng key cho 2 giao dịch khác nhau? Phòng ngừa thêm ở tầng nào?

### Chốt kỹ thuật
- Rủi ro: giao dịch thứ hai bị coi là retry của giao dịch đầu, server trả lại kết quả cũ, giao dịch thật bị mất âm thầm.
- Server lưu (key, hash payload, kết quả). Cùng key khác payload → trả lỗi 409/422 rõ ràng thay vì trả kết quả cũ.
- Scope key theo (client_id, loại thao tác), có TTL.
- Client dùng UUIDv4/v7 sinh mỗi giao dịch mới, không dùng timestamp hay số đếm.
- Giám sát tỷ lệ va chạm key khác payload, cảnh báo khi > 0.

### Ví dụ tư vấn
"Mỗi lệnh có mã riêng để chống làm hai lần. Nếu hai lệnh khác nhau vô tình cùng mã, hệ thống báo lỗi ngay chứ không âm thầm bỏ một lệnh."

### Ví dụ đàm phán
"Kiểm tra này gần như không tốn chi phí vận hành nhưng chặn được một loại lỗi mất giao dịch rất khó phát hiện."

## G05-A10 · Kiểm tra MCP server bên thứ ba
Lớp: A
Nguồn: gốc
Tags: mcp, supply-chain, security

### Sếp hỏi
Agent của bạn gọi một MCP server của bên thứ ba. Bạn kiểm tra gì trước khi cho dùng trong production, ngoài đọc tài liệu?

### Chốt kỹ thuật
- Nguồn gốc: ai phát hành, mã nguồn mở hay đóng, lịch sử bảo trì, chữ ký gói, pin phiên bản và hash.
- Đọc mã hoặc chạy trong sandbox, quan sát: gọi mạng tới đâu, đọc file gì, có gửi dữ liệu ra ngoài không.
- Mô tả tool có chứa chỉ thị ẩn không (tool poisoning); diff mô tả tool mỗi lần nâng phiên bản.
- Quyền tối thiểu: credential riêng phạm vi hẹp, mạng chỉ ra đúng domain cần.
- Độ tin cậy: timeout, rate limit, xử lý lỗi; có SLA không; phương án dự phòng khi server ngừng.
- Pháp lý: dữ liệu đi qua server lưu ở đâu, điều khoản sử dụng.

### Ví dụ tư vấn
"Cài phần mềm của bên ngoài vào hệ thống công ty thì phải kiểm tra như kiểm tra nhà thầu: họ là ai, họ truy cập những gì, và họ có gửi dữ liệu đi đâu không."

### Ví dụ đàm phán
"Đánh giá bảo mật mỗi kết nối bên ngoài mất khoảng 1–2 ngày công. Bên em không bỏ bước này cho kết nối chạm dữ liệu khách hàng."

## G05-A11 · SSE bị proxy gom buffer
Lớp: A
Nguồn: gốc
Tags: sse, nginx, infrastructure

### Sếp hỏi
SSE qua proxy/nginx gom buffer khiến dữ liệu đổ về cuối cùng một lần. Bạn chẩn đoán và sửa ở tầng nào trước khi nghi ngờ code backend?

### Chốt kỹ thuật
- Chẩn đoán: curl -N thẳng vào backend (bỏ qua proxy). Nếu stream đều thì lỗi ở proxy; nếu không thì ở backend.
- Nginx: proxy_buffering off cho location đó, hoặc header X-Accel-Buffering: no; proxy_read_timeout đủ dài; tắt gzip cho text/event-stream (nén cũng gom buffer).
- Header từ backend: Content-Type: text/event-stream, Cache-Control: no-cache, no-transform.
- CDN và load balancer cloud: kiểm tra có hỗ trợ streaming và timeout idle; gửi heartbeat comment (": ping") mỗi 15–30 s.
- Backend: đảm bảo generator yield và flush, không bị middleware gom response (một số middleware đọc toàn bộ body).
- Dự án luật lao động: route /api/chat trả headers Cache-Control: no-cache, no-transform và X-Accel-Buffering: no.

### Ví dụ tư vấn
"Chữ chạy dần bị biến thành hiện cả cục là do một trạm trung chuyển giữ lại hàng rồi mới giao. Bên em chỉnh trạm đó để giao ngay từng phần."

### Ví dụ đàm phán
"Phần này phụ thuộc hạ tầng của anh/chị. Bên em cần quyền chỉnh cấu hình proxy hoặc làm việc với đội hạ tầng của anh/chị."

## G05-B12 · MCP là gì, có phải trả thêm không
Lớp: B
Nguồn: gốc
Tags: mcp, client

### Sếp hỏi
Khách hỏi: "MCP là gì, sao quan trọng, tôi có phải trả thêm tiền không?" Giải thích không dùng từ "protocol", "server", "client".

### Chốt kỹ thuật
- Một chuẩn chung để AI kết nối công cụ và dữ liệu, giống chuẩn ổ cắm.
- Lợi ích: kết nối một lần, nhiều trợ lý AI dùng chung; đổi nhà cung cấp AI không phải làm lại kết nối.
- Chi phí: nằm trong công tích hợp, không phải phí bản quyền.

### Ví dụ tư vấn
"Giống ổ cắm chuẩn: thiết bị nào cũng cắm được. Phần mềm của anh/chị được làm thành 'ổ cắm chuẩn' một lần, sau này trợ lý AI nào cũng dùng được mà không phải nối lại."

### Ví dụ đàm phán
"Không có phí bản quyền. Anh/chị chỉ trả công làm ổ cắm cho từng phần mềm, và làm một lần dùng cho mọi trợ lý."

## G05-B13 · Chữ nhảy từng chữ có phải là chậm
Lớp: B
Nguồn: gốc
Tags: streaming, ux, client

### Sếp hỏi
Khách hỏi: "Sao chat hiện chữ nhảy từng chữ một, chậm thế, có phải AI tính toán lâu không?" Giải thích streaming như lợi ích UX.

### Chốt kỹ thuật
- Model sinh câu trả lời tuần tự từng phần; hiện ngay giúp người dùng đọc trong khi phần sau đang được tạo.
- Tổng thời gian như nhau, nhưng thời gian chờ thấy chữ đầu tiên giảm từ vài giây xuống dưới 1 giây.

### Ví dụ tư vấn
"Giống xem người ta gõ trực tiếp: anh/chị đọc được ngay câu đầu thay vì nhìn màn hình trống 10 giây rồi mới hiện cả đoạn. Tổng thời gian không đổi, nhưng anh/chị bắt đầu đọc sớm hơn nhiều."

### Ví dụ đàm phán
"Nếu anh/chị thích hiện cả đoạn một lần, bên em đổi được, nhưng số liệu cho thấy người dùng bỏ đi nhiều hơn khi phải chờ màn hình trống."

## G05-B14 · AI của tôi có nói chuyện được với AI đối tác không
Lớp: B
Nguồn: gốc
Tags: a2a, maturity, client

### Sếp hỏi
Khách hỏi: "Hệ thống AI của tôi có nói chuyện được với AI của đối tác không (A2A)?" Trả lời đúng mức sẵn sàng thực tế, không thổi phồng.

### Chốt kỹ thuật
- Có chuẩn (A2A) nhưng còn mới; hai bên phải cùng hỗ trợ; vấn đề tin cậy, trách nhiệm và hợp đồng giữa hai hệ thống tự động chưa có thông lệ.
- Thực tế phổ biến: kết nối qua API truyền thống có hợp đồng rõ, AI ở mỗi bên gọi API.
- Có thể thiết kế sẵn để chuyển sang khi đối tác sẵn sàng.

### Ví dụ tư vấn
"Về kỹ thuật thì làm được nếu đối tác cũng theo cùng chuẩn, nhưng chuẩn này mới, ít đối tác đã có. Hiện tại cách chắc chắn nhất vẫn là kết nối phần mềm hai bên như bình thường, AI mỗi bên dùng kết nối đó."

### Ví dụ đàm phán
"Bên em không bán A2A như tính năng sẵn sàng. Nếu đối tác của anh/chị đã hỗ trợ, bên em làm thử một luồng nhỏ trước."

## G05-C15 · MCP với REST API khác gì, sao trả thêm tiền bọc MCP
Lớp: C
Nguồn: gốc
Tags: mcp, rest, honesty

### Sếp hỏi
Khách nói: "MCP với REST API thường khác gì nhau, sao phải trả thêm tiền để bọc thành MCP?" Khi nào MCP đáng tiền, khi nào thẳng thắn nói là không đáng?

### Chốt kỹ thuật
- MCP thêm: mô tả tool chuẩn cho model, khám phá tool động, tái dùng cho nhiều client AI (IDE, desktop, agent riêng), cơ chế ủy quyền chuẩn.
- Đáng khi: nhiều agent hoặc nhiều ứng dụng AI cùng dùng một bộ tool, muốn dùng với công cụ AI có sẵn (Claude Desktop, IDE), hoặc muốn đổi nhà cung cấp model dễ.
- Không đáng khi: một agent, vài API cố định, team kiểm soát cả hai đầu. Gọi REST thẳng qua function calling là đủ.

### Ví dụ tư vấn
"Nếu anh/chị chỉ có một trợ lý gọi hai phần mềm, nối thẳng là đủ và rẻ hơn. Chuẩn MCP đáng làm khi có nhiều trợ lý hoặc muốn nhân viên dùng các công cụ AI phổ biến kết nối vào phần mềm công ty."

### Ví dụ đàm phán
"Bên em bỏ hạng mục bọc MCP khỏi báo giá giai đoạn 1. Khi số trợ lý tăng lên thì làm sau, không phải sửa lại phần đã làm."

## G05-C16 · Bỏ retry và fallback cho tool thanh toán
Lớp: C
Nguồn: gốc
Tags: payments, reliability, negotiation

### Sếp hỏi
Khách ép: "Bỏ bớt retry/fallback cho đỡ phức tạp, giảm giá được không?" Áp dụng cho tool gọi thanh toán, bạn có đồng ý không, thuyết phục bằng rủi ro cụ thể nào?

### Chốt kỹ thuật
- Không đồng ý với thanh toán. Lỗi mạng giữa chừng tạo trạng thái không xác định: tiền có thể đã trừ nhưng hệ thống không biết.
- Retry an toàn cần idempotency key; không có retry + đối soát thì phải xử lý thủ công từng ca.
- Đề xuất trung gian: giảm độ phức tạp ở chỗ khác (bỏ fallback cho tool chỉ đọc, ít quan trọng).

### Ví dụ tư vấn
"Không có cơ chế này, một lần rớt mạng có thể khiến khách bị trừ tiền mà đơn vẫn báo chưa thanh toán. Mỗi ca như vậy là một cuộc gọi khiếu nại và một lần đối soát thủ công."

### Ví dụ đàm phán
"Bên em giữ nguyên cho thanh toán, và đề xuất bỏ cơ chế dự phòng ở ba công cụ tra cứu ít dùng để giảm chi phí tương đương."

## G05-A17 · Thiết kế giao thức sự kiện SSE cho chat agent
Lớp: A
Nguồn: bổ sung
Tags: sse, protocol-design

### Sếp hỏi
Thiết kế bộ sự kiện SSE cho một chat agent có tool, trích dẫn và human-in-the-loop. Những loại sự kiện nào, payload ra sao, xử lý reconnect thế nào?

### Chốt kỹ thuật
- Sự kiện: start (id phiên, id message), step (tên bước, nhãn, trạng thái), token (đoạn chữ), tool_call/tool_result (tóm tắt, không lộ dữ liệu nhạy cảm), citation (id, nhãn, nguyên văn), suggest/approval_required (cần người dùng chọn), error (mã, có thử lại được không), done (thống kê, confidence).
- Mỗi sự kiện có id tăng dần; client gửi Last-Event-ID khi reconnect, server phát lại từ buffer hoặc trả trạng thái đã lưu.
- Phiên bản hóa schema sự kiện; client bỏ qua sự kiện lạ thay vì crash.
- Heartbeat định kỳ.
- Dự án luật lao động dùng start, step, token, section, citation, suggest_rewrite, error, done.

### Ví dụ tư vấn
"Màn hình nhận từng loại thông báo riêng: đang làm bước nào, đoạn chữ mới, điều luật trích dẫn, hay cần anh/chị chọn. Nhờ vậy giao diện hiện đúng thứ cần hiện."

### Ví dụ đàm phán
"Thiết kế rõ ràng từ đầu giúp thêm tính năng mới mà không phải sửa lại giao diện cũ."

## G05-A18 · Structured output: JSON mode, schema, hay tool call
Lớp: A
Nguồn: bổ sung
Tags: structured-output, json-schema

### Sếp hỏi
Bạn cần model trả JSON đúng schema mỗi lần. So sánh prompt "chỉ trả JSON", JSON mode, structured output theo schema và ép qua tool call. Xử lý khi parse fail thế nào?

### Chốt kỹ thuật
- Prompt thuần: rẻ, dễ, nhưng fail vài phần trăm (thêm chữ ngoài JSON, thiếu trường).
- JSON mode: đảm bảo JSON hợp lệ, không đảm bảo đúng schema.
- Structured output theo schema (constrained decoding): đúng schema gần như tuyệt đối; hạn chế với schema phức tạp, có thể giảm chất lượng nội dung khi ràng buộc chặt.
- Tool call: ép qua tham số tool, phổ biến và hỗ trợ rộng.
- Luôn validate bằng Pydantic phía server; fail thì retry có kèm lỗi validation (tối đa 1–2 lần), sau đó chuyển nhà cung cấp hoặc trả lỗi có kiểm soát.
- Dự án luật lao động: router coi parse JSON fail như lỗi nhà cung cấp, nên cuộc đua nhiều model chỉ nhận kết quả parse được.

### Ví dụ tư vấn
"Bên em buộc AI điền vào biểu mẫu cố định thay vì viết tự do, và kiểm tra từng ô trước khi dùng."

### Ví dụ đàm phán
"Dùng tính năng ép biểu mẫu của nhà cung cấp gần như không tốn thêm, nhưng loại bỏ lỗi định dạng làm hỏng giao diện."

## G05-A19 · Hủy request khi người dùng bấm Stop
Lớp: A
Nguồn: bổ sung
Tags: cancellation, cost, streaming

### Sếp hỏi
Người dùng bấm Stop. Làm sao để backend dừng gọi LLM và tool thật sự, không chạy ngầm tốn tiền?

### Chốt kỹ thuật
- Client: AbortController đóng kết nối fetch/SSE.
- Server: phát hiện client ngắt (Starlette: request.is_disconnected(), hoặc lỗi khi ghi vào stream); truyền tín hiệu hủy xuống các tác vụ con qua cancellation token hoặc asyncio cancel.
- LLM streaming: đóng stream với nhà cung cấp để ngừng sinh token (đa số tính tiền theo token đã sinh).
- Tool có side effect đang chạy: không hủy giữa chừng nếu không an toàn; cho chạy xong hoặc dùng compensation.
- Code đồng bộ chạy trong thread pool khó hủy: kiểm tra cờ hủy giữa các bước.
- Đo: token sinh sau khi client ngắt phải gần 0.

### Ví dụ tư vấn
"Bấm dừng là hệ thống ngừng làm thật, không chạy tiếp ở phía sau, nên anh/chị không trả tiền cho câu trả lời không ai đọc."

### Ví dụ đàm phán
"Với lưu lượng lớn, phần này tiết kiệm vài phần trăm chi phí gọi AI mỗi tháng."
