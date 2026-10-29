---
group: G03
title: Kiến trúc agent
part: I
---

# Nhóm 3 — Kiến trúc agent

## G03-A01 · Workflow hay agent: debug, audit và chi phí kiểm thử
Lớp: A
Nguồn: gốc
Tags: workflow, agent, audit, testing

### Sếp hỏi
Workflow và agent không chỉ khác nhau ở "ai quyết định bước tiếp theo". Về khả năng debug, audit và chi phí kiểm thử trước khi release, hai lựa chọn này khác nhau thế nào? Cho một ví dụ bạn chọn workflow dù agent "thông minh hơn".

### Chốt kỹ thuật
- Workflow: đồ thị bước cố định do code quyết định. Số đường đi hữu hạn và liệt kê được, nên mỗi nhánh có unit test riêng, log đọc theo thứ tự đã biết, chi phí mỗi request gần như hằng số.
- Agent: model chọn bước tiếp theo. Số trajectory gần như vô hạn, nên audit phải lưu toàn bộ chuỗi thought/action/observation, test phải chuyển từ "phủ nhánh" sang "đo tỷ lệ thành công trên bộ eval" (cần vài trăm case và chạy lặp vì kết quả không tất định).
- Debug: workflow lỗi ở bước nào là biết ngay; agent lỗi có thể do một quyết định sai từ 3 bước trước, phải replay trajectory.
- Chi phí: agent có đuôi phân phối dài (p99 token và latency gấp 5–10 lần p50) vì có thể lặp; workflow thì chặn trên được.
- Ví dụ chọn workflow: quy trình hoàn tiền (kiểm tra đơn → kiểm tra chính sách → tính tiền → gọi API hoàn tiền). Rủi ro tài chính cao, kiểm toán cần chứng minh đường đi, nên LLM chỉ dùng ở các nút hẹp (đọc lý do khách viết, phân loại) còn luồng do code nắm.
- Quy tắc: bắt đầu bằng workflow, chỉ trao quyền quyết định cho model ở chỗ không liệt kê trước được các nhánh.

### Ví dụ tư vấn
"Workflow giống dây chuyền có checklist: chậm đổi hơn nhưng lúc nào cũng biết hàng đang ở trạm nào. Agent giống nhân viên tự xoay xở: linh hoạt hơn nhưng muốn kiểm tra lại phải xem cả nhật ký làm việc. Với việc liên quan tới tiền, bên em đề xuất dây chuyền có checklist."

### Ví dụ đàm phán
Khách: "Bên kia nói làm agent tự động hoàn toàn, sao bên anh chỉ làm workflow?" → "Bên em làm được agent, nhưng với hoàn tiền thì workflow rẻ hơn khi kiểm thử và khi kiểm toán. Anh/chị trả ít hơn cho phần QA và ít rủi ro hơn khi có tranh chấp. Phần đọc hiểu yêu cầu của khách vẫn dùng AI."

## G03-A02 · Pattern workflow không đưa vào production doanh nghiệp
Lớp: A
Nguồn: gốc
Tags: patterns, evaluator-optimizer, sla

### Sếp hỏi
Trong các pattern workflow (prompt chaining, routing, parallelization, orchestrator-worker, evaluator-optimizer…), pattern nào bạn sẽ không bao giờ dùng cho khách doanh nghiệp trong production? Vì sao?

### Chốt kỹ thuật
- Không dùng evaluator-optimizer dạng vòng lặp mở (lặp tới khi evaluator hài lòng). Chi phí và độ trễ không có chặn trên nên không cam kết được SLA; hai model có thể "tự đồng ý sai" với nhau.
- Orchestrator-worker để orchestrator tự sinh số worker không giới hạn cũng loại trừ vì chi phí bùng nổ theo dữ liệu đầu vào.
- Nếu buộc dùng: giới hạn cứng số vòng (2–3), ngân sách token mỗi request, điều kiện dừng dựa trên kiểm tra khách quan (schema, test, rule) thay vì điểm của LLM, và đường lui sang người duyệt.
- Câu trả lời tốt là "không dùng dạng không chặn trên", chứ không phải loại bỏ hẳn một pattern.

### Ví dụ tư vấn
"Có cách cho AI tự sửa bài tới khi đạt, nhưng không ai biết trước nó sửa mấy lần. Bên em giới hạn tối đa 2 lần sửa, quá thì chuyển người xem, để hóa đơn hàng tháng của anh/chị không có bất ngờ."

### Ví dụ đàm phán
Khách đòi "cứ cho nó lặp tới khi hoàn hảo": "Bên em làm được, nhưng sẽ không cam kết được thời gian phản hồi và chi phí trần. Nếu anh/chị chấp nhận điều khoản chi phí theo thực tế thì làm, còn muốn giá cố định thì cần giới hạn số vòng."

## G03-A03 · Ba điểm sinh lỗi dây chuyền của ReAct
Lớp: A
Nguồn: gốc
Tags: react, validation, tool-calling

### Sếp hỏi
ReAct loop có 3 điểm sinh lỗi dây chuyền: thought sai, action sai, observation bị hiểu sai. Với mỗi điểm, nêu một cơ chế chặn cụ thể bạn sẽ xây, không phải "viết prompt tốt hơn".

### Chốt kỹ thuật
- Thought sai: buộc model ra kế hoạch có cấu trúc (bước, tool dự định, lý do) và kiểm tra bằng code: tool có tồn tại, có nằm trong quyền của phiên không, bước có lặp lại y hệt bước trước không (phát hiện vòng lặp). Có thể thêm một model nhỏ chấm "kế hoạch có khớp câu hỏi không" cho luồng rủi ro cao.
- Action sai: JSON schema validation chặt (enum, min/max, regex định dạng mã), whitelist tham số, kiểm tra nghiệp vụ trước khi gọi (số tiền ≤ hạn mức, mã đơn thuộc đúng khách). Lỗi validation trả về dạng có cấu trúc để model sửa, tối đa N lần.
- Observation hiểu sai: tool trả structured output có trường rõ nghĩa (status, data, error_code) thay vì text; cắt và tóm tắt output lớn trước khi đưa lại cho model; đối chiếu câu trả lời cuối với dữ liệu tool (ví dụ con số trong câu trả lời phải xuất hiện trong observation).
- Thêm giới hạn: số bước tối đa, phát hiện gọi lặp cùng tool cùng tham số.

