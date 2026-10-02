from app.adapters.telegram import extract_directed_text, handle_telegram_message


def test_help_message_lists_demo_command():
    reply = handle_telegram_message('/help')
    assert reply is not None
    assert '/demo_a' in reply
    assert '/case CASE-A-001' in reply


def test_unmentioned_group_message_is_ignored():
    reply = handle_telegram_message('approve everything now')
    assert reply is None


def test_swain_mention_extracts_question():
    assert extract_directed_text('@Swain tìm top 5 người giàu nhất') == 'tìm top 5 người giàu nhất'
    assert extract_directed_text('Swain: /health') == '/health'
    assert extract_directed_text('/demo_a@Swain_SubAgent_bot') == '/demo_a'


def test_swain_mention_routes_to_general_provider(monkeypatch):
    class FakeProvider:
        def answer(self, question: str) -> str:
            assert question == 'hello'
            return 'general answer'

    monkeypatch.setattr('app.adapters.telegram.GeneralAssistantProvider', FakeProvider)
    assert handle_telegram_message('@Swain hello') == 'general answer'
