# Trợ lý pháp luật lao động — Tổng quan dự án

Cập nhật: 27/10/2026. Tài liệu này mô tả **code đã viết**, **tech stack**, **logic triển khai**, **workflow xử lý**, và **kế hoạch còn lại**.

Mã nguồn: `C:\Users\Admin\Documents\RAG\RAG` (remote `github.com/MinhBe/RAG`, đã commit 6 mốc ở local, **chưa push**).

---

## 1. Dự án là gì

Trợ lý AI hỏi đáp **pháp luật lao động Việt Nam** với 3 nguyên tắc:

1. **Trả lời có trích dẫn** đến từng Điều – Khoản – Điểm, và **từ chối khi không đủ căn cứ** (không bịa).
2. **Biết luật theo thời gian**: cùng một câu hỏi, trả lời khác nhau tùy "vào ngày nào" (vì luật có sửa đổi, hết hiệu lực).
3. **Làm được việc pháp chế thực tế**: soạn văn bản hành chính (NĐ 30), tổng hợp án lệ, báo cáo nhiều văn bản.

Dự án ghép ý tưởng từ 3 repo nguồn (agentailor — giao diện agent; LexCompanion — lõi RAG pháp lý; LAWGIC — parser luật + so sánh phiên bản), nhưng **code backend được viết mới** để nhẹ và dễ ghép (bỏ Neo4j, dùng Postgres).

---

## 2. Tech stack

| Tầng | Công nghệ | Ghi chú |
|---|---|---|
| Giao diện | Next.js 15 (App Router), React 19, TypeScript | Chat streaming, thẻ trích dẫn bấm được |
| Truyền dữ liệu | SSE dạng POST + `fetch`/ReadableStream | Sự kiện có tên: `start/step/token/citation/done/error` |
| API | FastAPI, Uvicorn, Pydantic v2 | |
| ORM / DB | SQLAlchemy 2 + psycopg3, **PostgreSQL 17 + pgvector** | Một DB cho cả luật, hiệu lực, sửa đổi, án lệ, hội thoại |
| Tìm kiếm | pgvector (cosine) + trigram/ILIKE, lọc theo hiệu lực | Rerank BGE sẵn sàng bật sau |
| Embedding | **AITeamVN/Vietnamese_Embedding_v2** (1024 chiều), tự host trong container | Chế độ `hashing` dự phòng khi chưa tải model |
| LLM | **LLMRouter** tự viết: Gemini / Claude / FPT theo loại việc | Retry 429/5xx + xoay vòng 10 key Gemini |
| Soạn thảo | python-docx (thể thức NĐ 30) | Xuất `.docx` |
| Xử lý dữ liệu | duckdb đọc parquet Hugging Face | Tải 1 lần, cache cục bộ |
| Triển khai | Docker Compose: `postgres` + `api` + `web` (+ `langfuse` theo profile `obs`) | Mở `localhost:3000` và `:8000/docs` |

**Nhà cung cấp LLM theo việc** (`app/llm/router.py`): định tuyến/viết lại truy vấn → Gemini flash-lite; hỏi đáp → Gemini flash; soạn thảo/báo cáo → Claude (dự phòng Gemini); xử lý hàng loạt → FPT. Hiện chỉ có khóa Gemini; Claude/FPT để trống trong `.env`.

---

## 3. Dữ liệu đã nạp

Tất cả lấy tự động từ Hugging Face (`th1nhng0/vietnamese-legal-documents`, `tmquan/anle-toaan-gov-vn`) qua duckdb, không gửi gì ra ngoài khi dùng:

| Văn bản | Mã | Quy mô |
|---|---|---|
| Bộ luật Lao động 2019 (45/2019/QH14) | `blld2019` | 220 Điều, ~1.132 node |
| Bộ luật Lao động 2012 (10/2012/QH13) | `blld2012` | 242 Điều, ~1.071 node (đã đánh dấu hết hiệu lực 01/01/2021) |
| Nghị định 145/2020/NĐ-CP | `nd145_2020` | 115 Điều, ~880 node |
| Bản án / án lệ lao động | bảng `precedent` | 150 bản án |

Mã node: `blld2019-d35-k2-a` = Điều 35, Khoản 2, Điểm a. Xử lý được các bẫy thật: lọc bản dịch tiếng Anh, sửa lỗi font (mojibake cp1252), dừng ở phụ lục để tránh trùng số Điều.

