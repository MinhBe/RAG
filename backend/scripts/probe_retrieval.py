"""Đo nhanh truy xuất hiện tại trên vài câu hỏi có đáp án biết trước.

    docker compose exec api python -m scripts.probe_retrieval
"""

from __future__ import annotations

from app.db.base import SessionLocal
from app.rag.search import search_nodes

# câu hỏi -> Điều BLLĐ 2019 trả lời đúng
PROBES = [
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "blld2019-d113"),
    ("Làm thêm giờ tối đa bao nhiêu giờ một năm?", "blld2019-d107"),
    ("Khi nghỉ việc có được trợ cấp thôi việc không?", "blld2019-d46"),
    ("Người sử dụng lao động có được đơn phương chấm dứt hợp đồng không?", "blld2019-d36"),
    ("Lao động nữ mang thai được nghỉ thai sản bao lâu?", "blld2019-d139"),
    ("Thời gian thử việc tối đa là bao lâu?", "blld2019-d25"),
    ("Có bị phạt tiền khi vi phạm kỷ luật lao động không?", "blld2019-d127"),
    ("Tiền lương làm việc vào ban đêm được tính thế nào?", "blld2019-d98"),
    ("Hợp đồng lao động phải có những nội dung gì?", "blld2019-d21"),
    ("Tuổi nghỉ hưu của người lao động là bao nhiêu?", "blld2019-d169"),
]


def article_of(node_id: str) -> str:
    return "-".join(node_id.split("-")[:2])


def main() -> None:
    db = SessionLocal()
    hit1 = hit8 = 0
    for q, want in PROBES:
        hits = search_nodes(db, q, top_k=8)
        arts = [article_of(h["node_id"]) for h in hits]
        rank = arts.index(want) + 1 if want in arts else None
        distinct = len(dict.fromkeys(arts))
        hit1 += rank == 1
        hit8 += rank is not None
        print(f"{'✓' if rank else '✗'} rank={rank!s:4} distinctArticles={distinct}  {q}")
        print(f"     top3: {[h['node_id'] for h in hits[:3]]}")
    n = len(PROBES)
    print(f"\nĐúng ở hạng 1: {hit1}/{n}   Có trong top 8: {hit8}/{n}")
    db.close()


if __name__ == "__main__":
    main()
