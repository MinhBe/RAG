
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / ".omh" / "state" / "jobs.sqlite"
TERMINAL_STATUSES = {"done", "failed", "blocked", "expired"}


def now_ts() -> float:
    return time.time()


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    trace_id: str
    case_id: str
    status: str
    user_text: str
    chat_id: int | None = None
    message_id: int | None = None
    deadline_at: float | None = None
    deduped: bool = False


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    job_id: str
    trace_id: str
    round: int
    bot_id: str
    mission: str
    provider_id: str | None
    depends_on: tuple[str, ...]
    status: str
    input: dict
    report: dict | None
    attempts: int
    lease_until: float | None
    timeout_s: int
    created_at: float
    updated_at: float

    @property
    def mission_id(self) -> str:
        return self.mission

    @property
    def payload(self) -> dict:
        return self.input


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    init_db(conn)
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _drop_legacy_schema_if_needed(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "tasks") and "mission" not in _columns(conn, "tasks"):
        conn.executescript(
            """
            DROP TABLE IF EXISTS reports;
            DROP TABLE IF EXISTS tasks;
            DROP TABLE IF EXISTS jobs;
            """
        )
    if _table_exists(conn, "jobs") and "chat_id" not in _columns(conn, "jobs"):
        conn.executescript(
            """
            DROP TABLE IF EXISTS reports;
            DROP TABLE IF EXISTS tasks;
            DROP TABLE IF EXISTS jobs;
            """
        )


