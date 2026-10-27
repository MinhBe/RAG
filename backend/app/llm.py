"""LLM backends behind one small streaming interface.

`AnthropicLLM` calls Claude. `OfflineLLM` builds an extractive answer from the
retrieved sources so the app, tests and CI run without an API key.
"""

import asyncio
import math
import re
from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from app.config import MODEL_PRICES, Settings
from app.rag.text import fold, tokenize


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class Generation:
    """Streams text deltas; `usage` is filled in once the stream ends."""

    stream: AsyncIterator[str]
    usage: Usage = field(default_factory=lambda: Usage(model="unknown"))


class LLM(Protocol):
    name: str

    def generate(self, system: str, messages: list[dict], sources: list[dict]) -> Generation: ...


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = MODEL_PRICES.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class AnthropicLLM:
    def __init__(self, settings: Settings) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.effort = settings.llm_effort
        self.max_tokens = settings.llm_max_tokens
        self.name = f"anthropic:{self.model}"

    def generate(self, system: str, messages: list[dict], sources: list[dict]) -> Generation:
        gen = Generation(stream=None, usage=Usage(model=self.model))  # type: ignore[arg-type]

        async def _stream() -> AsyncIterator[str]:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                output_config={"effort": self.effort},
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
            gen.usage.input_tokens = final.usage.input_tokens
            gen.usage.output_tokens = final.usage.output_tokens
            gen.usage.cost_usd = cost_usd(self.model, final.usage.input_tokens, final.usage.output_tokens)

        gen.stream = _stream()
        return gen


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_TABLE_HEADER = re.compile(r"^\|.*\|\n\|[-| :]+\|$", re.MULTILINE)


def _terms(text: str, folded: bool) -> set[str]:
    """Single syllables (bigrams would double-count common phrases).

    Folded forms are only used when the question was typed without accents,
    otherwise "bảo" (warranty) would also match "báo" (quote)."""
    return {t for t in tokenize(text) if t.startswith("~") == folded and "_" not in t}


class OfflineLLM:
    """Extractive fallback: picks the source lines that overlap the question most."""

    name = "offline-extractive"

    def __init__(self, max_lines: int = 3, delay: float = 0.01) -> None:
        self.max_lines = max_lines
        self.delay = delay

    def _answer(self, question: str, sources: list[dict]) -> str:
        if not sources:
            return "Xin lỗi, mình chưa tìm thấy thông tin này trong tài liệu chính sách."
        folded = question == fold(question)
        q = _terms(question, folded)
        lines = []
        for src in sources:
            for line in _SENTENCE_SPLIT.split(_TABLE_HEADER.sub("", src["text"])):
                line = line.strip(" -|*")
                if len(line) < 15 or set(line) <= set("-| :"):
                    continue
                lines.append((src["n"], line, _terms(line, folded)))
        if not lines:
            return "Xin lỗi, mình chưa tìm thấy thông tin này trong tài liệu chính sách."

        # Weight shared terms by squared rarity among the candidate lines, so one
        # specific word ("sofa") beats several generic ones ("bảo hành") repeated everywhere.
        df = Counter(t for _, _, toks in lines for t in toks)

        def score(toks: set[str]) -> float:
            return sum(math.log(len(lines) / df[t]) ** 2 for t in q & toks)

        ranked = sorted(lines, key=lambda x: (score(x[2]), -x[0]), reverse=True)
        picked = [(line, n) for n, line, toks in ranked[: self.max_lines] if score(toks) > 0] or [
            (ranked[0][1], ranked[0][0])
        ]
        body = "\n".join(f"- {line} [{n}]" for line, n in picked)
        return (
            f"Theo tài liệu chính sách:\n{body}\n\n_(Chế độ offline: câu trả lời được trích nguyên văn, chưa qua LLM.)_"
        )

    def generate(self, system: str, messages: list[dict], sources: list[dict]) -> Generation:
        question = messages[-1]["content"] if isinstance(messages[-1]["content"], str) else ""
        question = question.split("<cau_hoi>")[-1].split("</cau_hoi>")[0]
        text = self._answer(question, sources)

        async def _stream() -> AsyncIterator[str]:
            for piece in re.findall(r"\S+\s*", text):
                yield piece
                await asyncio.sleep(self.delay)

        return Generation(stream=_stream(), usage=Usage(model=self.name))


def build_llm(settings: Settings, role: str = "answer") -> LLM:
    provider = settings.llm_provider
    if provider == "auto":
        if settings.gemini_api_key:
            provider = "litellm"
        elif settings.anthropic_api_key:
            provider = "anthropic"
        else:
            provider = "offline"
    if provider == "litellm":
        import os

        from app.gateway import LiteLLMBackend, load_roles

        # Settings reads .env but does not export it, so pass the model names along explicitly.
        env = {**os.environ}
        if settings.gemini_model:
            env["GEMINI_MODEL"] = settings.gemini_model
        if settings.gemini_model_lite:
            env["GEMINI_MODEL_LITE"] = settings.gemini_model_lite
        return LiteLLMBackend(role, load_roles(settings.models_config, env)[role], settings)
    if provider == "anthropic":
        return AnthropicLLM(settings)
    if provider == "offline":
        return OfflineLLM()
    raise ValueError(f"Unknown LLM provider: {provider}")
