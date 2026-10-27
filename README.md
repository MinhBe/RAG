# Trợ lý pháp luật lao động Việt Nam

Hỏi đáp luật lao động có trích dẫn Điều–Khoản–Điểm, biết hiệu lực theo thời gian,
soạn văn bản, tổng hợp án lệ. Ghép từ ba dự án nguồn (xem Acknowledgements) và viết mới phần kết nối.

## Chạy nhanh (localhost)

Cần: Docker Desktop đang chạy.

```bash
cp .env.example .env      # rồi điền khóa Gemini/Claude
docker compose up -d --build
```

- Giao diện: http://localhost:3000
- API + tài liệu thử: http://localhost:8000/docs
- Langfuse (tùy chọn): `docker compose --profile obs up -d` → http://localhost:3001

Dừng: `docker compose down` (thêm `-v` để xóa cả dữ liệu Postgres).

## Kiến trúc (MVP)

| Thành phần | Công nghệ |
|---|---|
| Web | Next.js (App Router), SSE qua fetch stream |
| API | FastAPI, SQLAlchemy, SSE |
| CSDL | PostgreSQL + pgvector (luật, hiệu lực, sửa đổi, hội thoại) |
| Tìm kiếm | pgvector (vector) + trigram/full-text, rerank BGE (M2) |
| Embedding | tự host (hashing ở M0, Vietnamese_Embedding_v2 ở M2) |
| LLM | LLMRouter: Gemini / Claude / FPT theo loại việc |
| Agent | LangGraph |

Mã node luật: `blld2019-d35-k2-a` (Điều 35, Khoản 2, Điểm a).

## Trạng thái

Đang xây theo mốc M0→M7 (xem `../ke-hoach-trien-khai.md`). Hiện tại: khung chạy được,
hỏi đáp LLM thuần; nạp dữ liệu và trích dẫn ở các mốc kế tiếp.

## Acknowledgements

- [agentailor/fullstack-langgraph-nextjs-agent](https://github.com/agentailor/fullstack-langgraph-nextjs-agent) (MIT) — mẫu giao diện agent.
- [LexCompanion](https://github.com/danialtranz/LexCompanion) (Apache-2.0) — lõi RAG pháp lý, soạn văn bản.
- LAWGIC (VAIC 2026) — parser Điều–Khoản–Điểm, so sánh phiên bản, hỏi đáp có trích dẫn (dùng lại code theo sự cho phép của tác giả).
- Dữ liệu: Hugging Face `tmquan/phapdien-moj-gov-vn`, `th1nhng0/vietnamese-legal-documents`, `tmquan/anle-toaan-gov-vn` (CC-BY 4.0); `GreenNode/zalo-ai-legal-text-retrieval-vn` (MIT).
