from types import SimpleNamespace

import httpx
import litellm
import pytest

from app.config import REPO_ROOT, Settings
from app.gateway import LiteLLMBackend, RoleConfig, call_with_retry, load_roles, retry_delay
from app.llm import OfflineLLM, build_llm

MODELS_YAML = REPO_ROOT / "config" / "models.yaml"


def _rate_limit(retry_after: str | None = None) -> litellm.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://example.test"))
    return litellm.RateLimitError("quota", "gemini", "gemini/test", response=response)


class HTTPError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_repo_models_yaml_has_every_role():
    roles = load_roles(MODELS_YAML, {})
    assert set(roles) == {"answer", "router", "extract"}
    # Thinking models spend part of max_tokens on reasoning; below ~1024 they can return "".
    assert all(r.max_tokens >= 1024 for r in roles.values())
    assert all(r.temperature == 0 for r in roles.values())


def test_load_roles_fills_env_vars_and_fails_fast_when_missing(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text("roles:\n  answer:\n    model: gemini/${ANSWER_MODEL}\n", encoding="utf-8")
    assert load_roles(path, {"ANSWER_MODEL": "model-x"})["answer"].model == "gemini/model-x"
    with pytest.raises(ValueError, match="ANSWER_MODEL"):
        load_roles(path, {})


def test_default_and_env_override_for_gemini_models():
    defaults = load_roles(MODELS_YAML, {})
    assert defaults["answer"].model == "gemini/gemini-3.5-flash"
    assert defaults["router"].model == "gemini/gemini-3.1-flash-lite"
    custom = load_roles(MODELS_YAML, {"GEMINI_MODEL": "a", "GEMINI_MODEL_LITE": "b"})
    assert (custom["answer"].model, custom["extract"].model) == ("gemini/a", "gemini/b")


def test_build_llm_reads_model_names_from_settings():
    settings = Settings(
        llm_provider="litellm", gemini_api_key="g", gemini_model="x", gemini_model_lite="y", models_config=MODELS_YAML
    )
    assert build_llm(settings, "answer").name == "litellm:gemini/x"
    assert build_llm(settings, "router").name == "litellm:gemini/y"


def test_retry_after_header_wins_over_backoff():
    assert retry_delay(_rate_limit("7"), attempt=0) == 7.0


def test_backoff_has_jitter_and_grows():
    assert retry_delay(_rate_limit(), attempt=0, rng=lambda: 1.0) == 0.5
    assert retry_delay(_rate_limit(), attempt=3, rng=lambda: 1.0) == 4.0
    assert retry_delay(_rate_limit(), attempt=3, rng=lambda: 0.25) == 1.0


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    assert retry_delay(HTTPError(status), attempt=0) is None


@pytest.mark.parametrize("status", [500, 503])
def test_server_errors_are_retried(status):
    assert retry_delay(HTTPError(status), attempt=0) is not None


def test_unknown_exceptions_are_not_retried():
    assert retry_delay(KeyError("bug"), attempt=0) is None


async def _no_sleep(_: float) -> None:
    return None


async def test_call_with_retry_recovers_after_429():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise _rate_limit("1")
        return "ok"

    assert await call_with_retry(flaky, sleep=_no_sleep) == "ok"
    assert len(calls) == 3


async def test_call_with_retry_gives_up_on_404_immediately():
    calls = []

    async def missing_model():
        calls.append(1)
        raise HTTPError(404)

    with pytest.raises(HTTPError):
        await call_with_retry(missing_model, sleep=_no_sleep)
    assert len(calls) == 1


def _chunk(text: str | None = None, usage=None):
    choices = [SimpleNamespace(delta=SimpleNamespace(content=text))] if text is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


async def _fake_stream(chunks):
    for c in chunks:
        yield c


async def test_backend_streams_text_usage_and_uses_fallback(monkeypatch):
    seen = []

    async def fake_acompletion(**kwargs):
        seen.append((kwargs["model"], kwargs["api_key"]))
        if kwargs["model"] == "gemini/main":
            raise HTTPError(404)
        return _fake_stream(
            [
                _chunk("Đổi "),
                _chunk("trong 30 ngày [1]"),
                _chunk(usage=SimpleNamespace(prompt_tokens=900, completion_tokens=40)),
            ]
        )

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    cfg = RoleConfig(model="gemini/main", fallbacks=["anthropic/claude-haiku-5-5"])
    backend = LiteLLMBackend(
        "answer", cfg, Settings(gemini_api_key="g-key", anthropic_api_key="a-key"), sleep=_no_sleep
    )

    gen = backend.generate("system", [{"role": "user", "content": "hi"}], [])
    text = "".join([t async for t in gen.stream])

    assert text == "Đổi trong 30 ngày [1]"
    assert seen == [("gemini/main", "g-key"), ("anthropic/claude-haiku-5-5", "a-key")]
    assert gen.usage.model == "anthropic/claude-haiku-5-5"
    assert (gen.usage.input_tokens, gen.usage.output_tokens) == (900, 40)
    assert gen.usage.cost_usd > 0


def test_build_llm_picks_gateway_when_gemini_key_set():
    settings = Settings(llm_provider="auto", gemini_api_key="g", models_config=MODELS_YAML)
    assert build_llm(settings).name == f"litellm:{load_roles(MODELS_YAML, {})['answer'].model}"
    assert isinstance(build_llm(Settings(llm_provider="auto", gemini_api_key=None, anthropic_api_key=None)), OfflineLLM)
