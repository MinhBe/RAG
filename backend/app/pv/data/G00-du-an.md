---
group: G00
title: Dự án trợ lý luật lao động
part: 0
---

# Nhóm 0 — Dự án trợ lý pháp luật lao động

## G00-A01 · Giới thiệu dự án trong một phút
Lớp: A
Nguồn: dự án
Tags: overview, pitch
Files: README.md, docker-compose.yml

### Sếp hỏi
Giới thiệu dự án của bạn trong một phút.

### Chốt kỹ thuật
- Trợ lý hỏi đáp pháp luật lao động Việt Nam, mỗi câu trả lời trích dẫn tới Điều, Khoản, Điểm và bấm xem được nguyên văn.
- Kho: Bộ luật Lao động 2019 (hiện hành), Bộ luật Lao động 2012 (hết hiệu lực, để tra theo mốc thời gian), Nghị định 145/2020 và 150 bản án lao động từ Hugging Face.
- Stack: Next.js 15 + React 19, FastAPI, Postgres 17 + pgvector làm cơ sở dữ liệu duy nhất, Docker Compose; demo trên Vercel + Hugging Face Spaces + Neon.
- Ghép ý tưởng từ ba repo: giao diện streaming từ agentailor, tìm kiếm từ LexCompanion, parser + so sánh phiên bản luật + prompt hỏi đáp từ LAWGIC (dùng lại có phép của tác giả). Lõi viết lại từ đầu.
- Điểm nhấn: chống bịa trích dẫn bằng code, phân loại câu hỏi 5 nhóm, xử lý hiệu lực theo thời gian, router nhiều nhà cung cấp LLM.

### Ví dụ tư vấn
"Người lao động hỏi bằng lời thường, hệ thống trả lời dựa trên đúng điều luật còn hiệu lực và chỉ cho họ nguyên văn, thay vì một câu trả lời chung chung không rõ nguồn."

### Ví dụ đàm phán
"Phiên bản hiện tại phục vụ tốt câu hỏi phổ thông trong ba văn bản cốt lõi. Mở rộng thêm văn bản là việc nạp dữ liệu, kiến trúc không phải đổi."

## G00-A02 · Luồng một câu hỏi từ lúc gửi tới lúc hiện câu trả lời
Lớp: A
Nguồn: dự án
Tags: pipeline, sse
Files: backend/app/agent/pipeline.py, backend/app/agent/qa.py, backend/app/api/routes.py

### Sếp hỏi
Một câu hỏi đi qua những bước nào từ lúc người dùng bấm gửi tới lúc hiện câu trả lời?

### Chốt kỹ thuật
- Frontend POST /api/chat kèm lịch sử, nhận luồng SSE.
- Lớp 1: regex phát hiện chèn lệnh trên chữ đã bỏ dấu, chặn ngay không gọi LLM.
- Ba việc song song: LLM phân loại (5 nhóm), truy hồi 8 Điều/Khoản bằng pgvector (tìm kép nếu là câu nối tiếp), LLM soạn câu trả lời JSON từ 8 kết quả.
- Phân loại không phải legal thì bỏ câu trả lời đang soạn và trả lời theo nhóm (lạc đề, ngoài kho, từ mơ hồ → đề xuất câu viết lại).
- Kiểm tra trích dẫn: chỉ giữ node_id có trong kết quả truy hồi; không còn trích dẫn hợp lệ thì đề xuất viết lại hoặc từ chối.
- Phát sự kiện start, step, token, section, citation, done.

### Ví dụ tư vấn
"Hệ thống kiểm tra câu hỏi có hợp lệ không, tìm điều luật liên quan, cho AI soạn trả lời, rồi tự kiểm tra lại mọi trích dẫn trước khi hiện ra."

### Ví dụ đàm phán
"Chạy song song các bước giúp câu hỏi luật không phải chờ thêm bước phân loại, đổi lại tốn thêm một ít chi phí với câu bị loại."

## G00-A03 · Vì sao bỏ Neo4j, chỉ dùng Postgres
Lớp: A
Nguồn: dự án
Tags: postgres, neo4j, architecture
Files: backend/app/db/models.py, backend/app/amend/store.py

