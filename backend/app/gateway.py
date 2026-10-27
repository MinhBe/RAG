"""One gateway for every model call: roles from config/models.yaml, LiteLLM underneath.

Business code asks for a role ("answer", "router", "extract"); which model serves it
is a line in the YAML file. Switching Gemini -> Claude is a config change plus an eval run.
"""

import asyncio
import os
import random
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import MODEL_PRICES, Settings
from app.llm import Generation, Usage

# ${VAR} or ${VAR:-default}
_ENV_VAR = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")

# Retry only what can succeed on a second try: rate limits and server-side errors.
# 400 (bad request), 401/403 (key), 404 (model name) fail the same way every time.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


@dataclass
class RoleConfig:
    model: str
    fallbacks: list[str] = field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 2000


def load_roles(path: Path, env: dict[str, str] | None = None) -> dict[str, RoleConfig]:
    """Reads the role table, filling ${VAR} or ${VAR:-default} from the environment.

    A missing variable with no default is an error at startup, not a 404 on the first request."""
    env = dict(os.environ) if env is None else env

    def expand(value: str, role: str) -> str:
        def sub(m: re.Match) -> str:
            name, default = m.group(1), m.group(2)
            if env.get(name):
                return env[name]
            if default is not None:
                return default
            raise ValueError(f"{path.name}: role '{role}' needs {name}, set it in .env")

        return _ENV_VAR.sub(sub, value)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["roles"]
    roles = {}
    for name, cfg in raw.items():
        roles[name] = RoleConfig(
            model=expand(cfg["model"], name),
            fallbacks=[expand(m, name) for m in cfg.get("fallbacks") or []],
            temperature=float(cfg.get("temperature", 0.0)),
            max_tokens=int(cfg.get("max_tokens", 2000)),
        )
    return roles


def _status(exc: BaseException) -> int | None:
    return getattr(exc, "status_code", None)


def _retry_after(exc: BaseException) -> float | None:
    headers = getattr(exc, "headers", None) or {}
    response = getattr(exc, "response", None)
    if not headers and response is not None:
        headers = response.headers
    value = {k.lower(): v for k, v in dict(headers).items()}.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:  # an HTTP date instead of seconds; fall back to our own backoff
        return None


def retry_delay(
    exc: BaseException, attempt: int, base: float = 0.5, cap: float = 20.0, rng: Callable[[], float] = random.random
) -> float | None:
    """Seconds to wait before the next attempt, or None if this error must not be retried.

    Retry-After from the provider wins over our own formula. Otherwise exponential
    backoff with full jitter, so many clients hitting the same limit don't retry in lockstep."""
    status = _status(exc)
    if status is not None and status not in RETRYABLE_STATUS:
        return None
    if status is None and not isinstance(exc, (TimeoutError, ConnectionError)):
        return None
    after = _retry_after(exc)
    if after is not None:
        return min(after, cap)
    return rng() * min(cap, base * 2**attempt)


async def call_with_retry[T](
    fn: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as exc:
            delay = retry_delay(exc, attempt)
            if delay is None or attempt == max_attempts - 1:
                raise
            await sleep(delay)
    raise AssertionError("unreachable")


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    short = model.split("/", 1)[-1]
    if short in MODEL_PRICES:
        price_in, price_out = MODEL_PRICES[short]
        return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    try:
        import litellm

        cost_in, cost_out = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        return cost_in + cost_out
    except Exception:  # unknown model in LiteLLM's price map: report 0 rather than guess
        return 0.0


class LiteLLMBackend:
    """Streams one role's answer. Tries the main model, then each fallback, each with retries."""

    def __init__(
        self,
        role: str,
        cfg: RoleConfig,
        settings: Settings,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.role = role
        self.cfg = cfg
        self.keys = {"gemini": settings.gemini_api_key, "anthropic": settings.anthropic_api_key}
        self.sleep = sleep
        self.name = f"litellm:{cfg.model}"

    def _api_key(self, model: str) -> str | None:
        return self.keys.get(model.split("/", 1)[0])

    async def _open(self, model: str, system: str, messages: list[dict]):
        import litellm

        return await litellm.acompletion(
            model=model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
            api_key=self._api_key(model),
        )

    def generate(self, system: str, messages: list[dict], sources: list[dict]) -> Generation:
        gen = Generation(stream=None, usage=Usage(model=self.cfg.model))  # type: ignore[arg-type]

        async def _stream() -> AsyncIterator[str]:
            # Retries and fallbacks only cover opening the stream: once text has reached
            # the user, starting over on another model would show two different answers.
            models = [self.cfg.model, *self.cfg.fallbacks]
            for i, model in enumerate(models):
                try:
                    response = await call_with_retry(lambda m=model: self._open(m, system, messages), sleep=self.sleep)
                    break
                except Exception:
                    if i == len(models) - 1:
                        raise
            gen.usage.model = model
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                usage = getattr(chunk, "usage", None)
                if usage:
                    gen.usage.input_tokens = usage.prompt_tokens or 0
                    gen.usage.output_tokens = usage.completion_tokens or 0
            gen.usage.cost_usd = _cost(model, gen.usage.input_tokens, gen.usage.output_tokens)

        gen.stream = _stream()
        return gen
