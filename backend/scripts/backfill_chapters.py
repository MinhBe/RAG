"""Gán Chương cho các node đã có trong kho.

Parser nhận diện `Chương I` + tiêu đề ở dòng sau nhưng bỏ đi, nên legal_node
không có tầng Chương. Script đọc lại văn bản gốc, dựng bản đồ Điều -> Chương,
rồi cập nhật tại chỗ. Không đụng tới text hay embedding.

    docker compose exec api python -m scripts.backfill_chapters
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text as sa_text

from app.db.base import engine
from app.ingestion.parser import RE_ARTICLE, RE_CHAPTER, RE_CLOSING, RE_APPENDIX, _normalize

RAW_DIR = Path("/app/data/raw")
DOCS = ["blld2019", "blld2012", "nd145_2020"]

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int:
    total = 0
    for i, ch in enumerate(s):
        v = ROMAN[ch]
        nxt = ROMAN[s[i + 1]] if i + 1 < len(s) else 0
        total += -v if v < nxt else v
    return total


def chapter_map(raw: str) -> dict[int, tuple[int, str]]:
    """article_no -> (chapter_no, chapter_title)."""
    out: dict[int, tuple[int, str]] = {}
    cur: tuple[int, str] | None = None
    want_title = False
    last_article: int | None = None

    for line in _normalize(raw):
        if want_title:
            want_title = False
            if cur is not None:
                cur = (cur[0], line.strip())
            continue
        if RE_CLOSING.match(line) or RE_APPENDIX.match(line):
            break
        if m := RE_CHAPTER.match(line):
            cur = (roman_to_int(m.group(1)), "")
            want_title = True
            continue
        if m := RE_ARTICLE.match(line):
            num = int(m.group(1))
            # số Điều giảm = sang vùng đánh số khác (phụ lục) -> dừng, như parser
            if last_article is not None and num <= last_article:
                break
            last_article = num
            if cur is not None:
                out[num] = cur
    return out


def main() -> int:
    with engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE legal_node ADD COLUMN IF NOT EXISTS chapter_no INTEGER"
        ))
        conn.execute(sa_text(
            "ALTER TABLE legal_node ADD COLUMN IF NOT EXISTS chapter_title TEXT"
        ))

        total = 0
        for doc_id in DOCS:
            path = RAW_DIR / f"{doc_id}.txt"
            if not path.exists():
                print(f"  bỏ qua {doc_id}: không thấy {path}")
                continue

            cmap = chapter_map(path.read_text(encoding="utf-8"))
            if not cmap:
                print(f"  {doc_id}: không tách được Chương nào")
                continue

            # gom các Điều cùng Chương để cập nhật theo lô
            by_chapter: dict[tuple[int, str], list[int]] = {}
            for art_no, ch in cmap.items():
                by_chapter.setdefault(ch, []).append(art_no)

            doc_rows = 0
            for (ch_no, ch_title), arts in by_chapter.items():
                res = conn.execute(
                    sa_text(
                        "UPDATE legal_node SET chapter_no = :c, chapter_title = :t "
                        "WHERE doc_id = :d AND article_no = ANY(:arts)"
                    ),
                    {"c": ch_no, "t": ch_title, "d": doc_id, "arts": arts},
                )
                doc_rows += res.rowcount or 0

            n_ch = len(by_chapter)
            print(f"  {doc_id}: {n_ch} Chương, {len(cmap)} Điều -> {doc_rows} node")
            total += doc_rows

        missing = conn.execute(sa_text(
            "SELECT count(*) FROM legal_node WHERE chapter_no IS NULL"
        )).scalar()
        print(f"\nĐã gán {total} node. Còn {missing} node chưa có Chương.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
