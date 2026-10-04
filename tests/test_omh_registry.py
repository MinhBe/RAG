
from app.adapters.telegram import handle_telegram_message
from app.core.omh_registry import (
    load_omh_registry,
    omh_capability_records,
    omh_skill_inventory_text,
)


def test_omh_registry_loads_local_source():
    registry = load_omh_registry()
    assert registry.available is True
    assert registry.integrity_state in {"available_git_source", "available_unverified_source"}
    assert "omh_state" in registry.plugin_tools
    assert "pre_llm_call" in registry.plugin_hooks
    assert any(skill.name == "omh-deep-research" for skill in registry.skills)
    assert any("research" in skill.capability_tags for skill in registry.skills)


def test_omh_capability_records_are_routing_safe():
    records = omh_capability_records()
    assert records
    assert all(record["mode"] == "registry_controlled_hook_bridge" for record in records)
    assert any(record["name"] == "omh-ralplan" for record in records)


def test_telegram_omh_command_reports_status():
    response = handle_telegram_message("@Swain_SubAgent_bot /omh", receiver_username="Swain_SubAgent_bot")
    assert response is not None
    assert "Oh My Hermes deployment status" in response
    assert "mode: registry_controlled_hook_bridge" in response


def test_omh_skill_inventory_text_lists_skills():
    text = omh_skill_inventory_text()
    assert "Hermes skill inventory" in text
    assert "omh-deep-research" in text
    assert "OMH roles" in text


def test_telegram_skills_command_reports_local_inventory():
    response = handle_telegram_message("@Swain_SubAgent_bot /skills", receiver_username="Swain_SubAgent_bot")
    assert response is not None
    assert "Hermes skill inventory" in response
    assert "omh-triage" in response