### Ví dụ tư vấn
"Mỗi lần AI định làm gì, hệ thống kiểm tra như kế toán kiểm chứng từ: đúng mẫu không, đúng thẩm quyền không, số tiền có vượt hạn mức không. Sai mẫu thì trả lại, không thực hiện."

### Ví dụ đàm phán
Khách muốn bỏ lớp kiểm tra cho rẻ: "Lớp này chạy bằng code nên gần như không tốn tiền AI. Nó là thứ chặn chuyện chuyển nhầm đơn của khách A sang khách B. Bỏ nó đi thì tiết kiệm vài ngày công nhưng rủi ro mỗi ngày vận hành."

## G03-A04 · Khi nào plan-and-execute bị lỗ
Lớp: A
Nguồn: gốc
Tags: planning, react, cost

### Sếp hỏi
Plan-and-execute tốn thêm một lượt gọi LLM để lập kế hoạch. Khi nào khoản đầu tư này "lỗ", tức ReAct thuần vẫn rẻ và tốt hơn?

### Chốt kỹ thuật
- Lỗ khi tác vụ ngắn (≤3 bước), các bước phụ thuộc chặt vào kết quả bước trước (kế hoạch lập sẵn sẽ sai ngay sau observation đầu tiên và phải replan), hoặc môi trường thay đổi liên tục.
- Lời khi tác vụ dài (≥5 bước), có nhiều bước độc lập chạy song song được, bước tốn kém nên cần duyệt kế hoạch trước, hoặc cần cho người xem kế hoạch trước khi chạy.
- Đo bằng: tổng token và latency end-to-end trên bộ eval, tỷ lệ replan. Tỷ lệ replan > 30% là dấu hiệu kế hoạch ban đầu vô ích.
- Biến thể rẻ: model nhỏ lập kế hoạch, model lớn chỉ dùng ở bước khó.

### Ví dụ tư vấn
"Đi chợ mua 2 món thì không cần viết danh sách. Đi siêu thị mua 30 món thì viết danh sách trước sẽ nhanh hơn. Bên em chỉ thêm bước lập kế hoạch cho những việc dài."

### Ví dụ đàm phán
"Bước lập kế hoạch tốn thêm khoảng 10–15% chi phí mỗi tác vụ dài, đổi lại giảm số lần làm lại. Với tác vụ ngắn bên em không bật, nên anh/chị không trả tiền thừa."

## G03-A05 · Orchestrator-worker không giảm độ trễ tuyến tính
Lớp: A
Nguồn: gốc
Tags: parallelization, latency, tail-latency

### Sếp hỏi
Orchestrator-worker với 5 worker song song: chi phí token tăng gần như tuyến tính nhưng độ trễ tổng không giảm tuyến tính. Vì sao, và điểm nào bạn dừng thêm worker?

### Chốt kỹ thuật
- Latency = thời gian lập kế hoạch + max(thời gian các worker) + thời gian tổng hợp. Phần lập kế hoạch và tổng hợp là tuần tự (định luật Amdahl), và phần tổng hợp còn dài thêm khi có nhiều kết quả hơn.
- Max của N biến ngẫu nhiên tăng theo N: càng nhiều worker, càng dễ dính một worker rơi vào đuôi p99 (rate limit, retry).
- Rate limit của nhà cung cấp (RPM/TPM) làm worker thực ra xếp hàng.
- Dừng khi: thêm worker không giảm p95 end-to-end trên bộ đo, hoặc phần tuần tự đã chiếm > 50% latency, hoặc chạm rate limit. Giảm đuôi bằng timeout từng worker + trả kết quả từng phần, hoặc hedging (gửi trùng cho worker chậm).

### Ví dụ tư vấn
"Chia việc cho 5 người làm song song thì nhanh hơn, nhưng vẫn phải chờ người chậm nhất và mất thời gian ghép lại. Thuê 10 người thay vì 5 thì không nhanh gấp đôi."

### Ví dụ đàm phán
Khách đòi "thêm worker cho nhanh": "Bên em đã đo, từ 5 lên 8 worker chi phí tăng 60% nhưng chỉ nhanh hơn khoảng 10%. Nếu anh/chị cần nhanh hơn, bên em đề xuất cache kết quả và trả lời từng phần trước."

## G03-A06 · Thuế giao tiếp giữa các agent
Lớp: A
Nguồn: gốc
Tags: multi-agent, cost, context

### Sếp hỏi
Multi-agent có "thuế giao tiếp" giữa các agent. Bạn ước lượng thuế này bằng gì, và khi nào nó vượt lợi ích của việc tách agent?

### Chốt kỹ thuật
- Đo: (1) token lặp lại: mỗi agent phải nhận lại ngữ cảnh/tóm tắt từ agent khác; (2) số lượt chuyển giao trung bình mỗi tác vụ; (3) latency thêm của mỗi lượt; (4) lỗi do mất ngữ cảnh khi chuyển giao (đo trên eval: tác vụ fail mà nguyên nhân là agent sau thiếu thông tin agent trước có).
- Vượt lợi ích khi: các agent cần chung phần lớn ngữ cảnh (> 50% token trùng), số lượt chuyển giao lớn hơn số bước nếu một agent tự làm, hoặc tỷ lệ lỗi chuyển giao cao hơn tỷ lệ lỗi chọn tool của một agent gộp.
- Tách đáng khi: việc độc lập chạy song song, cần cô lập quyền truy cập dữ liệu, hoặc ngữ cảnh một agent gộp vượt cửa sổ và làm giảm độ chính xác.

### Ví dụ tư vấn
"Chia phòng ban thì chuyên môn hơn, nhưng mỗi lần chuyển hồ sơ lại phải giải thích lại từ đầu. Nếu hồ sơ phải chuyển qua lại 5 lần thì một người làm trọn gói còn nhanh hơn."

### Ví dụ đàm phán
"Bên em không mặc định làm nhiều agent. Bên em sẽ đo trên dữ liệu thật: nếu tách không giảm lỗi hay độ trễ thì giữ một agent, chi phí xây dựng và vận hành của anh/chị thấp hơn."

## G03-A07 · Chi phí ẩn: 1 agent 40 tool vs 5 sub-agent 8 tool
Lớp: A
Nguồn: gốc
Tags: tool-selection, multi-agent, operations

