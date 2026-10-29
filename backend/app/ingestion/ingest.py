"""Nạp một văn bản luật vào Postgres: parse -> validate -> ghi node + embedding.

Dùng:
    docker compose exec api python -m app.ingestion.ingest \
        --file data/raw/blld2019.txt --doc-id blld2019 \
        --title "Bộ luật Lao động" --number "45/2019/QH14" \
        --effective 2021-01-01 --type luat
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path

from loguru import logger
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.base import SessionLocal, engine, Base
from app.db.models import LegalDocument, LegalNode
from app.ingestion.parser import assign_ids, parse_articles, validate
from app.rag.embeddings import embed


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _nodes_from_articles(doc_id: str, articles: list[dict], eff_from, eff_to):
    """Dàn cây thành list bản ghi LegalNode (chưa có embedding), kèm text ngữ cảnh."""
    rows: list[dict] = []
    seq = 0
    for a in articles:
        seq += 1
        a_ctx = f"Điều {a['number']}. {a['heading']}. {a['text']}".strip()
        rows.append(
            dict(
                node_id=a["article_id"], doc_id=doc_id, level="article",
                article_no=a["number"], clause_no=None, point_letter=None,
                parent_id=None, heading=a["heading"], text=a["text"] or a["heading"],
                seq=seq, effective_from=eff_from, effective_to=eff_to, _ctx=a_ctx,
            )
        )
        for c in a["clauses"]:
            seq += 1
            c_ctx = f"Điều {a['number']} ({a['heading']}), Khoản {c['number']}: {c['text']}"
            rows.append(
                dict(
                    node_id=c["clause_id"], doc_id=doc_id, level="clause",
                    article_no=a["number"], clause_no=c["number"], point_letter=None,
                    parent_id=a["article_id"], heading=a["heading"], text=c["text"],
                    seq=seq, effective_from=eff_from, effective_to=eff_to, _ctx=c_ctx,
                )
            )
            for p in c["points"]:
                seq += 1
                p_ctx = (
                    f"Điều {a['number']} ({a['heading']}), Khoản {c['number']}, "
                    f"Điểm {p['letter']}: {p['text']}"
                )
                rows.append(
                    dict(
                        node_id=p["point_id"], doc_id=doc_id, level="point",
                        article_no=a["number"], clause_no=c["number"], point_letter=p["letter"],
                        parent_id=c["clause_id"], heading=a["heading"], text=p["text"],
                        seq=seq, effective_from=eff_from, effective_to=eff_to, _ctx=p_ctx,
                    )
                )
    return rows


def ingest_document(
    db: Session,
    *,
    doc_id: str,
    title: str,
    raw_text: str,
    number: str | None = None,
    doc_type: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    source_url: str | None = None,
    strict: bool = False,
) -> dict:
    articles = parse_articles(raw_text)
    assign_ids(doc_id, articles)
    errors = validate(articles, raw_text)
    if errors:
        logger.warning("Parser cảnh báo {} lỗi cho {}:", len(errors), doc_id)
        for e in errors[:15]:
            logger.warning("  - {}", e)
        if strict:
            raise ValueError(f"Parser lỗi, dừng (strict): {errors[:5]}")

    # Xóa dữ liệu cũ của văn bản này (idempotent).
    db.execute(delete(LegalNode).where(LegalNode.doc_id == doc_id))
    db.query(LegalDocument).filter(LegalDocument.doc_id == doc_id).delete()
    db.flush()

    db.add(
        LegalDocument(
            doc_id=doc_id, title=title, doc_type=doc_type, number=number,
            effective_date=effective_from, expired_date=effective_to,
            status="active", source_url=source_url,
        )
    )

    rows = _nodes_from_articles(doc_id, articles, effective_from, effective_to)
    # Chống trùng node_id (phụ lục không có nhãn PHỤ LỤC) — giữ bản đầu.
    seen: set[str] = set()
    deduped = []
    for r in rows:
        if r["node_id"] in seen:
            continue
        seen.add(r["node_id"])
        deduped.append(r)
    if len(deduped) != len(rows):
        logger.warning("Bỏ {} node trùng id.", len(rows) - len(deduped))
    rows = deduped
    logger.info("Nhúng {} node...", len(rows))
    vecs = embed([r["_ctx"] for r in rows])
    for r, v in zip(rows, vecs, strict=True):
        r.pop("_ctx")
        db.add(LegalNode(**r, text_hash=_hash(r["text"]), embedding=v))
    db.commit()

    n_art = sum(1 for r in rows if r["level"] == "article")
    logger.info("Đã nạp {}: {} node ({} Điều).", doc_id, len(rows), n_art)
    return {"doc_id": doc_id, "nodes": len(rows), "articles": n_art, "errors": errors}


def _cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--number")
    ap.add_argument("--type", dest="doc_type")
    ap.add_argument("--effective")
    ap.add_argument("--expired")
    ap.add_argument("--source-url")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    raw = Path(args.file).read_text(encoding="utf-8")
    eff = date.fromisoformat(args.effective) if args.effective else None
    exp = date.fromisoformat(args.expired) if args.expired else None

    db = SessionLocal()
    try:
        res = ingest_document(
            db, doc_id=args.doc_id, title=args.title, raw_text=raw,
            number=args.number, doc_type=args.doc_type,
            effective_from=eff, effective_to=exp, source_url=args.source_url,
            strict=args.strict,
        )
        print(res)
    finally:
        db.close()


if __name__ == "__main__":
    _cli()
