"""Khôi phục tầng Chương từ văn bản gốc (scripts/backfill_chapters.py)."""

import pytest

from scripts.backfill_chapters import chapter_map, roman_to_int


@pytest.mark.parametrize(("roman", "n"), [("I", 1), ("IV", 4), ("IX", 9), ("XIV", 14), ("XVII", 17)])
def test_roman_to_int(roman, n):
    assert roman_to_int(roman) == n


SAMPLE = """Chương I
NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Bộ luật này quy định tiêu chuẩn lao động.
Điều 2. Đối tượng áp dụng
1. Người lao động.
Chương II
VIỆC LÀM, TUYỂN DỤNG VÀ QUẢN LÝ LAO ĐỘNG
Điều 3. Việc làm
Việc làm là hoạt động lao động tạo ra thu nhập.
PHỤ LỤC
Điều 1. Mẫu hợp đồng
"""


def test_chapter_map_assigns_title_from_next_line():
    assert chapter_map(SAMPLE) == {
        1: (1, "NHỮNG QUY ĐỊNH CHUNG"),
        2: (1, "NHỮNG QUY ĐỊNH CHUNG"),
        3: (2, "VIỆC LÀM, TUYỂN DỤNG VÀ QUẢN LÝ LAO ĐỘNG"),
    }


def test_chapter_map_stops_at_appendix():
    # phụ lục đánh số Điều lại từ 1: không được ghi đè Điều 1 của phần quy phạm
    assert chapter_map(SAMPLE)[1] == (1, "NHỮNG QUY ĐỊNH CHUNG")
