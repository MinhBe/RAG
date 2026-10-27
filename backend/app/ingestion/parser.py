"""Tách văn bản luật -> cây Điều / Khoản / Điểm.

Port từ LAWGIC (backend/ingestion/parser.py, dùng lại theo sự cho phép của tác giả).
Regex làm chính, máy trạng thái (ngăn xếp Điều→Khoản→Điểm), kèm bộ kiểm tra bất biến.

Cấu trúc nhận diện được (đã xác minh trên văn bản thuế của LAWGIC; cần test lại cho
văn bản lao động):

    Chương I                       <- số La Mã, KHÔNG có tiêu đề cùng dòng
    QUY ĐỊNH CHUNG                 <- tiêu đề ở DÒNG SAU, viết HOA
    Mục 1. ĐĂNG KÝ ...             <- tiêu đề CÙNG dòng (khác Chương)
    Điều 1. Phạm vi điều chỉnh     <- Điều + tiêu đề CÙNG dòng
    Bộ luật này quy định ...       <- BODY
    1. Người lao động ...          <- Khoản
    a) Tổ chức, cá nhân ...        <- Điểm
"""

from __future__ import annotations

import re
import unicodedata

RE_CHAPTER = re.compile(r"^Chương\s+([IVXLCDM]+)\s*$")
RE_SECTION = re.compile(r"^Mục\s+(\d+)\b")
RE_ARTICLE = re.compile(r"^Điều\s+(\d+)\s*[.．]\s*(.*)$")
RE_CLAUSE = re.compile(r"^(\d{1,2})\s*[.．]\s+(.+)$")
RE_POINT = re.compile(r"^([a-zđ])\)\s*(.+)$")
RE_CLOSING = re.compile(
    r"^(?:Luật|Bộ luật|Nghị định|Thông tư|Nghị quyết|Quyết định)\s+này\s+(?:đã\s+)?được\s+"
    r"(?:Quốc hội|Chính phủ|Ủy ban Thường vụ Quốc hội)"
)
# Phụ lục / biểu mẫu sau phần quy phạm — đánh số Điều riêng, phải DỪNG để không
# tạo node_id trùng (vd Nghị định có phụ lục đánh lại "Điều 1").
RE_APPENDIX = re.compile(r"^(?:PHỤ\s*LỤC|BIỂU\s*MẪU|Mẫu\s+số)\b", re.I)
RE_HEADING_LEAK = re.compile(
    r"\b(?:Mục\s+\d+\s*[.．]|Chương\s+[IVXLCDM]+)\s+[A-ZĐÁÀẢÃẠÂÊÔƠƯ]{2,}"
)

# Thứ tự chữ cái tiếng Việt dùng cho Điểm: không có f, j, w, z; "đ" sau "d".
VN_LETTERS = "abcdđeghiklmnopqrstuvxy"
MIN_COVERAGE = 0.98


def _normalize(raw_text: str) -> list[str]:
    text = unicodedata.normalize("NFC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ")  # no-break space -> space thường
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def parse_articles(text: str) -> list[dict]:
    articles: list[dict] = []
    current_article: dict | None = None
    current_clause: dict | None = None
    current_point: dict | None = None
    skip_next_line = False

    for line in _normalize(text):
        if skip_next_line:
            skip_next_line = False
            continue
        if RE_CLOSING.match(line) or RE_APPENDIX.match(line):
            break  # hết phần quy phạm; phía sau là chữ ký / phụ lục
        if RE_CHAPTER.match(line):
            skip_next_line = True
            current_article = current_clause = current_point = None
            continue
        if RE_SECTION.match(line):
            current_article = current_clause = current_point = None
            continue
        if match := RE_ARTICLE.match(line):
            num = int(match.group(1))
            # Số Điều giảm = sang bối cảnh đánh số khác (phụ lục) -> dừng.
            if current_article is not None and num <= current_article["number"]:
                break
            current_article = {
                "number": num,
                "heading": match.group(2).strip(),
                "text": "",
                "clauses": [],
            }
            articles.append(current_article)
            current_clause = current_point = None
            continue
        if current_article is None:
            continue
        if match := RE_CLAUSE.match(line):
            current_clause = {
                "number": int(match.group(1)),
                "text": match.group(2).strip(),
                "points": [],
            }
            current_article["clauses"].append(current_clause)
            current_point = None
            continue
        if current_clause is not None and (match := RE_POINT.match(line)):
            current_point = {"letter": match.group(1), "text": match.group(2).strip()}
            current_clause["points"].append(current_point)
            continue
        target = current_point or current_clause or current_article
        target["text"] = f"{target['text']} {line}".strip()

    return articles


