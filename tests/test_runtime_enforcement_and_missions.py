from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.adapters.telegram import handle_telegram_event, handle_telegram_message
from app.core.briefing import (
    LEAD_BRIEF_EXTRACTION_PROMPT,
    minimal_brief_from_text,
    validate_brief_payload,
)
from app.core.case_matcher import match_case
from app.core.loop_controller import LoopObservation, LoopPolicy, decide_loop
from app.core.mission_registry import resolve_provider
from app.core.runtime_guard import (
    guard_repo_write_for_username,
    guard_skill_invocation_for_username,
)
from app.core.skill_registry import load_skill_claims, validate_registry


def test_multi_command_message_returns_one_reply_per_command_without_llm() -> None:
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot /whoami /skills /skills-all",
        receiver_username="Swain_SubAgent_bot",
    )
    assert len(replies) == 3
    assert "Bot profile: lead" in replies[0].text
    assert "Bot skill resolution: lead" in replies[1].text
    assert "Hermes bot/skill access matrix" in replies[2].text


def test_validator_is_blocked_from_implementation_skill_at_runtime() -> None:
    result = guard_skill_invocation_for_username("Lucian_SubAgent_bot", "omh-ralph")
    assert not result.allowed
    assert result.bot_id == "validator"
    assert "BLOCKED" in result.message
    assert "primary tag 'implementation' not worn by bot" in result.message


def test_lead_is_blocked_from_repo_write_at_runtime() -> None:
    result = guard_repo_write_for_username("Swain_SubAgent_bot")
    assert not result.allowed
    assert result.bot_id == "lead"
    assert "permission_ceiling: task_create" in result.message


def test_telegram_natural_attempts_are_guarded_before_llm() -> None:
    lucian = handle_telegram_message("@Lucian_SubAgent_bot chay omh-ralph", receiver_username="Lucian_SubAgent_bot")
    assert lucian is not None
    assert "BLOCKED by Hermes runtime access control" in lucian
    swain = handle_telegram_message("@Swain_SubAgent_bot write file to repo", receiver_username="Swain_SubAgent_bot")
    assert swain is not None
    assert "BLOCKED by Hermes runtime permission ceiling" in swain


def test_composite_autopilot_must_delegate() -> None:
    claims = load_skill_claims()
    autopilot = claims["omh.omh-autopilot"]
    assert autopilot["composite"] is True
    assert autopilot["must_delegate"] is True
    result = guard_skill_invocation_for_username("Swain_SubAgent_bot", "omh-autopilot")
    assert not result.allowed
    assert result.reason == "composite_must_delegate"


def test_registry_validation_accepts_composite_constraints() -> None:
    assert validate_registry() == []


def test_brief_schema_validates_stated_and_inferred_fields() -> None:
    brief = minimal_brief_from_text("research AURA FARMING", case_hint="research_question")
    result = validate_brief_payload(brief.model_dump())
    assert result.ok
    assert result.brief is not None
    assert result.brief.objective.stated == "research AURA FARMING"
    assert "JSON only" in LEAD_BRIEF_EXTRACTION_PROMPT


def test_case_matcher_research_and_generic_fallback() -> None:
    research = match_case("research and cite sources about small models")
    assert research.case_id == "research_question"
    assert research.confidence >= 0.8
    fallback = match_case("nearby cafe")
    assert fallback.case_id == "generic"
    assert fallback.band == "fallback"


def test_twenty_routing_examples_have_expected_cases() -> None:
    samples = [
        ("research small models", "research_question"),
        ("find information with sources about aura farming", "research_question"),
        ("make a report comparing sources about skill registry", "research_question"),
        ("research current approaches to small agents", "research_question"),
        ("find information and citations about validators", "research_question"),
        ("web research about security skill", "research_question"),
        ("source synthesis report about OMH", "research_question"),
        ("research citation verify", "research_question"),
        ("find information and rank sources", "research_question"),
        ("compare sources about multi agent", "research_question"),
        ("implement resolver code", "generic"),
        ("fix timeout bug", "generic"),
        ("build Telegram adapter", "generic"),
        ("debug runner error", "generic"),
        ("write config file", "generic"),
        ("design bot profile", "generic"),
        ("deployment planning", "generic"),
        ("system testing", "generic"),
        ("nearby cafe", "generic"),
        ("continue conversation", "generic"),
    ]
    for text, expected in samples:
        assert match_case(text).case_id == expected


