---
group: G08
title: Fullstack
part: I
---

# Nhóm 8 — Fullstack

## G08-A01 · Tool chạy 8 giây không có token để stream
Lớp: A
Nguồn: gốc
Tags: sse, heartbeat, ux

### Sếp hỏi
Tool chạy 8 giây ở backend không có token nào để stream. Thiết kế loại sự kiện heartbeat hoặc "đang xử lý" nào để UI không trông như bị treo?

### Chốt kỹ thuật
- Sự kiện step có nhãn người đọc được ("Đang tra cứu văn bản") phát ngay khi bắt đầu bước, và khi bước kết thúc.
- Heartbeat dạng comment SSE (": ping") mỗi 10–15 giây để proxy không cắt kết nối idle; heartbeat không cần hiển thị.
- Nếu tool có tiến độ đo được (đã xử lý 3/10 tài liệu) thì phát progress.
- UI: hiện bước hiện tại, thời gian đã chờ, sau ngưỡng hiện "lâu hơn bình thường".
- Dự án luật lao động: sự kiện step với các bước retrieve, generate, rewrite được giao diện hiển thị thành "Luồng tra cứu".

### Ví dụ tư vấn
"Trong lúc tra cứu, màn hình nói rõ hệ thống đang làm gì, nên anh/chị biết nó đang chạy chứ không treo."

### Ví dụ đàm phán
"Phần hiển thị tiến độ làm sẵn trong giao diện chuẩn, không tính thêm."

## G08-A02 · AbortController ở client nhưng backend vẫn gọi LLM
Lớp: A
Nguồn: gốc
Tags: cancellation, cost

### Sếp hỏi
AbortController hủy request ở client nhưng backend vẫn đang gọi LLM tốn tiền. Thiết kế cơ chế để backend thực sự dừng khi client bấm Stop.

### Chốt kỹ thuật
- Phát hiện ngắt: với StreamingResponse, khi client đóng, lần ghi tiếp theo ném lỗi hoặc generator bị đóng (GeneratorExit/CancelledError); kiểm tra chủ động bằng request.is_disconnected().
- Lan truyền hủy: dùng asyncio task và cancel; với code đồng bộ trong thread, truyền cờ hủy (threading.Event) kiểm tra giữa các bước và giữa các chunk stream.
- Đóng stream với nhà cung cấp LLM (context manager của SDK) để ngừng sinh.
- Endpoint Stop riêng (POST /cancel/{run_id}) cho trường hợp kết nối không ngắt (ví dụ chạy nền), dùng chung cờ hủy theo run_id.
- Đo token sinh sau thời điểm hủy.

### Ví dụ tư vấn
"Bấm dừng là hệ thống ngừng ngay cả phía máy chủ, không tiếp tục làm và tính tiền cho câu trả lời không ai đọc."

### Ví dụ đàm phán
"Ở quy mô lớn, cơ chế này tiết kiệm vài phần trăm chi phí AI mỗi tháng."

## G08-A03 · tool_calls JSONB hay bảng riêng
Lớp: A
Nguồn: gốc
Tags: postgres, jsonb, schema-design

### Sếp hỏi
Lưu tool_calls dạng JSONB linh hoạt nhưng khó query và báo cáo, lưu bảng riêng cứng schema nhưng khó mở rộng. Tiêu chí nào khiến bạn chọn hướng nào?

### Chốt kỹ thuật
- JSONB khi: schema tool thay đổi thường xuyên, dữ liệu chủ yếu đọc lại nguyên khối (hiện lịch sử, debug), ít truy vấn tổng hợp.
- Bảng riêng khi: cần báo cáo thường xuyên (số lần gọi theo tool, tỷ lệ lỗi, độ trễ), cần ràng buộc và join, dữ liệu lớn cần index theo nhiều cột.
- Lai: bảng tool_call với cột cố định cho trường hay truy vấn (tool_name, status, latency_ms, cost, created_at, message_id) và JSONB cho tham số và kết quả; index GIN cho JSONB nếu cần tìm trong đó.
- Dữ liệu phân tích lớn đẩy sang kho phân tích (ClickHouse, BigQuery) thay vì truy vấn trên DB giao dịch.

### Ví dụ tư vấn
"Những thông tin hay cần thống kê được lưu thành cột riêng để báo cáo nhanh, phần chi tiết lưu nguyên khối để tra cứu khi cần."