### Sếp hỏi
Kế hoạch ban đầu dùng Neo4j. Vì sao chuyển sang chỉ dùng Postgres?

### Chốt kỹ thuật
- Quan hệ cần lưu đơn giản: cây Điều → Khoản → Điểm (parent_id), node cũ bị node mới thay thế (node_supersession), văn bản sửa đổi văn bản (document_relation). Lần lịch sử chỉ cần recursive CTE.
- pgvector cho phép một DB lo cả vector, quan hệ và lịch sử; bớt một service để vận hành, sao lưu, deploy (demo chạy trên Neon miễn phí).
- Đánh đổi: nếu cần truy vấn đồ thị nhiều bước phức tạp giữa hàng chục văn bản thì graph DB tiện hơn; vài nghìn node hiện tại chưa cần.

### Ví dụ tư vấn
"Một cơ sở dữ liệu làm được hết việc ở quy mô này, nên ít thứ phải vận hành và chi phí thấp."

### Ví dụ đàm phán
"Khi dữ liệu và câu hỏi phức tạp lên, kiến trúc cho phép tách phần đồ thị ra sau."

## G00-A04 · SSE thay vì WebSocket
Lớp: A
Nguồn: dự án
Tags: sse, streaming
Files: backend/app/sse.py, frontend/lib/sse.ts

### Sếp hỏi
Vì sao trả kết quả bằng SSE mà không dùng WebSocket?

### Chốt kỹ thuật
- Dữ liệu một chiều từ server về trình duyệt, SSE đủ; chạy trên HTTP thường, dễ qua proxy và CDN; FastAPI trả bằng StreamingResponse.
- Header Cache-Control: no-cache, no-transform và X-Accel-Buffering: no để proxy không gom buffer.
- Sự kiện có tên (step, token, section, citation, suggest_rewrite, done) nên giao diện xử lý theo loại.
- Frontend dùng fetch + ReadableStream (POST được, có body) thay vì EventSource (chỉ GET).

### Ví dụ tư vấn
"Câu trả lời hiện dần và hiển thị từng bước hệ thống đang làm."

### Ví dụ đàm phán
"SSE đơn giản hơn WebSocket để vận hành, không cần hạ tầng đặc biệt."

## G00-A05 · Các bảng chính trong cơ sở dữ liệu
Lớp: A
Nguồn: dự án
Tags: schema, database
Files: backend/app/db/models.py, db/init/001_init.sql

### Sếp hỏi
Mô tả các bảng chính trong cơ sở dữ liệu.

### Chốt kỹ thuật
- legal_document: văn bản, số hiệu, ngày ban hành, ngày hiệu lực, trạng thái.
- legal_node: Điều/Khoản/Điểm với level, article_no, clause_no, point_letter, parent_id, nội dung, text_hash, seq, effective_from/to, embedding vector(1024).
- node_supersession: node cũ → node mới, loại thay đổi (amended, replaced, removed, added), độ giống.
- document_relation: AMENDS, REPLACES, GUIDES.
- precedent: bản án/án lệ, nội dung markdown, embedding.
- thread, message: khung lưu hội thoại phía server; hiện giao diện lưu ở localStorage.
- Extension: vector, pg_trgm.

### Ví dụ tư vấn
"Mỗi điều luật được lưu riêng, biết nó thuộc văn bản nào, còn hiệu lực không, và đã bị điều nào thay thế."

### Ví dụ đàm phán
"Cấu trúc này cho phép thêm văn bản mới mà không phải đổi thiết kế."

## G00-A06 · Thiết kế node_id
Lớp: A
Nguồn: dự án
Tags: identifiers, citations
Files: backend/app/db/models.py, backend/app/rag/search.py

### Sếp hỏi
node_id có dạng blld2019-d35-k2-a. Vì sao thiết kế như vậy?

### Chốt kỹ thuật
- Tất định, đọc là hiểu: văn bản, Điều 35, Khoản 2, Điểm a. Nạp lại dữ liệu ra cùng mã, link trích dẫn cũ không gãy.
- LLM trả về node_id nó dựa vào; mã có cấu trúc dễ kiểm tra với danh sách đã truy hồi.
- Giao diện đổi mã sang tên đọc được ("Điều 35 Khoản 2 (Bộ luật Lao động 2019)") qua _display, tên văn bản lấy từ legal_document có cache.

