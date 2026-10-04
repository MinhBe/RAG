from __future__ import annotations

from dataclasses import dataclass

from app.core.briefing import minimal_brief_from_text
from app.core.case_matcher import match_case
from app.core.job_store import JobRecord, create_job
from app.core.mission_registry import resolve_provider
from app.core.text_normalize import fold_text
from app.core.trace_log import append_trace_event


@dataclass(frozen=True)
class IntakeAck:
    job: JobRecord
    task_count: int
    bot_ids: tuple[str, ...]

    @property
    def text(self) -> str:
        bots = ", ".join(self.bot_ids)
        return (
            f"Da nhan. job_id={self.job.job_id} trace_id={self.job.trace_id} case={self.job.case_id}.\n"
            f"Queued {self.task_count} tasks for: {bots}. Lead se bao tien do/kq khi co report."
        )


def should_async_intake(user_text: str, bot_id: str | None) -> bool:
    """Lead must not free-form claim delegation; create a job for every natural-language intake."""
    return bot_id == "lead" and bool(user_text.strip())


def _tasks_for_case(case_id: str, user_text: str) -> list[dict]:
    if case_id == "local_place_lookup":
        plan = [
            ("scout", "research.local_places", "common"),
            ("sentinel", "risk.critic", "common"),
            ("validator", "answer.verify", "common"),
        ]
    elif case_id == "research_question":
        plan = [
            ("scout", "research.question", "specific"),
            ("sentinel", "risk.critic", "common"),
            ("validator", "answer.verify", "common"),
        ]
    else:
        plan = [
            ("lead", "planning.generic", "common"),
            ("sentinel", "risk.critic", "common"),
            ("validator", "answer.verify", "common"),
        ]
    tasks: list[dict] = []
    for bot_id, mission_id, tier in plan:
        provider = resolve_provider(mission_id, bot_id, tier=tier)
        tasks.append(
            {
                "bot_id": bot_id,
                "mission_id": mission_id,
                "provider_id": provider.provider_id if provider.allowed else None,
                "status": "queued",
                "payload": {
                    "user_text": user_text,
                    "tier": tier,
                    "provider_allowed": provider.allowed,
                    "provider_reason": provider.reason,
                },
            }
        )
    return tasks


def create_intake_job(user_text: str, user_override: bool = False) -> IntakeAck:
    brief = minimal_brief_from_text(user_text)
    brief_dict = brief.model_dump()
    if user_override:
        brief_dict.setdefault("constraints", {})["user_override"] = True
    case_match = match_case(user_text)
    tasks = _tasks_for_case(case_match.case_id, user_text)
    job = create_job(case_id=case_match.case_id, user_text=user_text, brief=brief_dict, tasks=tasks, trace_id=brief.trace_id)
    append_trace_event(job.trace_id, "brief.created", {"brief": brief_dict})
    append_trace_event(job.trace_id, "case.matched", case_match.__dict__)
    append_trace_event(job.trace_id, "job.created", {"job_id": job.job_id, "task_count": len(tasks), "tasks": tasks})
    return IntakeAck(job=job, task_count=len(tasks), bot_ids=tuple(task["bot_id"] for task in tasks))


def is_user_override_request(user_text: str) -> bool:
    folded = fold_text(user_text)
    return any(token in folded for token in ("giao viec", "moi nguoi", "tat ca", "all agents", "everyone"))
