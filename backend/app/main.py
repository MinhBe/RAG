import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.knowledge import Event, KnowledgeAgent
from app.config import get_settings
from app.llm import build_llm
from app.rag.embeddings import build_embedder
from app.rag.index import HybridIndex
from app.rag.loader import load_documents

logger = logging.getLogger("backoffice")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    docs = load_documents(settings.data_dir)
    index = HybridIndex(docs, build_embedder(settings.embedder))
    llm = build_llm(settings)
    app.state.index = index
    app.state.agent = KnowledgeAgent(index, llm, settings)
    logger.info("Indexed %d chunks from %d documents; llm=%s", len(index.chunks), len(docs), llm.name)
    yield


app = FastAPI(title="Mộc An back-office agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = []


def sse(event: Event) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "chunks": len(request.app.state.index.chunks),
        "llm": request.app.state.agent.llm.name,
        "embedder": request.app.state.index.embedder.name,
    }


@app.get("/api/documents")
async def list_documents(request: Request) -> list[dict]:
    return [
        {
            "doc_id": d.doc_id,
            "title": d.title,
            "version": d.meta.get("version"),
            "effective_date": str(d.meta.get("effective_date")),
        }
        for d in request.app.state.index.documents.values()
    ]


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, request: Request) -> dict:
    doc = request.app.state.index.documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    return {"doc_id": doc.doc_id, "title": doc.title, "markdown": doc.body}


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    agent: KnowledgeAgent = request.app.state.agent

    async def events() -> AsyncIterator[str]:
        try:
            async for event in agent.run(body.message, [t.model_dump() for t in body.history]):
                if await request.is_disconnected():
                    break
                yield sse(event)
        except Exception as exc:  # surface failures to the UI instead of a silently closed stream
            logger.exception("chat failed")
            yield sse(
                Event("error", {"message": "Hệ thống đang gặp sự cố, vui lòng thử lại.", "detail": type(exc).__name__})
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