### Sếp hỏi
Một agent với 40 tool, và một kiến trúc 5 sub-agent mỗi agent 8 tool. Sau 6 tháng chạy production, liệt kê các chi phí ẩn (không phải token) của từng hướng.

### Chốt kỹ thuật
- 1 agent 40 tool: độ chính xác chọn tool giảm khi số tool tăng (tool mô tả gần nhau dễ nhầm); mỗi lần thêm tool phải chạy lại eval toàn bộ vì tool mới có thể "cướp" lượt của tool cũ; một tập quyền rất rộng nên review bảo mật khó; prompt dài khiến mọi request trả token mô tả 40 tool (giảm được bằng prompt cache hoặc tool retrieval).
- 5 sub-agent: đồng bộ state và định dạng chuyển giao; 5 bộ prompt, 5 bộ eval, 5 dashboard; lỗi nằm ở ranh giới (router chọn sai sub-agent) khó quy trách nhiệm; nâng cấp model phải kiểm tra 5 nơi; độ trễ thêm một bước định tuyến.
- Điểm giữa thường tốt: một agent + tool retrieval (chỉ đưa 8–10 tool liên quan vào context theo câu hỏi).

### Ví dụ tư vấn
"Một nhân viên ôm 40 việc thì hay nhầm việc nọ với việc kia. Năm nhân viên mỗi người 8 việc thì ít nhầm hơn nhưng tốn công phối hợp và quản lý. Bên em chọn theo mức nhầm thực đo được."

### Ví dụ đàm phán
"Chi phí vận hành 5 agent cao hơn khoảng 30–50% (giám sát, kiểm thử). Bên em chỉ đề xuất khi số đo cho thấy một agent đang nhầm việc nhiều."

## G03-A08 · Checkpointer phình to
Lớp: A
Nguồn: gốc
Tags: langgraph, checkpointer, state

### Sếp hỏi
Checkpointer lưu state sau mỗi bước. State có cần lưu luôn output trung gian của tool (ví dụ 50.000 dòng dữ liệu) không? Thiết kế gì để checkpointer không phình to?

### Chốt kỹ thuật
- Không. State chỉ giữ những gì cần để resume và để model suy luận: tham chiếu (object storage key, id bảng tạm), metadata (số dòng, schema, hash, thời điểm), và bản tóm tắt.
- Dữ liệu lớn để ở object storage hoặc bảng tạm có TTL; lưu content hash để resume kiểm tra dữ liệu chưa đổi.
- Reducer chỉ nối thêm phần cần thiết; cắt lịch sử message cũ thành tóm tắt; giới hạn kích thước state bằng test (ví dụ fail CI nếu state > 256 KB).
- Dọn checkpoint cũ theo TTL, chỉ giữ checkpoint cuối của luồng đã xong.

### Ví dụ tư vấn
"Hệ thống ghi sổ tiến độ, không chép lại cả kho dữ liệu vào sổ. Sổ ghi 'đã lấy 50.000 dòng, nằm ở kho số X', nên dừng giữa chừng vẫn làm tiếp được mà không tốn chỗ lưu."

### Ví dụ đàm phán
"Thiết kế này giảm chi phí lưu trữ và giúp khôi phục nhanh khi có sự cố. Nó nằm trong kiến trúc chuẩn, không phải hạng mục tính thêm."

## G03-A09 · Tiêu chí bước nào cần người duyệt
Lớp: A
Nguồn: gốc
Tags: human-in-the-loop, risk

### Sếp hỏi
Human-in-the-loop làm chậm agent nhưng giảm rủi ro. Thiết kế tiêu chí quyết định bước nào cần duyệt người, dựa trên giá trị giao dịch, khả năng đảo ngược và độ tin cậy lịch sử của agent ở bước đó.

### Chốt kỹ thuật
- Tính điểm rủi ro mỗi hành động = giá trị (tiền hoặc mức ảnh hưởng) × hệ số không đảo ngược được × (1 − độ chính xác lịch sử của agent ở loại hành động đó, đo từ eval và production).
- Ba vùng: dưới ngưỡng thấp tự chạy; vùng giữa tự chạy nhưng hậu kiểm theo mẫu (sampling 5–10%); trên ngưỡng cao bắt buộc duyệt trước.
- Luật cứng bất kể điểm: hành động không đảo ngược được với bên ngoài (chuyển tiền, gửi email khách, xóa dữ liệu) lần đầu với đối tượng mới luôn duyệt.
- Ngưỡng là tham số theo khách, xem lại hàng tháng; độ chính xác lịch sử cần tối thiểu vài trăm mẫu mới đáng tin.
- Đo chi phí của duyệt: thời gian chờ, tỷ lệ người duyệt bấm "đồng ý" mà không đọc (nếu > 95% đồng ý trong 2 giây, duyệt đã thành hình thức).

### Ví dụ tư vấn
"Giống hạn mức ký duyệt trong công ty: nhân viên tự chi dưới 2 triệu, trên 2 triệu cần trưởng phòng, trên 50 triệu cần giám đốc. AI cũng có hạn mức, và hạn mức nới dần khi nó chứng minh làm đúng."

### Ví dụ đàm phán
Khách muốn bỏ duyệt: "Bên em đề xuất giữ duyệt cho 10% giao dịch giá trị cao nhất, 90% còn lại tự động. Sau 2 tháng nếu tỷ lệ đúng trên 99,5% thì nâng ngưỡng."

## G03-A10 · Self-correction thật hay chỉ lặp lại sai theo kiểu khác
Lớp: A
Nguồn: gốc
Tags: self-correction, loop, metrics

### Sếp hỏi
Agent "tự sửa lỗi": khi nào là tiến bộ thật, khi nào chỉ là lặp lại sai theo cách khác? Đo bằng tín hiệu gì?

### Chốt kỹ thuật
- Tiến bộ thật cần tín hiệu khách quan bên ngoài model: số test pass, số lỗi validation, số trường hợp lệ. Mỗi vòng phải giảm đơn điệu số lỗi hoặc giải quyết lỗi khác loại mà không tái phát lỗi cũ.
- Dấu hiệu lặp vô ích: tập lỗi dao động (sửa A thì hỏng B, sửa B lại hỏng A), output vòng sau gần giống vòng trước (similarity > 0,95), hoặc model chỉ đổi cách diễn đạt.
- Tín hiệu để đo: đồ thị số lỗi theo vòng, khoảng cách chỉnh sửa giữa các vòng, phân loại lỗi mỗi vòng.
- Dừng sau N vòng (thường 2–3) không hội tụ và escalate. Thống kê trên eval: nếu vòng 3 hiếm khi cứu được case nào thì giảm trần xuống 2.

