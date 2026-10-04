
from app.core.omh_hooks import (
    gather_evidence,
    handle_omh_command,
    omh_state_activate,
    pre_llm_call,
    pre_tool_call,
    role_catalog,
)


def test_omh_role_catalog_loaded():
    assert "planner" in role_catalog()
    assert "verifier" in role_catalog()


def test_pre_llm_injects_role_when_enabled(monkeypatch):
    monkeypatch.setenv("HERMES_OMH_HOOKS_ENABLED", "true")
    result = pre_llm_call(
        user_message="[omh-role:planner] draft plan",
        is_first_turn=True,
        assistant_name="Swain",
    )
    assert result.context is not None
    assert "OMH Role: planner" in result.context
    assert "[omh-role" not in result.user_message


def test_pre_tool_call_unknown_delegate_role(monkeypatch):
    monkeypatch.setenv("HERMES_OMH_HOOKS_ENABLED", "true")
    result = pre_tool_call(tool_name="delegate_task", tool_input={"goal": "[omh-role:not-a-real-role] do it"})
    assert result.allowed is True
    assert result.context is not None
    assert "Unknown role" in result.context


def test_omh_state_command_and_status(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_OMH_HOOKS_ENABLED", "true")
    monkeypatch.setenv("HERMES_OMH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HERMES_OMH_EVENTS_PATH", str(tmp_path / "events" / "hooks.jsonl"))
    omh_state_activate("ralplan", phase="planning", goal="test")
    status = handle_omh_command("/omh status")
    assert "hooks_enabled: true" in status
    assert "active_modes: 1" in status
    assert "ralplan" in status


def test_evidence_rejects_unallowlisted_command(monkeypatch):
    monkeypatch.setenv("HERMES_OMH_HOOKS_ENABLED", "true")
    monkeypatch.setenv("HERMES_OMH_EVIDENCE_ENABLED", "true")
    result = gather_evidence(["git status"])
    assert result["all_pass"] is False
    assert "allowlist" in result["results"][0]["output"].lower()
