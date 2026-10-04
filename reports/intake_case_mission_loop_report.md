# Intake, Case, Mission, and Loop Report

## Brief intake

Implemented pp/core/briefing.py:

- Brief schema
- stated vs inferred fields
- 	race_id
- Lead-only extraction prompt
- JSON validation functions

This is schema/prompt infrastructure only; LLM extraction must produce JSON that code validates before use.

## Case matcher

Implemented pp/core/case_matcher.py:

- esearch_question
- generic
- thresholds: accept >= 0.8, review >= 0.5, fallback below 0.5
- unmatched generic logging to .omh/events/unmatched_cases.jsonl

The first runnable specialized case is esearch_question, not place search.

## Mission/provider resolver

Implemented pp/core/mission_registry.py with:

- egistry/missions.yaml
- egistry/providers.yaml
- egistry/cases.yaml

Provider resolution calls the existing bot skill/permission resolver before allowing a provider.

## Loop controller

Implemented pp/core/loop_controller.py:

- max rounds
- budget
- deadline
- stop if score does not improve for configured window

LLM may evaluate content, but code decides loop continuation.
