"""Chặn câu hỏi không nên tới LLM trả lời: chèn lệnh (prompt injection).

Lọc bằng mẫu cố định, không gọi LLM: câu chèn lệnh nhắm vào chính LLM nên không
giao cho LLM tự phán xử nó. So khớp trên chữ thường đã bỏ dấu, để "Bỏ qua hướng
dẫn" và "bo qua huong dan" như nhau.
"""

from __future__ import annotations

import re
import unicodedata

REDIRECT = (
    "Mình chỉ hỗ trợ câu hỏi về pháp luật lao động Việt Nam: hợp đồng lao động, tiền "
    "lương, thời giờ làm việc và nghỉ ngơi, kỷ luật, chấm dứt hợp đồng… Bạn thử hỏi "
    "một câu trong phạm vi đó nhé, ví dụ: «Thời gian thử việc tối đa là bao lâu?»"
)

_INJECTION = [
    # tiếng Anh
    r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,20}"
    r"\b(instructions?|prompts?|rules?|directions?)\b",
    r"\bif you are an? .{0,40}\b(assistant|assistance|ai|model|llm|bot)\b",
    r"\bhuman readers? (may|can|should) ignore\b",
    r"\b(system|hidden|initial) prompt\b",
    r"\b(api[ _-]?keys?|secret[ _-]?keys?|access[ _-]?tokens?|the flag)\b",
    r"\b(you are now|from now on you are|act as|pretend (to be|you are)|roleplay as)\b",
    r"\b(jailbreak|developer mode|dan mode)\b",
    # tiếng Việt (đã bỏ dấu)
    # "bỏ qua yêu cầu nghỉ phép của tôi" là câu hỏi thật: phải kèm "trước / ở trên / hệ thống"
    r"\bbo qua\b.{0,15}\b(huong dan|chi thi|lenh|quy tac|nguyen tac)\b.{0,15}"
    r"\b(truoc|tren|ban dau|he thong|da (duoc )?cho)\b",
    r"\b(quen|phot lo)\b.{0,20}\b(huong dan|chi thi|quy tac)\b",
    r"\b(tiet lo|in ra|gui|cho (toi|minh) xem)\b.{0,30}\b(prompt|khoa bi mat|key|huong dan he thong)\b",
    r"\b(tu (gio|nay|bay gio) ban (la|hay dong vai)|gia vo (la|ban la))\b",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in _INJECTION), re.IGNORECASE | re.DOTALL)


def normalize(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (đ -> d), gộp khoảng trắng."""
    text = text.lower().replace("đ", "d")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(normalize(text)))
