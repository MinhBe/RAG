from __future__ import annotations

import re
import unicodedata


def fold_text(value: str) -> str:
    """Return a lowercase ASCII comparison key for Vietnamese/user text."""
    text = value.replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).lower().strip()
