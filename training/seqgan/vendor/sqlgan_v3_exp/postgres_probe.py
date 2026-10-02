# ruff: noqa
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PostgresProbeResult:
    parse_status: str
    runtime_status: str
    truth_status: str
    error_class: str = ""
    error_message: str = ""


def probe_boolean_predicate(payload: str, dsn: str | None = None, timeout_ms: int = 500) -> PostgresProbeResult:
    """Safely parse a generated boolean predicate in an offline PostgreSQL lab.

    This function never contacts a target application.  It only wraps a candidate as:
        EXPLAIN (FORMAT JSON) SELECT 1 WHERE (<payload>);

    Use a disposable local PostgreSQL instance and a least-privileged account.  If psycopg2
    is unavailable or no DSN is supplied, the result is `not_run`.
    """
    if not dsn:
        dsn = os.environ.get("SQLGAN_POSTGRES_DSN", "")
    if not dsn:
        return PostgresProbeResult("not_run", "not_run", "not_run", "NO_DSN", "Set SQLGAN_POSTGRES_DSN for an offline lab database.")
    try:
        import psycopg2  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return PostgresProbeResult("not_run", "not_run", "not_run", "NO_PSYCOPG2", str(exc))

    sql = f"EXPLAIN (FORMAT JSON) SELECT 1 WHERE ({payload})"
    try:
        with psycopg2.connect(dsn) as conn:  # type: ignore[name-defined]
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = %s", (int(timeout_ms),))
                cur.execute(sql)
                cur.fetchall()
        return PostgresProbeResult("parse_ok", "not_run", "not_run")
    except Exception as exc:  # pragma: no cover - requires postgres
        return PostgresProbeResult("parse_fail", "not_run", "not_run", exc.__class__.__name__, str(exc)[:500])
