"""LLMRouter — một cửa duy nhất cho mọi lời gọi LLM.

Ý tưởng lấy từ LAWGIC core/llm.py: tự retry lỗi tạm thời (429/5xx/mạng) có
backoff + jitter, ép trả JSON theo schema. Thêm: chọn model theo loại việc
(task) và xoay vòng nhiều key Gemini khi một key lỗi.

Các task:
  route  / lite  -> Gemini flash-lite  (định tuyến, viết lại truy vấn, tóm tắt ngắn)
  answer         -> Gemini flash       (hỏi đáp có trích dẫn)
  draft / report -> Claude             (soạn thảo, báo cáo dài)  — fallback Gemini
  judge          -> Gemini flash       (chấm eval)
  bulk           -> FPT                 (xử lý dữ liệu hàng loạt) — fallback Gemini

Nhà cung cấp dùng SDK tương thích OpenAI (Gemini, FPT) hoặc Anthropic (Claude).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Iterator

from loguru import logger

from app.config import get_settings

settings = get_settings()

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4
_BASE_DELAY = 1.0


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


class LLMError(RuntimeError):
    pass


class LLMRouter:
    def __init__(self) -> None:
        self._gemini_keys = settings.gemini_keys
        self._gemini_idx = 0

    # ---- chọn nhà cung cấp + model theo task ----
    def _plan(self, task: str) -> list[tuple[str, str]]:
        g_flash = ("gemini", settings.gemini_model)
        g_lite = ("gemini", settings.gemini_model_lite)
        claude = ("claude", settings.anthropic_model)
        fpt = ("fpt", settings.fpt_model)

        table: dict[str, list[tuple[str, str]]] = {
            "route": [g_lite, g_flash],
            "lite": [g_lite, g_flash],
            "answer": [g_flash, g_lite],
            "draft": [claude, g_flash],
            "report": [claude, g_flash],
            "judge": [g_flash, g_lite],
            "bulk": [fpt, g_flash],
        }
        plan = table.get(task, [g_flash, g_lite])
        # Lọc nhà cung cấp chưa cấu hình.
        return [(p, m) for (p, m) in plan if self._available(p)]

    def _available(self, provider: str) -> bool:
        if provider == "gemini":
            return bool(self._gemini_keys)
        if provider == "claude":
            return bool(settings.anthropic_api_key)
        if provider == "fpt":
            return bool(settings.fpt_api_key)
        return False

    def available_providers(self) -> dict[str, bool]:
        return {
            "gemini": bool(self._gemini_keys),
            "claude": bool(settings.anthropic_api_key),
            "fpt": bool(settings.fpt_api_key),
        }

    # ---- client ----
    def _openai_client(self, base_url: str, api_key: str):
        from openai import OpenAI

        return OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60.0)

    def _next_gemini_key(self) -> str:
        key = self._gemini_keys[self._gemini_idx % len(self._gemini_keys)]
        self._gemini_idx += 1
        return key

    # ---- gọi chính ----
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        task: str = "answer",
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResult:
        plan = self._plan(task)
        if not plan:
            raise LLMError(
                "Chưa cấu hình nhà cung cấp LLM nào (thiếu key Gemini/Claude/FPT trong .env)."
            )
        last_exc: Exception | None = None
        for provider, model in plan:
            try:
                return self._call(provider, model, messages, temperature, max_tokens)
            except Exception as exc:  # noqa: BLE001 — thử nhà cung cấp kế tiếp
                logger.warning("LLM {} ({}) lỗi: {}", provider, model, exc)
                last_exc = exc
        raise LLMError(f"Mọi nhà cung cấp đều lỗi: {last_exc}")

    def _call(self, provider, model, messages, temperature, max_tokens) -> LLMResult:
        if provider == "claude":
            return self._call_claude(model, messages, temperature, max_tokens)
        base_url, api_key = self._endpoint(provider)
        return self._call_openai(provider, base_url, api_key, model, messages, temperature, max_tokens)

    def _endpoint(self, provider: str) -> tuple[str, str]:
        if provider == "gemini":
            return settings.gemini_base_url, self._next_gemini_key()
        if provider == "fpt":
            return settings.fpt_base_url, settings.fpt_api_key or ""
        raise LLMError(f"Nhà cung cấp không hỗ trợ: {provider}")

    def _call_openai(
        self, provider, base_url, api_key, model, messages, temperature, max_tokens
    ) -> LLMResult:
        def _once(key: str) -> LLMResult:
            client = self._openai_client(base_url, key)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return LLMResult(text=resp.choices[0].message.content or "", provider=provider, model=model)

        return self._with_retry(lambda: _once(api_key), provider=provider, rotate=(provider == "gemini"))

    def _call_claude(self, model, messages, temperature, max_tokens) -> LLMResult:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key, max_retries=0)
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] != "system"]

        def _once() -> LLMResult:
            resp = client.messages.create(
                model=model,
                system=system or None,
                messages=conv,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            return LLMResult(text=text, provider="claude", model=model)

        return self._with_retry(_once, provider="claude", rotate=False)

    def extract_json(
        self, messages: list[dict[str, str]], *, task: str = "answer", temperature: float = 0.0
    ) -> dict:
        """Gọi LLM và parse JSON. Retry nhích nhiệt độ khi JSON hỏng."""
        import json

        for attempt in range(3):
            temp = temperature if attempt == 0 else 0.5
            res = self.chat(messages, task=task, temperature=temp)
            raw = res.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                raw = raw[4:] if raw.lower().startswith("json") else raw
                raw = raw.strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise LLMError("Không parse được JSON từ LLM sau 3 lần.")

    # ---- streaming (chỉ Gemini/FPT, OpenAI-compatible) ----
    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        task: str = "answer",
        temperature: float = 0.2,
    ) -> Iterator[str]:
        plan = self._plan(task)
        for provider, model in plan:
            try:
                if provider == "claude":
                    yield from self._stream_claude(model, messages, temperature)
                    return
                base_url, api_key = self._endpoint(provider)
                client = self._openai_client(base_url, api_key)
                stream = client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature, stream=True
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("stream {} lỗi, thử nhà cung cấp kế: {}", provider, exc)
                continue
        raise LLMError("Không stream được từ nhà cung cấp nào.")

    def _stream_claude(self, model, messages, temperature) -> Iterator[str]:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key, max_retries=0)
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] != "system"]
        with client.messages.stream(
            model=model, system=system or None, messages=conv,
            temperature=temperature, max_tokens=4096,
        ) as s:
            for text in s.text_stream:
                yield text

    # ---- retry ----
    def _with_retry(self, call, *, provider: str, rotate: bool) -> LLMResult:
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None
                )
                transient = status in _RETRYABLE_STATUS or status is None
                if not transient or attempt == _MAX_ATTEMPTS - 1:
                    raise
                delay = random.uniform(0, _BASE_DELAY * (2 ** attempt))  # full jitter
                logger.info("retry {} (lần {}/{}) sau {:.1f}s", provider, attempt + 1, _MAX_ATTEMPTS, delay)
                if rotate and self._gemini_keys:
                    # Lần sau dùng key khác; _endpoint sẽ tự lấy key kế tiếp.
                    pass
                time.sleep(delay)
        raise LLMError("hết lượt retry")


_ROUTER: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = LLMRouter()
    return _ROUTER
