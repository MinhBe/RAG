"""Vietnamese text normalisation and tokenisation.

Vietnamese words are often two or three syllables ("đổi trả", "hoàn tiền"), and
users frequently type without diacritics ("doi tra"). Instead of a full word
segmenter we index:
  * syllables and syllable bigrams (cheap approximation of word segmentation)
  * the same tokens with diacritics removed, prefixed with "~", so a query
    without accents still matches while accented queries keep exact matches.
"""

import re
import unicodedata

_TOKEN_RE = re.compile(r"[0-9a-zà-ỹđ]+(?:[.,][0-9]+)*", re.IGNORECASE)

# Function words that carry little meaning for retrieval.
STOPWORDS = frozenset(
    """
    và hoặc của là thì mà có được cho với các những một này đó khi nếu để
    theo trong ngoài tại từ đến về như nào gì bao không ạ ơi nhé vậy thế
    tôi mình bạn em anh chị shop cửa hàng
    """.split()
)


def normalize(text: str) -> str:
    # NFC so that composed and decomposed diacritics compare equal.
    return unicodedata.normalize("NFC", text).lower()


def fold(text: str) -> str:
    """Remove Vietnamese diacritics: "Đổi trả" -> "doi tra"."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def syllables(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize(text))


def tokenize(text: str) -> list[str]:
    sylls = syllables(text)
    content = [s for s in sylls if s not in STOPWORDS]
    bigrams = [f"{a}_{b}" for a, b in zip(sylls, sylls[1:]) if not (a in STOPWORDS and b in STOPWORDS)]
    tokens = content + bigrams
    return tokens + ["~" + fold(t) for t in tokens]
