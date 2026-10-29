"""Trích dẫn chiếu nội văn bản: "khoản 2 Điều 35", "điểm d khoản 1 Điều 35 của Bộ luật Lao động".

Khó nhất không phải bắt được con số mà là biết dẫn chiếu trỏ sang văn bản nào.
Nghị định 145 có tới Điều 115, nên "theo khoản 3 Điều 12" để trống tên văn bản
vẫn khớp được trong chính nó, trong khi nghĩa thật là Điều 12 Bộ luật Lao động.
Vì vậy ngữ cảnh văn bản được kế thừa: lần nhắc tên rõ ràng gần nhất phía trước
thắng, rồi tới ngữ cảnh của Điều cha, cuối cùng mới mặc định là văn bản nguồn.
"""

from __future__ import annotations

import re

# điểm a | khoản 1 | Điều 35 — ba phần đầu đều có thể vắng trừ "Điều"
RE_REF = re.compile(
    r"(?:điểm\s+([a-zđ])\s+)?"
    r"(?:khoản\s+(\d{1,2})\s+)?"
    r"Điều\s+(\d{1,3})\b",
    re.IGNORECASE,
)

# tên văn bản đi ngay sau dẫn chiếu: "của Bộ luật này", "của Bộ luật Lao động"
RE_DOC_AFTER = re.compile(
    r"^[\s,]*(?:của\s+|tại\s+)?"
    r"(Bộ\s*luật|Nghị\s*định|Luật|Thông\s*tư)\s+"
    r"(này|Lao\s*động|số\s*[\w/\-]+)",
    re.IGNORECASE,
)

# tên văn bản nhắc ở bất kỳ đâu trong câu, dùng làm ngữ cảnh kế thừa
RE_DOC_ANY = re.compile(
    r"(Bộ\s*luật|Nghị\s*định|Luật|Thông\s*tư)\s+(này|Lao\s*động)",
    re.IGNORECASE,
)

#: tên gọi -> doc_id. "Bộ luật Lao động" trỏ bản đang có hiệu lực.
NAMED_DOCS = {"bo luat lao dong": "blld2019"}


def _flat(s: str) -> str:
    """Bỏ dấu thô để so khớp tên văn bản, đủ dùng cho vài tên cố định."""
    out = s.lower()
    for a, b in (
        ("àáảãạăằắẳẵặâầấẩẫậ", "a"), ("èéẻẽẹêềếểễệ", "e"),
        ("ìíỉĩị", "i"), ("òóỏõọôồốổỗộơờớởỡợ", "o"),
        ("ùúủũụưừứửữự", "u"), ("ỳýỷỹỵ", "y"), ("đ", "d"),
    ):
        for ch in a:
            out = out.replace(ch, b)
    return re.sub(r"\s+", " ", out).strip()


def _resolve_doc(phrase_kind: str, phrase_name: str, src_doc: str) -> str | None:
    """Tên văn bản trong câu -> doc_id."""
    name = _flat(phrase_name)
    if name == "nay":
        return src_doc
    full = _flat(f"{phrase_kind} {phrase_name}")
    for key, doc in NAMED_DOCS.items():
        if key in full:
            # Bộ luật 2012 tự nhắc tên mình thì vẫn là chính nó
            return src_doc if src_doc == "blld2012" else doc
    return None


def _node_id(doc: str, art: int, clause: int | None, point: str | None) -> str:
    nid = f"{doc}-d{art}"
    if clause is not None:
        nid += f"-k{clause}"
        if point:
            nid += f"-{point}"
    return nid


def extract_refs(
    text: str,
    src_doc: str,
    *,
    article_context: str | None = None,
) -> list[tuple[str, str]]:
    """Trả về [(node_id đích, đoạn trích)] — chưa kiểm tra node có thật hay không.

    ``article_context`` là toàn văn của Điều cha, dùng khi bản thân đoạn text
    không nhắc tên văn bản nào.
    """
    if not text:
        return []

    # ngữ cảnh dự phòng từ Điều cha
    inherited: str | None = None
    if article_context:
        for m in RE_DOC_ANY.finditer(article_context):
            doc = _resolve_doc(m.group(1), m.group(2), src_doc)
            if doc and doc != src_doc:
                inherited = doc
                break

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    last_explicit: str | None = None

    for m in RE_REF.finditer(text):
        point, clause, art = m.group(1), m.group(2), m.group(3)

        tail = text[m.end():m.end() + 70]
        if dm := RE_DOC_AFTER.match(tail):
            doc = _resolve_doc(dm.group(1), dm.group(2), src_doc)
            if doc:
                last_explicit = doc
        doc = last_explicit or inherited or src_doc

        nid = _node_id(
            doc, int(art),
            int(clause) if clause else None,
            point.lower() if point else None,
        )
        if nid in seen:
            continue
        seen.add(nid)
        out.append((nid, m.group(0).strip()))

    return out
