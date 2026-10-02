from app.adapters.telegram import handle_telegram_message


def test_help_message_lists_demo_command():
    reply = handle_telegram_message("/help")
    assert "/demo_a" in reply
    assert "/case CASE-A-001" in reply


def test_unknown_message_does_not_call_llm_or_tools():
    reply = handle_telegram_message("approve everything now")
    assert "Unknown command" in reply
    assert "persistence/readback" in reply
