
from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.core.job_store import (
    TERMINAL_STATUSES,
    TaskRecord,
    active_jobs,
    claim_next_task,
    complete_task,
    fail_task,
    get_job,
    mark_job_final_sent,
    mark_progress_sent,
    progress_sent_task_id,
    reports_for_job,
    tasks_for_job,
)
from app.core.mission_registry import resolve_provider
from app.core.task_providers import run_fake_provider
from app.core.trace_log import append_trace_event

ProviderRunner = Callable[[TaskRecord], dict]


@dataclass(frozen=True)
class WorkerEvent:
    kind: str
    job_id: str
    task_id: str | None
    bot_id: str | None
    text: str
    chat_id: int | None = None
    message_id: int | None = None


@dataclass(frozen=True)
class JobNotification:
    kind: str
    job_id: str
    text: str
    chat_id: int | None
    message_id: int | None


def _run_with_timeout(task: TaskRecord, provider_runner: ProviderRunner, timeout_s: float) -> dict:
    result_queue: queue.Queue[tuple[str, dict | BaseException]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            result_queue.put(("ok", provider_runner(task)))
        except BaseException as exc:  # noqa: BLE001 - provider boundary; error is serialized into task report.
            result_queue.put(("error", exc))

    thread = threading.Thread(target=target, name=f"provider-{task.task_id}", daemon=True)
    thread.start()
    try:
        status, payload = result_queue.get(timeout=timeout_s)
    except queue.Empty as exc:
        raise TimeoutError(f"task {task.task_id} timed out after {timeout_s}s") from exc
    if status == "error":
        raise RuntimeError(str(payload))
    return payload  # type: ignore[return-value]


def _dependency_reports(task: TaskRecord) -> list[dict]:
    reports: list[dict] = []
    for dependency_id in task.depends_on:
        for candidate in tasks_for_job(task.job_id):
            if candidate.task_id == dependency_id and candidate.report is not None:
                reports.append(candidate.report)
    return reports


def process_one_task(bot_id: str, provider_runner: ProviderRunner = run_fake_provider) -> WorkerEvent | None:
    task = claim_next_task(bot_id)
    if task is None:
        return None
    append_trace_event(task.trace_id, "task.claimed", {"task_id": task.task_id, "bot_id": task.bot_id, "mission": task.mission})
    provider = resolve_provider(task.mission, task.bot_id, tier=str(task.input.get("tier", "common")))
    enriched_input = dict(task.input)
    enriched_input["provider_resolution"] = provider.__dict__
    enriched_input["dependency_reports"] = _dependency_reports(task)
    task = TaskRecord(
        task_id=task.task_id,
        job_id=task.job_id,
        trace_id=task.trace_id,
        round=task.round,
        bot_id=task.bot_id,
        mission=task.mission,
        provider_id=provider.provider_id if provider.allowed else task.provider_id,
        depends_on=task.depends_on,
        status=task.status,
        input=enriched_input,
        report=task.report,
        attempts=task.attempts,
        lease_until=task.lease_until,
        timeout_s=task.timeout_s,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    try:
        report = _run_with_timeout(task, provider_runner, max(float(task.timeout_s), 0.01))
        report["provider_allowed"] = provider.allowed
        report["provider_reason"] = provider.reason
        completed = complete_task(task.task_id, report, status="done")
        append_trace_event(task.trace_id, "task.done", {"task_id": task.task_id, "bot_id": task.bot_id, "mission": task.mission, "report": report})
        return WorkerEvent("task_done", completed.job_id, completed.task_id, completed.bot_id, f"{completed.bot_id} done {completed.mission}")
    except TimeoutError as exc:
        failed = fail_task(task.task_id, f"TIMEOUT: {exc}")
        append_trace_event(task.trace_id, "task.timeout", {"task_id": task.task_id, "bot_id": task.bot_id, "error": str(exc), "new_status": failed.status})
        return WorkerEvent("task_timeout", failed.job_id, failed.task_id, failed.bot_id, str(exc))
    except RuntimeError as exc:
        failed = fail_task(task.task_id, f"ERROR: {exc}")
        append_trace_event(task.trace_id, "task.error", {"task_id": task.task_id, "bot_id": task.bot_id, "error": str(exc), "new_status": failed.status})
        return WorkerEvent("task_error", failed.job_id, failed.task_id, failed.bot_id, str(exc))


def process_ready_tasks_once(bot_ids: list[str], provider_runner: ProviderRunner = run_fake_provider) -> list[WorkerEvent]:
    events: list[WorkerEvent] = []
    for bot_id in bot_ids:
        event = process_one_task(bot_id, provider_runner=provider_runner)
        if event is not None:
            events.append(event)
    return events


def _best_effort_final_text(job_id: str) -> str:
    job = get_job(job_id)
    tasks = tasks_for_job(job_id)
    reports = reports_for_job(job_id)
    failures = [task for task in tasks if task.status in {"failed", "blocked", "expired"}]
    place_names: list[str] = []
    notices: set[str] = set()
    for report in reports:
        for place in report.get("places", []) or []:
            name = place.get("name")
            if name:
                place_names.append(str(name))
        for item in report.get("limitations", []) or []:
            notices.add(str(item))
        for item in report.get("must_disclose", []) or []:
            notices.add(str(item))
        required_notice = report.get("required_notice")
        if required_notice:
            notices.add(str(required_notice))
    lines = [f"Ket qua job_id={job_id}"]
    if job is not None:
        lines.append(f"case={job.case_id}")
    if place_names:
        lines.append("Dia diem mau tu provider gia:")
        lines.extend(f"- {name}" for name in place_names[:5])
    else:
        lines.append("Chua co ket qua dia diem day du; tra ket qua tot nhat hien co.")
    if notices:
        lines.append("Luu y: " + "; ".join(sorted(notices)))
    if failures:
        lines.append("Con thieu/loi: " + ", ".join(f"{task.bot_id}:{task.status}" for task in failures))
    return "\n".join(lines)


def collect_job_notifications() -> list[JobNotification]:
    notifications: list[JobNotification] = []
    for job in active_jobs():
        tasks = tasks_for_job(job.job_id)
        if not tasks:
            continue
        scout_done = next((task for task in tasks if task.bot_id == "scout" and task.status == "done"), None)
        if scout_done is not None and progress_sent_task_id(job.job_id) != scout_done.task_id:
            text = f"Tien do job_id={job.job_id}: Scout da xong {scout_done.mission}. Dang cho Critic/Validator."
            notifications.append(JobNotification("progress", job.job_id, text, job.chat_id, job.message_id))
            mark_progress_sent(job.job_id, scout_done.task_id)
        terminal = all(task.status in TERMINAL_STATUSES for task in tasks)
        deadline_hit = job.deadline_at is not None and job.deadline_at < __import__("time").time()
        if terminal or deadline_hit:
            text = _best_effort_final_text(job.job_id)
            notifications.append(JobNotification("final", job.job_id, text, job.chat_id, job.message_id))
            mark_job_final_sent(job.job_id, status="done" if terminal else "expired")
            append_trace_event(job.trace_id, "job.final", {"job_id": job.job_id, "terminal": terminal, "deadline_hit": deadline_hit, "text": text})
    return notifications
