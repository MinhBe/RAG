"""Câu hỏi nối tiếp: "còn lao động nữ thì sao?" chỉ có nghĩa khi đọc kèm câu trước.

Truy xuất không đoán chắc câu nào là nối tiếp: khi có lịch sử, nó tìm CẢ câu hiện
tại lẫn câu trước + câu hiện tại rồi đan xen kết quả. Quy tắc chỉ quyết định danh
sách nào đứng trước, nên đoán sai cũng không làm mất kết quả của câu hỏi mới.
"""

from __future__ import annotations

import re
from typing import Any

# từ nối thường gặp ở câu hỏi tiếp theo trong hội thoại tiếng Việt
_CUES = re.compile(
    r"^(còn|vậy|thế|nếu vậy|như vậy|trường hợp)\b"
    r"|\b(thì sao|ra sao|trường hợp (đó|này|trên)|như trên|điều (đó|này)|khoản (đó|này))\b",
    re.IGNORECASE,
)
_SHORT_WORDS = 5            # câu cụt kiểu "người quản lý thì?" gần như luôn là nối tiếp
_HISTORY_TURNS = 2          # số lượt hỏi gần nhất đưa vào prompt
_ANSWER_PREVIEW = 300       # cắt câu trả lời trước để prompt không phình


def last_user_question(history: list[dict[str, str]] | None) -> str | None:
    for turn in reversed(history or []):
        if turn.get("role") == "user" and (turn.get("content") or "").strip():
            return turn["content"].strip()
    return None


def looks_like_follow_up(message: str) -> bool:
    text = message.strip()
    return bool(_CUES.search(text)) or len(text.split()) <= _SHORT_WORDS


def merge_hits(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]], k: int, *, primary_share: float = 0.75,
) -> list[dict[str, Any]]:
    """Giữ tối đa k kết quả: phần lớn chỗ cho danh sách ưu tiên, phần còn lại cho
    danh sách kia, bỏ trùng node_id. Đan xen 1:1 thì mỗi bên chỉ còn k/2 chỗ và
    cắt mất kết quả đúng nằm ở hạng 5 của danh sách ưu tiên."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def take(hits, limit):
        for h in hits:
            if len(out) >= limit:
                return
            if h["node_id"] not in seen:
                seen.add(h["node_id"])
                out.append(h)

    take(primary, round(k * primary_share))
    take(secondary, k)
    take(primary, k)          # bên kia hết kết quả thì lấp chỗ trống bằng bên ưu tiên
    return out


def search_with_history(db, message: str, history: list[dict[str, str]] | None, *, top_k: int, search):
    """Tìm theo câu hiện tại; có lịch sử thì tìm thêm theo câu trước + câu hiện tại."""
    alone = search(db, message, top_k=top_k)
    prev = last_user_question(history)
    if not prev:
        return alone
    combined = search(db, f"{prev} {message}", top_k=top_k)
    if looks_like_follow_up(message):
        return merge_hits(combined, alone, top_k)
    return merge_hits(alone, combined, top_k)


def history_block(history: list[dict[str, str]] | None) -> str:
    """Vài lượt hỏi–đáp gần nhất, để LLM hiểu đại từ và câu cụt."""
    turns = [t for t in (history or []) if (t.get("content") or "").strip()]
    # lấy từ lượt hỏi thứ _HISTORY_TURNS tính từ cuối trở đi
    user_idx = [i for i, t in enumerate(turns) if t.get("role") == "user"]
    if not user_idx:
        return ""
    start = user_idx[-_HISTORY_TURNS] if len(user_idx) >= _HISTORY_TURNS else user_idx[0]
    lines = []
    for t in turns[start:]:
        who = "Người dùng" if t.get("role") == "user" else "Trợ lý"
        content = " ".join(t["content"].split())
        if who == "Trợ lý" and len(content) > _ANSWER_PREVIEW:
            content = content[:_ANSWER_PREVIEW] + "…"
        lines.append(f"{who}: {content}")
    return "\n".join(lines)
