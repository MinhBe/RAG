"""HTML -> text theo dòng, giữ ranh giới khối để parser nhận diện Điều/Khoản/Điểm."""

from __future__ import annotations

import html
import re

_DROP = re.compile(r"<(style|script|head)\b[^>]*>.*?</\1>", re.I | re.S)
_BLOCK = re.compile(r"</(p|div|tr|li|h[1-6])>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_MULTINL = re.compile(r"\n{2,}")


def fix_mojibake(s: str) -> str:
    """Sửa trường hợp UTF-8 bị đọc nhầm thành Latin-1 (vd 'QUá»C Há»˜I' -> 'QUỐC HỘI').

    Chỉ áp dụng khi phát hiện dấu hiệu mojibake rõ, để không phá văn bản vốn đúng.
    """
    markers = s.count("Ã") + s.count("á»") + s.count("Æ") + s.count("áº")
    if markers < 5:
        return s
    # Dữ liệu gốc là UTF-8 bị đọc nhầm; thường là cp1252 (có ký tự như '˜'),
    # đôi khi latin-1. Thử lần lượt, giữ bản giảm được nhiều mojibake nhất.
    for enc in ("cp1252", "latin-1"):
        try:
            fixed = s.encode(enc, errors="strict").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if (fixed.count("Ã") + fixed.count("á»")) < markers:
            return fixed
    return s


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    s = fix_mojibake(raw.replace("\r\n", "\n"))
    s = _DROP.sub("", s)         # bỏ hẳn style/script/head
    s = _BLOCK.sub("\n", s)      # kết thúc khối -> xuống dòng
    s = _TAG.sub("", s)          # bỏ thẻ còn lại
    s = html.unescape(s)
    s = s.replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    s = "\n".join(ln for ln in lines if ln)
    return _MULTINL.sub("\n", s)
