"""Lấy án lệ/bản án lao động từ HF tmquan/anle-toaan-gov-vn, nạp vào Postgres (M6b).

Lọc các bản án liên quan lao động (nhắc 'lao động' hoặc viện dẫn BLLĐ), giới hạn số
lượng cho MVP. Tải parquet 'documents' về cache rồi query bằng duckdb.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import httpx
from loguru import logger

from app.db.base import Base, SessionLocal, engine
from app.db.models import Precedent
from app.rag.embeddings import embed

OUT = Path("data/raw")
CACHE = OUT / "_anle.parquet"
LIMIT = 150


def _parquet_urls() -> list[str]:
    r = httpx.get(
        "https://datasets-server.huggingface.co/parquet",
        params={"dataset": "tmquan/anle-toaan-gov-vn", "config": "documents"},
        timeout=60,
    )
    r.raise_for_status()
    return [f["url"] for f in r.json()["parquet_files"]]


def _ensure_cache() -> None:
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        logger.info("Dùng parquet án lệ đã tải: {}", CACHE)
        return
    url = _parquet_urls()[0]
    logger.info("Tải parquet án lệ...")
    with httpx.stream("GET", url, timeout=None, follow_redirects=True) as r:
        r.raise_for_status()
        with open(CACHE, "wb") as f:
            for c in r.iter_bytes(1 << 20):
                f.write(c)
    logger.info("  {:.1f} MB", CACHE.stat().st_size / 1e6)


def _as_date(v) -> date | None:
    if not v:
        return None
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def main() -> None:
    import duckdb

    OUT.mkdir(parents=True, exist_ok=True)
    _ensure_cache()
    Base.metadata.create_all(bind=engine)

    con = duckdb.connect()
    q = f"""
        SELECT doc_name, court, court_level, precedent_number, is_precedent, category,
               issued_date, to_json(citations_law) AS citations_law, web_url, markdown
        FROM read_parquet('{CACHE}')
        WHERE (lower(markdown) LIKE '%lao động%' OR lower(category) LIKE '%lao động%')
          AND markdown IS NOT NULL AND length(markdown) > 500
        ORDER BY is_precedent DESC NULLS LAST, issued_date DESC
        LIMIT {LIMIT}
    """
    rows = con.execute(q).fetchall()
    cols = [d[0] for d in con.description]
    logger.info("Lọc được {} bản án lao động.", len(rows))

    db = SessionLocal()
    db.query(Precedent).delete()
    db.commit()

    recs = [dict(zip(cols, r)) for r in rows]
    # Nhúng theo đoạn đầu bản án (tình huống + nhận định) cho gọn.
    summaries = [ (r["markdown"] or "")[:2000] for r in recs ]
    vecs = embed(summaries)
    for r, v in zip(recs, vecs):
        cl = r.get("citations_law")
        if not isinstance(cl, str):
            cl = json.dumps(cl, ensure_ascii=False) if cl is not None else None
        db.merge(
            Precedent(
                doc_name=r["doc_name"],
                title=r.get("doc_name"),
                court=r.get("court"),
                court_level=r.get("court_level"),
                precedent_number=r.get("precedent_number"),
                is_precedent=bool(r.get("is_precedent")),
                category=r.get("category"),
                issued_date=_as_date(r.get("issued_date")),
                citations_law=cl,
                source_url=r.get("web_url"),
                text=r["markdown"],
                embedding=v,
            )
        )
    db.commit()
    n = db.query(Precedent).count()
    db.close()
    logger.info("Đã nạp {} án lệ/bản án lao động.", n)


if __name__ == "__main__":
    main()
