"""Khói M5: soạn quyết định theo NĐ30 + kiểm tra thể thức + xuất DOCX."""

from app.draft.nd30 import DraftInput, format_check, render_docx, render_text

d = DraftInput(
    doc_type="quyet_dinh",
    org_parent="CÔNG TY CỔ PHẦN ABC",
    org_name="Phòng Nhân sự",
    number="12/QĐ-NS",
    subject="QUYẾT ĐỊNH Về việc xử lý kỷ luật lao động",
    bases=[
        "Bộ luật Lao động ngày 20 tháng 11 năm 2019",
        "Nội quy lao động của Công ty",
    ],
    body=(
        "Điều 1. Thi hành kỷ luật lao động bằng hình thức khiển trách đối với "
        "ông Nguyễn Văn A, nhân viên Phòng Kinh doanh.\n"
        "Điều 2. Quyết định có hiệu lực kể từ ngày ký.\n"
        "Điều 3. Các ông (bà) có liên quan chịu trách nhiệm thi hành quyết định này."
    ),
    signer_title="GIÁM ĐỐC",
    signer_name="Trần Văn B",
)

print("=== KIỂM TRA THỂ THỨC ===")
print(format_check(d) or "Hợp lệ, không có cảnh báo.")
print("\n=== XEM TRƯỚC ===")
print(render_text(d))
data = render_docx(d)
open("data/raw/_draft_demo.docx", "wb").write(data)
print(f"\n=== DOCX: {len(data):,} bytes -> data/raw/_draft_demo.docx ===")
