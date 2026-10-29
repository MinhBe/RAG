"""Thư viện câu hỏi phỏng vấn cho trang /pv.

Mỗi nhóm là một file Markdown trong app/pv/data. Mỗi câu bắt đầu bằng
"## <mã> · <tiêu đề>", vài dòng "Khóa: giá trị", rồi bốn phần "### Sếp hỏi",
"### Chốt kỹ thuật", "### Ví dụ tư vấn", "### Ví dụ đàm phán". Mã câu cố định nên
dùng được làm khóa khi embedding sau này.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"

SECTIONS = {
    "Sếp hỏi": "question",
    "Chốt kỹ thuật": "technical",
    "Ví dụ tư vấn": "consulting",
    "Ví dụ đàm phán": "negotiation",
}
LAYERS = {
    "A": "Đào sâu kỹ thuật",
    "B": "Giải thích cho khách hàng",
    "C": "Khách ép giá / bắt bí",
    "T": "Tình huống thực chiến",
}

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_ITEM = re.compile(r"^## (\S+) · (.+)$", re.MULTILINE)
_SECTION = re.compile(r"^### (.+)$", re.MULTILINE)
_META = re.compile(r"^(Lớp|Nguồn|Tags|Files): *(.*)$")


def _parse_meta(lines: list[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for line in lines:
        m = _META.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "Lớp":
            meta["layer"] = val
        elif key == "Nguồn":
            meta["source"] = val
        else:
            meta[key.lower()] = [v.strip() for v in val.split(",") if v.strip()]
    return meta


def parse_group(text: str) -> dict[str, Any]:
    front = _FRONT.match(text)
    if not front:
        raise ValueError("thiếu frontmatter")
    head = dict(
        line.split(":", 1) for line in front.group(1).splitlines() if ":" in line
    )
    group = {k.strip(): v.strip() for k, v in head.items()}
    body = text[front.end():]

    items = []
    starts = list(_ITEM.finditer(body))
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        chunk = body[m.end():end]
        secs = list(_SECTION.finditer(chunk))
        meta = _parse_meta(chunk[: secs[0].start()].splitlines() if secs else [])
        item: dict[str, Any] = {
            "id": m.group(1),
            "title": m.group(2).strip(),
            "group": group["group"],
            "layer": meta.get("layer", "A"),
            "source": meta.get("source", ""),
            "tags": meta.get("tags", []),
            "files": meta.get("files", []),
        }
        for j, s in enumerate(secs):
            name = s.group(1).strip()
            if name not in SECTIONS:
                raise ValueError(f"{item['id']}: phần lạ «{name}»")
            s_end = secs[j + 1].start() if j + 1 < len(secs) else len(chunk)
            item[SECTIONS[name]] = chunk[s.end():s_end].strip()
        missing = [k for k in SECTIONS.values() if not item.get(k)]
        if missing:
            raise ValueError(f"{item['id']}: thiếu {', '.join(missing)}")
        items.append(item)
    return {**group, "items": items}


@lru_cache(maxsize=1)
def load_library() -> list[dict[str, Any]]:
    groups = [parse_group(p.read_text(encoding="utf-8")) for p in sorted(DATA_DIR.glob("*.md"))]
    ids = [it["id"] for g in groups for it in g["items"]]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise ValueError(f"mã câu trùng: {sorted(dup)}")
    return groups


def embedding_chunks() -> list[dict[str, Any]]:
    """Mỗi câu tách thành các đoạn để embedding: câu hỏi kèm từng phần trả lời,
    để tìm theo câu hỏi hay theo nội dung gợi ý đều trúng đúng mã câu."""
    out = []
    for g in load_library():
        for it in g["items"]:
            for key in ("technical", "consulting", "negotiation"):
                out.append({
                    "chunk_id": f"{it['id']}#{key}",
                    "item_id": it["id"],
                    "group": g["group"],
                    "section": key,
                    "text": f"{g['title']} — {it['title']}\n{it['question']}\n\n{it[key]}",
                })
    return out
