from app.pv.library import SECTIONS, embedding_chunks, load_library, parse_group


def test_every_item_has_four_parts_and_unique_id():
    groups = load_library()
    items = [it for g in groups for it in g["items"]]
    assert len(items) > 200
    assert len({it["id"] for it in items}) == len(items)
    for it in items:
        for key in SECTIONS.values():
            assert it[key].strip(), f"{it['id']} thiếu {key}"
        assert it["id"].startswith(it["group"] + "-")


def test_parse_rejects_missing_section():
    text = (
        "---\ngroup: GX\ntitle: Thử\npart: I\n---\n\n## GX-A01 · Câu thử\nLớp: A\n\n"
        "### Sếp hỏi\nHỏi?\n\n### Chốt kỹ thuật\nĐáp.\n"
    )
    try:
        parse_group(text)
    except ValueError as exc:
        assert "GX-A01" in str(exc)
    else:
        raise AssertionError("phải báo thiếu phần")


def test_embedding_chunks_point_back_to_item():
    chunks = embedding_chunks()
    ids = {it["id"] for g in load_library() for it in g["items"]}
    assert {c["item_id"] for c in chunks} == ids
    assert all(c["text"] for c in chunks)