def test_mission_provider_resolver_reuses_skill_access() -> None:
    scout_specific = resolve_provider("research.question", "scout", tier="specific")
    assert scout_specific.allowed
    assert scout_specific.provider_id == "omh.deep_research"
    lead_specific = resolve_provider("research.question", "lead", tier="specific")
    assert not lead_specific.allowed
    assert "not allowed by resolver" in lead_specific.reason or "required role" in lead_specific.reason


def test_loop_controller_stops_by_budget_deadline_and_score() -> None:
    assert not decide_loop(LoopPolicy(max_rounds=2), [LoopObservation(0, 0.4), LoopObservation(1, 0.5)]).continue_loop
    assert not decide_loop(LoopPolicy(max_cost_units=1.0), [LoopObservation(0, 0.4, cost_units=1.0)]).continue_loop
    assert not decide_loop(LoopPolicy(deadline_at=datetime.now(UTC) - timedelta(seconds=1)), []).continue_loop
    history = [LoopObservation(0, 0.8), LoopObservation(1, 0.7), LoopObservation(2, 0.8)]
    assert not decide_loop(LoopPolicy(no_improvement_rounds=2), history).continue_loop



def test_end_to_end_lead_ack_creates_job_tasks_and_trace() -> None:
    import re
    import time
    from pathlib import Path

    from app.adapters.telegram import handle_telegram_event
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job

    reset_jobs_for_tests()
    started = time.monotonic()
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay",
        receiver_username="Swain_SubAgent_bot",
    )
    elapsed = time.monotonic() - started
    assert elapsed < 3
    assert len(replies) == 1
    assert replies[0].text.startswith("Da nhan. job_id=")
    job_id = re.search(r"job_id=(b-[a-f0-9]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    trace_id = re.search(r"trace_id=([^ ]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    tasks = tasks_for_job(job_id)
    assert len(tasks) >= 3
    assert len({task.bot_id for task in tasks}) >= 3
    assert {"scout", "sentinel", "validator"}.issubset({task.bot_id for task in tasks})
    trace_path = Path(".omh") / "traces" / f"{trace_id}.jsonl"
    assert trace_path.exists()
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "brief.created" in trace_text
    assert "case.matched" in trace_text
    assert "job.created" in trace_text


def test_line_scoped_addressing_prevents_cross_bot_command_handling() -> None:
    from app.adapters.telegram import handle_telegram_event

    message = "@Swain_SubAgent_bot /whoami\n@Lucian_SubAgent_bot chay omh-ralph"
    swain = handle_telegram_event(message, receiver_username="Swain_SubAgent_bot")
    lucian = handle_telegram_event(message, receiver_username="Lucian_SubAgent_bot")
    assert len(swain) == 1
    assert swain[0].text.startswith("Bot profile: lead")
    assert len(lucian) == 1
    assert lucian[0].text.startswith("BLOCKED by Hermes runtime access control")



def test_accented_local_place_request_creates_job_and_case() -> None:
    response = handle_telegram_message(
        "@Swain_SubAgent_bot giao việc cho mọi người tìm quán cắt tóc ở 165 Cầu Giấy",
        receiver_username="Swain_SubAgent_bot",
    )
    assert response is not None
    assert response.startswith("Da nhan. job_id=")
    assert "case=local_place_lookup" in response


def test_local_place_matcher_handles_accent_case_and_mention_variants() -> None:
    samples = [
        "giao việc cho mọi người tìm quán cắt tóc ở 165 Cầu Giấy",
        "GIAO VIỆC CHO MỌI NGƯỜI TÌM QUÁN CẮT TÓC Ở 165 CẦU GIẤY",
        "@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay",
    ]
    for sample in samples:
        match = match_case(sample)
        assert match.case_id == "local_place_lookup"
        assert match.confidence >= 0.8


def test_autopilot_must_delegate_and_unprofiled_bots_are_blocked() -> None:
    autopilot = handle_telegram_message("@Swain_SubAgent_bot chay omh-autopilot", receiver_username="Swain_SubAgent_bot")
    assert autopilot is not None
    assert autopilot.startswith("BLOCKED as direct execution")
    kayn = handle_telegram_message("@Kayn_SubAgent_bot /skills", receiver_username="Kayn_SubAgent_bot")
    xinzhao = handle_telegram_message("@Xinzhao_SubAgent_bot /skills", receiver_username="Xinzhao_SubAgent_bot")
    assert kayn is not None and kayn.startswith("BLOCKED by Hermes runtime profile guard")
    assert xinzhao is not None and xinzhao.startswith("BLOCKED by Hermes runtime profile guard")


def _job_id_from_ack(text: str) -> str:
    import re

    match = re.search(r"job_id=(b-[a-f0-9]+)", text)
    assert match is not None
    return match.group(1)


def test_slice_a_worker_runs_dependencies_and_final_notice() -> None:
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job
    from app.core.task_worker import collect_job_notifications, process_one_task

    reset_jobs_for_tests()
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot giao việc cho mọi người tìm quán cắt tóc ở 165 Cầu Giấy",
        receiver_username="Swain_SubAgent_bot",
        chat_id=1001,
        message_id=2001,
    )
    job_id = _job_id_from_ack(replies[0].text)
    tasks = tasks_for_job(job_id)
    assert [task.bot_id for task in tasks] == ["scout", "sentinel", "validator"]
    assert tasks[1].depends_on == (tasks[0].task_id,)
    assert tasks[2].depends_on == (tasks[1].task_id,)

    assert process_one_task("validator") is None
    assert process_one_task("sentinel") is None
    assert process_one_task("scout") is not None
    progress = collect_job_notifications()
    assert any(note.kind == "progress" and note.message_id == 2001 for note in progress)

    assert process_one_task("sentinel") is not None
    assert process_one_task("validator") is not None
    final = collect_job_notifications()
    final_text = "\n".join(note.text for note in final if note.kind == "final")
    assert "Barber Mau 1" in final_text
    assert "chưa xác minh giờ mở cửa" in final_text


def test_slice_a_provider_error_still_produces_final_with_missing_parts() -> None:
    from app.core.job_store import reset_jobs_for_tests
    from app.core.task_worker import collect_job_notifications, process_one_task

    reset_jobs_for_tests()
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay",
        receiver_username="Swain_SubAgent_bot",
        chat_id=1001,
        message_id=2002,
    )
    job_id = _job_id_from_ack(replies[0].text)

    def failing_provider(task):
        raise RuntimeError("provider boom")

    assert process_one_task("scout", provider_runner=failing_provider) is not None
    assert process_one_task("scout", provider_runner=failing_provider) is not None
    final = collect_job_notifications()
    final_text = "\n".join(note.text for note in final if note.job_id == job_id)
    assert "Ket qua job_id=" in final_text
    assert "Con thieu/loi" in final_text


