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

