from app.adapters.telegram import extract_directed_text, handle_telegram_message


def test_help_message_lists_demo_command():
    reply = handle_telegram_message("@Swain /help")
    assert reply is not None
    assert "/demo_a" in reply
    assert "/case CASE-A-001" in reply
    assert "9router is only a provider" in reply


def test_message_without_swain_is_ignored():
    assert handle_telegram_message("approve everything now") is None


def test_extracts_alias_mention():
    assert extract_directed_text("@Swain /health") == "/health"
    assert extract_directed_text("Swain: /health") == "/health"


def test_extracts_actual_bot_command():
    assert extract_directed_text("/demo_a@Swain_SubAgent_bot") == "/demo_a"


def test_natural_language_goes_through_hermes_core(monkeypatch):
    class FakeResult:
        response_text = "core response"

    def fake_run_chat_turn(message: str) -> FakeResult:
        assert message == "hello"
        return FakeResult()

    monkeypatch.setattr("app.adapters.telegram.run_chat_turn", fake_run_chat_turn)
    assert handle_telegram_message("@Swain hello") == "core response"


def test_actual_bot_username_mention_is_not_partially_stripped():
    assert extract_directed_text("/demo_a@Swain_SubAgent_bot") == "/demo_a"
    assert extract_directed_text("@Swain_SubAgent_bot ê bro") == "ê bro"
    assert extract_directed_text("@Swain ê bro") == "ê bro"
