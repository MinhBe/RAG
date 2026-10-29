from pathlib import Path

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
PRIVATE_KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY")


def _assignments() -> dict[str, str]:
    out = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        out[name.strip()] = value.strip()
    return out


def test_private_keys_are_empty_in_env_example():
    for name, value in _assignments().items():
        if any(name.upper().startswith(prefix) for prefix in PRIVATE_KEYS):
            assert value == "", f"{name} phải để trống trong .env.example"
