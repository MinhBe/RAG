"""Fixture dùng chung.

Ba tầng test, chạy được ở mọi máy mà không cần bí mật:
- không đánh dấu: thuần Python, luôn chạy
- @pytest.mark.db: cần Postgres có dữ liệu, tự bỏ qua nếu thiếu
- @pytest.mark.llm: gọi LLM thật, chỉ chạy khi RUN_LLM_TESTS=1
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LLM_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="gọi LLM thật; đặt RUN_LLM_TESTS=1 để chạy")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def db():
    """Phiên DB tới kho đã nạp; bỏ qua cả nhóm test nếu không có."""
    from sqlalchemy import text

    from app.db.base import SessionLocal

    session = SessionLocal()
    try:
        n = session.execute(text("SELECT count(*) FROM legal_node")).scalar() or 0
    except Exception as exc:  # noqa: BLE001 - mọi lỗi kết nối đều có nghĩa là "không có DB"
        session.close()
        pytest.skip(f"không kết nối được Postgres: {exc.__class__.__name__}")
    if n == 0:
        session.close()
        pytest.skip("kho luật trống — chạy ingest trước")
    yield session
    session.close()
