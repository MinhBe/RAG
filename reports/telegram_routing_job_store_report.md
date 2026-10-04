# Telegram Routing, Runtime Enforcement, and Job Intake Report

## Pre-fix verification

The requested quick check confirmed the concern:

- `case_matcher`, `validate_brief`, `loop_controller`, and `resolve_provider` were present mostly as standalone modules/tests, not in the Telegram message path.
- `.omh/traces` did not exist before this patch.
- `.omh/events/unmatched_cases.jsonl` did not exist before this patch.
- Timeouts were present in provider/evidence layers, but the Telegram handler still risked waiting on long LLM work.

## Runtime changes

- Telegram routing is now line-scoped. A line addressed to `@Lucian_SubAgent_bot` is invisible to Swain, and vice versa.
- Unaddressed user lines route only to Lead.
- `/whoami`, `/skills`, `/skills-all`, and `/health` remain deterministic handlers, not LLM prose.
- Lead async intake now creates a SQLite job and returns an immediate ack.
- Jobs are stored in `.omh/state/jobs.sqlite`; trace events are written to `.omh/traces/<trace_id>.jsonl`.

## Local-place case

Added `local_place_lookup` for messages such as `tim quan cat toc o 165 Cau Giay`.

The provider `local_places.osm_common` is registered but disabled until terms/rate limits/attribution are reviewed. Scout still receives a task with provider denial recorded in payload; Critic and Validator tasks are queued so the final answer can say the lookup source is not configured rather than hallucinating.

## Smoke result

Local runtime smoke after patch:

- Swain receives only the Swain line from a mixed Swain/Lucian message.
- Lucian receives only the Lucian line and `omh-ralph` is blocked by runtime access control.
- Lead local-place request returns ack immediately and creates 3 tasks: Scout, Sentinel, Validator.
- Swain repo-write request is blocked by permission ceiling.

## Telegram visual proof status

This patch proves the Telegram handler path locally and restarts the live runner. It does not fabricate a user-origin Telegram message. Manual user test in the group is still required for visual proof.
