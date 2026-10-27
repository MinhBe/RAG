"""Chạy so sánh phiên bản BLLĐ 2012 -> 2019, ghi quan hệ sửa đổi vào Postgres."""

from app.amend.store import diff_documents
from app.db.base import SessionLocal

db = SessionLocal()
diffs = diff_documents(db, "blld2012", "blld2019", write=True)
from collections import Counter

c = Counter(d["change_type"] for d in diffs)
print("Tổng cặp:", len(diffs))
for k, v in c.most_common():
    print(f"  {k}: {v}")
db.close()
