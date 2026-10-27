from types import SimpleNamespace

from app.config import Settings
from app.llm import AnthropicLLM, build_llm, cost_usd


class FakeStream:
    def __init__(self, chunks, captured, **kwargs):
        self.chunks = chunks
        captured.update(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    async def text_stream(self):
        for c in self.chunks:
            yield c

    async def get_final_message(self):
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=1200, output_tokens=150))


async def test_anthropic_llm_streams_and_reports_usage():
    llm = AnthropicLLM(Settings(anthropic_api_key="test-key", llm_model="claude-opus-5-5", llm_effort="low"))
    captured: dict = {}
    llm.client.messages.stream = lambda **kw: FakeStream(["Đổi ", "trong 30 ngày [1]"], captured, **kw)

    gen = llm.generate("system", [{"role": "user", "content": "hi"}], [])
    text = "".join([t async for t in gen.stream])

    assert text == "Đổi trong 30 ngày [1]"
    assert captured["model"] == "claude-opus-5-5"
    assert captured["output_config"] == {"effort": "low"}
    assert gen.usage.input_tokens == 1200
    assert gen.usage.cost_usd == cost_usd("claude-opus-5-5", 1200, 150)


def test_cost_uses_price_table():
    assert cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == 24.0
    assert cost_usd("unknown-model", 10, 10) == 0.0


def test_auto_provider_falls_back_to_offline_without_key():
    assert build_llm(Settings(llm_provider="auto", anthropic_api_key=None)).name == "offline-extractive"