---

## 4. Lược đồ cơ sở dữ liệu (`app/db/models.py`)

```
legal_document(doc_id, title, doc_type, number, effective_date, expired_date, status, ...)
legal_node(node_id, doc_id, level[article|clause|point], article_no, clause_no,
           point_letter, parent_id, heading, text, text_hash, seq,
           effective_from, effective_to, embedding vector(1024))
node_supersession(old_id, new_id, change_type, similarity)     -- thay cho SUPERSEDED_BY của Neo4j
document_relation(from_doc, to_doc, rel)
precedent(doc_name, court, precedent_number, is_precedent, category, issued_date,
          citations_law, source_url, text, embedding)
thread / message                                                -- hội thoại
```

Quyết định kiến trúc: **bỏ Neo4j**, lưu quan hệ sửa đổi trong Postgres. `law_as_of` dùng điều kiện ngày; `node_history` dùng recursive CTE trên `node_supersession`.

---

## 5. Cấu trúc code (`backend/app/`)

| Thư mục | Vai trò |
|---|---|
| `config.py` | Đọc `.env` (DB, khóa LLM, embedder…) |
| `db/` | `base.py` (engine/session), `models.py` (lược đồ) |
| `ingestion/` | `parser.py` (tách Điều–Khoản–Điểm, port LAWGIC), `ingest.py` (nạp + nhúng) |
| `rag/` | `text.py` (tách từ VN), `embeddings.py` (vie-v2 / hashing), `search.py` (hybrid + `search_precedents`) |
| `llm/router.py` | LLMRouter: chọn model theo task, retry, ép JSON, streaming |
| `amend/` | `diff.py` (ghép cặp + phân loại thay đổi, thuần Python), `store.py` (ghi Postgres, `law_as_of`, `node_history`) |
| `agent/` | `pipeline.py` (chọn luồng chat), `qa.py` (hỏi đáp có trích dẫn), `precedent.py` (tổng hợp án lệ) |
| `draft/nd30.py` | Soạn văn bản hành chính NĐ30 + kiểm tra thể thức + xuất DOCX |
| `report/multi_doc.py` | Báo cáo nhiều văn bản |
| `graph/builder.py` | Dựng knowledge graph cho `/api/graph`: gom node, rồi cạnh, tầng Chương và Văn bản |
| `ingestion/references.py` | Trích dẫn chiếu "khoản 2 Điều 35" và đoán văn bản đích |
| `api/routes.py` | Toàn bộ endpoint |
| `sse.py` | Định dạng sự kiện SSE |

`backend/scripts/` chứa script lấy dữ liệu HF (`fetch_*`, `find_ids_duckdb`), nạp lại embedding (`reembed`), chạy diff (`run_diff`), dựng tầng Chương (`backfill_chapters`) và cạnh dẫn chiếu (`backfill_references`).

Test nằm ở `backend/tests/`, chạy trong container:

```bash
docker compose exec api sh -c "pip install -q -r requirements-dev.txt && python -m pytest"
```

Test cần DB (`@pytest.mark.db`) tự bỏ qua khi kho trống. Test gọi LLM thật (`@pytest.mark.llm`) chỉ chạy khi đặt `RUN_LLM_TESTS=1`.

---

## 6. API (FastAPI, `localhost:8000/docs`)

| Method | Đường dẫn | Chức năng |
|---|---|---|
| GET | `/health` | Trạng thái DB, số node, nhà cung cấp LLM |
| GET | `/api/law/{node_id}` | Nguyên văn một điều/khoản |
| GET | `/api/documents` | Danh sách văn bản |
| POST | `/api/search` | Tìm kiếm hybrid |
| GET | `/api/law_as_of?date=` | Luật còn hiệu lực tại một ngày |
| GET | `/api/node/{id}/history` | Lịch sử sửa đổi của một quy định |
| POST | `/api/admin/diff` | So sánh 2 phiên bản văn bản |
| POST | `/api/draft/preview` · `/export` | Soạn văn bản NĐ30 (xem trước / xuất DOCX) |
| POST | `/api/report` · `/report/export` | Báo cáo nhiều văn bản |
| POST | `/api/precedent` | Tổng hợp án lệ |
| POST | `/api/chat` | Hỏi đáp (SSE streaming) |

