"""Khói M6: báo cáo nhiều văn bản + node_history (quan hệ sửa đổi 2012->2019)."""

from app.amend.store import node_history
from app.db.base import SessionLocal
from app.report.multi_doc import build_report

r = build_report("quy định về làm thêm giờ và thời giờ nghỉ ngơi", top_k=12)
print("=== BÁO CÁO ===")
print(r["markdown"][:1200])
print("\nSố nguồn:", len(r["sources"]))

print("\n=== LỊCH SỬ SỬA ĐỔI (thử một node 2012) ===")
db = SessionLocal()
# tìm một node 2012 có supersession
from sqlalchemy import text

row = db.execute(text("SELECT old_id FROM node_supersession LIMIT 1")).first()
if row:
    for h in node_history(db, row[0]):
        print(f"  bước {h['step']}: {h['node_id']} | hiệu lực {h['effective_from']} -> {h['effective_to']} | {h['text'][:60]}")
else:
    print("  (chưa có quan hệ sửa đổi)")
db.close()
