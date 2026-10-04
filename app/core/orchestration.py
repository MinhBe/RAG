
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

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
        suffix = " duplicate" if self.job.deduped else ""
        return (
            f"Da nhan{suffix}. job_id={self.job.job_id} trace_id={self.job.trace_id} case={self.job.case_id}.\n"
            f"Queued {self.task_count} tasks for: {bots}. Lead se bao tien do/kq khi co report."
        )


def should_async_intake(user_text: str, bot_id: str | None) -> bool:
    return bot_id == "lead" and bool(user_text.strip())


def _task_id(label: str) -> str:
    return f"t-{label}-{uuid4().hex[:6]}"


def _task(bot_id: str, mission_id: str, tier: str, user_text: str, *, depends_on: list[str] | None = None, timeout_s: int = 60) -> dict:
    provider = resolve_provider(mission_id, bot_id, tier=tier)
    return {
        "task_id": _task_id(bot_id),
        "bot_id": bot_id,
        "mission": mission_id,
        "provider_id": provider.provider_id if provider.allowed else None,
        "depends_on": depends_on or [],
        "status": "pending",
        "timeout_s": timeout_s,
        "input": {
            "user_text": user_text,
            "tier": tier,
            "provider_allowed": provider.allowed,
            "provider_reason": provider.reason,
        },
    }


def _tasks_for_case(case_id: str, user_text: str) -> list[dict]:
    if case_id == "local_place_lookup":
        scout = _task("scout", "research.local_places", "common", user_text)
        critic = _task("sentinel", "risk.critic", "common", user_text, depends_on=[scout["task_id"]])
        validator = _task("validator", "answer.verify", "common", user_text, depends_on=[critic["task_id"]])
        return [scout, critic, validator]
    if case_id == "research_question":
        scout = _task("scout", "research.question", "specific", user_text)
        critic = _task("sentinel", "risk.critic", "common", user_text, depends_on=[scout["task_id"]])
        validator = _task("validator", "answer.verify", "common", user_text, depends_on=[critic["task_id"]])
        return [scout, critic, validator]
    planner = _task("lead", "planning.generic", "common", user_text)
    critic = _task("sentinel", "risk.critic", "common", user_text, depends_on=[planner["task_id"]])
    validator = _task("validator", "answer.verify", "common", user_text, depends_on=[critic["task_id"]])
    return [planner, critic, validator]


def create_intake_job(
    user_text: str,
    user_override: bool = False,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> IntakeAck:
    brief = minimal_brief_from_text(user_text)
    brief_dict = brief.model_dump()
    if user_override:
        brief_dict.setdefault("constraints", {})["user_override"] = True
    case_match = match_case(user_text)
    tasks = _tasks_for_case(case_match.case_id, user_text)
    job = create_job(
        case_id=case_match.case_id,
        user_text=user_text,
        brief=brief_dict,
        tasks=tasks,
        trace_id=brief.trace_id,
        chat_id=chat_id,
        message_id=message_id,
    )
    if not job.deduped:
        append_trace_event(job.trace_id, "brief.created", {"brief": brief_dict})
        append_trace_event(job.trace_id, "case.matched", case_match.__dict__)
        append_trace_event(job.trace_id, "job.created", {"job_id": job.job_id, "task_count": len(tasks), "tasks": tasks})
    return IntakeAck(job=job, task_count=len(tasks), bot_ids=tuple(task["bot_id"] for task in tasks))


def is_user_override_request(user_text: str) -> bool:
    folded = fold_text(user_text)
    return any(token in folded for token in ("giao viec", "moi nguoi", "tat ca", "all agents", "everyone"))
