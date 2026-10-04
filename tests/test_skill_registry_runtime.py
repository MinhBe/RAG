
from __future__ import annotations

from app.adapters.telegram import handle_telegram_message
from app.core.chat_pipeline import run_chat_turn
from app.core.skill_registry import (
    allowed_skill_context_for_bot,
    bot_id_for_telegram_username,
    format_all_bot_skill_matrix,
    format_bot_identity,
    format_skill_resolution_for_username,
)


def test_telegram_username_maps_to_bot_profile() -> None:
    assert bot_id_for_telegram_username("Swain_SubAgent_bot") == "lead"
    assert bot_id_for_telegram_username("@Lucian_SubAgent_bot") == "validator"
    assert bot_id_for_telegram_username("unknown") is None


def test_whoami_uses_current_receiver_profile() -> None:
    response = handle_telegram_message("@Swain_SubAgent_bot /whoami", receiver_username="Swain_SubAgent_bot")
    assert response is not None
    assert "Bot profile: lead" in response
    assert "permission_ceiling: task_create" in response


def test_skills_are_scoped_to_current_bot() -> None:
    lead = handle_telegram_message("@Swain_SubAgent_bot /skills", receiver_username="Swain_SubAgent_bot")
    validator = handle_telegram_message("@Lucian_SubAgent_bot /skills", receiver_username="Lucian_SubAgent_bot")
    assert lead is not None
    assert validator is not None
    assert "omh-ralplan" in lead
    assert "omh-ralph-task" not in lead
    assert "hermes-executor-verification" in validator
    assert "omh-ralph-task" not in validator


def test_skills_all_shows_matrix() -> None:
    matrix = format_all_bot_skill_matrix()
    assert "lead" in matrix
    assert "builder_core" in matrix
    assert "validator" in matrix


def test_chat_skill_inventory_route_uses_bot_scope() -> None:
    result = run_chat_turn("thông tin skill đang có trên hermes", assistant_name="Swain", bot_id="lead")
    assert result.route == "command"
    assert result.provider == "local_skill_resolver"
    assert "Bot skill resolution: lead" in result.response_text
    assert "omh-ralplan" in result.response_text
    assert "omh-ralph-task" not in result.response_text


def test_allowed_skill_context_is_bot_scoped() -> None:
    context = allowed_skill_context_for_bot("builder_core")
    assert context is not None
    assert "bot_id: builder_core" in context
    assert "omh-ralph-task" in context
    assert "hermes-executor-verification" not in context


def test_identity_and_username_resolution_helpers() -> None:
    assert "Bot profile: sentinel" in format_bot_identity("sentinel")
    assert "Bot skill resolution: scout" in format_skill_resolution_for_username("Shen_SubAgent_bot")
