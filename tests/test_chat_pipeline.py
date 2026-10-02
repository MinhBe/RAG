from app.core.chat_pipeline import run_chat_turn


def test_chat_turn_uses_hermes_core_entrypoint(monkeypatch):
    class FakeProvider:
        def answer(self, question: str) -> str:
            assert question == "hello"
            return "world"

    monkeypatch.setattr("app.core.chat_pipeline.GeneralAssistantProvider", FakeProvider)
    result = run_chat_turn("hello")
    assert result.response_text == "world"
    assert result.route == "general_llm"
    assert result.provider == "9router_openai_compatible"
    assert "provider_is_not_orchestrator" in result.policy_notes
