---
group: G07
title: Knowledge Graph
part: I
---

# Nhóm 7 — Knowledge Graph

## G07-A01 · Khi nào cần knowledge graph thay vì chỉ vector search
Lớp: A
Nguồn: bổ sung
Tags: knowledge-graph, rag, decision

### Sếp hỏi
Khi nào bạn thêm knowledge graph vào hệ thống RAG, khi nào vector search là đủ? Nêu loại câu hỏi cụ thể mà vector search thất bại.

### Chốt kỹ thuật
- Vector search tốt cho câu hỏi một đoạn trả lời được ("thời gian thử việc tối đa").
- Thất bại với: câu hỏi nhiều bước qua quan hệ ("điều nào sửa đổi điều đã được viện dẫn trong bản án X"); câu tổng hợp toàn kho ("các chủ đề chính trong 500 bản án"); câu cần đường đi lịch sử ("điều này đã thay đổi qua những văn bản nào"); câu về thực thể có quan hệ rõ (cấu trúc tổ chức, chuỗi cung ứng).
- Chi phí graph: thiết kế ontology, trích xuất thực thể/quan hệ (LLM tốn tiền và có lỗi), cập nhật, truy vấn phức tạp hơn.
- Thường đủ: quan hệ có cấu trúc sẵn trong dữ liệu (cha-con, dẫn chiếu, thay thế) lưu bằng bảng quan hệ, không cần trích xuất bằng LLM.
- Dự án luật lao động: quan hệ cây Điều-Khoản-Điểm, thay thế và dẫn chiếu lưu trong Postgres, dựng đồ thị tại chỗ cho trang /graph thay vì dùng graph DB.

### Ví dụ tư vấn
"Tìm theo nghĩa giống tra mục lục. Đồ thị quan hệ giống sơ đồ ai liên quan tới ai. Chỉ cần sơ đồ khi câu hỏi của anh/chị đi qua nhiều mối quan hệ."

### Ví dụ đàm phán
"Bên em không xây đồ thị nếu 90% câu hỏi chỉ cần tra cứu. Bên em đo trên câu hỏi thật trước."

## G07-A02 · Thiết kế ontology cho văn bản pháp luật
Lớp: A
Nguồn: bổ sung
Tags: ontology, legal, schema

### Sếp hỏi
Thiết kế ontology (loại node, loại cạnh) cho đồ thị văn bản pháp luật. Những quan hệ nào bắt buộc, quan hệ nào nên bỏ để giữ đơn giản?

### Chốt kỹ thuật
- Node: Văn bản (luật, nghị định, thông tư) với số hiệu, ngày ban hành, hiệu lực; đơn vị cấu trúc (Chương, Mục, Điều, Khoản, Điểm); khái niệm được định nghĩa; cơ quan ban hành; bản án (nếu có).
- Cạnh bắt buộc: CONTAINS (cấu trúc), AMENDS/REPLACES/REPEALS (cấp văn bản và cấp điều khoản, có ngày hiệu lực), GUIDES (nghị định hướng dẫn luật), REFERS_TO (dẫn chiếu "theo quy định tại khoản 2 Điều 35"), DEFINES (khái niệm).
- Cạnh có thời gian: mọi quan hệ thay thế mang ngày, để truy vấn theo mốc.
- Nên bỏ ở giai đoạn đầu: quan hệ ngữ nghĩa mơ hồ ("liên quan tới") do LLM trích xuất, vì nhiễu và khó kiểm chứng.
- Quan hệ cấu trúc và dẫn chiếu trích xuất được bằng regex với độ chính xác cao, nên ưu tiên.

### Ví dụ tư vấn
"Sơ đồ ghi rõ văn bản nào chứa điều nào, điều nào sửa điều nào từ ngày nào, và điều nào dẫn chiếu điều nào. Những quan hệ chắc chắn mới đưa vào."

### Ví dụ đàm phán
"Quan hệ trích bằng quy tắc thì chính xác và rẻ. Quan hệ suy luận bằng AI thì tốn và cần người kiểm tra, bên em để giai đoạn sau."

## G07-A03 · Trích xuất thực thể và quan hệ bằng LLM: kiểm soát chất lượng
Lớp: A
Nguồn: bổ sung
Tags: extraction, entity-resolution, quality

