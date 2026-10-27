"""Tìm id văn bản bằng cách tải metadata parquet (nhỏ) về rồi query cục bộ.

Phân biệt bản tiếng Việt với bản dịch tiếng Anh ('Code ...') qua title.
"""

from __future__ import annotations

from pathlib import Path

import httpx

OUT = Path("data/raw")
META = OUT / "_metadata.parquet"
NUMBERS = ["45/2019/QH14", "10/2012/QH13", "145/2020/NĐ-CP"]


def _parquet_url(config: str) -> str:
    r = httpx.get(
        "https://datasets-server.huggingface.co/parquet",
        params={"dataset": "th1nhng0/vietnamese-legal-documents", "config": config},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["parquet_files"][0]["url"]


def main() -> None:
    import duckdb

    OUT.mkdir(parents=True, exist_ok=True)
    if not (META.exists() and META.stat().st_size > 1_000_000):
        url = _parquet_url("metadata")
        print("Tải metadata parquet...")
        with httpx.stream("GET", url, timeout=None, follow_redirects=True) as r:
            r.raise_for_status()
            with open(META, "wb") as f:
                for c in r.iter_bytes(1 << 20):
                    f.write(c)
        print(f"  {META.stat().st_size/1e6:.1f} MB")

    con = duckdb.connect()
    nums = ",".join(f"'{n}'" for n in NUMBERS)
    rows = con.execute(
        f"SELECT id, so_ky_hieu, loai_van_ban, title FROM read_parquet('{META}') "
        f"WHERE so_ky_hieu IN ({nums}) ORDER BY so_ky_hieu"
    ).fetchall()
    for r in rows:
        print(f"id={r[0]} | so={r[1]} | loai={r[2]} | {(r[3] or '')[:75]}")


if __name__ == "__main__":
    main()
