"""Tiện ích Server-Sent Events. Một định dạng dùng chung cho mọi luồng.

Sự kiện: token | step | tool_start | tool_end | interrupt | citation | done | error
Đọc phía client bằng fetch + ReadableStream (xem frontend/lib/sse.ts).
"""

from __future__ import annotations

import json
from typing import Any


def sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