### Ví dụ tư vấn
"Sửa bài mà điểm kiểm tra tăng dần là tiến bộ. Sửa đi sửa lại mà lỗi chỉ đổi chỗ thì dừng lại hỏi người."

### Ví dụ đàm phán
"Vòng tự sửa thứ 3 trở đi tốn tiền nhưng gần như không thêm đúng. Bên em giới hạn 2 vòng, tiết kiệm cho anh/chị mà không giảm chất lượng."

## G03-A11 · Node không quay đầu được trong LangGraph
Lớp: A
Nguồn: gốc
Tags: langgraph, side-effect, idempotency, outbox

### Sếp hỏi
Trong LangGraph, node nào là "điểm không quay đầu được", tức qua node đó thì checkpointer thông thường không rollback nổi? Thiết kế gì cho các node này?

### Chốt kỹ thuật
- Node có side effect ra ngoài hệ thống: chuyển tiền, gửi email/SMS, ghi vào hệ thống bên thứ ba, gọi API không idempotent. Checkpointer chỉ khôi phục state nội bộ, không thu hồi được hành động bên ngoài; resume từ checkpoint trước node đó còn có thể chạy lại hành động lần hai.
- Thiết kế: tách node side effect riêng, có interrupt chờ xác nhận trước; dùng idempotency key sinh từ (thread_id, bước, payload hash) để chạy lại không nhân đôi; outbox pattern: ghi "ý định" vào DB trong cùng transaction với state, worker riêng thực thi và ghi kết quả.
- Định nghĩa compensation (hoàn tiền, gửi email đính chính) cho từng hành động thay vì hy vọng rollback (saga pattern).
- Ghi audit log trước và sau khi gọi bên ngoài để biết hành động đã thực hiện hay chưa khi sự cố xảy ra đúng lúc giữa chừng.

### Ví dụ tư vấn
"Hệ thống có thể 'quay lại' trong sổ sách của mình, nhưng email đã gửi thì không rút lại được. Nên bước gửi email hay chuyển tiền luôn được kiểm tra kỹ và chỉ chạy đúng một lần."

### Ví dụ đàm phán
"Cơ chế chống chạy hai lần là hạng mục bắt buộc cho mọi bước liên quan tiền. Bỏ nó đi thì một sự cố mạng có thể làm khách hàng của anh/chị bị trừ tiền hai lần."

## G03-A12 · Phần dùng chung và phần custom 20% cho 3 khách
Lớp: A
Nguồn: gốc
Tags: architecture, multi-tenant, config

### Sếp hỏi
Ba agent production cho ba khách hàng, cùng framework nhưng mỗi khách custom khác nhau 20%. Kiến trúc hóa phần dùng chung và custom thế nào để không phải sửa 3 nơi mỗi khi có bug chung?

### Chốt kỹ thuật
- Core là một package có version (semver): runtime agent, router LLM, guardrail, logging, eval harness.
- Phần khách hàng là cấu hình + plugin: prompt override, tập tool được bật, business rule, ngưỡng duyệt, giọng văn. Plugin đi qua interface rõ ràng (hook trước/sau mỗi bước) thay vì fork code.
- Mỗi khách có bộ eval riêng chạy trên mỗi bản core mới; nâng core theo kiểu canary từng khách.
- Cấm fork: mọi nhu cầu custom vượt cấu hình phải được đưa thành điểm mở rộng của core.
- Đánh dấu feature flag theo khách để tắt nhanh khi lỗi.

### Ví dụ tư vấn
"Giống một mẫu xe có nhiều phiên bản: khung và động cơ chung, nội thất mỗi khách chọn riêng. Sửa lỗi động cơ một lần là cả ba xe được sửa."

### Ví dụ đàm phán
Khách đòi custom sâu: "Phần custom trong khung cấu hình nằm trong giá. Phần custom phải sửa lõi thì bên em tính riêng và phải duy trì riêng, vì nó làm chậm các bản vá bảo mật cho anh/chị."

## G03-A13 · Khi nào tự viết agent loop bằng Python
Lớp: A
Nguồn: gốc
Tags: framework, langgraph, build-vs-buy

### Sếp hỏi
Khi nào bạn chọn viết agent loop thủ công bằng Python thuần thay vì LangGraph/CrewAI/AutoGen? Nêu tiêu chí cụ thể.

### Chốt kỹ thuật
- Tự viết khi: luồng tuyến tính hoặc ít nhánh (≤ 3–4 bước), không cần dừng chờ người rồi resume qua nhiều request, không cần lưu state lâu dài, team cần kiểm soát từng lời gọi (song song hóa, hedging, cache) và loop cơ bản dưới khoảng 200 dòng.
- Dùng framework khi: có vòng lặp và nhánh động, cần checkpoint/resume, human-in-the-loop giữa chừng, streaming từng bước của đồ thị, hoặc nhiều người cùng phát triển cần một mô hình chung.
- Tiêu chí đo: thời gian để thêm một nhánh mới và thời gian để debug một sự cố; nếu framework làm hai con số này tăng thì không đáng.
- Dự án luật lao động của tôi là ví dụ: luồng phân loại, truy hồi, soạn trả lời, kiểm tra trích dẫn viết bằng Python generator và ThreadPoolExecutor, LangGraph để dành khi thêm vòng hỏi lại người dùng.

### Ví dụ tư vấn
"Việc đơn giản thì viết tay cho gọn, dễ sửa. Khi quy trình có nhiều chỗ phải dừng chờ người duyệt rồi làm tiếp, bên em mới dùng khung có sẵn."

### Ví dụ đàm phán
"Bên em chọn công cụ theo độ phức tạp của bài toán, không thêm framework để báo giá cao hơn. Nếu sau này cần, chuyển sang framework mất khoảng 1–2 tuần."

## G03-A14 · Routing bằng LLM vs model nhỏ hay rule ở 1 triệu request/ngày
Lớp: A
Nguồn: gốc
Tags: routing, classifier, cost, latency

