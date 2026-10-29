"""Giới hạn lượt dùng cho bản demo công khai.

Nếu DEMO_MODE=false (mặc định ở local), middleware này bỏ qua tất cả.
Nếu DEMO_MODE=true (trên HF Spaces):
  - Mỗi IP: tối đa DEMO_IP_LIMIT lần gọi /api/chat mỗi DEMO_WINDOW_SECONDS giây.
  - Toàn hệ thống: tối đa DEMO_GLOBAL_LIMIT lần mỗi ngày.

Lưu trữ trong bộ nhớ (dict Python) — đủ dùng cho 1 worker HF Spaces free tier.
Khi pod khởi động lại, bộ đếm reset về 0.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
IP_LIMIT = int(os.getenv("DEMO_IP_LIMIT", "20"))        # lần / WINDOW giây mỗi IP
WINDOW = int(os.getenv("DEMO_WINDOW_SECONDS", "86400"))  # 24 giờ
GLOBAL_LIMIT = int(os.getenv("DEMO_GLOBAL_LIMIT", "200")) # tổng toàn ngày

_lock = Lock()
_ip_timestamps: dict[str, deque] = defaultdict(deque)
_global_count = 0
_global_reset_at = time.time() + WINDOW


class DemoRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not DEMO_MODE or not request.url.path.startswith("/api/chat"):
            return await call_next(request)

        global _global_count, _global_reset_at

        ip = request.client.host if request.client else "unknown"
        now = time.time()

        with _lock:
            # Reset global nếu quá cửa sổ
            if now > _global_reset_at:
                _global_count = 0
                _global_reset_at = now + WINDOW

            # Kiểm tra toàn hệ thống
            if _global_count >= GLOBAL_LIMIT:
                return JSONResponse(
                    {"error": "Demo đã hết lượt hôm nay. Thử lại ngày mai!",
                     "code": "global_limit"},
                    status_code=429,
                )

            # Kiểm tra theo IP
            q = _ip_timestamps[ip]
            while q and now - q[0] > WINDOW:
                q.popleft()
            if len(q) >= IP_LIMIT:
                reset_in = int(WINDOW - (now - q[0]))
                return JSONResponse(
                    {"error": f"Bạn đã dùng {IP_LIMIT} lần hôm nay. "
                               f"Thử lại sau {reset_in // 3600} giờ {(reset_in % 3600) // 60} phút.",
                     "code": "ip_limit"},
                    status_code=429,
                )

            q.append(now)
            _global_count += 1

        return await call_next(request)
