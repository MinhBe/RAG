"""Tìm kiếm hybrid trên Postgres: vector (pgvector) + từ khóa (trigram/ILIKE).

Mặc định chỉ lấy node còn hiệu lực (effective_to IS NULL). Lọc theo ngày ở M4.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rag.embeddings import embed_one


def _display(row: dict[str, Any]) -> str:
    parts = []
    if row.get("article_no"):
        parts.append(f"Điều {row['article_no']}")
    if row.get("clause_no"):
        parts.append(f"Khoản {row['clause_no']}")
    if row.get("point_letter"):
        parts.append(f"Điểm {row['point_letter']}")
    head = " ".join(parts) if parts else row["node_id"]
    return f"{head} ({row['doc_id']})"


def search_nodes(
    db: Session,
    query: str,
    *,
    top_k: int = 5,
    as_of: date | None = None,
    only_in_force: bool = True,
) -> list[dict[str, Any]]:
    # Có dữ liệu chưa?
    n = db.execute(text("SELECT count(*) FROM legal_node")).scalar() or 0
    if n == 0:
        return []

    eff_clause = ""
    params: dict[str, Any] = {"q": query, "k": top_k}
    if as_of is not None:
        eff_clause = (
            " AND effective_from <= :d AND (effective_to IS NULL OR effective_to > :d)"
        )
        params["d"] = as_of
    elif only_in_force:
        eff_clause = " AND effective_to IS NULL"

    # Vector search nếu có embedding; nếu chưa embed thì lùi về trigram.
    has_vec = db.execute(
        text("SELECT count(*) FROM legal_node WHERE embedding IS NOT NULL")
    ).scalar() or 0

    rows: list[dict[str, Any]] = []
    if has_vec:
        qvec = embed_one(query)
        params["vec"] = str(qvec)
        sql = text(
            f"""
            SELECT node_id, doc_id, article_no, clause_no, point_letter, heading, text,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM legal_node
            WHERE embedding IS NOT NULL {eff_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        )
        rows = [dict(r._mapping) for r in db.execute(sql, params)]
    else:
        sql = text(
            f"""
            SELECT node_id, doc_id, article_no, clause_no, point_letter, heading, text,
                   similarity(text, :q) AS score
            FROM legal_node
            WHERE text ILIKE '%' || :q || '%' {eff_clause}
            ORDER BY score DESC
            LIMIT :k
            """
        )
        rows = [dict(r._mapping) for r in db.execute(sql, params)]

    for r in rows:
        r["display"] = _display(r)
        r["score"] = float(r.get("score") or 0.0)
    return rows