### Sếp hỏi
Routing bằng LLM vs model phân loại nhỏ (hoặc rule-based): với 4 nhánh câu hỏi merchant, chi phí, độ trễ và độ chính xác khác nhau thế nào ở quy mô 1 triệu request/ngày?

### Chốt kỹ thuật
- LLM router: 300–1.500 ms, khoảng 200–500 token mỗi lần; 1 triệu request/ngày là 200–500 triệu token/ngày. Chính xác tốt với câu mơ hồ, không cần dữ liệu huấn luyện, nhưng không tất định và phụ thuộc nhà cung cấp.
- Model phân loại nhỏ (fine-tune encoder như PhoBERT, hoặc embedding + logistic regression): 5–30 ms trên CPU, chi phí gần như bằng 0, cần 1–3 nghìn câu gán nhãn, chính xác cao với 4 nhánh rõ ràng.
- Rule: dưới 1 ms, dễ giải thích, vỡ khi cách hỏi đa dạng.
- Thiết kế phân tầng: rule cho case chắc chắn → model nhỏ → chỉ khi confidence thấp (thường 5–10% traffic) mới gọi LLM. Dùng log LLM router làm dữ liệu huấn luyện model nhỏ.
- Liên hệ dự án: dự án luật dùng regex cho chèn lệnh (không gọi LLM) và LLM cho 5 nhóm phân loại vì traffic nhỏ; lên quy mô lớn sẽ chuyển sang phân tầng.

### Ví dụ tư vấn
"Lễ tân phân luồng khách: câu dễ thì chỉ đường ngay, câu khó mới gọi chuyên viên. Gọi chuyên viên cho mọi khách thì vừa chậm vừa tốn."

### Ví dụ đàm phán
"Ở 1 triệu câu mỗi ngày, phân luồng bằng model nhỏ tiết kiệm phần lớn chi phí định tuyến. Bên em cần 2 tuần gán nhãn dữ liệu ban đầu, khoản này hoàn vốn trong tháng đầu."

## G03-A15 · Evaluator-optimizer tự củng cố lỗi
Lớp: A
Nguồn: gốc
Tags: evaluator, bias, eval

### Sếp hỏi
Evaluator-optimizer: hai model "tự đồng ý sai" với nhau là rủi ro thật. Thiết kế gì để vòng lặp này không tự củng cố lỗi?

