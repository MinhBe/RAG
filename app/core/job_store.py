
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / '.omh' / 'state' / 'jobs.sqlite'


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    trace_id: str
    case_id: str
    status: str
    user_text: str


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    job_id: str
    trace_id: str
    bot_id: str
    mission_id: str
    provider_id: str | None
    status: str
    payload: dict


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS jobs (
          job_id TEXT PRIMARY KEY,
          trace_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          status TEXT NOT NULL,
          user_text TEXT NOT NULL,
          brief_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
          task_id TEXT PRIMARY KEY,
          job_id TEXT NOT NULL,
          trace_id TEXT NOT NULL,
          bot_id TEXT NOT NULL,
          mission_id TEXT NOT NULL,
          provider_id TEXT,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        CREATE TABLE IF NOT EXISTS reports (
          report_id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          job_id TEXT NOT NULL,
          bot_id TEXT NOT NULL,
          status TEXT NOT NULL,
          report_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(task_id) REFERENCES tasks(task_id),
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        '''
    )
    conn.commit()


def create_job(case_id: str, user_text: str, brief: dict, tasks: list[dict], trace_id: str | None = None) -> JobRecord:
    job_id = f'b-{uuid4().hex[:8]}'
    actual_trace_id = trace_id or f'trace-{job_id}'
    now = _now()
    with connect() as conn:
        conn.execute(
            'INSERT INTO jobs(job_id, trace_id, case_id, status, user_text, brief_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (job_id, actual_trace_id, case_id, 'queued', user_text, json.dumps(brief, ensure_ascii=False), now, now),
        )
        for task in tasks:
            task_id = task.get('task_id') or f't-{uuid4().hex[:8]}'
            conn.execute(
                'INSERT INTO tasks(task_id, job_id, trace_id, bot_id, mission_id, provider_id, status, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    task_id,
                    job_id,
                    actual_trace_id,
                    task['bot_id'],
                    task['mission_id'],
                    task.get('provider_id'),
                    task.get('status', 'queued'),
                    json.dumps(task.get('payload', {}), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        conn.commit()
    return JobRecord(job_id=job_id, trace_id=actual_trace_id, case_id=case_id, status='queued', user_text=user_text)


def tasks_for_job(job_id: str) -> list[TaskRecord]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM tasks WHERE job_id = ? ORDER BY created_at, task_id', (job_id,)).fetchall()
    return [
        TaskRecord(
            task_id=row['task_id'],
            job_id=row['job_id'],
            trace_id=row['trace_id'],
            bot_id=row['bot_id'],
            mission_id=row['mission_id'],
            provider_id=row['provider_id'],
            status=row['status'],
            payload=json.loads(row['payload_json']),
        )
        for row in rows
    ]


def claim_next_task(bot_id: str) -> TaskRecord | None:
    now = _now()
    with connect() as conn:
        row = conn.execute(
            'SELECT * FROM tasks WHERE bot_id = ? AND status = ? ORDER BY created_at, task_id LIMIT 1',
            (bot_id, 'queued'),
        ).fetchone()
        if row is None:
            return None
        conn.execute('UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?', ('claimed', now, row['task_id']))
        conn.commit()
    return TaskRecord(
        task_id=row['task_id'],
        job_id=row['job_id'],
        trace_id=row['trace_id'],
        bot_id=row['bot_id'],
        mission_id=row['mission_id'],
        provider_id=row['provider_id'],
        status='claimed',
        payload=json.loads(row['payload_json']),
    )


def reset_jobs_for_tests() -> None:
    if DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()
