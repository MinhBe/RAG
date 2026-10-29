"""Pipeline chat phỏng vấn (/pv).

Cách hoạt động:
  - Lần gọi đầu (history rỗng): AI tự giới thiệu và hỏi câu đầu tiên.
  - Các lần sau: AI đánh giá câu trả lời, cho nhận xét ngắn, rồi hỏi câu tiếp theo.
  - Khi hỏi đủ số câu: AI tổng kết buổi phỏng vấn.

Câu hỏi lấy từ app/pv/data/*.md (221 câu, 13 nhóm). Mỗi buổi lấy N câu ngẫu nhiên
(có thể lọc theo nhóm). Toàn bộ nội dung câu hỏi + gợi ý trả lời được nhúng vào
system prompt để AI đánh giá chính xác.
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from loguru import logger

from app.llm.router import LLMError, get_router
from app.pv.library import load_library

DEFAULT_N = 5  # số câu hỏi mỗi buổi

INTERVIEWER_SYSTEM = """\
Bạn là người phỏng vấn kỹ thuật AI/RAG/LLM chuyên nghiệp.
Nhiệm vụ của bạn: hỏi ứng viên các câu hỏi kỹ thuật từ danh sách bên dưới, \
đánh giá câu trả lời, và cho nhận xét cụ thể.

QUY TẮC:
1. Hỏi ĐÚNG MỘT câu hỏi tại một thời điểm (dùng "Sếp hỏi" trong danh sách).
2. Sau khi ứng viên trả lời: nhận xét ngắn (2–4 câu) dựa trên "Chốt kỹ thuật", \
điểm mạnh/yếu, rồi chuyển câu tiếp theo.
3. Đánh giá theo thang: Xuất sắc / Đạt / Cần bổ sung / Chưa đạt.
4. Nếu ứng viên trả lời lạc đề hoặc sai hoàn toàn: giải thích ngắn gọn điểm chính.
5. Sau câu hỏi cuối cùng: tổng kết buổi phỏng vấn (điểm mạnh tổng thể, điểm cần cải thiện).
6. Trả lời bằng tiếng Việt, giọng chuyên nghiệp nhưng thân thiện.
7. KHÔNG tiết lộ toàn bộ nội dung "Chốt kỹ thuật" — chỉ dùng để đánh giá nội bộ.

DANH SÁCH CÂU HỎI BUỔI HÔM NAY:
{questions_block}

Bắt đầu bằng cách chào ứng viên và hỏi câu đầu tiên ngay."""


def _format_questions(items: list) -> str:
    parts = []
    for i, item in enumerate(items, 1):
        lines = [
            f"--- Câu {i}/{len(items)} [{item['id']}] {item['title']} ---",
            f"Sếp hỏi: {item['question'].strip()}",
            f"Chốt kỹ thuật (nội bộ): {item['technical'].strip()}",
        ]
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _pick_questions(group: str | None, n: int) -> list:
    lib = load_library()
    pool: list = []
    for g in lib:
        if group and g["group"] != group:
            continue
        pool.extend(g["items"])
    if not pool:
        pool = [item for g in lib for item in g["items"]]
    return random.sample(pool, min(n, len(pool)))


def run_pv_chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
    group: str | None = None,
    n: int = DEFAULT_N,
) -> Iterator[tuple[str, object]]:
    """Yield (event, data) cho SSE. event in {'token', 'system', 'done', 'error'}.

    Lần đầu (history rỗng, system_prompt=None): tạo system prompt từ thư viện, trả về
    qua event 'system' để client lưu lại và gửi lại ở các request sau.
    """
    history = history or []
    router = get_router()

    if not any(router.available_providers().values()):
        yield "token", {"text": "Chưa cấu hình khóa LLM nào trong .env. Hãy điền khóa rồi khởi động lại."}
        yield "done", {}
        return

    if not system_prompt:
        # Lần đầu của buổi: chọn câu hỏi, tạo system prompt
        items = _pick_questions(group, n)
        questions_block = _format_questions(items)
        system_prompt = INTERVIEWER_SYSTEM.format(questions_block=questions_block)
        # Gửi system_prompt về để client lưu lại cho các turn sau
        yield "system", {"prompt": system_prompt}

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        full_text = ""
        for chunk in router.stream(messages, task="chat"):
            full_text += chunk
            yield "token", {"text": chunk}
        yield "done", {"full": full_text}
    except LLMError as exc:
        logger.warning("PV chat LLM error: {}", exc)
        yield "token", {"text": f"Lỗi LLM: {exc}"}
        yield "done", {}
    except Exception as exc:  # noqa: BLE001
        logger.exception("PV chat unexpected error")
        yield "error", {"message": str(exc)}
