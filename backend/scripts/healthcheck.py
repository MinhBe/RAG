"""Gọi thử mọi endpoint để phát hiện chức năng hỏng."""


import httpx

B = "http://localhost:8000"
c = httpx.Client(base_url=B, timeout=120)


def show(name, r):
    ok = r.status_code < 400
    snippet = r.text[:140].replace("\n", " ")
    print(f"[{'OK ' if ok else 'ERR'}] {r.status_code} {name}  :: {snippet}")


show("GET /health", c.get("/health"))
show("GET /api/documents", c.get("/api/documents"))
show("GET /api/law/blld2019-d25", c.get("/api/law/blld2019-d25"))
show("POST /api/search", c.post("/api/search", json={"query": "nghỉ hằng năm", "top_k": 3}))
show("GET /api/law_as_of", c.get("/api/law_as_of", params={"date": "2023-06-01"}))
show("GET /api/node/history", c.get("/api/node/blld2012-d182-k1/history"))
show("POST /api/admin/diff", c.post("/api/admin/diff", json={"old_doc_id": "blld2012", "new_doc_id": "blld2019", "write": False}))
show("POST /api/draft/preview", c.post("/api/draft/preview", json={"doc_type": "quyet_dinh", "org_name": "Phòng Nhân sự", "number": "1/QĐ", "subject": "Về việc X", "body": "Điều 1. ...", "signer_name": "A"}))
show("POST /api/draft/export", c.post("/api/draft/export", json={"doc_type": "quyet_dinh", "org_name": "P", "number": "1/QĐ", "subject": "X", "body": "Điều 1.", "signer_name": "A"}))
show("POST /api/report", c.post("/api/report", json={"topic": "thời giờ nghỉ ngơi", "top_k": 6}))
show("POST /api/precedent", c.post("/api/precedent", json={"query": "sa thải trái pháp luật", "top_k": 2}))
show("GET /api/threads", c.get("/api/threads"))
# chat SSE
with c.stream("POST", "/api/chat", json={"message": "Nghỉ lễ Tết được mấy ngày?", "history": []}) as r:
    evs = [ln for ln in r.iter_lines() if ln.startswith("event:")]
    print(f"[{'OK ' if r.status_code < 400 else 'ERR'}] {r.status_code} POST /api/chat (SSE)  :: events={len(evs)} {evs[:6]}")
