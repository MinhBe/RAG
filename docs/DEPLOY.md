# Hướng dẫn Deploy Demo (HF Spaces + Neon + Vercel)

Stack miễn phí, phù hợp demo cho nhà tuyển dụng.

---

## 1. PostgreSQL — Neon (miễn phí)

1. Đăng ký tại https://neon.tech → tạo project **lawvn**.
2. Trong tab **Connection Details**, chọn **psycopg** → sao chép chuỗi kết nối:
   ```
   postgresql://lawvn:<pass>@ep-xxx.neon.tech/lawvn?sslmode=require
   ```
3. Lưu lại — dùng ở bước HF Spaces.

---

## 2. API + Embedding — Hugging Face Spaces

### 2.1 Tạo Space

1. https://huggingface.co/new-space → chọn **Docker**, đặt tên `lawvn-api`, **Public**.
2. Upload các file sau (hoặc dùng `git push` qua HF git):
   ```
   backend/                   ← toàn bộ thư mục backend/
   └── Dockerfile.space       ← đổi tên thành Dockerfile
   ```
   Cụ thể: tạo repo HF riêng chứa nội dung `backend/`, đặt `Dockerfile.space` là `Dockerfile`.

### 2.2 Biến môi trường (Repository → Settings → Variables and Secrets)

| Tên biến | Giá trị | Loại |
|---|---|---|
| `DATABASE_URL` | chuỗi Neon bước 1 | **Secret** |
| `GEMINI_API_KEY_1` | khóa Gemini miễn phí | **Secret** |
| `EMBEDDER` | `vie-v2` | Variable |
| `EMBED_DIM` | `1024` | Variable |
| `DEMO_MODE` | `true` | Variable |
| `EXTRA_CORS_ORIGINS` | URL Vercel (bước 3) | Variable |

### 2.3 Nạp dữ liệu lần đầu

Sau khi Space build xong, gọi endpoint ingest qua Swagger UI (`/docs`) hoặc curl:
```bash
HF_URL=https://minhbe-lawvn-api.hf.space
curl -X POST $HF_URL/api/admin/ingest   # nạp 3 văn bản luật từ HF datasets
curl -X POST $HF_URL/api/admin/diff     # tính quan hệ sửa đổi 2012→2019
curl -X POST $HF_URL/api/admin/precedents  # nạp 150 bản án
```
*(Cần thêm endpoint /admin/ingest nếu chưa có — xem notes bên dưới)*

---

## 3. Web — Vercel

1. https://vercel.com/new → **Import Git Repository** → chọn `MinhBe/RAG`.
2. **Root Directory**: `frontend`.
3. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_BASE_URL = https://minhbe-lawvn-api.hf.space
   ```
4. Deploy → lấy URL (vd `lawvn.vercel.app`).
5. Quay lại HF Spaces, cập nhật `EXTRA_CORS_ORIGINS` = URL Vercel.

---

## 4. Kiểm tra sau khi deploy

```bash
# Health check
curl https://minhbe-lawvn-api.hf.space/health

# Thử chat
curl -N -X POST https://minhbe-lawvn-api.hf.space/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Thời gian thử việc tối đa là bao lâu?", "thread_id": "test"}'
```

---

## Ghi chú

- **HF Spaces free tier** ngủ sau 48h không dùng; lần đầu sau ngủ mất ~60s để khởi động (tải model embedding).
- **Neon free tier** giới hạn 0.5 GB storage — đủ cho ~3.000 node + embedding 1024d.
- **Demo rate limit**: 20 câu/IP/ngày, 200 câu toàn hệ thống/ngày (cấu hình trong `DEMO_IP_LIMIT`, `DEMO_GLOBAL_LIMIT`).
