import os

import pytest

# Tests never call a paid API.
os.environ["LLM_PROVIDER"] = "offline"
os.environ["EMBEDDER"] = "hashing"


@pytest.fixture(scope="session")
def index():
    from app.config import get_settings
    from app.rag.embeddings import HashingEmbedder
    from app.rag.index import HybridIndex
    from app.rag.loader import load_documents

    return HybridIndex(load_documents(get_settings().data_dir), HashingEmbedder())
