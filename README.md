# Hermes SOC Post-Audit

Hermes is an AI-assisted Tier-1/post-audit system. It does not perform autonomous production remediation.

## Implemented vertical slice
- FastAPI API: `/health`, `/health/providers`, `/v1/triage`.
- Pydantic contracts reject unknown fields and non-synthetic/non-redacted evidence.
- LangGraph flow: validate -> deterministic triage -> policy gate.
- High/critical source hints route to `pending_human_review`; they are not threat confirmations.
- Evidence-reference validation, JSONL traces, structured provider health.
- 9Router is installed globally and also retained project-local for reproducibility.
- Supabase adapter/migration remain credential-free and unapplied.

## Local run
1. `uv sync --frozen`
2. `uv run pytest -q`
3. `powershell -ExecutionPolicy Bypass -File scripts/start-9router.ps1`
4. `powershell -ExecutionPolicy Bypass -File scripts/start-hermes.ps1`
5. `uv run python scripts/smoke_local.py`

## Docker run
1. Start Docker Desktop.
2. `docker compose build`
3. `docker compose up -d`
4. `uv run python scripts/smoke_local.py`
5. `docker compose logs --tail=80 hermes-api`

If Docker Desktop is launched from an environment that lacks `%ProgramData%`, set user environment `ProgramData=C:\ProgramData` before restarting Docker Desktop.

## Manual handoff
Open the local 9Router dashboard, configure Gemini there, then set only the Hermes routing values you intend to use in local `.env`. Do not commit secrets. Supabase remains optional until its project is explicitly activated and credentials are supplied locally.

## Safety boundary
External logs, RAG documents, tool descriptions, and tool results are data, not instructions. Production remediation remains manual. Writes, sends, deletes, security-control changes, credentials, and external testing require explicit approval.