def init_db(conn: sqlite3.Connection) -> None:
    _drop_legacy_schema_if_needed(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          job_id TEXT PRIMARY KEY,
          trace_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          status TEXT NOT NULL,
          user_text TEXT NOT NULL,
          brief_json TEXT NOT NULL,
          chat_id INTEGER,
          message_id INTEGER,
          deadline_at REAL,
          final_sent_at REAL,
          last_progress_task_id TEXT,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS jobs_dedupe
          ON jobs(chat_id, message_id)
          WHERE chat_id IS NOT NULL AND message_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS tasks (
          task_id TEXT PRIMARY KEY,
          job_id TEXT NOT NULL,
          trace_id TEXT NOT NULL,
          round INTEGER NOT NULL DEFAULT 1,
          bot_id TEXT NOT NULL,
          mission TEXT NOT NULL,
          provider_id TEXT,
          depends_on TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'pending',
          input_json TEXT NOT NULL,
          report_json TEXT,
          attempts INTEGER NOT NULL DEFAULT 0,
          lease_until REAL,
          timeout_s INTEGER NOT NULL DEFAULT 60,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        CREATE INDEX IF NOT EXISTS tasks_ready_idx ON tasks(bot_id, status, created_at);
        CREATE TABLE IF NOT EXISTS reports (
          report_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          job_id TEXT NOT NULL,
          bot_id TEXT NOT NULL,
          status TEXT NOT NULL,
          report_json TEXT NOT NULL,
          created_at REAL NOT NULL,
          FOREIGN KEY(task_id) REFERENCES tasks(task_id),
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        """
    )


def _job_from_row(row: sqlite3.Row, *, deduped: bool = False) -> JobRecord:
    return JobRecord(
        job_id=row["job_id"],
        trace_id=row["trace_id"],
        case_id=row["case_id"],
        status=row["status"],
        user_text=row["user_text"],
        chat_id=row["chat_id"],
        message_id=row["message_id"],
        deadline_at=row["deadline_at"],
        deduped=deduped,
    )


def _task_from_row(row: sqlite3.Row) -> TaskRecord:
    report_raw = row["report_json"]
    return TaskRecord(
        task_id=row["task_id"],
        job_id=row["job_id"],
        trace_id=row["trace_id"],
        round=int(row["round"]),
        bot_id=row["bot_id"],
        mission=row["mission"],
        provider_id=row["provider_id"],
        depends_on=tuple(json.loads(row["depends_on"] or "[]")),
        status=row["status"],
        input=json.loads(row["input_json"]),
        report=json.loads(report_raw) if report_raw else None,
        attempts=int(row["attempts"]),
        lease_until=row["lease_until"],
        timeout_s=int(row["timeout_s"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def create_job(
    case_id: str,
    user_text: str,
    brief: dict,
    tasks: list[dict],
    trace_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    deadline_s: int = 180,
) -> JobRecord:
    ts = now_ts()
    actual_trace_id = trace_id or f"trace_{uuid4().hex[:12]}"
    with connect() as conn:
        if chat_id is not None and message_id is not None:
            existing = conn.execute(
                "SELECT * FROM jobs WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id),
            ).fetchone()
            if existing is not None:
                return _job_from_row(existing, deduped=True)
        job_id = f"b-{uuid4().hex[:8]}"
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO jobs(
              job_id, trace_id, case_id, status, user_text, brief_json,
              chat_id, message_id, deadline_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                actual_trace_id,
                case_id,
                "queued",
                user_text,
                json.dumps(brief, ensure_ascii=False),
                chat_id,
                message_id,
                ts + deadline_s,
                ts,
                ts,
            ),
        )
        for task in tasks:
            task_id = task.get("task_id") or f"t-{uuid4().hex[:8]}"
            mission = task.get("mission") or task.get("mission_id")
            conn.execute(
                """
                INSERT INTO tasks(
                  task_id, job_id, trace_id, round, bot_id, mission, provider_id,
                  depends_on, status, input_json, attempts, timeout_s, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    job_id,
                    actual_trace_id,
                    int(task.get("round", 1)),
                    task["bot_id"],
                    mission,
                    task.get("provider_id"),
                    json.dumps(task.get("depends_on", []), ensure_ascii=False),
                    task.get("status", "pending"),
                    json.dumps(task.get("input", task.get("payload", {})), ensure_ascii=False),
                    int(task.get("attempts", 0)),
                    int(task.get("timeout_s", 60)),
                    ts,
                    ts,
                ),
            )
        conn.execute("COMMIT")
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _job_from_row(row)


def get_job(job_id: str) -> JobRecord | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def tasks_for_job(job_id: str) -> list[TaskRecord]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tasks WHERE job_id = ? ORDER BY created_at, task_id", (job_id,)).fetchall()
    return [_task_from_row(row) for row in rows]


def reports_for_job(job_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT report_json FROM reports WHERE job_id = ? ORDER BY created_at", (job_id,)).fetchall()
    return [json.loads(row["report_json"]) for row in rows]


def _dependencies_done(conn: sqlite3.Connection, task: sqlite3.Row) -> bool:
    depends_on = json.loads(task["depends_on"] or "[]")
    if not depends_on:
        return True
    placeholders = ",".join("?" for _ in depends_on)
    rows = conn.execute(f"SELECT status FROM tasks WHERE task_id IN ({placeholders})", depends_on).fetchall()
    return len(rows) == len(depends_on) and all(row["status"] == "done" for row in rows)


def claim_next_task(bot_id: str, *, ts: float | None = None) -> TaskRecord | None:
    current = ts or now_ts()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _expire_stale_tasks_in_conn(conn, current)
        _block_tasks_with_failed_dependencies_in_conn(conn, current)
        rows = conn.execute(
            "SELECT * FROM tasks WHERE bot_id = ? AND status = 'pending' ORDER BY created_at, task_id",
            (bot_id,),
        ).fetchall()
        selected: sqlite3.Row | None = None
        for row in rows:
            if _dependencies_done(conn, row):
                selected = row
                break
        if selected is None:
            conn.execute("COMMIT")
            return None
        conn.execute(
            """
            UPDATE tasks
            SET status = 'running', attempts = attempts + 1, lease_until = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (current + int(selected["timeout_s"]), current, selected["task_id"]),
        )
        conn.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE job_id = ?", (current, selected["job_id"]))
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (selected["task_id"],)).fetchone()
        conn.execute("COMMIT")
    return _task_from_row(row)


def complete_task(task_id: str, report: dict, *, status: str = "done") -> TaskRecord:
    ts = now_ts()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown task_id: {task_id}")
        report_json = json.dumps(report, ensure_ascii=False)
        conn.execute(
            """
            UPDATE tasks
            SET status = ?, report_json = ?, lease_until = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (status, report_json, ts, task_id),
        )
        conn.execute(
            "INSERT INTO reports(report_id, task_id, job_id, bot_id, status, report_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"r-{uuid4().hex[:8]}", task_id, row["job_id"], row["bot_id"], status, report_json, ts),
        )
        _block_tasks_with_failed_dependencies_in_conn(conn, ts)
        updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        conn.execute("COMMIT")
    return _task_from_row(updated)


def fail_task(task_id: str, error: str, *, retry_limit: int = 2) -> TaskRecord:
    ts = now_ts()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown task_id: {task_id}")
        attempts = int(row["attempts"])
        report = {"ok": False, "error": error, "attempts": attempts}
        if attempts < retry_limit:
            status = "pending"
            lease_until = None
        else:
            status = "failed"
            lease_until = None
        conn.execute(
            "UPDATE tasks SET status = ?, report_json = ?, lease_until = ?, updated_at = ? WHERE task_id = ?",
            (status, json.dumps(report, ensure_ascii=False), lease_until, ts, task_id),
        )
        if status == "failed":
            conn.execute(
                "INSERT INTO reports(report_id, task_id, job_id, bot_id, status, report_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"r-{uuid4().hex[:8]}", task_id, row["job_id"], row["bot_id"], status, json.dumps(report, ensure_ascii=False), ts),
            )
        _block_tasks_with_failed_dependencies_in_conn(conn, ts)
        updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        conn.execute("COMMIT")
    return _task_from_row(updated)


def _expire_stale_tasks_in_conn(conn: sqlite3.Connection, ts: float) -> None:
    conn.execute(
        "UPDATE tasks SET status = 'pending', lease_until = NULL, updated_at = ? WHERE status = 'running' AND lease_until IS NOT NULL AND lease_until < ?",
        (ts, ts),
    )


def expire_stale_tasks(*, ts: float | None = None) -> int:
    current = ts or now_ts()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        before = conn.total_changes
        _expire_stale_tasks_in_conn(conn, current)
        conn.execute("COMMIT")
        return conn.total_changes - before


def _block_tasks_with_failed_dependencies_in_conn(conn: sqlite3.Connection, ts: float) -> None:
    pending = conn.execute("SELECT * FROM tasks WHERE status = 'pending'").fetchall()
    for task in pending:
        depends_on = json.loads(task["depends_on"] or "[]")
        if not depends_on:
            continue
        placeholders = ",".join("?" for _ in depends_on)
        rows = conn.execute(f"SELECT status FROM tasks WHERE task_id IN ({placeholders})", depends_on).fetchall()
        if any(row["status"] in {"failed", "blocked", "expired"} for row in rows):
            report = {"ok": False, "error": "blocked by failed dependency", "depends_on": depends_on}
            conn.execute(
                "UPDATE tasks SET status = 'blocked', report_json = ?, updated_at = ? WHERE task_id = ?",
                (json.dumps(report, ensure_ascii=False), ts, task["task_id"]),
            )
            conn.execute(
                "INSERT INTO reports(report_id, task_id, job_id, bot_id, status, report_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"r-{uuid4().hex[:8]}", task["task_id"], task["job_id"], task["bot_id"], "blocked", json.dumps(report, ensure_ascii=False), ts),
            )


def active_jobs() -> list[JobRecord]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE final_sent_at IS NULL ORDER BY created_at").fetchall()
    return [_job_from_row(row) for row in rows]


def mark_progress_sent(job_id: str, task_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE jobs SET last_progress_task_id = ?, updated_at = ? WHERE job_id = ?", (task_id, now_ts(), job_id))


def progress_sent_task_id(job_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT last_progress_task_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return row["last_progress_task_id"] if row else None


def mark_job_final_sent(job_id: str, *, status: str = "done") -> None:
    ts = now_ts()
    with connect() as conn:
        conn.execute("UPDATE jobs SET status = ?, final_sent_at = ?, updated_at = ? WHERE job_id = ?", (status, ts, ts, job_id))


def reset_jobs_for_tests() -> None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM jobs")
        conn.execute("COMMIT")
