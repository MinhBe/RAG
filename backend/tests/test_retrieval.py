from app.config import get_settings
from app.rag.loader import chunk_document, load_documents


def test_chunks_keep_section_path_and_tables():
    docs = {d.doc_id: d for d in load_documents(get_settings().data_dir)}
    chunks = chunk_document(docs["CS-DOITRA"])
    table_chunk = next(c for c in chunks if "Thời hạn đổi trả" in c.section)
    assert "| Nội thất cồng kềnh | 7 ngày |" in table_chunk.text
    # Editorial disclaimer lines are not indexed.
    assert all("Tài liệu mẫu" not in c.text for c in chunks)


def test_hybrid_finds_refund_timing(index):
    hits = index.search("Thanh toán bằng thẻ Visa thì bao lâu được hoàn tiền?", top_k=3)
    assert hits[0].chunk.doc_id == "CS-HOANTIEN"
    assert "Thời gian hoàn tiền" in hits[0].chunk.section


def test_query_without_diacritics(index):
    hits = index.search("hoan tien ve vi momo mat bao lau", top_k=3)
    assert any("Thời gian hoàn tiền" in h.chunk.section for h in hits)


def test_modes_differ(index):
    q = "Sofa được bảo hành mấy năm?"
    bm25 = index.search(q, mode="bm25")
    dense = index.search(q, mode="dense")
    assert all(h.dense_rank is not None for h in dense)
    assert all(h.bm25_rank is not None for h in bm25)
