"""Lấy văn bản luật từ Hugging Face `th1nhng0/vietnamese-legal-documents`.

Thử datasets-server /filter trước; nếu lỗi, fallback duckdb đọc parquet qua hf://.
Lưu text đã tách dòng vào data/raw/<doc_id>.txt và in metadata để nạp.

Dùng:
    docker compose exec -T api python scripts/fetch_hf_docs.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from html_text import html_to_text  # noqa: E402

BASE = "https://datasets-server.huggingface.co"
DS = "th1nhng0/vietnamese-legal-documents"
OUT = Path("data/raw")

# so_ky_hieu -> doc_id nội bộ
WANT = {
    "45/2019/QH14": "blld2019",
    "10/2012/QH13": "blld2012",
    "145/2020/NĐ-CP": "nd145_2020",
    "145/2020/ND-CP": "nd145_2020",
    "12/2022/NĐ-CP": "nd12_2022",
    "12/2022/ND-CP": "nd12_2022",
}


def _filter(config: str, where: str, limit: int = 5, retries: int = 3) -> list[dict]:
    last = None
    for attempt in range(retries):
        try:
            r = httpx.get(
                f"{BASE}/filter",
                params={"dataset": DS, "config": config, "split": "data", "where": where, "limit": limit},
                timeout=120,
            )
            if r.status_code == 200:
                return [row["row"] for row in r.json().get("rows", [])]
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:200]
        time.sleep(3 * (attempt + 1))
    print(f"  [filter lỗi] {config} {where} -> {last}")
    return []


def find_ids() -> dict[str, dict]:
    """so_ky_hieu -> {id, doc_id, title, ...}."""
    found: dict[str, dict] = {}
    for so, doc_id in WANT.items():
        if doc_id in {v.get("doc_id") for v in found.values()}:
            continue
        rows = _filter("metadata", f"\"so_ky_hieu\" = '{so}'", limit=3)
        for d in rows:
            d["doc_id"] = doc_id
            found[so] = d
            print(f"  tìm thấy {so} -> id={d.get('id')} ({doc_id}) | {(d.get('title') or '')[:70]}")
            break
    return found


def fetch_content(doc_db_id) -> str | None:
    # id là CHUỖI (vd "vbpqta_11135" hoặc "27615") -> luôn quote.
    rows = _filter("content", f"\"id\" = '{doc_db_id}'", limit=1)
    if rows and rows[0].get("content_html"):
        return rows[0].get("content_html")
    rows = _filter("legacy_content", f"\"id\" = '{doc_db_id}'", limit=1)
    if rows:
        return rows[0].get("content")
    return None


# id đã tra được (bỏ qua find_ids chậm). doc_id -> (hf_id, nhãn)
KNOWN_IDS = {
    "blld2019": "vbpqta_11135",
    "blld2012": "27615",
    "nd145_2020": "152668",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ids = KNOWN_IDS
    if not ids:
        found = find_ids()
        ids = {m["doc_id"]: m["id"] for m in found.values()}
    for did, hf_id in ids.items():
        path = OUT / f"{did}.txt"
        if path.exists() and path.stat().st_size > 1000:
            print(f"  BỎ QUA {did} (đã có {path})")
            continue
        raw_html = fetch_content(hf_id)
        if not raw_html:
            print(f"  [thiếu nội dung] {did} (id={hf_id})")
            continue
        text = html_to_text(raw_html)
        path.write_text(text, encoding="utf-8")
        n_dieu = text.count("\nĐiều ") + (1 if text.startswith("Điều ") else 0)
        print(f"  LƯU {path}  ({len(text):,} ký tự, ~{n_dieu} 'Điều')")


if __name__ == "__main__":
    main()
