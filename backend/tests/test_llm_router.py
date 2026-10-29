"""Router LLM: bỏ phần <think>, parse JSON, và cuộc đua giữa các model Dahl (không gọi mạng)."""

import threading
import time

import pytest

from app.llm import router as r


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("<think>nghĩ...</think>\n45 ngày", "45 ngày"),
        ("nghĩ trong template</think>45 ngày", "45 ngày"),
        ("<think>hết token khi còn đang nghĩ", ""),
        ("45 ngày", "45 ngày"),
    ],
)
def test_strip_think(raw, want):
    assert r.strip_think(raw) == want


def test_parse_json_accepts_fenced_and_rejects_garbage():
    assert r.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert r.parse_json('Đây: {"a": 2} xong') == {"a": 2}
    with pytest.raises(ValueError):
        r.parse_json("không có json")


@pytest.fixture
def dahl_router(monkeypatch):
    monkeypatch.setattr(r.settings, "dahl_models", "fast-bad,slow-good,error")
    router = r.LLMRouter()
    router._dahl_keys = ["k"]

    def fake(model, messages, temperature, max_tokens, parse, won):
        if model == "error":
            raise RuntimeError("429")
        if model == "fast-bad":
            text = "không phải JSON"
        else:
            time.sleep(0.2)
            text = '{"ok": true}'
        return r.LLMResult(text=text, provider="dahl", model=model,
                           data=parse(text) if parse else None)

    monkeypatch.setattr(router, "_call_dahl", fake)
    return router


def test_race_takes_the_first_valid_answer(dahl_router):
    """Model nhanh nhất trả JSON hỏng thì không được thắng; model lỗi bị bỏ qua."""
    res = dahl_router.chat([{"role": "user", "content": "x"}], parse=r.parse_json)
    assert (res.model, res.data) == ("slow-good", {"ok": True})


def test_race_without_parse_takes_the_fastest(dahl_router):
    assert dahl_router.chat([{"role": "user", "content": "x"}]).model == "fast-bad"


def test_race_falls_back_when_every_dahl_model_fails(monkeypatch):
    router = r.LLMRouter()
    router._dahl_keys = ["k"]
    monkeypatch.setattr(router, "_call_dahl", lambda *a: (_ for _ in ()).throw(RuntimeError("busy")))
    monkeypatch.setattr(router, "_plan", lambda task: [("dahl", "*"), ("gemini", "g")])
    monkeypatch.setattr(router, "_call", lambda *a: r.LLMResult(text="từ gemini", provider="gemini", model="g"))
    assert router.chat([{"role": "user", "content": "x"}]).provider == "gemini"


def test_losers_stop_retrying_once_a_model_won(monkeypatch):
    """Model đang chờ chỗ (429) phải dừng thử lại khi model khác đã trả lời."""
    calls = []

    class Busy(Exception):
        status_code = 429

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append(kw["model"])
                    raise Busy()

    router = r.LLMRouter()
    router._dahl_keys = ["k"]
    monkeypatch.setattr(router, "_openai_client", lambda *a: Client)
    monkeypatch.setattr(r, "_DAHL_BUSY_DELAY", 0.6)
    won = threading.Event()
    threading.Timer(0.1, won.set).start()
    with pytest.raises(r.LLMError, match="model khác"):
        router._call_dahl("m", [], 0.2, None, None, won)
    assert len(calls) < r._DAHL_BUSY_RETRIES