### Ví dụ tư vấn
"Mỗi điều luật có mã cố định, nên đường dẫn trích dẫn không bao giờ hỏng khi cập nhật dữ liệu."

### Ví dụ đàm phán
"Mã ổn định là nền để tích hợp với hệ thống khác sau này."

## G00-A07 · Xử lý hiệu lực theo thời gian
Lớp: A
Nguồn: dự án
Tags: temporal, legal
Files: backend/app/rag/search.py, backend/app/amend/store.py

### Sếp hỏi
Luật thay đổi theo thời gian. Hệ thống biết điều nào còn hiệu lực bằng cách nào?

### Chốt kỹ thuật
- Mỗi node có effective_from và effective_to; mặc định chỉ tìm node effective_to IS NULL.
- Tra theo mốc (/api/law_as_of): effective_from ≤ ngày và (effective_to IS NULL hoặc effective_to > ngày).
- So hai phiên bản: node cũ được đóng effective_to và nối sang node mới qua node_supersession; /api/node/{id}/history lần chuỗi bằng recursive CTE.
- Điểm yếu: phải tự nạp văn bản mới, chưa có nguồn theo dõi văn bản tự động.

### Ví dụ tư vấn
"Hệ thống mặc định chỉ dùng điều đang hiệu lực, và tra được quy định tại một ngày trong quá khứ."

### Ví dụ đàm phán
"Theo dõi văn bản mới là việc vận hành định kỳ, có thể tự động hóa khi có nguồn dữ liệu phù hợp."

## G00-A08 · Index vector khi dữ liệu lớn
Lớp: A
Nguồn: dự án
Tags: hnsw, pgvector, scaling
Files: db/init/001_init.sql, backend/app/rag/search.py

### Sếp hỏi
Cột embedding có index không? Khi dữ liệu lớn lên thì làm gì?

### Chốt kỹ thuật
- Hiện chưa có index vector, pgvector quét tuần tự; vài nghìn node vẫn chỉ vài mili giây.
- Lên hàng trăm nghìn node: index HNSW với vector_cosine_ops (khớp toán tử <=>). Đánh đổi: tìm gần đúng, tốn RAM và thời gian dựng.
- Lọc hiệu lực đi kèm: lọc sau HNSW có thể thiếu kết quả; dùng iterative scan (pgvector 0.8), tăng ef_search, hoặc partial index cho node còn hiệu lực.

### Ví dụ tư vấn
"Ở quy mô hiện tại tìm kiếm đã đủ nhanh. Khi dữ liệu lớn gấp trăm lần, bên em thêm chỉ mục chuyên dụng."

### Ví dụ đàm phán
"Không tối ưu sớm khi chưa cần, nhưng đã biết rõ bước tiếp theo."

## G00-A09 · Model embedding và lý do chọn
Lớp: A
Nguồn: dự án
Tags: embedding, vietnamese
Files: backend/app/rag/embeddings.py, backend/app/main.py

### Sếp hỏi
Dự án dùng embedding model nào, vì sao?

### Chốt kỹ thuật
- AITeamVN/Vietnamese_Embedding_v2, 1024 chiều, chạy trong container bằng sentence-transformers, normalize_embeddings=True, nạp sẵn khi API khởi động.
- Lý do: tối ưu tiếng Việt, tự host nên không phí theo lượt, không gửi dữ liệu ra ngoài, vector ổn định.
- Nhờ embedding, "đuổi việc" vẫn tìm ra điều luật dùng chữ "sa thải".

### Ví dụ tư vấn
"Hệ thống hiểu nghĩa câu hỏi chứ không chỉ khớp chữ, nên người dùng hỏi bằng từ thông thường vẫn tìm đúng điều luật."

### Ví dụ đàm phán
"Model chạy trên máy chủ của mình, không tốn phí theo lượt tìm kiếm."

## G00-A10 · Chế độ EMBEDDER=hashing và rủi ro
Lớp: A
Nguồn: dự án
Tags: embedding, pitfalls
Files: backend/app/rag/embeddings.py, backend/scripts/reembed.py

