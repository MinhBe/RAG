# Trợ lý Pháp luật Lao động Việt Nam 🇻🇳

> AI Assistant for Vietnamese Labor Law — built from scratch with FastAPI, pgvector, and custom Vietnamese embeddings.

**[🚀 Demo trực tuyến](#)** · **[📖 API Docs](https://lawvn-api.hf.space/docs)** · **[📋 Tổng quan kỹ thuật](docs/TONG-QUAN-DU-AN.md)**

---

## Dự án là gì

Trợ lý AI hỏi đáp **pháp luật lao động Việt Nam** với 3 tính năng cốt lõi:

| Tính năng | Mô tả |
|---|---|
| **Trả lời có trích dẫn** | Mỗi câu trả lời kèm Điều–Khoản–Điểm cụ thể; từ chối khi không đủ căn cứ |
| **Hiệu lực theo thời gian** | Hỏi "luật năm 2015" → ra BLLĐ 2012; hỏi "hiện tại" → ra BLLĐ 2019 + NĐ145 |
| **Tác vụ pháp chế thực tế** | Soạn văn bản NĐ30, tổng hợp 150 bản án/án lệ lao động |

Dự án tổng hợp ý tưởng từ 3 repo nguồn (agentailor, LexCompanion, LAWGIC) nhưng **backend được viết lại hoàn toàn** — gọn hơn, bỏ Neo4j, dùng PostgreSQL + pgvector.

---

## Kiến trúc kỹ thuật

```
Browser (Next.js 15)  ──SSE stream──▶  FastAPI  ──▶  PostgreSQL 17 + pgvector
                                          │
                         LLMRouter ◀──────┤
                         (Gemini / Claude)│
                                          ▼
                         Vietnamese_Embedding_v2 (self-hosted)
                         AITeamVN/Vietnamese_Embedding_v2, 1024-dim
```

| Tầng | Công nghệ | Ghi chú |
|---|---|---|
| **Web** | Next.js 15 (App Router), React 19, TypeScript | SSE streaming, citation chips |
| **API** | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 | Async SSE via `POST /api/chat` |
| **Database** | PostgreSQL 17 + pgvector + pg_trgm | Vector (1024d) + trigram hybrid search |
| **Embedding** | AITeamVN/Vietnamese_Embedding_v2 (self-hosted) | Không gửi dữ liệu ra ngoài |
| **LLM** | LLMRouter: Gemini Flash / Flash-lite / Claude | Retry + round-robin 10 keys |
| **Deploy** | Docker Compose | `postgres` + `api` + `web` + `langfuse` (optional) |

### Điểm kỹ thuật đáng chú ý

- **Hybrid RAG**: pgvector cosine + trigram/ILIKE + lọc `effective_from/to` — truy xuất chính xác không cần Elasticsearch
- **Citation grounding**: LLM chỉ được trích dẫn node đã nằm trong kết quả retrieval; hallucinate citation → từ chối
- **Time-travel law**: `law_as_of(date)` dùng CTE trên `node_supersession` để theo chuỗi BLLĐ 2012 → BLLĐ 2019
- **No external embedding API**: model tự host trong Docker container → 0 đồng gọi API, latency ổn định

---

## Dữ liệu pháp lý

| Văn bản | Mã định danh | Quy mô |
|---|---|---|
| BLLĐ 2019 (45/2019/QH14) | `blld2019` | 220 Điều, ~1.132 node |
| BLLĐ 2012 (10/2012/QH13) | `blld2012` | 242 Điều, ~1.071 node (hết hiệu lực 01/01/2021) |
| NĐ 145/2020/NĐ-CP | `nd145_2020` | 115 Điều, ~880 node |
| Án lệ/bản án lao động | bảng `precedent` | 150 bản án (Hugging Face) |

Mã node: `blld2019-d35-k2-a` = Bộ luật 2019, Điều 35, Khoản 2, Điểm a.

---

## Chạy cục bộ (5 phút)

**Yêu cầu:** Docker Desktop đang chạy.

```bash
# 1. Clone
git clone https://github.com/MinhBe/RAG.git && cd RAG

# 2. Cấu hình — chỉ cần điền ít nhất 1 khóa Gemini miễn phí
cp .env.example .env
# Mở .env, điền GEMINI_API_KEY_1=...

# 3. Khởi động
docker compose up -d --build

# Lần đầu tải model embedding (~1.5 GB), mất khoảng 5 phút.
# Kiểm tra: docker compose logs api -f
```

- **Giao diện**: http://localhost:3000
- **API + Swagger**: http://localhost:8000/docs
- **Quan sát (optional)**: `docker compose --profile obs up -d` → http://localhost:3002

Dừng: `docker compose down` (thêm `-v` nếu muốn xóa cả dữ liệu DB).

---

## Demo nhanh qua API

```bash
# Hỏi đáp có trích dẫn
curl -N -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Người lao động có thể đơn phương chấm dứt hợp đồng không?", "thread_id": "demo"}'

# Tra hiệu lực theo thời gian
curl "http://localhost:8000/api/law_as_of?date=2015-06-01&doc_id=blld2019"

# Soạn quyết định xử lý kỷ luật
curl -X POST http://localhost:8000/api/draft/preview \
  -H 'Content-Type: application/json' \
  -d '{"doc_type": "quyet_dinh_ky_luat", "params": {"ho_ten": "Nguyễn Văn A", "hinh_thuc": "Cảnh cáo"}}'
```

---

## Cấu trúc repo

```
RAG/
├── backend/
│   ├── app/
│   │   ├── agent/        # pipeline.py, qa.py (RAG + citations), precedent.py
│   │   ├── amend/        # diff.py (so sánh 2 phiên bản), store.py (node_supersession)
│   │   ├── api/          # routes.py — toàn bộ endpoint
│   │   ├── db/           # models.py (PostgreSQL schema), base.py
│   │   ├── draft/        # nd30.py — soạn văn bản NĐ30 + xuất DOCX
│   │   ├── ingestion/    # parser.py (Điều–Khoản–Điểm), ingest.py (Hugging Face → DB)
│   │   ├── llm/          # router.py — LLMRouter (Gemini/Claude/FPT, retry, JSON coerce)
│   │   ├── rag/          # embeddings.py, search.py (hybrid), text.py (Vietnamese tokenizer)
│   │   └── report/       # multi_doc.py — báo cáo nhiều văn bản
│   └── scripts/          # ingest, reembed, smoke tests
├── frontend/             # Next.js 15, SSE client, citation chips
├── db/init/              # PostgreSQL init SQL (pgvector, pg_trgm)
├── docker-compose.yml
└── docs/
    └── TONG-QUAN-DU-AN.md  # Tài liệu kiến trúc chi tiết
```

---

## Acknowledgements

- [agentailor/fullstack-langgraph-nextjs-agent](https://github.com/agentailor/fullstack-langgraph-nextjs-agent) (MIT) — mẫu giao diện streaming agent
- [danialtranz/LexCompanion](https://github.com/danialtranz/LexCompanion) (Apache-2.0) — lõi RAG pháp lý, ý tưởng soạn văn bản
- [dlxik/LAWGIC--L-GPT6.7--VAIC2026](https://github.com/dlxik/LAWGIC--L-GPT6.7--VAIC2026) — parser Điều–Khoản–Điểm, so sánh phiên bản, hỏi đáp có trích dẫn *(dùng lại code theo sự cho phép của tác giả)*
- Dữ liệu: HF `th1nhng0/vietnamese-legal-documents` · `tmquan/anle-toaan-gov-vn` (CC-BY 4.0)

---

## License

MIT — xem [LICENSE](LICENSE). Phần code port từ LAWGIC giữ thông điệp cho phép của tác giả gốc.
