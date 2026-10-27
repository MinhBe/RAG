"""Chuẩn hóa và tách từ tiếng Việt.

Dùng underthesea nếu có (cài ở requirements-ml.txt), ngược lại lùi về tách theo
khoảng trắng — đủ để chạy khung ở M0/M1.
"""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")

try:  # underthesea chỉ có khi đã cài requirements-ml.txt
    from underthesea import word_tokenize as _ut_tokenize  # type: ignore

    _HAS_UT = True
except Exception:  # noqa: BLE001
    _HAS_UT = False


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    return _WS.sub(" ", s).strip()


def tokenize(s: str) -> list[str]:
    s = normalize(s).lower()
    if not s:
        return []
    if _HAS_UT:
        # fixed_words giữ cụm; trả list token (dấu _ nối cụm).
        return _ut_tokenize(s, format="text").split()
    return s.split()


def tokenized_text(s: str) -> str:
    """Chuỗi đã tách từ, dùng cho full-text BM25/tsvector."""
    return " ".join(tokenize(s))
