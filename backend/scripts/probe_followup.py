"""So truy xuất câu hỏi nối tiếp: cũ (chỉ câu hiện tại) vs mới (kèm lịch sử).

    docker compose exec api python -m scripts.probe_followup
"""

from __future__ import annotations

from app.agent.followup import looks_like_follow_up, search_with_history
from app.db.base import SessionLocal
from app.rag.search import search_nodes

# (câu trước, câu hiện tại, Điều trả lời đúng, loại)
CASES = [
    ("Thời gian thử việc tối đa là bao lâu?", "Còn với người quản lý doanh nghiệp thì sao?", "blld2019-d25", "nối tiếp"),
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "Làm lâu năm thì có được tăng thêm không?", "blld2019-d114", "nối tiếp"),
    ("Làm thêm giờ tối đa bao nhiêu giờ một năm?", "Vậy tiền lương trả thế nào?", "blld2019-d98", "nối tiếp"),
    ("Người sử dụng lao động có được đơn phương chấm dứt hợp đồng không?", "Thế phải báo trước bao nhiêu ngày?", "blld2019-d36", "nối tiếp"),
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "Tuổi nghỉ hưu của người lao động là bao nhiêu?", "blld2019-d169", "đối chứng"),
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "Thời gian thử việc tối đa?", "blld2019-d25", "đối chứng ngắn"),
]
K = 8


def rank(hits, article):
    arts = ["-".join(h["node_id"].split("-")[:2]) for h in hits]
    return arts.index(article) + 1 if article in arts else None


def main() -> None:
    db = SessionLocal()
    print(f"{'loại':15s} {'nối tiếp?':9s} {'cũ':>4s} {'mới':>4s}  câu hiện tại")
    for prev, msg, art, kind in CASES:
        history = [{"role": "user", "content": prev}, {"role": "assistant", "content": "…"}]
        old = rank(search_nodes(db, msg, top_k=K), art)
        new = rank(search_with_history(db, msg, history, top_k=K, search=search_nodes), art)
        print(f"{kind:15s} {str(looks_like_follow_up(msg)):9s} {old!s:>4} {new!s:>4}  {msg}")
    db.close()


if __name__ == "__main__":
    main()
