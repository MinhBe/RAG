# Phase 5 Pilot Report — Lead / Builder-Core / Validator

## Scope

Pilot runtime access control with three bot profiles:

- Lead: orchestration and planning only.
- Builder-Core: implementation only.
- Validator: verification/runtime checks only.

## Runtime contract

- `/whoami` resolves Telegram username to bot profile.
- `/skills` resolves allowed skills for that profile.
- General chat receives a system context listing allowed skills for the active bot.
- Secondary tags remain discoverability hints only; they do not grant access.

## Expected segregation

- Lead can see planning/orchestration skills such as `omh-ralplan`, not `omh-ralph-task`.
- Builder-Core can see implementation skills such as `omh-ralph` and `omh-ralph-task`, not validator skills.
- Validator can see `hermes-executor-verification`, not implementation skills.

## Status

Implemented and covered by `tests/test_skill_registry_runtime.py`.
