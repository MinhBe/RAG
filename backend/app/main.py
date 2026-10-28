"""Điểm vào API — Trợ lý pháp luật lao động."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from app.api.routes import router
from app.db.base import Base, engine
from app.demo_limits import DemoRateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # pgvector đã bật ở db/init; tạo bảng nếu chưa có.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)
    logger.info("DB sẵn sàng, bảng đã tạo.")
    yield


app = FastAPI(title="Trợ lý pháp luật lao động", version="0.1.0", lifespan=lifespan)

# Rate limiting cho demo công khai (bật khi DEMO_MODE=true)
app.add_middleware(DemoRateLimitMiddleware)

# CORS — cho phép cả localhost (dev) và domain Vercel (demo)
_extra_origins = [o.strip() for o in os.getenv("EXTRA_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *_extra_origins,
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