### Ví dụ đàm phán
"Thiết kế lai không tốn thêm đáng kể lúc xây, nhưng tránh phải làm lại khi anh/chị bắt đầu cần báo cáo."

## G08-A04 · Cursor pagination khi tin nhắn bị sửa hoặc xóa
Lớp: A
Nguồn: gốc
Tags: pagination, cursor, consistency

### Sếp hỏi
Phân trang lịch sử hội thoại bằng cursor: khi tin nhắn bị sửa hoặc xóa ở giữa, cursor còn đúng không? Thiết kế cursor chịu được dữ liệu thay đổi.

### Chốt kỹ thuật
- Cursor theo khóa sắp xếp bất biến và duy nhất: (created_at, id), không theo offset và không theo updated_at.
- Sửa nội dung không đổi vị trí nên cursor vẫn đúng; client cập nhật tin đã tải qua sự kiện riêng.
- Xóa: soft delete (deleted_at), vẫn giữ hàng để cursor trỏ tới hợp lệ, trả về dạng "tin đã xóa" hoặc lọc bỏ; truy vấn WHERE (created_at, id) < (cursor) vẫn đúng kể cả khi hàng cursor đã bị xóa cứng.
- Cursor mã hóa (base64 JSON có chữ ký) để client không sửa.
- Index phù hợp (thread_id, created_at DESC, id DESC).

### Ví dụ tư vấn
"Hệ thống đánh dấu vị trí theo thời điểm và mã tin nhắn, nên xóa hay sửa một tin ở giữa không làm lệch các trang."

### Ví dụ đàm phán
"Đây là chuẩn kỹ thuật bên em làm mặc định."

## G08-A05 · Client đóng tab giữa StreamingResponse
Lớp: A
Nguồn: gốc
Tags: fastapi, disconnect

### Sếp hỏi
StreamingResponse, client đóng tab giữa chừng: phát hiện bằng tín hiệu gì (không đoán qua timeout), và dừng gọi LLM ngay thế nào?

### Chốt kỹ thuật
- Tín hiệu: ASGI server nhận http.disconnect; Starlette cho request.is_disconnected(); khi ghi vào socket đã đóng, generator async bị hủy (CancelledError) hoặc generator đồng bộ bị đóng.
- Với async generator: bắt CancelledError/GeneratorExit trong finally để đóng stream LLM và hủy task con.
- Với generator đồng bộ (FastAPI chạy trong threadpool): server chỉ phát hiện ở lần yield tiếp theo; nên yield thường xuyên (cả heartbeat) và kiểm tra cờ hủy.
- Tác vụ con chạy trong ThreadPoolExecutor không tự hủy: phải truyền cờ và kiểm tra.
- Liên hệ dự án luật lao động: pipeline là generator đồng bộ, các bước song song chạy trong ThreadPoolExecutor, nên hiện tại nếu client đóng tab thì lượt gọi LLM đang chạy vẫn chạy hết; cải tiến là thêm cờ hủy.

### Ví dụ tư vấn
"Khách đóng trang là hệ thống biết ngay và ngừng làm, không chờ hết giờ."

### Ví dụ đàm phán
"Phần này nằm trong tối ưu chi phí vận hành, bên em làm khi lưu lượng đủ lớn để đáng."

## G08-A06 · JWT httpOnly cookie và CSRF cho endpoint streaming
Lớp: A
Nguồn: gốc
Tags: auth, csrf, security

### Sếp hỏi
JWT trong cookie httpOnly bảo vệ khỏi XSS đánh cắp token nhưng cần xử lý CSRF riêng cho API chat. Thiết kế cụ thể cho endpoint streaming.

### Chốt kỹ thuật
- Cookie SameSite=Lax hoặc Strict, Secure; endpoint chat chỉ nhận POST (không GET) nên Lax đã chặn phần lớn CSRF cross-site.
- Thêm CSRF token (double-submit cookie hoặc synchronizer token) gửi qua header tùy chỉnh (X-CSRF-Token); request có header tùy chỉnh và Content-Type application/json kích hoạt CORS preflight, trang lạ không gửi được.
- CORS chỉ cho origin của mình, credentials true.
- Kiểm tra Origin/Referer phía server.
- EventSource gốc không gửi header tùy chỉnh và chỉ hỗ trợ GET: dùng fetch + ReadableStream để stream POST có header.
- Token ngắn hạn + refresh token xoay vòng.

