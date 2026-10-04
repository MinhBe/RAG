# Phase 7 Registry Bridge Report

## Decision

Phase 7 is implemented as a bridge, not blind L0 tagging.

The control plane now supports generated and curated entity-level claims. Existing OMH skills are claims. Larger source inventories should be imported as source records first, then promoted into claim entities only after name+description evidence exists.

## Guardrail

Do not assign tags directly to raw placement rows or whole repositories. A repo can contain skills with different roles, and a raw placement is not a stable entity.

## Next import path

1. Read source inventory from `Model Setup/47_SKILL_SOURCE_FETCH_20261004`.
2. Extract stable skill-like entities with name + description + local path.
3. Emit `registry/skill_claims.generated.yaml` additions with `origin: inferred` and confidence.
4. Move reviewed claims into `registry/skill_claims.curated.yaml`.
5. Re-run `scripts/query_registry.py --bot <id>` to validate access.

## Current bridge status

OMH 12 skills are fully bridged. Other fetched repositories remain source inventory until skill-level evidence is extracted.
