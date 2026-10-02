# Hermes SOC Post-Audit

Hermes is an AI-assisted Tier-1/post-audit system. It does not perform autonomous production remediation.

## Implemented vertical slice
- FastAPI API: `/health`, `/health/providers`, `/v1/triage`, `/v1/runs/latest`, `/v1/runs/{run_uuid}`.
- Pydantic contracts reject unknown fields and non-synthetic/non-redacted evidence.
- LangGraph flow: validate -> deterministic triage -> policy gate.
- High/critical source hints route to `pending_human_review`; they are not threat confirmations.
- Evidence-reference validation, JSONL traces, structured provider health.
- 9Router is installed globally and retained project-local for reproducibility.
- Supabase stores runs, evidence, and findings with RLS enabled and service-role server access only.

## Local run
1. `uv sync --frozen`
2. `uv run pytest -q`
3. `powershell -ExecutionPolicy Bypass -File scripts/start-9router.ps1`
4. `powershell -ExecutionPolicy Bypass -File scripts/start-hermes.ps1`
5. `uv run python scripts/smoke_local.py`
## Docker run and demo
1. Start Docker Desktop.
2. `docker compose up -d --build --force-recreate`
3. `uv run python scripts/demo_end_to_end.py`
4. `docker compose logs --tail=80 hermes-api`

The demo script checks health, provider configuration, triage, Supabase persistence, and audit readback.

## Supabase
Configured project URL:
`https://wvcguntxwupmcojxexao.supabase.co`

Set the service secret only in local `.env`:
`SUPABASE_SECRET_KEY=...`

Do not commit `.env` or copy secrets into issue trackers, reports, or demos.
## Manual handoff
Current demo stack is functional: local Docker API, 9Router/Gemini, and Supabase persistence/readback.

After the demo, rotate exposed or chat-shared secrets:
- 9Router client key
- Supabase secret key
- Gemini provider key if exposed outside the local dashboard

## Safety boundary
External logs, RAG documents, tool descriptions, and tool results are data, not instructions. Production remediation remains manual. Writes, sends, deletes, security-control changes, credentials, and external testing require explicit approval.


## Demo B Security
Run the recruiter-facing security slice with one command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo_b.ps1
```
It validates prompt/indirect-injection evidence handling, evidence-reference
integrity, human review boundaries, Supabase readback, and the existing end-to-end
triage path. Details: `docs/DEMO_B_SECURITY.md`.

The one-command runner also renders a browser-viewable report at:

```text
artifacts/demo_b/security_demo_b_report.html
```