### Ví dụ tư vấn
"Đăng nhập được giữ an toàn trong trình duyệt, và mỗi yêu cầu chat phải kèm một mã xác nhận mà trang web lạ không có, nên không ai giả mạo được thao tác của người dùng."

### Ví dụ đàm phán
"Bảo mật đăng nhập là phần bắt buộc, bên em làm theo chuẩn OWASP."

## G08-A07 · Load balancer cắt stream sau 60 giây
Lớp: A
Nguồn: gốc
Tags: long-running, polling, resumable

### Sếp hỏi
Load balancer cắt stream sau 60 giây với câu trả lời dài. Thiết kế lại luồng thế nào để không phụ thuộc việc nới timeout hạ tầng?

### Chốt kỹ thuật
- Tách tạo và nhận: POST tạo run trả run_id ngay; worker nền chạy và ghi sự kiện vào store (Redis Streams, Postgres) theo thứ tự có id.
- Client stream từ GET /runs/{id}/events với Last-Event-ID; kết nối bị cắt thì nối lại từ sự kiện cuối, không mất dữ liệu.
- Heartbeat để giữ kết nối dưới ngưỡng idle.
- Dự phòng polling hoặc webhook/notify khi xong cho tác vụ rất dài.
- Lợi ích phụ: người dùng tải lại trang vẫn xem tiếp được, nhiều tab cùng xem một run.

### Ví dụ tư vấn
"Thay vì giữ một đường dây điện thoại liên tục, hệ thống ghi kết quả vào hộp thư và màn hình đọc hộp thư. Đứt kết nối thì đọc tiếp từ chỗ cũ."

### Ví dụ đàm phán
"Kiến trúc này cần thêm hàng đợi và kho sự kiện, tăng khoảng 1–2 tuần công. Bên em đề xuất khi có tác vụ dài trên 1 phút."

## G08-A08 · N+1 khi tải 1.000 hội thoại kèm tin nhắn cuối
Lớp: A
Nguồn: gốc
Tags: sql, denormalization, performance

### Sếp hỏi
N+1 query khi tải 1.000 hội thoại kèm tin nhắn cuối: JOIN hay denormalize (lưu sẵn last_message)? Đánh đổi khi tin nhắn bị sửa hoặc xóa sau đó?

### Chốt kỹ thuật
- Một truy vấn: LATERAL JOIN (SELECT … ORDER BY created_at DESC LIMIT 1) hoặc DISTINCT ON (thread_id), với index (thread_id, created_at DESC). Đủ nhanh cho vài nghìn hội thoại và luôn nhất quán.
- Denormalize: thread.last_message_id/preview/updated_at cập nhật khi thêm tin. Đọc rẻ nhất, cần thiết khi danh sách rất lớn hoặc sắp xếp theo hoạt động gần nhất.
- Đánh đổi: sửa hoặc xóa tin cuối phải cập nhật lại cột denormalized (trigger hoặc trong cùng transaction), nếu không preview sai.
- Phân trang danh sách hội thoại, không tải 1.000 một lần.

### Ví dụ tư vấn
"Danh sách hội thoại hiển thị tin mới nhất mà không phải đọc từng hội thoại một."

### Ví dụ đàm phán
"Tối ưu này làm khi số liệu cho thấy cần, để không thêm độ phức tạp sớm."

## G08-A09 · Endpoint async gọi thư viện blocking
Lớp: A
Nguồn: gốc
Tags: fastapi, asyncio, threadpool

### Sếp hỏi
Endpoint async FastAPI gọi một thư viện đồng bộ (blocking). Các request khác bị ảnh hưởng gì, và sửa bằng cơ chế nào mà không viết lại thư viện?

### Chốt kỹ thuật
- Lời gọi blocking trong async def chặn event loop: mọi request khác trên worker đó đứng chờ, kể cả health check, nên độ trễ tăng vọt và có thể bị coi là chết.
- Sửa: khai báo endpoint là def thường (FastAPI tự chạy trong threadpool); hoặc bọc bằng run_in_threadpool / asyncio.to_thread; tác vụ nặng CPU (embedding) thì chuyển sang process pool hoặc service riêng.
- Giới hạn kích thước threadpool (mặc định khoảng 40) để không cạn; tách pool cho tác vụ dài.
- Phát hiện: bật asyncio debug, đo độ trễ event loop.
- Dự án luật lao động dùng def thường cho route và ThreadPoolExecutor riêng cho các lượt gọi LLM song song.