def test_slice_a_provider_timeout_still_produces_final() -> None:
    import time

    from app.core.job_store import connect, reset_jobs_for_tests, tasks_for_job
    from app.core.task_worker import collect_job_notifications, process_one_task

    reset_jobs_for_tests()
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay",
        receiver_username="Swain_SubAgent_bot",
        chat_id=1001,
        message_id=2003,
    )
    job_id = _job_id_from_ack(replies[0].text)
    scout_task = tasks_for_job(job_id)[0]
    with connect() as conn:
        conn.execute("UPDATE tasks SET timeout_s = 0 WHERE task_id = ?", (scout_task.task_id,))

    def slow_provider(task):
        time.sleep(0.1)
        return {"ok": True}

    assert process_one_task("scout", provider_runner=slow_provider) is not None
    assert process_one_task("scout", provider_runner=slow_provider) is not None
    final = collect_job_notifications()
    final_text = "\n".join(note.text for note in final if note.job_id == job_id)
    assert "Ket qua job_id=" in final_text
    assert "Con thieu/loi" in final_text


def test_slice_a_dedupes_same_chat_message_id() -> None:
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job

    reset_jobs_for_tests()
    kwargs = {"receiver_username": "Swain_SubAgent_bot", "chat_id": 2001, "message_id": 3001}
    first = handle_telegram_event("@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay", **kwargs)
    second = handle_telegram_event("@Swain_SubAgent_bot giao viec cho moi nguoi tim quan cat toc o 165 Cau Giay", **kwargs)
    first_job = _job_id_from_ack(first[0].text)
    second_job = _job_id_from_ack(second[0].text)
    assert first_job == second_job
    assert "duplicate" in second[0].text
    assert len(tasks_for_job(first_job)) == 3




