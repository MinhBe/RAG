"""Fallback: lấy nội dung văn bản bằng DuckDB đọc parquet HF trực tiếp.

Dùng khi datasets-server /filter trên config `content` (5.6GB) bị 504.
    docker compose exec -T api pip install duckdb
    docker compose exec -T api python scripts/fetch_hf_duckdb.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from html_text import html_to_text  # noqa: E402

KNOWN_IDS = {"blld2019": "139264", "blld2012": "27615", "nd145_2020": "152668"}
OUT = Path("data/raw")


def _parquet_urls(config: str) -> list[str]:
    import httpx

    r = httpx.get(
        "https://datasets-server.huggingface.co/parquet",
        params={"dataset": "th1nhng0/vietnamese-legal-documents", "config": config},
        timeout=60,
    )
    r.raise_for_status()
    return [f["url"] for f in r.json().get("parquet_files", [])]


CACHE = OUT / "_content.parquet"


def _ensure_cached() -> None:
    """Tải parquet content về đĩa một lần (784MB) để truy vấn lại khỏi tải lại."""
    import httpx

    if CACHE.exists() and CACHE.stat().st_size > 100_000_000:
        print(f"Dùng parquet đã tải: {CACHE}")
        return
    url = _parquet_urls("content")[0]
    print(f"Tải parquet về {CACHE} ...")
    with httpx.stream("GET", url, timeout=None, follow_redirects=True) as r:
        r.raise_for_status()
        with open(CACHE, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    print(f"Xong: {CACHE.stat().st_size/1e6:.1f} MB")


def main() -> None:
    import duckdb

    OUT.mkdir(parents=True, exist_ok=True)
    _ensure_cached()
    con = duckdb.connect()
    ids = ",".join(f"'{v}'" for v in KNOWN_IDS.values())
    q = f"SELECT id, content_html FROM read_parquet('{CACHE}') WHERE id IN ({ids})"
    print("Truy vấn parquet cục bộ...")
    rows = con.execute(q).fetchall()
    by_id = {r[0]: r[1] for r in rows}
    for did, hf_id in KNOWN_IDS.items():
        html = by_id.get(hf_id)
        if not html:
            print(f"  [thiếu] {did} ({hf_id})")
            continue
        text = html_to_text(html)
        (OUT / f"{did}.txt").write_text(text, encoding="utf-8")
        print(f"  LƯU {did}.txt ({len(text):,} ký tự)")


if __name__ == "__main__":
    main()
