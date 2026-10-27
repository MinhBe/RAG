from app.rag.text import fold, normalize, tokenize


def test_fold_removes_diacritics_and_d():
    assert fold("Đổi trả hàng") == "Doi tra hang"


def test_normalize_unifies_composed_and_decomposed_forms():
    decomposed = "đổi"  # "đổi" typed with a combining hook above
    assert normalize(decomposed) == "đổi"


def test_tokens_include_bigrams_and_folded_forms():
    tokens = tokenize("Hoàn tiền về ví MoMo")
    assert "hoàn_tiền" in tokens
    assert "~hoan_tien" in tokens
    # A query typed without accents shares folded tokens with the accented text.
    assert "~hoan_tien" in tokenize("hoan tien")


def test_numbers_with_separators_stay_whole():
    assert "2.000.000" in tokenize("dưới 2.000.000 đồng")