### Sếp hỏi
Code còn chế độ EMBEDDER=hashing. Nó dùng để làm gì, rủi ro gì?

### Chốt kỹ thuật
- Băm từng từ vào một trong 1024 ô, không cần tải model; để dựng và test hệ thống từ đầu khi chưa cài thư viện ML vài GB.
- Mọi chế độ đều 1024 chiều để lược đồ không đổi.
- Rủi ro: không hiểu nghĩa; nếu nạp dữ liệu bằng hashing rồi đổi sang model thật mà quên chạy scripts/reembed.py, vector câu hỏi và vector DB ở hai không gian khác nhau, kết quả gần như ngẫu nhiên.
- Kiểm tra nhanh: embed lại một đoạn trong DB, cosine với vector đã lưu phải ≈ 1.

### Ví dụ tư vấn
"Chế độ đơn giản giúp dựng hệ thống nhanh lúc đầu, bản chạy thật luôn dùng model hiểu nghĩa."

### Ví dụ đàm phán
"Đây là bài học vận hành: mọi lần đổi model đều phải tính lại toàn bộ dữ liệu."

## G00-A11 · Chunking theo cấu trúc pháp lý
Lớp: A
Nguồn: dự án
Tags: chunking, parser
Files: backend/app/ingestion/parser.py, backend/scripts/reembed.py

### Sếp hỏi
Bạn chia nhỏ văn bản thế nào?

### Chốt kỹ thuật
- Theo cấu trúc pháp lý: Chương, Mục, Điều, Khoản, Điểm. Parser regex + ngăn xếp trạng thái Điều → Khoản → Điểm, kiểm tra bất biến (số Điều tăng dần…), port từ LAWGIC.
- Mỗi chunk là một đơn vị pháp lý trọn vẹn, trích dẫn tới Điểm.
- Khi embed, khoản ngắn được ghép tiền tố "Điều X (tiêu đề), Khoản Y:" để có ngữ cảnh.

### Ví dụ tư vấn
"Văn bản được cắt đúng theo Điều, Khoản, Điểm, không cắt giữa câu, nên trích dẫn luôn chính xác."

### Ví dụ đàm phán
"Mỗi loại văn bản mới cần kiểm tra bộ tách, thường vài ngày công."

## G00-A12 · Hybrid search: thật hay chưa
Lớp: A
Nguồn: dự án
Tags: hybrid-search, honesty
Files: backend/app/rag/search.py, backend/app/config.py

### Sếp hỏi
Docstring ghi là hybrid search. Đó có phải hybrid thật không?

### Chốt kỹ thuật
- Chưa. Hiện là vector search; chỉ khi DB chưa có embedding mới lùi về tìm theo chữ (ILIKE + trigram). Hai cách không chạy cùng lúc.
- Hybrid thật: full-text (tsvector/BM25) và vector chạy song song, gộp bằng RRF. Có ích với câu hỏi theo số hiệu ("Điều 35") và thuật ngữ chính xác.
- Tiếp theo: reranker bge-reranker-v2-m3 (đã khai báo, chưa gọi) chấm lại 20–30 ứng viên.
- Nói thẳng điểm yếu kèm hướng cải thiện thường được đánh giá cao hơn nói quá.

### Ví dụ tư vấn
"Hiện tìm theo nghĩa. Bước tiếp theo là kết hợp tìm theo từ khóa để bắt tốt các câu hỏi có số điều cụ thể."

### Ví dụ đàm phán
"Phần nâng cấp này khoảng một tuần, đo hiệu quả trên bộ câu hỏi trước khi bật."

## G00-A13 · Câu hỏi nối tiếp
Lớp: A
Nguồn: dự án
Tags: follow-up, retrieval
Files: backend/app/agent/followup.py

### Sếp hỏi
Người dùng hỏi tiếp "còn lao động nữ thì sao?". Hệ thống hiểu câu này thế nào?

