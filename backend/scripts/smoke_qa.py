"""Khói: tìm kiếm + hỏi đáp có trích dẫn trên dữ liệu đã nạp."""

from app.agent.qa import answer_with_citations
from app.db.base import SessionLocal
from app.rag.search import search_nodes

QUESTIONS = [
    "Thời gian thử việc tối đa là bao lâu?",
    "Thời giờ làm việc bình thường trong một ngày tối đa là bao nhiêu giờ?",
    "Tuổi nghỉ hưu của người lao động là bao nhiêu?",
]

db = SessionLocal()
for q in QUESTIONS:
    print("\n### SEARCH:", q)
    for h in search_nodes(db, q, top_k=3):
        print(f"  {h['display']} | {round(h['score'],3)} | {h['text'][:80]}")
db.close()

print("\n\n===== CITED QA =====")
for q in QUESTIONS[:2]:
    print("\n### Q:", q)
    answer = ""
    cites = []
    for event, data in answer_with_citations(q):
        if event == "token":
            answer += data["text"]
        elif event == "citation":
            cites.append(f"[{data['n']}] {data['display']}")
        elif event == "step":
            print("   (", data["label"], ")")
    print("A:", answer.strip()[:400])
    print("Trích dẫn:", cites)
