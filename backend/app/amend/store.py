"""Lưu/đọc quan hệ sửa đổi trong Postgres (thay Neo4j).

- diff_documents: so 2 phiên bản -> ghi node_supersession + đóng effective_to node cũ.
- law_as_of(date): node lá còn hiệu lực tại một ngày.
- node_history(node_id): lần theo chuỗi supersession (recursive CTE).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.amend.diff import classify, pair_articles, pair_leaves
from app.db.models import DocumentRelation, NodeSupersession


def _fetch_leaves(db: Session, doc_id: str) -> list[dict]:
    """Node lá = node không có con. Luật VN: Khoản không Điểm thì chính Khoản là quy định."""
    sql = text(
        """
        SELECT n.node_id, n.level, n.article_no, n.clause_no, n.point_letter, n.heading, n.text
        FROM legal_node n
        WHERE n.doc_id = :doc
          AND NOT EXISTS (SELECT 1 FROM legal_node c WHERE c.parent_id = n.node_id)
        """
    )
    return [dict(r._mapping) for r in db.execute(sql, {"doc": doc_id})]


def _fetch_articles(db: Session, doc_id: str) -> list[dict]:
    sql = text(
        "SELECT article_no, heading FROM legal_node WHERE doc_id = :doc AND level = 'article'"
    )
    return [dict(r._mapping) for r in db.execute(sql, {"doc": doc_id})]


def diff_documents(
    db: Session, old_doc_id: str, new_doc_id: str, *, write: bool = True
) -> list[dict]:
    new_doc = db.execute(
        text("SELECT effective_date FROM legal_document WHERE doc_id = :id"), {"id": new_doc_id}
    ).first()
    if not new_doc:
        raise ValueError(f"không tìm thấy văn bản {new_doc_id}")
    cutover: date | None = new_doc[0]

    article_map = pair_articles(_fetch_articles(db, old_doc_id), _fetch_articles(db, new_doc_id))
    pairs = pair_leaves(_fetch_leaves(db, old_doc_id), _fetch_leaves(db, new_doc_id), article_map)

    diffs: list[dict] = []
    for old, new in pairs:
        change_type, sim, summary = classify(old, new)
        diffs.append(
            {
                "old_id": old["node_id"] if old else None,
                "new_id": new["node_id"] if new else None,
                "level": (old or new).get("level"),
                "change_type": change_type,
                "similarity": round(sim, 4),
                "summary": summary,
            }
        )
        if not write:
            continue
        if old and new and change_type != "unchanged":
            db.merge(
                NodeSupersession(
                    old_id=old["node_id"], new_id=new["node_id"],
                    change_type=change_type, similarity=round(sim, 4),
                )
            )
        if old and cutover is not None:
            db.execute(
                text("UPDATE legal_node SET effective_to = :d WHERE node_id = :id AND effective_to IS NULL"),
                {"d": cutover, "id": old["node_id"]},
            )
    if write:
        db.merge(DocumentRelation(from_doc=new_doc_id, to_doc=old_doc_id, rel="REPLACES"))
        db.commit()
        logger.info("diff {} -> {}: {} cặp thay đổi", old_doc_id, new_doc_id, len(diffs))
    diffs.sort(key=lambda d: (d["old_id"] or "zzz", d["new_id"] or "zzz"))
    return diffs


def law_as_of(db: Session, as_of: date, topic: str | None = None) -> list[dict]:
    sql = text(
        """
        SELECT n.node_id, n.level, n.heading, n.text, d.title,
               n.effective_from, n.effective_to
        FROM legal_node n JOIN legal_document d ON d.doc_id = n.doc_id
        WHERE NOT EXISTS (SELECT 1 FROM legal_node c WHERE c.parent_id = n.node_id)
          AND (n.effective_from IS NULL OR n.effective_from <= :d)
          AND (n.effective_to IS NULL OR n.effective_to > :d)
          AND (CAST(:topic AS text) IS NULL OR d.title ILIKE '%' || :topic || '%')
        ORDER BY n.doc_id, n.seq
        """
    )
    return [dict(r._mapping) for r in db.execute(sql, {"d": as_of, "topic": topic})]


def node_history(db: Session, node_id: str) -> list[dict]:
    sql = text(
        """
        WITH RECURSIVE chain(node_id, step) AS (
            SELECT :id, 0
            UNION ALL
            SELECT s.new_id, chain.step + 1
            FROM node_supersession s JOIN chain ON s.old_id = chain.node_id
        )
        SELECT c.step, n.node_id, n.level, n.text, n.effective_from, n.effective_to
        FROM chain c JOIN legal_node n ON n.node_id = c.node_id
        ORDER BY c.step
        """
    )
    return [dict(r._mapping) for r in db.execute(sql, {"id": node_id})]
