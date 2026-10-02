from itertools import pairwise

from app.adapters.telegram import (
    configured_bot_usernames,
    extract_directed_text,
    handle_telegram_event,
    handle_telegram_message,
)


def test_help_message_lists_full_bot_usernames():
    reply = handle_telegram_message("@Swain_SubAgent_bot /help", receiver_username="Swain_SubAgent_bot")
    assert reply is not None
    assert "@Swain_SubAgent_bot" in reply
    assert "@Shen_SubAgent_bot" in reply
    assert "/demo_a" in reply
    assert "/chain apple" in reply
    assert "9router is only a provider" in reply


def test_message_without_full_mention_is_ignored_for_receiver():
    assert handle_telegram_message("approve everything now", receiver_username="Swain_SubAgent_bot") is None
    assert handle_telegram_message("@Swain /health", receiver_username="Swain_SubAgent_bot") is None


def test_extracts_full_username_mentions_only_for_receiver():
    assert extract_directed_text("@Swain_SubAgent_bot /health", receiver_username="Swain_SubAgent_bot") == "/health"
    assert extract_directed_text("Swain: /health", receiver_username="Swain_SubAgent_bot") is None
    assert extract_directed_text("@Shen_SubAgent_bot /health", receiver_username="Swain_SubAgent_bot") is None


def test_extracts_actual_bot_command_for_receiver():
    assert extract_directed_text("/demo_a@Swain_SubAgent_bot", receiver_username="Swain_SubAgent_bot") == "/demo_a"
    assert extract_directed_text("/demo_a@Shen_SubAgent_bot", receiver_username="Swain_SubAgent_bot") is None


def test_natural_language_goes_through_hermes_core(monkeypatch):
    class FakeResult:
        response_text = "core response"

    def fake_run_chat_turn(message: str) -> FakeResult:
        assert message == "hello"
        return FakeResult()

    monkeypatch.setattr("app.adapters.telegram.run_chat_turn", fake_run_chat_turn)
    assert handle_telegram_message("@Swain_SubAgent_bot hello", receiver_username="Swain_SubAgent_bot") == "core response"


def test_actual_bot_username_mention_is_not_partially_stripped():
    assert extract_directed_text("/demo_a@Swain_SubAgent_bot", receiver_username="Swain_SubAgent_bot") == "/demo_a"
    assert extract_directed_text("@Swain_SubAgent_bot ê bro", receiver_username="Swain_SubAgent_bot") == "ê bro"


def test_word_chain_event_returns_ten_turns_and_all_four_bots():
    replies = handle_telegram_event("@Swain_SubAgent_bot /chain apple", receiver_username="Swain_SubAgent_bot")
    assert len(replies) == 10
    senders = {reply.sender_username for reply in replies}
    assert set(configured_bot_usernames()).issubset(senders)
    assert replies[0].sender_username == "Swain_SubAgent_bot"
    assert replies[-1].text.endswith("Chain complete.")
    for previous, current in pairwise(replies):
        previous_word = previous.text.splitlines()[0].split()[-1]
        current_word = current.text.splitlines()[0].split()[-1]
        assert current_word[0].lower() == previous_word[-1].lower()