def _expected_content_length(text: str) -> int:
    total = 0
    started = False
    skip_next_line = False
    for line in _normalize(text):
        if skip_next_line:
            skip_next_line = False
            continue
        if RE_CLOSING.match(line):
            break
        if RE_CHAPTER.match(line):
            skip_next_line = True
            continue
        if RE_SECTION.match(line):
            continue
        if match := RE_ARTICLE.match(line):
            started = True
            total += len(match.group(2).strip())
            continue
        if not started:
            continue
        if match := RE_CLAUSE.match(line):
            total += len(match.group(2).strip())
        elif match := RE_POINT.match(line):
            total += len(match.group(2).strip())
        else:
            total += len(line)
    return total


def _parsed_content_length(articles: list[dict]) -> int:
    return sum(
        len(a["heading"])
        + len(a["text"])
        + sum(
            len(c["text"]) + sum(len(p["text"]) for p in c["points"])
            for c in a["clauses"]
        )
        for a in articles
    )


def assign_ids(doc_id: str, articles: list[dict]) -> None:
    """Sinh node_id từ VỊ TRÍ (ổn định giữa các lần chạy): blld2019-d35-k2-a."""
    for a in articles:
        a["article_id"] = f"{doc_id}-d{a['number']}"
        for c in a["clauses"]:
            c["clause_id"] = f"{a['article_id']}-k{c['number']}"
            for p in c["points"]:
                p["point_id"] = f"{c['clause_id']}-{p['letter']}"


def _iter_nodes(article: dict):
    an = article["number"]
    yield article.get("article_id", f"d{an}"), article["text"]
    for clause in article["clauses"]:
        yield clause.get("clause_id", f"d{an}-k{clause['number']}"), clause["text"]
        for point in clause["points"]:
            yield point.get("point_id", f"d{an}-k{clause['number']}-{point['letter']}"), point["text"]


def validate(articles: list[dict], raw_text: str) -> list[str]:
    """Trả list lỗi. Rỗng = sạch. Chạy trên 100% node, gần như miễn phí."""
    errors: list[str] = []

    numbers = [a["number"] for a in articles]
    dups = sorted({n for n in numbers if numbers.count(n) > 1})
    if dups:
        errors.append(f"Điều trùng: {dups}")
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"Điều không liên tục: đếm {len(numbers)}, max {max(numbers)}")

    for a in articles:
        clause_numbers = [c["number"] for c in a["clauses"]]
        if clause_numbers and clause_numbers != list(range(1, len(clause_numbers) + 1)):
            errors.append(f"Điều {a['number']}: Khoản không liên tục {clause_numbers}")
        for c in a["clauses"]:
            letters = [p["letter"] for p in c["points"]]
            if letters and letters != list(VN_LETTERS[: len(letters)]):
                errors.append(
                    f"Điều {a['number']} Khoản {c['number']}: Điểm sai thứ tự {letters}"
                )
            if not c["text"]:
                errors.append(f"{c['clause_id']}: text rỗng")
            for p in c["points"]:
                if not p["text"]:
                    errors.append(f"{p['point_id']}: text rỗng")
        for node_id, txt in _iter_nodes(a):
            if match := RE_HEADING_LEAK.search(txt):
                errors.append(f"{node_id}: lọt mốc cấu trúc vào text -> {match.group(0)!r}")

    parsed = _parsed_content_length(articles)
    expected = _expected_content_length(raw_text)
    if expected and parsed / expected < MIN_COVERAGE:
        errors.append(
            f"Độ phủ chỉ {parsed / expected:.1%} ({parsed:,}/{expected:,} ký tự) - đang nuốt nội dung"
        )
    return errors