### Chốt kỹ thuật
- Có lịch sử thì tìm hai lần: câu hiện tại, và câu trước ghép câu hiện tại; gộp kết quả.
- Quy tắc nhẹ (từ nối "còn", "thì sao", hoặc câu dưới 5 từ) quyết định danh sách nào ưu tiên, chiếm 75% chỗ. Đoán sai cũng không mất kết quả câu mới.
- Từng thử đan xen 1:1, mỗi bên chỉ còn 4 chỗ, cắt mất kết quả đúng ở hạng 5; đổi sang 75/25 và đo bằng script probe.
- Hai lượt hỏi gần nhất đưa vào prompt, đánh dấu là dữ liệu.

### Ví dụ tư vấn
"Hệ thống hiểu câu hỏi tiếp theo dựa vào câu trước, như người tư vấn nhớ mạch câu chuyện."

### Ví dụ đàm phán
"Cách làm không cần gọi thêm AI nên không tăng chi phí."

## G00-A14 · Chống bịa điều luật
Lớp: A
Nguồn: dự án
Tags: hallucination, citations
Files: backend/app/agent/qa.py

### Sếp hỏi
Làm sao đảm bảo LLM không bịa điều luật?

### Chốt kỹ thuật
- LLM chỉ được trả lời từ 8 điều luật trong prompt, trả JSON kèm citation_node_ids.
- Code loại node_id không nằm trong kết quả truy hồi; "Điều 999" tự nghĩ ra không lọt.
- Không còn trích dẫn hợp lệ thì không trả lời, chuyển sang đề xuất viết lại hoặc từ chối.
- Thẻ trích dẫn hiện nguyên văn từ DB, không phải lời LLM.
- Còn thiếu: kiểm tra từng ý có được đoạn trích hỗ trợ không (NLI).

### Ví dụ tư vấn
"Mỗi trích dẫn được kiểm tra có thật trong kho, và người dùng bấm vào là thấy nguyên văn."

### Ví dụ đàm phán
"Kiểm tra bằng code gần như không tốn chi phí nhưng loại bỏ hẳn trích dẫn bịa."

## G00-A15 · Bộ phân loại câu hỏi 5 nhóm
Lớp: A
Nguồn: dự án
Tags: classification, routing
Files: backend/app/agent/guard.py, backend/app/agent/qa.py

### Sếp hỏi
Bộ phân loại câu hỏi hoạt động thế nào? Vì sao chạy song song?

### Chốt kỹ thuật
- 5 nhóm: legal, unclear_wording (từ lạ dễ hiểu sai), out_of_corpus (cần văn bản chưa có), off_topic, injection.
- Song song vì phần lớn câu là legal; chờ phân loại xong mới tìm thì chậm thêm một lượt LLM. Câu bị loại thì bỏ câu trả lời đang soạn.
- Lỗi hoặc nhóm lạ thì coi là legal (fail-open); lớp kiểm tra trích dẫn vẫn bảo vệ phía sau.
- Ở quy mô lớn sẽ thay bằng model phân loại nhỏ để giảm chi phí.

### Ví dụ tư vấn
"Hệ thống nhận ra câu chào hỏi, câu ngoài phạm vi, câu dùng từ lạ, và trả lời phù hợp từng loại."

### Ví dụ đàm phán
"Phân loại tốn thêm một lượt AI nhỏ mỗi câu, đổi lại trải nghiệm tự nhiên hơn nhiều."

## G00-A16 · Người dùng dùng sai thuật ngữ
Lớp: A
Nguồn: dự án
Tags: query-rewriting, ux
Files: backend/app/agent/guard.py, backend/app/agent/qa.py

### Sếp hỏi
Người dùng hỏi người thử việc bị "thủ tiêu" khi nào. Hệ thống xử lý ra sao?

### Chốt kỹ thuật
- Embedding không cứu được vì "thủ tiêu" nghĩa khác hẳn "chấm dứt hợp đồng".
- Bộ phân loại xếp vào unclear_wording kèm câu viết lại bằng thuật ngữ đúng; giao diện hiện thẻ "Có phải bạn muốn hỏi…" để bấm dùng.
- Phân loại là legal nhưng không tìm ra căn cứ thì một lượt LLM nữa đề xuất câu hỏi chuẩn.
- Hỏi lại thay vì tự đoán: với tư vấn pháp lý, trả lời sai câu hỏi tệ hơn hỏi lại.