### Sếp hỏi
Dùng LLM trích xuất thực thể và quan hệ từ 100.000 tài liệu. Ba vấn đề chất lượng lớn nhất và cách kiểm soát?

### Chốt kỹ thuật
- Trùng lặp thực thể (entity resolution): "BLLĐ 2019", "Bộ luật Lao động số 45/2019/QH14", "Bộ luật lao động" là một. Giải pháp: chuẩn hóa bằng từ điển và mã định danh, so khớp mờ + embedding, LLM xác nhận cặp nghi ngờ, người duyệt cặp có điểm trung bình.
- Quan hệ bịa hoặc sai hướng: bắt LLM trích kèm câu bằng chứng (span), kiểm tra span có trong văn bản; schema đóng (chỉ loại quan hệ cho phép); validate kiểu node hai đầu.
- Không nhất quán giữa các lần chạy và chi phí: temperature 0, prompt có ví dụ, model nhỏ cho phần lớn và model lớn cho phần khó; cache theo hash đoạn văn.
- Đo: precision/recall trên mẫu gán nhãn 200–500 đoạn; theo dõi tỷ lệ node mồ côi, bậc node bất thường.

### Ví dụ tư vấn
"AI trích xuất nhanh nhưng hay gọi một thứ bằng nhiều tên. Bên em có bước gom tên trùng và bắt AI chỉ ra câu gốc cho mỗi quan hệ."

### Ví dụ đàm phán
"Chi phí trích xuất 100 nghìn tài liệu bằng AI khoảng X. Bên em làm thử 1.000 tài liệu, đo chất lượng, rồi mới chạy toàn bộ."

## G07-A04 · GraphRAG local search vs global search
Lớp: A
Nguồn: bổ sung
Tags: graphrag, communities, summarization

### Sếp hỏi
Giải thích local search và global search trong GraphRAG. Chi phí và khi nào dùng mỗi loại?

### Chốt kỹ thuật
- Local search: tìm thực thể liên quan câu hỏi (bằng embedding), mở rộng hàng xóm, lấy các đoạn văn và quan hệ gắn với chúng làm context. Hợp câu hỏi về thực thể cụ thể. Chi phí gần RAG thường.
- Global search: dùng community detection (Leiden) chia đồ thị thành cụm, LLM tóm tắt từng cụm lúc index; khi hỏi, map câu hỏi qua các tóm tắt cụm rồi reduce. Hợp câu hỏi tổng hợp toàn kho ("xu hướng tranh chấp lao động chính"). Chi phí index rất cao, chi phí truy vấn cao (nhiều lời gọi map).
- Cập nhật: thêm tài liệu làm thay đổi cụm, phải tóm tắt lại.
- Thay thế rẻ hơn cho câu tổng hợp: phân cụm embedding + tóm tắt, hoặc truy vấn có cấu trúc trên metadata.

### Ví dụ tư vấn
"Hỏi về một điều cụ thể thì đi theo các mối quan hệ quanh điều đó. Hỏi 'tổng quan có gì' thì dùng các bản tóm tắt theo nhóm chủ đề đã chuẩn bị sẵn."

### Ví dụ đàm phán
"Tính năng tổng hợp toàn kho tốn chi phí chuẩn bị lớn, bên em chỉ làm khi đây là nhu cầu thường xuyên."

## G07-A05 · Lưu đồ thị trong Postgres hay graph DB
Lớp: A
Nguồn: bổ sung
Tags: neo4j, postgres, recursive-cte

### Sếp hỏi
Bạn chọn lưu đồ thị trong Postgres (bảng cạnh + recursive CTE) hay Neo4j? Tiêu chí?

### Chốt kỹ thuật
- Postgres đủ khi: truy vấn chủ yếu 1–3 bước, đồ thị vài triệu cạnh, cần transaction chung với dữ liệu khác, team quen SQL, muốn ít service. Recursive CTE xử lý được chuỗi thay thế, cây cha-con; index trên (from, type) và (to, type).
- Graph DB khi: truy vấn đường đi sâu và biến đổi (nhiều bước, pattern phức tạp), thuật toán đồ thị thường xuyên (PageRank, community, shortest path), khám phá tương tác bởi analyst, đồ thị rất lớn và dày.
- Chi phí graph DB: thêm service, đồng bộ dữ liệu, kỹ năng Cypher, chi phí bản quyền với tính năng doanh nghiệp.
- Dự án luật lao động ban đầu định dùng Neo4j theo repo gốc, sau chuyển sang Postgres vì quan hệ đơn giản và chỉ cần recursive CTE để lần lịch sử sửa đổi.