### Chốt kỹ thuật
- Evaluator khác họ model (khác nhà cung cấp) với optimizer để giảm thiên kiến chung.
- Rubric rõ, chấm từng tiêu chí đạt/không đạt, bắt evaluator trích bằng chứng trong output.
- Ưu tiên kiểm tra khách quan trước LLM: test, schema, rule, đối chiếu dữ liệu nguồn.
- Hiệu chỉnh evaluator định kỳ trên bộ mẫu người đã gán nhãn (đo agreement, Cohen's kappa); kappa giảm là dấu hiệu evaluator lệch.
- Giới hạn số vòng và lấy mẫu kết quả cuối cho người kiểm tra.

### Ví dụ tư vấn
"Không để người viết tự chấm bài của mình, và người chấm cũng phải được kiểm tra lại định kỳ bằng bài có đáp án."

### Ví dụ đàm phán
"Khoản kiểm định người chấm chỉ chiếm vài giờ mỗi tháng, nhưng nó đảm bảo con số chất lượng báo cho anh/chị là thật."

## G03-B16 · "Sao không để AI tự làm hết, cần gì người duyệt?"
Lớp: B
Nguồn: gốc
Tags: human-in-the-loop, client

### Sếp hỏi
Khách hỏi: "Sao không để AI tự làm hết, cần gì bước duyệt của người?" Giải thích bằng ví dụ đời thường, không dùng từ "agent", "LLM", "hallucination".

### Chốt kỹ thuật
- Bản chất: hệ thống xác suất, đúng phần lớn nhưng không đúng tuyệt đối; chi phí của lỗi không đều nhau.
- Duyệt chỉ đặt ở bước giá trị cao hoặc không đảo ngược được; phần còn lại tự động.
- Ngưỡng duyệt nới dần theo số liệu đúng/sai thực tế.

### Ví dụ tư vấn
"Giống nhân viên mới rất nhanh nhẹn: việc nhỏ cho tự làm, việc ký hợp đồng thì trưởng phòng xem qua. Khi nhân viên đó làm đúng đủ lâu, hạn mức được nâng lên. Hệ thống này cũng vậy."

### Ví dụ đàm phán
"Bước duyệt chỉ áp vào khoảng 5–10% việc có giá trị cao. Anh/chị vẫn tự động hóa được phần lớn, mà không phải chịu rủi ro ở những việc lớn."

## G03-B17 · Agent khác chatbot ở đâu mà đắt hơn
Lớp: B
Nguồn: gốc
Tags: agent, chatbot, pricing

### Sếp hỏi
Khách hỏi: "Agent với chatbot khác gì nhau mà agent đắt hơn nhiều?" Trả lời trong 3 câu, không thuật ngữ, đúng bản chất.

### Chốt kỹ thuật
- Chatbot: nhận câu hỏi, trả lời. Agent: tự lấy dữ liệu, tự chọn bước tiếp theo, và thực hiện hành động trên hệ thống thật.
- Đắt hơn vì nhiều bước xử lý mỗi yêu cầu, phải kết nối hệ thống, và phải có lớp kiểm soát khi hành động.

### Ví dụ tư vấn
"Chatbot là người trực tổng đài trả lời câu hỏi. Agent là nhân viên được giao quyền mở hệ thống, tra đơn, và làm luôn việc cho khách. Được giao quyền làm thật thì phải có kiểm soát, đó là phần chi phí thêm."

### Ví dụ đàm phán
"Nếu anh/chị chỉ cần trả lời câu hỏi thì chatbot là đủ và rẻ hơn, bên em làm chatbot. Agent chỉ đáng khi anh/chị muốn hệ thống tự xử lý việc."

## G03-B18 · "ChatGPT làm được mọi thứ rồi"
Lớp: B
Nguồn: gốc
Tags: chatgpt, positioning

### Sếp hỏi
Khách nói: "ChatGPT làm được mọi thứ rồi, sao phải xây riêng hệ thống agent?" Phản biện thế nào mà không chê ChatGPT?

### Chốt kỹ thuật
- Khác biệt không nằm ở độ thông minh mà ở: dữ liệu riêng, kết nối hệ thống nội bộ, quyền và phân quyền, nhật ký kiểm toán, kiểm soát chi phí, và cam kết chất lượng đo được.
- Thường hệ thống riêng vẫn dùng model như ChatGPT bên dưới.

### Ví dụ tư vấn
"ChatGPT như một chuyên gia giỏi bên ngoài. Hệ thống riêng là đưa chuyên gia đó vào công ty, cho đọc đúng tài liệu nội bộ, cho quyền vào đúng phần mềm, và ghi lại mọi việc họ làm. Bên em thường vẫn dùng chính những model đó."

### Ví dụ đàm phán
"Anh/chị cứ dùng ChatGPT cho việc cá nhân, rất hợp. Phần bên em làm là phần ChatGPT không tự làm được: nối vào dữ liệu công ty và chịu trách nhiệm kết quả."

## G03-B19 · "Nhỡ agent làm sai, ai chịu trách nhiệm?"
Lớp: B
Nguồn: gốc
Tags: liability, guardrail, contract

### Sếp hỏi
Khách lo: "Nhỡ agent tự động làm sai, ai chịu trách nhiệm?" Trình bày guardrail và human-in-the-loop bằng ngôn ngữ trách nhiệm và hợp đồng.

### Chốt kỹ thuật
- Phân vùng hành động theo rủi ro, mỗi vùng có cơ chế: tự động, hậu kiểm mẫu, duyệt trước.
- Hạn mức cứng (số tiền, số lần mỗi ngày), nhật ký đầy đủ, khả năng hoàn tác.
- Trách nhiệm ghi rõ trong SLA: lỗi do hệ thống vượt guardrail đã cam kết là trách nhiệm nhà cung cấp; quyết định sau khi người của khách đã duyệt là trách nhiệm khách.

### Ví dụ tư vấn
"Giống quy trình ký nháy rồi mới ký chính thức. Hệ thống chỉ tự làm những việc đã thống nhất trong hợp đồng là rủi ro thấp, có hạn mức. Việc lớn luôn có người của anh/chị duyệt, và mọi thao tác đều được ghi lại để tra cứu khi có tranh chấp."

### Ví dụ đàm phán
"Bên em cam kết bằng hợp đồng phần lớp kiểm soát hoạt động đúng. Đổi lại, danh mục việc được tự động phải do hai bên ký duyệt."

## G03-B20 · Vẽ kiến trúc multi-agent cho khách không chuyên
Lớp: B
Nguồn: gốc
Tags: multi-agent, presentation

### Sếp hỏi
Vẽ trong 2 phút kiến trúc multi-agent cho khách không biết kỹ thuật, sao cho họ hiểu "tiền của họ đi vào đâu".

### Chốt kỹ thuật
- 4 hộp: Tiếp nhận yêu cầu → Các trợ lý chuyên trách (tra cứu, tính toán, soạn trả lời) → Kiểm tra và người duyệt → Gửi đi. Một hộp nền: Nhật ký và giám sát.
- Gắn tiền vào từng hộp: chi phí mỗi lần AI xử lý, chi phí kết nối hệ thống, chi phí kiểm soát và giám sát.
- Kết thúc bằng một con số dễ hiểu: chi phí trung bình mỗi yêu cầu.

### Ví dụ tư vấn
"Mỗi yêu cầu đi qua bốn trạm. Tiền của anh/chị trả cho số trạm và số lần AI làm việc ở mỗi trạm, trung bình khoảng X đồng một yêu cầu, và cho phần giám sát để biết nó làm đúng."

### Ví dụ đàm phán
"Nếu anh/chị muốn giảm chi phí, mình có thể bỏ bớt trạm cho loại yêu cầu đơn giản. Bên em chỉ ra trạm nào bỏ được mà không tăng rủi ro."

## G03-C21 · "n8n/Zapier có sẵn rồi"
Lớp: C
Nguồn: gốc
Tags: no-code, n8n, positioning

### Sếp hỏi
Khách nói: "n8n/Zapier có sẵn rồi, sao phải thuê team build riêng?" Trả lời trung thực nhưng vẫn bảo vệ giá trị agent tùy chỉnh khi thực sự cần.

### Chốt kỹ thuật
- n8n/Zapier đủ dùng cho luồng cố định, ít nhánh, dữ liệu có cấu trúc, khối lượng vừa phải.
- Agent tùy chỉnh đáng khi: đầu vào không cấu trúc (email, văn bản, hội thoại), quyết định nhiều nhánh khó biểu diễn bằng kéo thả, yêu cầu eval/kiểm toán/kiểm soát chi phí mà no-code không có, hoặc khối lượng lớn khiến phí theo task của no-code đắt.
- Kết hợp được: n8n cho phần tích hợp, agent cho phần suy luận.

### Ví dụ tư vấn
"Luồng nào cố định thì dùng n8n luôn, rẻ và nhanh. Phần cần đọc hiểu nội dung và quyết định thì bên em làm, rồi gắn vào n8n."

### Ví dụ đàm phán
"Bên em đề xuất cắt khoảng 40% phạm vi sang n8n. Báo giá giảm tương ứng, phần còn lại là chỗ no-code không làm tốt."

## G03-C22 · Đối thủ rẻ hơn 40%
Lớp: C
Nguồn: gốc
Tags: pricing, negotiation

### Sếp hỏi
Khách ép: "Đối thủ báo giá rẻ hơn 40% cho cùng hệ thống agent." Liệt kê các câu hỏi ngược để làm lộ khác biệt ẩn giữa hai báo giá thay vì giảm giá ngay.

### Chốt kỹ thuật
- Phạm vi có gồm bộ eval và regression test không? Bao nhiêu case?
- Có guardrail, hạn mức, người duyệt cho hành động rủi ro không?
- Ai trả chi phí gọi model, có trần chi phí không?
- SLA uptime, thời gian phản hồi sự cố, phạt vi phạm?
- Dữ liệu lưu ở đâu, ai sở hữu code và prompt sau khi kết thúc hợp đồng?
- Bảo trì khi nhà cung cấp model đổi phiên bản tính thế nào?
- Có giám sát chất lượng hàng tháng không?

### Ví dụ tư vấn
"Hai báo giá chỉ so được khi cùng phạm vi. Mình đặt hai báo giá cạnh nhau theo danh sách này, thường chênh lệch nằm ở những mục bị cắt."

### Ví dụ đàm phán
"Nếu sau khi so mà phạm vi giống nhau, bên em sẵn sàng xem lại giá. Nếu khác, bên em có thể làm gói rút gọn bỏ đúng các mục đó để anh/chị thấy giá tương đương."

## G03-C23 · "Chỉ cần 1 con bot là đủ"
Lớp: C
Nguồn: gốc
Tags: multi-agent, honesty

### Sếp hỏi
Khách nói: "Chỉ cần 1 con bot trả lời tất cả, không cần multi-agent phức tạp." Khi khách đúng, thừa nhận thế nào; khi khách sai, chứng minh bằng số liệu gì mà không nghe như bán thêm?

### Chốt kỹ thuật
- Khách đúng khi nghiệp vụ hẹp, ít loại câu hỏi, ít tool: thừa nhận ngay và làm một bot.
- Khách sai khi nhiều miền nghiệp vụ, nhiều tool: đưa số đo từ chính dữ liệu của khách, ví dụ chạy thử 200 câu thật với một bot, đo tỷ lệ chọn sai tool và trả lời sai theo từng miền.
- Đề xuất làm một bot trước, tách khi số đo xấu đi: tự nhiên chứng minh được.

### Ví dụ tư vấn
"Anh/chị nói đúng với nhu cầu hiện tại, mình làm một bot. Bên em đo thêm tỷ lệ trả lời sai theo từng loại câu hỏi; loại nào sai nhiều thì lúc đó mới tách riêng."

### Ví dụ đàm phán
"Bên em không thu thêm cho kiến trúc phức tạp khi chưa cần. Báo giá giai đoạn 1 là một bot, giai đoạn 2 tách chỉ khi số đo chứng minh."

## G03-C24 · Multi-agent thật sự tốt hơn hay chỉ để tính tiền?
Lớp: C
Nguồn: gốc
Tags: multi-agent, criteria

### Sếp hỏi
Khách hỏi dồn: "Multi-agent có thật sự tốt hơn hay chỉ là trend để tính tiền nhiều hơn?" Trả lời thẳng, kèm tiêu chí khách tự kiểm chứng được.

### Chốt kỹ thuật
- Tốt hơn chỉ khi: việc độc lập chạy song song được, cần cô lập quyền dữ liệu giữa các phần, hoặc một agent bị quá tải ngữ cảnh làm sai nhiều.
- Tiêu chí khách tự kiểm: tỷ lệ hoàn thành việc, tỷ lệ phải chuyển người, thời gian phản hồi p95, chi phí mỗi việc, đo trước và sau khi tách trên cùng bộ câu hỏi.

### Ví dụ tư vấn
"Thẳng thắn là nhiều nơi làm multi-agent vì đang mốt. Anh/chị cứ yêu cầu bốn con số này trước và sau khi tách. Không cải thiện thì gộp lại."

### Ví dụ đàm phán
"Bên em đưa bốn con số đó vào điều khoản nghiệm thu. Không đạt thì bên em gộp lại không tính phí."

## G03-A25 · Thiết kế state cho agent chạy nhiều giờ
Lớp: A
Nguồn: bổ sung
Tags: state, long-running, resume

### Sếp hỏi
Một agent xử lý hồ sơ chạy 3 giờ, đi qua 200 bước. Máy chết ở bước 150. Thiết kế state, checkpoint và cơ chế resume thế nào để không làm lại từ đầu và không làm trùng việc đã làm?

### Chốt kỹ thuật
- State tách 3 phần: tiến độ (danh sách đơn vị việc và trạng thái pending/done/failed), dữ liệu tham chiếu (pointer tới kết quả từng đơn vị), và ngữ cảnh suy luận (tóm tắt, không phải toàn bộ lịch sử).
- Checkpoint sau mỗi đơn vị việc, ghi nguyên tử (transaction) cùng với kết quả.
- Mỗi đơn vị việc idempotent: khóa theo id đơn vị, chạy lại thì kiểm tra đã done chưa.
- Lease/heartbeat: worker giữ khóa có thời hạn; chết thì worker khác nhận lại phần chưa xong.
- Tách ngữ cảnh model khỏi tiến độ: resume không cần nạp lại 150 bước vào context, chỉ cần tóm tắt và danh sách còn lại.

### Ví dụ tư vấn
"Giống làm việc theo danh sách tích từng ô. Mất điện thì mở danh sách ra làm tiếp ô chưa tích, không làm lại ô đã tích."

### Ví dụ đàm phán
"Cơ chế này làm tăng khoảng 10% công xây dựng, nhưng một lần sự cố giữa chừng không phải chạy lại 3 giờ và trả lại tiền model cho 150 bước."

## G03-A26 · Ngân sách context cho agent nhiều bước
Lớp: A
Nguồn: bổ sung
Tags: context-engineering, memory, compaction

### Sếp hỏi
Agent đi 30 bước, mỗi observation 3.000 token. Tới bước 20 context đã 60.000 token, chậm và bắt đầu "quên" yêu cầu ban đầu. Bạn quản lý context thế nào?

### Chốt kỹ thuật
- Ghim phần không được mất ở đầu: yêu cầu gốc, ràng buộc, kế hoạch hiện tại.
- Observation cũ thay bằng tóm tắt có cấu trúc (kết luận, dữ liệu then chốt, pointer tới bản đầy đủ); chỉ giữ nguyên văn 2–3 observation gần nhất.
- Tool trả kết quả đã lọc (chỉ trường cần), phân trang thay vì đổ hết.
- Scratchpad/notes ngoài context: agent ghi ghi chú vào bộ nhớ ngoài và đọc lại khi cần.
- Đo: độ chính xác theo độ dài context trên eval; đặt ngưỡng nén (ví dụ khi vượt 50% cửa sổ).
- Prompt caching cho phần đầu cố định để giảm chi phí.

### Ví dụ tư vấn
"Người làm việc lâu cũng phải ghi chú và tóm tắt, không thể nhớ nguyên văn mọi tài liệu đã đọc. Hệ thống cũng ghi tóm tắt để vẫn nhớ đúng việc chính."

### Ví dụ đàm phán
"Quản lý ngữ cảnh tốt giảm 30–60% chi phí cho tác vụ dài. Đây là phần tối ưu bên em làm sẵn, không tính thêm."

## G03-A27 · Agent gọi tool song song: race condition
Lớp: A
Nguồn: bổ sung
Tags: concurrency, tool-calling, consistency

### Sếp hỏi
Model trả về 3 tool call song song: đọc tồn kho, giữ hàng, tạo đơn. Chuyện gì có thể sai và bạn xử lý ở tầng nào?

### Chốt kỹ thuật
- Model không hiểu phụ thuộc: tạo đơn có thể chạy trước khi giữ hàng xong, hoặc đọc tồn kho đã cũ khi giữ hàng.
- Executor phải biết loại tool: tool chỉ đọc chạy song song được; tool ghi chạy tuần tự hoặc theo đồ thị phụ thuộc khai báo sẵn.
- Ghi có điều kiện ở tầng dữ liệu: optimistic locking (version), hoặc giữ hàng bằng một lệnh nguyên tử thay vì đọc rồi ghi.
- Gộp các bước có ràng buộc thành một tool nghiệp vụ duy nhất ("đặt hàng" làm cả giữ hàng và tạo đơn trong một transaction) thay vì để model tự điều phối.

### Ví dụ tư vấn
"Không để trợ lý vừa kiểm kho vừa xuất hàng cùng lúc theo hai tờ phiếu khác nhau. Việc đặt hàng được làm thành một thao tác trọn gói, không thể làm dở dang."

### Ví dụ đàm phán
"Thiết kế tool theo nghiệp vụ tốn thêm vài ngày phân tích lúc đầu nhưng loại bỏ cả một nhóm lỗi bán quá số tồn kho."

## G03-A28 · Đo chi phí và độ trễ của một kiến trúc agent trước khi xây
Lớp: A
Nguồn: bổ sung
Tags: estimation, cost-model

### Sếp hỏi
Trước khi xây, sếp muốn biết chi phí mỗi tháng và độ trễ p95 của kiến trúc bạn đề xuất. Bạn ước lượng thế nào khi chưa có hệ thống?

### Chốt kỹ thuật
- Mô hình chi phí: số request × số lượt gọi LLM trung bình mỗi request × (token vào × giá vào + token ra × giá ra), cộng embedding, rerank, hạ tầng. Tính cho p50 và p95 số bước.
- Lấy số bước và token từ prototype chạy trên 50–100 câu thật, không đoán.
- Độ trễ: tổng các bước tuần tự (mỗi bước = TTFT + token ra / tốc độ sinh), cộng phần tool; bước song song lấy max.
- Thêm biên an toàn 30–50% cho retry, prompt phình theo thời gian, và giá thay đổi.
- Trình bày theo kịch bản thấp/trung bình/cao và đòn bẩy giảm chi phí (cache, model nhỏ cho bước dễ).

### Ví dụ tư vấn
"Bên em chạy thử trên 100 câu hỏi thật của anh/chị, đếm chi phí từng câu rồi nhân lên, kèm ba kịch bản. Anh/chị biết trước trần chi phí trước khi ký."

### Ví dụ đàm phán
"Nếu ngân sách thấp hơn kịch bản trung bình, bên em chỉ ra cụ thể cần đánh đổi gì: trả lời chậm hơn, dùng model nhỏ hơn ở bước nào."

## G03-A29 · Phát hiện và dừng vòng lặp vô hạn
Lớp: A
Nguồn: bổ sung
Tags: loop-detection, budget, safety

### Sếp hỏi
Liệt kê các cơ chế cụ thể để phát hiện và dừng một agent đang lặp vô hạn, theo thứ tự rẻ nhất trước.

### Chốt kỹ thuật
- Trần cứng: số bước tối đa, token tối đa, thời gian tối đa, tiền tối đa mỗi phiên.
- Phát hiện lặp: hash (tool, tham số) xuất hiện lần thứ 3 thì dừng; chuỗi action có chu kỳ.
- Phát hiện không tiến triển: không có tool call mới, không có dữ liệu mới trong K bước.
- Ở tầng hệ thống: cảnh báo phiên có thời lượng hoặc chi phí vượt p99 lịch sử; kill switch theo phiên và theo khách.
- Khi dừng: trả kết quả từng phần và lý do, chuyển người, ghi trajectory để phân tích.

### Ví dụ tư vấn
"Mỗi việc có hạn mức thời gian và tiền. Chạm hạn mức là hệ thống tự dừng, báo lại đã làm tới đâu, chứ không chạy mãi."

### Ví dụ đàm phán
"Trần chi phí mỗi việc là cam kết bên em ghi vào hợp đồng, để không có hóa đơn bất ngờ."

## G03-A30 · Bộ nhớ dài hạn cho agent
Lớp: A
Nguồn: bổ sung
Tags: memory, personalization, privacy

### Sếp hỏi
Agent cần "nhớ" sở thích và lịch sử của người dùng qua nhiều phiên. Thiết kế bộ nhớ dài hạn thế nào, ghi gì, đọc lúc nào, và rủi ro gì?

### Chốt kỹ thuật
- Phân loại: sự kiện (đã làm gì), sự thật về người dùng (sở thích, thông tin hồ sơ), quy trình (cách làm việc hiệu quả).
- Ghi có chọn lọc: model đề xuất mục cần nhớ, có rule lọc (không lưu dữ liệu nhạy cảm, mật khẩu, số thẻ), có hạn sử dụng.
- Đọc: truy hồi theo ngữ cảnh (embedding + metadata người dùng), giới hạn số mục đưa vào prompt.
- Rủi ro: nhớ sai rồi củng cố sai (cần cho người dùng xem và xóa), rò dữ liệu giữa người dùng (khóa theo user_id ở tầng truy vấn), prompt injection qua bộ nhớ (nội dung nhớ được đánh dấu là dữ liệu), và nghĩa vụ xóa theo luật bảo vệ dữ liệu cá nhân.

### Ví dụ tư vấn
"Hệ thống ghi sổ tay về từng khách như một nhân viên chăm sóc khách hàng tốt, nhưng chỉ ghi điều cần thiết, khách xem và xóa được, và sổ của khách này không bao giờ lẫn sang khách khác."

### Ví dụ đàm phán
"Tính năng nhớ tăng trải nghiệm nhưng kéo theo nghĩa vụ tuân thủ dữ liệu cá nhân. Bên em đề xuất bật cho nhóm người dùng đồng ý trước."