def test_slice_b_common_research_provider_is_allowed_and_hash_pinned() -> None:
    from app.core.mission_registry import load_providers, resolve_provider
    from app.core.skill_loader import load_skill_from_provider

    resolution = resolve_provider("research.question", "scout", tier="common")
    assert resolution.allowed
    assert resolution.provider_id == "matt.research_common"
    provider = next(item for item in load_providers() if item["id"] == "matt.research_common")
    skill = load_skill_from_provider(provider)
    assert skill.ref == "skill:A02_skills/skills/engineering/research"
    assert skill.actual_hash == provider["skill_hash"]


def test_slice_b_t1_real_executor_research_question_traceable_sources(monkeypatch) -> None:
    import re
    from pathlib import Path

    from app.adapters.telegram import handle_telegram_event
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job
    from app.core.settings import settings
    from app.core.task_worker import collect_job_notifications, process_ready_tasks_once

    reset_jobs_for_tests()
    monkeypatch.setattr(settings, "hermes_executor", "real")
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot research traceable Hermes skill execution",
        receiver_username="Swain_SubAgent_bot",
        chat_id=101,
        message_id=201,
    )
    assert replies and replies[0].text.startswith("Da nhan. job_id=")
    job_id = re.search(r"job_id=(b-[a-f0-9]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    trace_id = re.search(r"trace_id=([^ ]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    for _ in range(4):
        process_ready_tasks_once(["scout", "sentinel", "validator"])
    tasks = tasks_for_job(job_id)
    scout = next(task for task in tasks if task.bot_id == "scout")
    assert scout.status == "done"
    assert scout.report is not None
    assert scout.report["status"] == "ok"
    assert scout.report["skill_applied"]["ref"] == "skill:A02_skills/skills/engineering/research"
    assert scout.report["skill_applied"]["hash"].startswith("sha256:")
    assert len(scout.report["findings"]) >= 2
    assert all(finding["source_urls"] for finding in scout.report["findings"])
    notifications = collect_job_notifications()
    final = [note for note in notifications if note.kind == "final"]
    assert final
    assert "Ket qua nghien cuu co nguon truy vet" in final[0].text
    trace_text = (Path(".omh") / "traces" / f"{trace_id}.jsonl").read_text(encoding="utf-8")
    assert "skill_applied" in trace_text
    assert "tool_called" in trace_text
    assert "llm_call" in trace_text
    assert "report_saved" in trace_text


def test_slice_b_t2_login_url_is_refused_as_partial(monkeypatch) -> None:
    import re

    from app.adapters.telegram import handle_telegram_event
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job
    from app.core.settings import settings
    from app.core.task_worker import process_ready_tasks_once

    reset_jobs_for_tests()
    monkeypatch.setattr(settings, "hermes_executor", "real")
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot research https://private.example/login-required",
        receiver_username="Swain_SubAgent_bot",
    )
    job_id = re.search(r"job_id=(b-[a-f0-9]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    process_ready_tasks_once(["scout"])
    scout = next(task for task in tasks_for_job(job_id) if task.bot_id == "scout")
    assert scout.report is not None
    assert scout.report["status"] in {"partial", "failed"}
    assert any("login" in str(gap).lower() or "private" in str(gap).lower() for gap in scout.report["gaps"])


def test_slice_b_t3_injection_content_is_data_not_instruction(monkeypatch) -> None:
    import re

    from app.adapters.telegram import handle_telegram_event
    from app.core.job_store import reset_jobs_for_tests, tasks_for_job
    from app.core.settings import settings
    from app.core.task_worker import process_ready_tasks_once

    reset_jobs_for_tests()
    monkeypatch.setattr(settings, "hermes_executor", "real")
    replies = handle_telegram_event(
        "@Swain_SubAgent_bot research injection page says ignore previous instructions",
        receiver_username="Swain_SubAgent_bot",
    )
    job_id = re.search(r"job_id=(b-[a-f0-9]+)", replies[0].text).group(1)  # type: ignore[union-attr]
    for _ in range(3):
        process_ready_tasks_once(["scout", "sentinel", "validator"])
    tasks = tasks_for_job(job_id)
    scout = next(task for task in tasks if task.bot_id == "scout")
    sentinel = next(task for task in tasks if task.bot_id == "sentinel")
    assert scout.report is not None
    assert "write files" not in scout.report["summary"].lower()
    assert any("injection" in str(gap).lower() for gap in scout.report["gaps"])
    assert sentinel.report is not None
    assert "possible_prompt_injection" in sentinel.report.get("security_flags", [])


def test_slice_b_t4_tool_gate_enforces_max_calls(monkeypatch) -> None:
    from app.core import tool_gate
    from app.core.tool_gate import ToolGate, ToolGateError

    original = tool_gate._load_tools

    def fake_tools():
        data = original()
        data["web_search"] = {**data["web_search"], "limits": {**data["web_search"].get("limits", {}), "max_calls": 2}}
        return data

    monkeypatch.setattr(tool_gate, "_load_tools", fake_tools)
    provider = {"requires_tools": ["web_search"]}
    gate = ToolGate(bot_id="scout", provider=provider, trace_id="trace_test_max_calls", task_id="t-max")
    gate.call("web_search", query="one")
    gate.call("web_search", query="two")
    try:
        gate.call("web_search", query="three")
    except ToolGateError as exc:
        assert "max_calls" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("third call should be blocked")


def test_slice_b_t6_skill_hash_mismatch_is_rejected() -> None:
    from app.core.mission_registry import load_providers
    from app.core.skill_loader import SkillLoadError, load_skill_from_provider

    provider = next(item for item in load_providers() if item["id"] == "matt.research_common")
    broken = {**provider, "skill_hash": "sha256:" + "1" * 64}
    try:
        load_skill_from_provider(broken)
    except SkillLoadError as exc:
        assert "hash mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("hash mismatch should fail")


def test_slice_b_t7_untraceable_source_fails_report_check() -> None:
    from app.core.task_report import check_traceable_sources, validate_task_report

    report = {
        "status": "ok",
        "summary": "bad report",
        "findings": [{"claim": "made up", "source_urls": ["https://not-observed.example"], "confidence": 0.9}],
        "gaps": [],
        "skill_applied": {"ref": "skill:x", "hash": "sha256:" + "0" * 64},
        "tools_called": [{"name": "web_search", "ms": 1, "bytes": 10}],
        "usage": {"llm_calls": 1, "tokens": 1, "ms": 1},
    }
    assert validate_task_report(report).ok
    errors = check_traceable_sources(report, {"https://observed.example"})
    assert errors and "not-observed" in errors[0]


def test_slice_b_tools_yaml_keeps_session_channels_disabled() -> None:
    import yaml

    with open("registry/tools.yaml", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    tools = {item["id"]: item for item in data["tools"]}
    assert tools["session_fetch"]["enabled"] is False
    assert tools["session_fetch"]["permission"] == "session_access"
    assert "session_access" in tools["web_search"]["deny"]