### Ví dụ tư vấn
"Ở quy mô hiện tại, một cơ sở dữ liệu là đủ để lưu cả quan hệ. Bên em chỉ thêm hệ thống chuyên dụng khi câu hỏi phức tạp lên."

### Ví dụ đàm phán
"Bỏ một hệ thống chuyên dụng giảm chi phí vận hành và bản quyền hằng năm, mà không mất tính năng anh/chị đang cần."

## G07-A06 · Truy vấn đồ thị theo thời gian (bitemporal)
Lớp: A
Nguồn: bổ sung
Tags: temporal-graph, versioning

### Sếp hỏi
Câu hỏi: "Ngày 1/6/2020, quy định về thời gian thử việc là gì và nó được sửa đổi thế nào sau đó?" Thiết kế mô hình dữ liệu và truy vấn.

### Chốt kỹ thuật
- Mỗi phiên bản điều khoản là một node riêng với valid_from, valid_to (thời gian hiệu lực pháp lý). Có thể thêm thời gian ghi nhận (recorded_at) nếu cần biết hệ thống biết điều đó từ khi nào (bitemporal).
- Cạnh SUPERSEDED_BY giữa phiên bản cũ và mới, kèm loại thay đổi và ngày.
- Truy vấn 1: lọc node theo chủ đề (vector) với valid_from ≤ ngày < valid_to.
- Truy vấn 2: từ node đó đi theo SUPERSEDED_BY (recursive CTE) để ra chuỗi thay đổi.
- Trình bày: dòng thời gian với diff nội dung giữa các phiên bản.
- Dự án luật lao động: /api/law_as_of và /api/node/{id}/history làm đúng hai truy vấn này.

### Ví dụ tư vấn
"Mỗi lần luật sửa, hệ thống giữ cả bản cũ và bản mới kèm ngày. Anh/chị hỏi theo ngày nào thì ra đúng quy định ngày đó, và xem được nó thay đổi ra sao."

### Ví dụ đàm phán
"Lưu lịch sử phiên bản tăng công nạp dữ liệu, nhưng là yêu cầu cốt lõi cho tư vấn pháp lý, nơi sự việc thường xảy ra trong quá khứ."

## G07-A07 · Phát hiện thay đổi giữa hai phiên bản văn bản
Lớp: A
Nguồn: bổ sung
Tags: diff, alignment, amendments

### Sếp hỏi
Có bản cũ và bản mới của một nghị định. Tự động xác định điều nào được giữ nguyên, sửa, thay thế, thêm, bỏ. Thuật toán và ngưỡng?

### Chốt kỹ thuật
- Ghép cặp node lá giữa hai bản: ưu tiên cùng vị trí cấu trúc (số Điều/Khoản) và tiêu đề Điều giống; sau đó ghép theo độ giống nội dung (SequenceMatcher, hoặc embedding cho trường hợp diễn đạt lại).
- Ngưỡng ví dụ (dự án luật lao động dùng lại từ LAWGIC): ghép cặp khi độ giống ≥ 0,75; ≥ 0,995 coi như không đổi; tiêu đề Điều giống ≥ 0,8.
- Phân loại: không đổi, sửa (amended), thay thế (replaced, giống thấp nhưng cùng vị trí), bỏ (removed, không có cặp), thêm (added).
- Tách thay đổi quan trọng: số tiền, số tháng, ngày, "không/được" (phủ định) bằng regex để làm nổi bật.
- Đánh giá trên các cặp văn bản đã biết thay đổi; người duyệt cặp ở vùng ranh giới.
- Ghi kết quả: cạnh thay thế, đóng hiệu lực node cũ.

### Ví dụ tư vấn
"Hệ thống tự so hai bản, tô đậm chỗ thay đổi con số và chỗ đổi 'được' thành 'không được', để chuyên viên chỉ cần xem lại những điểm quan trọng."

