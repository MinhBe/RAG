"""Các endpoint HTTP."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.pipeline import run_chat
from app.db.base import get_db
from app.db.models import LegalDocument, LegalNode, Thread
from app.llm.router import get_router
from app.sse import sse

router = APIRouter()


# ---------- Health ----------
@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        n_docs = db.scalar(select(func.count()).select_from(LegalDocument)) or 0
        n_nodes = db.scalar(select(func.count()).select_from(LegalNode)) or 0
        db_ok = True
    except Exception:  # noqa: BLE001
        n_docs = n_nodes = 0
        db_ok = False
    return {
        "status": "ok",
        "db": db_ok,
        "documents": n_docs,
        "nodes": n_nodes,
        "data_loaded": n_nodes > 0,
        "llm": get_router().available_providers(),
    }


# ---------- Tra cứu điều luật ----------
@router.get("/api/law/{node_id}")
def get_law(node_id: str, db: Session = Depends(get_db)):
    node = db.get(LegalNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy node {node_id}")
    return {
        "node_id": node.node_id,
        "doc_id": node.doc_id,
        "level": node.level,
        "heading": node.heading,
        "text": node.text,
        "effective_from": node.effective_from,
        "effective_to": node.effective_to,
    }


@router.get("/api/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.scalars(select(LegalDocument)).all()
    return [
        {"doc_id": d.doc_id, "title": d.title, "doc_type": d.doc_type, "status": d.status}
        for d in docs
    ]


# ---------- Tìm kiếm (M2 sẽ hoàn thiện) ----------
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/api/search")
def search(req: SearchRequest, db: Session = Depends(get_db)):
    from app.rag.search import search_nodes

    hits = search_nodes(db, req.query, top_k=req.top_k)
    return {"query": req.query, "hits": hits}


# ---------- Hiệu lực theo thời gian + sửa đổi (M4) ----------
@router.get("/api/law_as_of")
def law_as_of_route(date: str, topic: str | None = None, db: Session = Depends(get_db)):
    from datetime import date as _date

    from app.amend.store import law_as_of

    rows = law_as_of(db, _date.fromisoformat(date), topic=topic)
    return {"date": date, "topic": topic, "count": len(rows), "nodes": rows}


@router.get("/api/node/{node_id}/history")
def node_history_route(node_id: str, db: Session = Depends(get_db)):
    from app.amend.store import node_history

    return {"node_id": node_id, "history": node_history(db, node_id)}


class DiffRequest(BaseModel):
    old_doc_id: str
    new_doc_id: str
    write: bool = False


@router.post("/api/admin/diff")
def diff_route(req: DiffRequest, db: Session = Depends(get_db)):
    from app.amend.store import diff_documents

    diffs = diff_documents(db, req.old_doc_id, req.new_doc_id, write=req.write)
    changed = [d for d in diffs if d["change_type"] != "unchanged"]
    return {"total": len(diffs), "changed": len(changed), "diffs": changed[:200]}


# ---------- Soạn thảo văn bản NĐ30 (M5) ----------
class DraftRequest(BaseModel):
    doc_type: str = "quyet_dinh"
    org_name: str = ""
    org_parent: str | None = None
    number: str | None = None
    place: str = "Hà Nội"
    subject: str = ""
    bases: list[str] = []
    body: str = ""
    signer_title: str = "GIÁM ĐỐC"
    signer_name: str = ""
    recipients: list[str] = ["Như trên", "Lưu: VT."]
    auto_bases: bool = True


def _suggest_bases(db: Session) -> list[str]:
    """Gợi ý 'Căn cứ' từ các văn bản còn hiệu lực trong kho."""
    from app.db.models import LegalDocument

    docs = db.scalars(
        select(LegalDocument).where(LegalDocument.status == "active")
    ).all()
    out = []
    for d in docs:
        if d.doc_type == "luat":
            out.append(f"{d.title} số {d.number}")
        elif d.doc_type:
            out.append(f"{d.title}")
    return out


def _to_input(req: DraftRequest, db: Session):
    from app.draft.nd30 import DraftInput

    bases = list(req.bases)
    if req.auto_bases and not bases:
        bases = _suggest_bases(db)
    return DraftInput(
        doc_type=req.doc_type, org_name=req.org_name, org_parent=req.org_parent,
        number=req.number, place=req.place, subject=req.subject, bases=bases,
        body=req.body, signer_title=req.signer_title, signer_name=req.signer_name,
        recipients=req.recipients,
    )


@router.post("/api/draft/preview")
def draft_preview(req: DraftRequest, db: Session = Depends(get_db)):
    from app.draft.nd30 import format_check, render_text

    d = _to_input(req, db)
    return {"text": render_text(d), "issues": format_check(d), "bases": d.bases}


@router.post("/api/draft/export")
def draft_export(req: DraftRequest, db: Session = Depends(get_db)):
    from app.draft.nd30 import render_docx

    data = render_docx(_to_input(req, db))
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="van-ban.docx"'},
    )


# ---------- Tổng hợp án lệ (M6b) ----------
class PrecedentRequest(BaseModel):
    query: str
    top_k: int = 4


@router.post("/api/precedent")
def precedent_route(req: PrecedentRequest):
    from app.agent.precedent import synthesize

    return synthesize(req.query, top_k=req.top_k)


# ---------- Báo cáo nhiều văn bản (M6) ----------
class ReportRequest(BaseModel):
    topic: str
    top_k: int = 15


@router.post("/api/report")
def report_route(req: ReportRequest):
    from app.report.multi_doc import build_report

    return build_report(req.topic, top_k=req.top_k)


@router.post("/api/report/export")
def report_export_route(req: ReportRequest):
    from fastapi.responses import Response

    from app.report.multi_doc import build_report, report_to_docx

    data = report_to_docx(build_report(req.topic, top_k=req.top_k))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="bao-cao.docx"'},
    )


# ---------- Chat (SSE) ----------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    history: list[ChatMessage] = []


@router.post("/api/chat")
def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in req.history]

    def gen():
        thread_id = req.thread_id or uuid.uuid4().hex
        yield sse("start", {"thread_id": thread_id})
        try:
            for event, data in run_chat(req.message, history):
                yield sse(event, data)
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


# ---------- Threads (tối giản) ----------
@router.get("/api/threads")
def list_threads(db: Session = Depends(get_db)):
    rows = db.scalars(select(Thread).order_by(Thread.updated_at.desc())).all()
    return [{"id": t.id, "title": t.title} for t in rows]


# ---------- Knowledge Graph ----------
@router.get("/api/graph")
def graph_route(query: str = "", top_k: int = 20, db: Session = Depends(get_db)):
    """Trả về nodes + edges cho knowledge graph theo từ khóa.
    Nếu query rỗng, trả về toàn bộ nodes (giới hạn top_k, ưu tiên Điều cấp article).
    """
    from app.rag.search import search_nodes, _display
    from app.db.models import NodeSupersession
    from sqlalchemy import select as sa_select2, text as sa_text

    if query.strip():
        hits = search_nodes(db, query, top_k=top_k)
    else:
        # Không có query → lấy tất cả nodes article-level trước, rồi clause
        rows = db.execute(
            sa_text(
                "SELECT node_id, doc_id, article_no, clause_no, point_letter, heading, text, level "
                "FROM legal_node "
                "ORDER BY CASE level WHEN 'article' THEN 0 WHEN 'clause' THEN 1 ELSE 2 END, node_id "
                "LIMIT :k"
            ),
            {"k": top_k},
        ).all()
        hits = []
        for r in rows:
            d = dict(r._mapping)
            d["display"] = _display(d)
            d["score"] = 0.0
            hits.append(d)

    if not hits:
        return {"nodes": [], "edges": [], "query": query}

    node_ids = [h["node_id"] for h in hits]
    id_set = set(node_ids)

    # --- Nodes ---
    nodes = []
    for h in hits:
        nodes.append({
            "id": h["node_id"],
            "label": h.get("display") or h["node_id"],
            "doc_id": h["doc_id"],
            "level": h.get("level", "article"),
            "heading": h.get("heading", ""),
            "text": h["text"][:300] if h.get("text") else "",
            "score": round(h.get("score", 0), 3),
        })

    # --- Edges ---
    edges: list[dict] = []
    seen_edges: set[tuple] = set()

    def add_edge(src: str, tgt: str, etype: str):
        key = (src, tgt)
        if key not in seen_edges and src != tgt:
            seen_edges.add(key)
            edges.append({"source": src, "target": tgt, "type": etype})

    # 1. Parent → child hierarchy (parent_id field)
    from app.db.models import LegalNode
    from sqlalchemy import select as sa_select
    parent_rows = db.execute(
        sa_select(LegalNode.node_id, LegalNode.parent_id)
        .where(LegalNode.node_id.in_(node_ids))
        .where(LegalNode.parent_id.isnot(None))
    ).all()
    for nid, pid in parent_rows:
        if pid in id_set:
            add_edge(pid, nid, "parent_child")

    # 2. Supersession links involving our nodes
    sup_rows = db.execute(
        sa_select(NodeSupersession.old_id, NodeSupersession.new_id)
        .where(
            NodeSupersession.old_id.in_(node_ids) |
            NodeSupersession.new_id.in_(node_ids)
        )
    ).all()
    for old_id, new_id in sup_rows:
        # Add endpoint nodes if not already in result
        for nid in (old_id, new_id):
            if nid not in id_set:
                node = db.get(LegalNode, nid)
                if node:
                    nodes.append({
                        "id": node.node_id,
                        "label": f"Điều {node.article_no}" + (f" K{node.clause_no}" if node.clause_no else ""),
                        "doc_id": node.doc_id,
                        "level": node.level,
                        "heading": node.heading or "",
                        "text": (node.text or "")[:300],
                        "score": 0,
                        "ghost": True,
                    })
                    id_set.add(nid)
        add_edge(old_id, new_id, "superseded_by")

    # 3. Same-article siblings (connect clauses of same article)
    article_groups: dict[str, list[str]] = {}
    for nid in node_ids:
        parts = nid.rsplit("-k", 1)
        art = parts[0]
        article_groups.setdefault(art, []).append(nid)
    for art, siblings in article_groups.items():
        if len(siblings) > 1:
            for i in range(len(siblings) - 1):
                add_edge(siblings[i], siblings[i + 1], "sibling")

    return {"nodes": nodes, "edges": edges, "query": query}


# ---------- Human-in-loop: Escalation (câu hỏi không đủ căn cứ) ----------
_ESC_FILE = Path("/app/data/escalations.json")
_esc_lock = threading.Lock()


def _load_esc() -> list[dict]:
    try:
        if _ESC_FILE.exists():
            return json.loads(_ESC_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return []


def _save_esc(rows: list[dict]) -> None:
    _ESC_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ESC_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


class EscalateRequest(BaseModel):
    question: str
    thread_id: str | None = None


class EscalateUpdate(BaseModel):
    status: str  # "approved" | "denied"


@router.post("/api/escalate")
def escalate(req: EscalateRequest):
    """Ghi nhận câu hỏi không đủ căn cứ để nhà phát hành xem xét."""
    row = {
        "id": uuid.uuid4().hex,
        "question": req.question,
        "thread_id": req.thread_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _esc_lock:
        rows = _load_esc()
        rows.insert(0, row)
        _save_esc(rows)
    return {"id": row["id"], "status": "pending"}


@router.get("/api/escalations")
def list_escalations():
    """Lấy danh sách câu hỏi chờ phê duyệt."""
    with _esc_lock:
        return _load_esc()


@router.patch("/api/escalations/{esc_id}")
def update_escalation(esc_id: str, req: EscalateUpdate):
    """Cập nhật trạng thái: approved / denied."""
    with _esc_lock:
        rows = _load_esc()
        for r in rows:
            if r["id"] == esc_id:
                r["status"] = req.status
                r["resolved_at"] = datetime.now(timezone.utc).isoformat()
                break
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy escalation")
        _save_esc(rows)
    return {"id": esc_id, "status": req.status}