### Ví dụ tư vấn
"Khi người dùng dùng từ không chuẩn, hệ thống gợi ý câu hỏi đúng thuật ngữ để họ xác nhận."

### Ví dụ đàm phán
"Tính năng này giảm số câu bị từ chối mà không đánh đổi độ chính xác."

## G00-A17 · Câu hỏi ngoài kho
Lớp: A
Nguồn: dự án
Tags: out-of-scope, data-driven
Files: backend/app/agent/guard.py, backend/app/api/routes.py

### Sếp hỏi
Câu hỏi đúng chủ đề nhưng kho không có văn bản thì sao?

### Chốt kỹ thuật
- Nhóm out_of_corpus: báo rõ kho có những văn bản nào và vì sao chưa trả lời chắc chắn.
- Ghi vào data/out_of_scope.jsonl để biết nên nạp văn bản nào tiếp, theo nhu cầu thật.
- Câu bị từ chối có nút chuyển chuyên gia (/api/escalate), trang dashboard xem danh sách.

### Ví dụ tư vấn
"Hệ thống nói thật là chưa có văn bản đó, ghi nhận câu hỏi để bổ sung, và cho phép chuyển chuyên gia."

### Ví dụ đàm phán
"Dữ liệu câu hỏi ngoài kho giúp anh/chị đầu tư nạp văn bản đúng chỗ người dùng cần."

## G00-A18 · Vì sao chưa dùng LangGraph
Lớp: A
Nguồn: dự án
Tags: langgraph, framework
Files: backend/requirements.txt, backend/app/agent/qa.py

### Sếp hỏi
requirements.txt có LangGraph nhưng code không dùng. Vì sao?

### Chốt kỹ thuật
- Luồng hiện tại là Python generator gọi nối tiếp + ThreadPoolExecutor chạy song song; với ít nhánh, code thường dễ đọc, test, debug hơn graph.
- LangGraph để dành cho lúc có vòng lặp và state cần lưu: hỏi lại người dùng rồi quay lại tìm kiếm, tạm dừng chờ chuyên gia duyệt; khi đó checkpoint Postgres có ích.
- Langfuse cũng chỉ mới có service và cấu hình (LANGFUSE_ENABLED=false), chưa gửi trace; thuộc mốc M7.
- Chọn công cụ theo độ phức tạp của bài toán, không thêm framework để có tên trong CV.

### Ví dụ tư vấn
"Quy trình hiện đơn giản nên viết trực tiếp. Khi có bước chờ người duyệt rồi làm tiếp, bên em mới dùng khung chuyên dụng."

### Ví dụ đàm phán
"Chuyển sang framework khi cần mất khoảng 1–2 tuần, không phải làm lại từ đầu."

## G00-A19 · LLMRouter và hedging
Lớp: A
Nguồn: dự án
Tags: llm-router, fallback, hedging
Files: backend/app/llm/router.py, backend/app/config.py

### Sếp hỏi
LLMRouter của dự án làm gì? Racing và hedging là gì?

### Chốt kỹ thuật
- Một cửa gọi LLM. Mỗi task (route, lite, answer, draft, report, judge, bulk) có danh sách nhà cung cấp theo ưu tiên; nhà nào chưa có key thì bỏ qua.
- Retry lỗi tạm thời (429, 5xx, mạng) có backoff + jitter, xoay vòng key Gemini, ép JSON; parse fail tính là lỗi nhà cung cấp.
- Racing: Dahl (gói miễn phí, nhiều model nhỏ) được gửi song song tới mọi model, lấy kết quả hợp lệ sớm nhất.
- Hedging: sau 15 giây (DAHL_HEDGE_AFTER) chưa có kết quả thì Gemini vào đua cùng.
- Đánh đổi: tốn nhiều lượt gọi để giảm độ trễ đuôi; hợp lý vì Dahl miễn phí, API trả phí thì tính lại ngưỡng.

### Ví dụ tư vấn
"Hệ thống gửi câu hỏi cho nhiều AI cùng lúc, lấy câu trả lời đến sớm nhất, và gọi thêm dự phòng khi quá chậm."

