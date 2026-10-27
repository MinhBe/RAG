"""Khói M4: law_as_of trả đúng luật theo ngày."""

from datetime import date

from app.amend.store import law_as_of
from app.db.base import SessionLocal

db = SessionLocal()
for d in [date(2015, 6, 1), date(2023, 6, 1)]:
    rows = law_as_of(db, d)
    docs = {}
    for r in rows:
        docs[r["title"]] = docs.get(r["title"], 0) + 1
    print(f"\nlaw_as_of({d}): {len(rows)} node lá còn hiệu lực")
    for t, n in docs.items():
        print(f"   {n:>5}  {t}")
db.close()
