"""So sánh hai phiên bản văn bản -> ghép node lá, phân loại thay đổi.

Port phần Python thuần của LAWGIC graph/diffing.py (dùng lại theo cho phép của tác
giả). Mọi ngưỡng giữ nguyên số đo gốc. Phần ghi (Neo4j) được thay bằng Postgres ở
app/amend/store.py.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

SIMILARITY_PAIR_THRESHOLD = 0.75
ARTICLE_HEADING_THRESHOLD = 0.8
SIMILARITY_UNCHANGED_THRESHOLD = 0.995
STRUCTURAL_MIN_SIMILARITY = 0.5

_RE_MONEY = re.compile(r"([\d.,]+)\s*(?:đồng|VNĐ|VND)", re.I)
_RE_MONTHS = re.compile(r"(\d+)\s*tháng", re.I)
_RE_PERMANENT = re.compile(r"vĩnh\s*viễn|không\s*thời\s*hạn", re.I)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


def _parse_money(text: str) -> list[int]:
    out = []
    for raw in _RE_MONEY.findall(text):
        digits = raw.replace(".", "").replace(",", "")
        if digits.isdigit():
            out.append(int(digits))
    return sorted(out)


def _parse_months(text: str) -> list[int]:
    return sorted(int(m) for m in _RE_MONTHS.findall(text))


def _severity(text: str) -> dict[str, Any]:
    return {
        "money": _parse_money(text),
        "months": _parse_months(text),
        "permanent": bool(_RE_PERMANENT.search(text)),
    }


def pair_articles(old_articles: list[dict], new_articles: list[dict]) -> dict[int, int]:
    """Ghép số Điều cũ -> số Điều mới theo heading. Node: {article_no, heading}."""
    mapping: dict[int, int] = {}
    used: set[int] = set()
    cands = sorted(
        (
            (_similarity(o["heading"], n["heading"]), o["article_no"], n["article_no"])
            for o in old_articles
            for n in new_articles
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    for score, old_no, new_no in cands:
        if score < ARTICLE_HEADING_THRESHOLD:
            break
        if old_no in mapping or new_no in used:
            continue
        mapping[old_no] = new_no
        used.add(new_no)
    return mapping


def pair_leaves(
    old: list[dict], new: list[dict], article_map: dict[int, int] | None = None
) -> list[tuple[dict | None, dict | None]]:
    """Ghép node lá cũ<->mới. Node: {node_id, article_no, clause_no, point_letter, level, text}."""
    article_map = article_map or {}
    pairs: list[tuple[dict | None, dict | None]] = []

    def old_key(p: dict) -> tuple:
        return (article_map.get(p["article_no"], p["article_no"]), p["clause_no"], p["point_letter"])

    def new_key(p: dict) -> tuple:
        return (p["article_no"], p["clause_no"], p["point_letter"])

    new_by_key = {new_key(p): p for p in new}
    used_new: set[str] = set()
    unmatched_old: list[dict] = []
    for o in old:
        m = new_by_key.get(old_key(o))
        if m and m["node_id"] not in used_new and _similarity(o["text"], m["text"]) >= STRUCTURAL_MIN_SIMILARITY:
            pairs.append((o, m))
            used_new.add(m["node_id"])
        else:
            unmatched_old.append(o)

    leftover_new = [p for p in new if p["node_id"] not in used_new]
    cands = sorted(
        (
            (_similarity(o["text"], n["text"]), o, n)
            for o in unmatched_old
            for n in leftover_new
            if o.get("level") == n.get("level")
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    paired_old: set[str] = set()
    paired_new: set[str] = set()
    for score, o, n in cands:
        if score < SIMILARITY_PAIR_THRESHOLD:
            break
        if o["node_id"] in paired_old or n["node_id"] in paired_new:
            continue
        pairs.append((o, n))
        paired_old.add(o["node_id"])
        paired_new.add(n["node_id"])

    pairs += [(o, None) for o in unmatched_old if o["node_id"] not in paired_old]
    pairs += [(None, n) for n in leftover_new if n["node_id"] not in paired_new]
    return pairs


def classify(old: dict | None, new: dict | None) -> tuple[str, float, str]:
    """Trả (change_type, similarity, summary). change_type theo LAWGIC."""
    if old is None:
        return "added", 0.0, "Quy định mới, không có bản cũ tương ứng"
    if new is None:
        return "removed", 0.0, "Bản mới bỏ hẳn quy định này"

    sim = _similarity(old["text"], new["text"])
    if sim >= SIMILARITY_UNCHANGED_THRESHOLD:
        return "unchanged", sim, "Giữ nguyên"

    so, sn = _severity(old["text"]), _severity(new["text"])
    reasons: list[str] = []
    direction = 0
    if so["money"] and sn["money"]:
        if sn["money"][-1] > so["money"][-1]:
            direction += 1
            reasons.append(f"mức tiền tăng {so['money'][-1]:,} -> {sn['money'][-1]:,}")
        elif sn["money"][-1] < so["money"][-1]:
            direction -= 1
            reasons.append(f"mức tiền giảm {so['money'][-1]:,} -> {sn['money'][-1]:,}")
    if sn["permanent"] and not so["permanent"]:
        direction += 1
        reasons.append("chuyển sang vĩnh viễn")
    elif so["permanent"] and not sn["permanent"]:
        direction -= 1
        reasons.append("bỏ vĩnh viễn")
    elif so["months"] and sn["months"]:
        if sn["months"][-1] > so["months"][-1]:
            direction += 1
            reasons.append(f"thời hạn tăng {so['months'][-1]} -> {sn['months'][-1]} tháng")
        elif sn["months"][-1] < so["months"][-1]:
            direction -= 1
            reasons.append(f"thời hạn giảm {so['months'][-1]} -> {sn['months'][-1]} tháng")

    if direction > 0:
        return "tightened", sim, "; ".join(reasons)
    if direction < 0:
        return "loosened", sim, "; ".join(reasons)
    return "reworded", sim, "; ".join(reasons) or "Đổi câu chữ, mức không đổi"
