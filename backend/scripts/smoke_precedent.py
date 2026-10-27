from app.agent.precedent import synthesize

r = synthesize("tranh chấp về đơn phương chấm dứt hợp đồng lao động trái pháp luật", top_k=3)
print("=== TỔNG HỢP ÁN LỆ ===")
print(r["summary"][:1500])
print("\n=== CÁC BẢN ÁN ===")
for c in r["cases"]:
    print(f"  {c['doc_name']} | án lệ: {c['precedent_number']} | tòa: {c['court']} | score {c['score']}")