### Ví dụ đàm phán
"Tự động phát hiện thay đổi tiết kiệm phần lớn công đọc so sánh, chuyên viên vẫn duyệt kết quả cuối."

## G07-A08 · Trực quan hóa đồ thị cho người dùng
Lớp: A
Nguồn: bổ sung
Tags: visualization, ux, force-graph

### Sếp hỏi
Trang knowledge graph hiển thị vài trăm node thành một mớ rối. Bạn thiết kế lại thế nào để người dùng hiểu được?

### Chốt kỹ thuật
- Bắt đầu từ ngữ cảnh: đồ thị quanh câu hỏi hoặc node đang xem, không phải toàn kho.
- Bố cục phân cấp theo cấu trúc (Văn bản → Chương → Điều → Khoản) thay vì force-directed thuần; force chỉ cho quan hệ chéo.
- Lọc theo loại quan hệ (chip lọc), theo văn bản, theo hiệu lực.
- Thu gọn và mở rộng node (expand on click), giới hạn số node hiển thị.
- Mã hóa trực quan: màu theo loại node, nét đứt cho quan hệ hết hiệu lực, kích thước theo mức quan trọng.
- Bảo đảm toàn vẹn: node thêm sau phải có cạnh nối tới cha, không bị mồ côi (dự án luật lao động có bất biến này trong builder: gom node trước, dựng cạnh sau).
- Panel chi tiết hiển thị nguyên văn và liên kết.

### Ví dụ tư vấn
"Sơ đồ chỉ hiện những gì liên quan tới câu hỏi, sắp theo cấu trúc văn bản, và anh/chị bấm vào đâu thì mở rộng ở đó."

### Ví dụ đàm phán
"Trang sơ đồ là công cụ khám phá cho chuyên viên. Người dùng phổ thông chỉ cần câu trả lời có trích dẫn, nên bên em ưu tiên phần đó trước."

## G07-B09 · Giải thích knowledge graph cho khách
Lớp: B
Nguồn: bổ sung
Tags: client, explanation

### Sếp hỏi
Khách hỏi: "Knowledge graph là gì, nó giúp gì mà tôi phải trả thêm?" Giải thích không dùng thuật ngữ.

### Chốt kỹ thuật
- Bản chất: lưu cả mối quan hệ giữa các thông tin, không chỉ nội dung.
- Lợi ích cụ thể theo câu hỏi khách thật sự hỏi.

### Ví dụ tư vấn
"Tài liệu thường giống đống hồ sơ rời. Đồ thị quan hệ giống sơ đồ ghi rõ hồ sơ nào sửa hồ sơ nào, nhắc tới hồ sơ nào. Nhờ vậy hệ thống trả lời được câu 'quy định này đã thay đổi những lần nào' mà tìm kiếm thường không làm được."

### Ví dụ đàm phán
"Nếu câu hỏi của anh/chị chủ yếu là tra cứu một quy định, không cần phần này. Bên em đưa vào khi anh/chị cần theo dõi thay đổi và liên kết."

## G07-C10 · "Bên kia nói có GraphRAG, sao bên anh không có?"
Lớp: C
Nguồn: bổ sung
Tags: hype, negotiation

### Sếp hỏi
Khách nói: "Bên kia nói có GraphRAG, hiện đại hơn, sao bên anh không đề xuất?" Trả lời thế nào?

### Chốt kỹ thuật
- GraphRAG đáng khi có câu hỏi tổng hợp toàn kho hoặc nhiều bước qua quan hệ; chi phí index cao, cập nhật khó.
- Đề xuất đo: lấy 50 câu hỏi thật, chạy hai cách, so chất lượng và chi phí.

### Ví dụ tư vấn
"GraphRAG mạnh với loại câu hỏi tổng hợp kiểu 'các xu hướng chính'. Câu hỏi của anh/chị chủ yếu là tra cứu quy định cụ thể, nơi cách hiện tại chính xác và rẻ hơn."

### Ví dụ đàm phán
"Bên em sẵn sàng làm thử trên 50 câu hỏi của anh/chị và so kết quả. Nếu GraphRAG tốt hơn rõ rệt, bên em đưa vào."