### Ví dụ tư vấn
"Một việc chậm không được làm cả quầy phục vụ đứng chờ. Việc chậm được giao sang người khác làm, quầy vẫn tiếp khách."

### Ví dụ đàm phán
"Đây là lỗi kiến trúc phổ biến làm hệ thống chậm khi đông người, bên em kiểm tra trong giai đoạn đánh giá hiệu năng."

## G08-B10 · "Sao chat load chậm hơn ChatGPT?"
Lớp: B
Nguồn: gốc
Tags: latency, client

### Sếp hỏi
Khách hỏi: "Sao chat của tôi load chậm hơn ChatGPT?" Phân biệt độ trễ do model, do hạ tầng có thể cải thiện, và do chính khách.

### Chốt kỹ thuật
- Model: kích thước model, độ dài prompt (tài liệu đưa vào), độ dài câu trả lời.
- Hệ thống: các bước tra cứu, kiểm tra, gọi phần mềm của khách; vị trí máy chủ; cache.
- Phía khách: phần mềm nội bộ chậm khi được gọi, mạng, yêu cầu kiểm tra kỹ.
- ChatGPT không tra tài liệu riêng và không kiểm tra căn cứ, nên ít bước hơn.

### Ví dụ tư vấn
"ChatGPT trả lời ngay từ trí nhớ. Hệ thống của anh/chị trước khi trả lời còn tra tài liệu công ty và kiểm tra căn cứ. Trong 6 giây hiện tại có 2 giây tra cứu bên em giảm được, 3 giây AI viết, và 1 giây chờ phần mềm kho của anh/chị."

### Ví dụ đàm phán
"Bên em cam kết phần giảm được của mình. Phần phần mềm nội bộ chậm thì bên em đề xuất cache hoặc làm việc với đội IT của anh/chị."

## G08-B11 · "Dữ liệu chat lưu ở đâu, có an toàn không?"
Lớp: B
Nguồn: gốc
Tags: data-security, client

### Sếp hỏi
Khách hỏi: "Dữ liệu chat của khách hàng tôi lưu ở đâu, có an toàn không?" Trả lời đủ để an tâm mà không lộ chi tiết hạ tầng nhạy cảm.

### Chốt kỹ thuật
- Nêu: vùng lưu trữ (trong nước hay nước ngoài), mã hóa khi lưu và truyền, phân quyền truy cập theo vai trò và nhật ký truy cập, thời hạn lưu và quyền xóa, nhà cung cấp AI không dùng dữ liệu để huấn luyện, chứng chỉ/tiêu chuẩn đang tuân thủ.
- Không nêu: địa chỉ máy chủ, cấu hình mạng, tên tài khoản quản trị.

### Ví dụ tư vấn
"Dữ liệu lưu tại trung tâm dữ liệu ở Việt Nam, được mã hóa, chỉ nhân sự được phân quyền truy cập và mọi lượt truy cập đều được ghi lại. Mặc định lưu 12 tháng, anh/chị yêu cầu xóa lúc nào cũng được."

### Ví dụ đàm phán
"Nếu anh/chị cần chứng nhận hay kiểm toán bảo mật cụ thể, bên em cung cấp tài liệu theo thỏa thuận bảo mật."

## G08-C12 · "Giao diện chat đơn giản, sao tính phí cao?"
Lớp: C
Nguồn: gốc
Tags: production-readiness, negotiation

### Sếp hỏi
Khách nói: "Giao diện chat đơn giản thế, sao tính phí cao, có template free trên mạng?" Phân biệt chi phí "chạy được" với "chạy ổn định với 10.000 người dùng đồng thời".

### Chốt kỹ thuật
- Template giải quyết hiển thị. Production cần: xác thực và phân quyền, lưu và đồng bộ lịch sử, stream ổn định qua proxy và mạng yếu, nối lại khi mất kết nối, hủy, giới hạn tần suất, giám sát lỗi phía client, khả năng truy cập, đa thiết bị, kiểm thử tải.
- Ví dụ cụ thể: 10.000 người cùng mở stream là 10.000 kết nối dài; cấu hình máy chủ, timeout, heartbeat khác hẳn bản demo.

### Ví dụ tư vấn
"Template giống mẫu nhà trên giấy. Bên em làm phần móng, điện nước, phòng cháy để 10.000 người cùng vào không sập."

### Ví dụ đàm phán
"Nếu số người dùng dưới 100 và nội bộ, bên em dùng template và giảm giá phần giao diện. Phần nền chỉ cần khi mở rộng."