### Ví dụ đàm phán
"Cấu hình này tối ưu cho chi phí gần bằng 0 trong bản demo. Với khách trả phí, bên em chỉnh lại để cân bằng chi phí."

## G00-A20 · Chống prompt injection trong dự án
Lớp: A
Nguồn: dự án
Tags: prompt-injection, guard
Files: backend/app/agent/guard.py, backend/tests/test_guard.py

### Sếp hỏi
Dự án chống prompt injection thế nào?

### Chốt kỹ thuật
- Lớp 1 regex trên chữ thường đã bỏ dấu: "ignore previous instructions", "bỏ qua hướng dẫn trước", đòi system prompt hay API key, "từ giờ bạn là…". Không gọi LLM vì câu tấn công nhắm vào chính LLM.
- Mẫu hẹp để không chặn nhầm ("bỏ qua yêu cầu nghỉ phép của tôi" không bị chặn), có test riêng.
- Lớp 2: LLM phân loại nhóm injection cho câu diễn đạt lại.
- Nội dung người dùng bọc trong «» và ghi rõ là dữ liệu.
- Lớp cuối: kể cả bị lừa, câu trả lời vẫn phải có trích dẫn hợp lệ mới hiện.

### Ví dụ tư vấn
"Có bộ lọc cố định không thể bị thuyết phục, cộng một lớp AI bắt những câu lừa khéo hơn."

### Ví dụ đàm phán
"Lớp bảo vệ chạy trước khi gọi AI nên còn giúp tiết kiệm chi phí với câu tấn công."

## G00-A21 · Rate limit cho bản demo
Lớp: A
Nguồn: dự án
Tags: rate-limit, demo
Files: backend/app/demo_limits.py

### Sếp hỏi
Bản demo công khai được bảo vệ khỏi bị gọi quá nhiều thế nào?

### Chốt kỹ thuật
- DemoRateLimitMiddleware bật khi DEMO_MODE=true: giới hạn /api/chat theo IP trong cửa sổ thời gian và tổng mỗi ngày toàn hệ thống.
- Bộ đếm trong bộ nhớ Python, đủ cho một worker HF Spaces. Hạn chế: restart mất bộ đếm, nhiều worker đếm riêng; chặt hơn thì dùng Redis hoặc Postgres.
- Key LLM chỉ ở .env hoặc secret của nền tảng.

### Ví dụ tư vấn
"Mỗi người có số lượt hỏi giới hạn, và tổng lượt mỗi ngày có trần, để bản demo không bị lạm dụng."

### Ví dụ đàm phán
"Bản thương mại sẽ chuyển bộ đếm sang hệ thống dùng chung để chạy nhiều máy chủ."

## G00-A22 · So sánh phiên bản văn bản
Lớp: A
Nguồn: dự án
Tags: diff, amendments
Files: backend/app/amend/diff.py, backend/app/amend/store.py

### Sếp hỏi
Khi có văn bản sửa đổi, làm sao biết điều nào đã thay đổi?

### Chốt kỹ thuật
- So node lá bản cũ và mới bằng SequenceMatcher; ghép cặp khi giống ≥ 0,75; ≥ 0,995 coi như không đổi; tiêu đề Điều ≥ 0,8.
- Gán loại: amended, replaced, removed, added; tách riêng thay đổi số tiền, số tháng, "vĩnh viễn/không thời hạn" để tóm tắt.
- Ghi node_supersession và đóng effective_to node cũ; tìm kiếm mặc định tự bỏ điều hết hiệu lực.

### Ví dụ tư vấn
"Hệ thống tự so hai phiên bản, chỉ ra điều nào sửa, điều nào mới, điều nào bị bỏ."

### Ví dụ đàm phán
"Phần này dùng lại thuật toán đã kiểm chứng từ dự án LAWGIC, giữ nguyên các ngưỡng đã đo."

## G00-A23 · Triển khai
Lớp: A
Nguồn: dự án
Tags: deploy, docker
Files: docker-compose.yml, docs/DEPLOY.md

### Sếp hỏi
Hệ thống được triển khai thế nào?

