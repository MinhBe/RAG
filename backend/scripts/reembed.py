"""Tính lại embedding cho toàn bộ node bằng model thật (M2).

Chạy sau khi đổi EMBEDDER trong .env và cài requirements-ml:
    docker compose exec -e EMBEDDER=vie-v2 -T api python scripts/reembed.py
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select, update

from app.config import get_settings
from app.db.base import SessionLocal
from app.db.models import LegalNode
from app.rag.embeddings import embed


def _ctx(n: LegalNode) -> str:
    head = f"Điều {n.article_no}" + (f" ({n.heading})" if n.heading else "")
    if n.level == "article":
        return f"Điều {n.article_no}. {n.heading or ''}. {n.text}".strip()
    if n.level == "clause":
        return f"{head}, Khoản {n.clause_no}: {n.text}"
    return f"{head}, Khoản {n.clause_no}, Điểm {n.point_letter}: {n.text}"


def main() -> None:
    s = get_settings()
    logger.info("EMBEDDER={} DIM={}", s.embedder, s.embed_dim)
    db = SessionLocal()
    nodes = list(db.scalars(select(LegalNode)))
    logger.info("Tính lại embedding cho {} node...", len(nodes))
    batch = 64
    done = 0
    for i in range(0, len(nodes), batch):
        chunk = nodes[i : i + batch]
        vecs = embed([_ctx(n) for n in chunk])
        for n, v in zip(chunk, vecs, strict=True):
            db.execute(update(LegalNode).where(LegalNode.node_id == n.node_id).values(embedding=v))
        db.commit()
        done += len(chunk)
        if done % 640 == 0 or done == len(nodes):
            logger.info("  {}/{}", done, len(nodes))
    db.close()
    logger.info("Xong.")


if __name__ == "__main__":
    main()