## G08-C13 · "Bỏ dashboard chi phí cho đỡ tốn"
Lớp: C
Nguồn: gốc
Tags: observability, cost, negotiation

### Sếp hỏi
Khách ép: "Bỏ phần theo dõi chi phí/dashboard vận hành cho đỡ tốn, cần gì mấy cái đó?" Thuyết phục giữ lại bằng kịch bản cụ thể nào?

### Chốt kỹ thuật
- Kịch bản: một tính năng mới làm prompt dài gấp 3, hoặc một vòng lặp lỗi, hoặc bị lạm dụng; không có dashboard thì chỉ biết khi nhận hóa đơn cuối tháng.
- Dashboard tối thiểu: chi phí theo ngày, theo tính năng, theo khách; cảnh báo vượt ngân sách.

### Ví dụ tư vấn
"Không có đồng hồ đo, một lỗi làm chi phí tăng gấp 3 sẽ chỉ lộ ra khi hóa đơn tới, tức là đã mất 30 ngày tiền. Có cảnh báo thì biết trong vài giờ."

### Ví dụ đàm phán
"Bên em đề xuất bản tối giản: cảnh báo vượt ngân sách và báo cáo tuần, chi phí rất thấp so với một lần sự cố."

## G08-A14 · Lưu lịch sử chat ở client hay server
Lớp: A
Nguồn: bổ sung
Tags: storage, privacy, sync

### Sếp hỏi
Lịch sử chat lưu localStorage hay server? Đánh đổi về quyền riêng tư, đồng bộ, phân tích và chi phí?

### Chốt kỹ thuật
- localStorage: không cần đăng nhập, không tốn DB, dữ liệu ở máy người dùng. Nhược: mất khi xóa trình duyệt, không đồng bộ thiết bị, giới hạn khoảng 5 MB, không phân tích được chất lượng, không gửi lịch sử cho server dùng trừ khi client gửi kèm mỗi request.
- Server: đồng bộ, phân tích, phục vụ human-in-the-loop và eval từ dữ liệu thật. Nhược: nghĩa vụ bảo vệ dữ liệu, cần đăng nhập, chi phí lưu trữ.
- Dự án luật lao động: hội thoại lưu ở localStorage, client gửi lịch sử theo mỗi request; bảng thread/message đã có sẵn để chuyển sang server khi có đăng nhập.

### Ví dụ tư vấn
"Bản thử nghiệm lưu trên máy người dùng cho đơn giản và riêng tư. Khi cần đồng bộ nhiều thiết bị và cải thiện chất lượng từ dữ liệu thật thì chuyển lên máy chủ, kèm chính sách bảo vệ dữ liệu."

### Ví dụ đàm phán
"Lưu trên máy chủ thêm chi phí lưu trữ và nghĩa vụ tuân thủ. Bên em chỉ làm khi anh/chị cần các lợi ích đó."

## G08-A15 · Rate limit cho API chat
Lớp: A
Nguồn: bổ sung
Tags: rate-limit, abuse, cost

### Sếp hỏi
Thiết kế rate limit cho API chat công khai. Đếm theo gì, lưu ở đâu, và khi nào bộ đếm trong bộ nhớ không đủ?

### Chốt kỹ thuật
- Đếm theo: người dùng đăng nhập (ưu tiên), IP (cho khách vãng lai, chú ý NAT nhiều người chung IP), và tổng hệ thống mỗi ngày (chặn hóa đơn bùng nổ).
- Đơn vị: số request, và tốt hơn là token hoặc chi phí, vì câu hỏi dài tốn hơn.
- Thuật toán: sliding window hoặc token bucket.
- Lưu: bộ nhớ trong tiến trình chỉ đúng với một worker và mất khi restart; nhiều worker hoặc nhiều máy thì cần Redis (INCR + EXPIRE, hoặc Lua script) hoặc gateway.
- Trả 429 kèm Retry-After và thông báo dễ hiểu.
- Dự án luật lao động: DemoRateLimitMiddleware đếm theo IP và tổng mỗi ngày trong bộ nhớ, đủ cho một worker HF Spaces.

### Ví dụ tư vấn
"Mỗi người có hạn mức câu hỏi để không ai dùng quá tay làm tăng chi phí của anh/chị."

### Ví dụ đàm phán
"Hạn mức có thể khác nhau theo gói khách hàng, là cơ sở để anh/chị thiết kế gói dịch vụ."
