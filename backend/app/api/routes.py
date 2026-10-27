"""Các endpoint HTTP."""

from __future__ import annotations

import uuid

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