### Chốt kỹ thuật
- Local: Docker Compose gồm postgres (pgvector/pgvector:pg17), api (FastAPI + Uvicorn), web (Next.js); Langfuse tùy chọn qua --profile obs.
- Demo: Postgres trên Neon, backend trên Hugging Face Spaces, frontend trên Vercel, đều miễn phí.
- Model embedding nạp sẵn khi API khởi động để câu đầu không phải chờ.

### Ví dụ tư vấn
"Hệ thống chạy trên một máy bằng một lệnh, và có bản demo công khai trên hạ tầng miễn phí."

### Ví dụ đàm phán
"Chuyển sang hạ tầng doanh nghiệp không phải đổi code, chỉ đổi cấu hình."

## G00-A24 · Kiểm thử
Lớp: A
Nguồn: dự án
Tags: testing, eval
Files: backend/tests, backend/scripts

### Sếp hỏi
Bạn kiểm thử hệ thống thế nào?

### Chốt kỹ thuật
- pytest cho parser, chương mục, dẫn chiếu, lớp chặn chèn lệnh, câu nối tiếp, LLM router, luồng LLM, knowledge graph, soạn thảo văn bản, lưu trữ DB.
- Script smoke và probe chạy với dữ liệu thật, ví dụ đo hạng của điều đúng trong kết quả truy hồi.
- Còn thiếu: bộ eval có đáp án chuẩn đo độ chính xác câu trả lời qua mỗi thay đổi; là việc ưu tiên tiếp theo.

### Ví dụ tư vấn
"Các phần quan trọng đều có kiểm thử tự động. Bước tiếp theo là bộ câu hỏi chấm điểm độ chính xác tự động."

### Ví dụ đàm phán
"Nói rõ phần còn thiếu giúp người phỏng vấn tin phần đã làm."

## G00-A25 · Nếu có thêm một tháng
Lớp: A
Nguồn: dự án
Tags: roadmap

### Sếp hỏi
Nếu có thêm một tháng, bạn cải thiện gì trước?

### Chốt kỹ thuật
- Bộ eval khoảng 100–200 câu có đáp án và điều luật chuẩn, chạy tự động.
- Hybrid search thật (full-text + vector, RRF) và bật reranker.
- Kiểm tra hỗ trợ từng ý của câu trả lời.
- Bật Langfuse để xem từng bước, token, chi phí.
- Nạp thêm văn bản theo out_of_scope.jsonl.
- Chuyển luồng sang LangGraph khi thêm vòng hỏi lại hoặc chờ chuyên gia.
- Thêm cờ hủy để dừng gọi LLM khi người dùng đóng tab.

### Ví dụ tư vấn
"Ưu tiên đầu tiên là đo được chất lượng, sau đó mới tối ưu tìm kiếm, vì không đo thì không biết tối ưu có hiệu quả không."

### Ví dụ đàm phán
"Thứ tự này đảm bảo mỗi cải tiến sau đều có số chứng minh."

## G00-A26 · Khó khăn lớn nhất
Lớp: A
Nguồn: dự án
Tags: challenges, storytelling
Files: backend/app/llm/router.py, backend/app/agent/followup.py, backend/app/agent/guard.py

### Sếp hỏi
Khó khăn lớn nhất khi làm dự án là gì và bạn giải quyết thế nào?

### Chốt kỹ thuật
- Chọn một ví dụ có số đo, kể theo vấn đề → giả thuyết → cách đo → giải pháp → kết quả.
- LLM miễn phí xếp hàng hơn một phút: gửi song song nhiều model và gọi dự phòng sau 15 giây.
- Câu nối tiếp mất kết quả đúng khi đan xen 1:1: đổi sang 75/25, đo bằng script probe trước và sau.
- Người dùng dùng từ đời thường hoặc sai thuật ngữ: thêm nhóm unclear_wording và thẻ gợi ý viết lại thay vì từ chối.

### Ví dụ tư vấn
"Một vấn đề thật: AI miễn phí có lúc chờ hơn một phút. Tôi cho hệ thống hỏi nhiều AI cùng lúc và gọi dự phòng khi quá 15 giây."

### Ví dụ đàm phán
"Câu chuyện có số đo trước và sau thuyết phục hơn liệt kê công nghệ."
