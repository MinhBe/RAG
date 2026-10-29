"""Embedding bộ câu hỏi phỏng vấn (app/pv/data) vào bảng pv_chunk.

Chạy lại sau mỗi lần sửa file .md: đoạn nào có text đổi thì embed lại, đoạn
không còn trong thư viện thì xoá. Dùng cùng model embedding với dữ liệu luật.

    docker compose exec api python -m scripts.embed_pv
"""

from __future__ import annotations

import time

from sqlalchemy import select

from app.db.base import Base, SessionLocal, engine
from app.db.models import PvChunk
from app.pv.library import embedding_chunks
from app.rag.embeddings import embed

BATCH = 32


def main() -> None:
    Base.metadata.create_all(bind=engine, tables=[PvChunk.__table__])
    chunks = embedding_chunks()
    db = SessionLocal()
    try:
        have = {c.chunk_id: c for c in db.scalars(select(PvChunk))}
        todo = [c for c in chunks if c["chunk_id"] not in have
                or have[c["chunk_id"]].text != c["text"] or have[c["chunk_id"]].embedding is None]
        stale = set(have) - {c["chunk_id"] for c in chunks}

        t0 = time.monotonic()
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            for c, vec in zip(batch, embed([c["text"] for c in batch]), strict=True):
                db.merge(PvChunk(
                    chunk_id=c["chunk_id"], item_id=c["item_id"], group_id=c["group"],
                    section=c["section"], text=c["text"], embedding=vec,
                ))
            db.commit()
            print(f"  {min(i + BATCH, len(todo))}/{len(todo)}", flush=True)
        for cid in stale:
            db.delete(have[cid])
        db.commit()
        print(f"Xong: {len(chunks)} đoạn, embed {len(todo)}, xoá {len(stale)}, "
              f"{time.monotonic() - t0:.0f}s")
    finally:
        db.close()


if __name__ == "__main__":
    main()