---

## 7. Workflow xử lý

### 7.1 Nạp dữ liệu (một lần)
```
parquet HF → (duckdb lọc + sửa mojibake) → text thô
  → parser Điều–Khoản–Điểm → gán node_id + hash
  → nhúng vie-v2 → ghi legal_node (embedding)
diff 2012→2019 → node_supersession + đóng effective_to node cũ
```

### 7.2 Hỏi đáp có trích dẫn (chat)
```
Người dùng → POST /api/chat (SSE)
  → pipeline: đã có dữ liệu? → qa.answer_with_citations
    1. nhúng câu hỏi → search_nodes (pgvector + lọc còn hiệu lực)
    2. không có kết quả → từ chối
    3. LLM trả JSON {answer, citation_node_ids, confidence}
    4. KIỂM TRA LẠI: chỉ giữ citation có thật trong kết quả truy hồi
    5. không còn căn cứ → từ chối; ngược lại → stream câu trả lời + thẻ trích dẫn
```

### 7.3 Tra luật theo thời gian
`law_as_of(date)` lấy node lá còn hiệu lực tại `date` (lọc `effective_from`/`effective_to`). Ví dụ đã kiểm: 2015 → ra luật 2012; 2023 → ra luật 2019 + NĐ145.

### 7.4 Soạn thảo / báo cáo / án lệ
- **Soạn NĐ30**: nhận các trường → tự gợi ý "Căn cứ" từ văn bản còn hiệu lực → `render_text` xem trước → duyệt → `render_docx` xuất file.
- **Báo cáo**: gom quy định theo chủ đề → LLM sắp mục + trích dẫn → xuất DOCX + bảng nguồn.
- **Án lệ**: tìm bản án gần nhất với tình huống → LLM tóm tắt tình huống/phán quyết/điều luật áp dụng.

---

## 8. Trạng thái các mốc

| Mốc | Nội dung | Trạng thái |
|---|---|---|
| M0 | Khung Docker + chat SSE | ✅ Đã kiểm |
| M1 | Parser + nạp 3 văn bản (~3.083 node) | ✅ |
| M2 | Embedding tiếng Việt thật | ✅ (chất lượng trả lời tăng rõ) |
| M3 | Hỏi đáp có trích dẫn + từ chối | ✅ |
| M4 | Hiệu lực theo thời gian | ✅ |
| M4b | So sánh phiên bản 2012→2019 (1.262 cặp) | ✅ |
| M5 | Soạn thảo NĐ30 + DOCX | ✅ |
| M6a | Báo cáo nhiều văn bản | ✅ |
| M6b | Tổng hợp án lệ (150 bản án) | ✅ |
| M7 | Memory học từ phản hồi, Langfuse, trần chi phí | ⏳ Để "harden sau" |

---

## 9. Kế hoạch còn lại

1. **M7 – memory học từ phản hồi**: nhớ văn phong, mẫu, nơi nhận thường dùng từ các lần người dùng sửa bản nháp; thay đổi ghi nhớ qua bước duyệt (người dùng xem/xóa được).
2. **M7 – quan sát & chi phí**: bật Langfuse (trace từng bước, token, chi phí); đặt trần token theo người dùng; dự phòng model khi lỗi (đã có khung trong LLMRouter).
3. **Eval** (đã hoãn theo yêu cầu): bộ câu hỏi–đáp gold cho luật lao động, đo recall@k / độ bám nguồn / trích dẫn đúng; chạy trong CI, chặn merge khi tụt điểm.
4. **Gộp tính năng vào chat**: hiện soạn thảo / báo cáo / án lệ là endpoint riêng; sẽ định tuyến thành 5 nhánh trong khung chat (hỏi đáp · nghiên cứu · soạn thảo · án lệ · báo cáo) kèm hộp duyệt.
5. **Nâng cấp tùy chọn**: bật rerank BGE; thêm nhiều nghị định/thông tư; mở rộng kho án lệ; thêm khóa Claude/FPT để tăng chất lượng văn bản dài.

---

## 10. Chạy thử

```bash
cd C:\Users\Admin\Documents\RAG\RAG
docker compose up -d
```
Mở `http://localhost:3000` (giao diện) và `http://localhost:8000/docs` (API).
