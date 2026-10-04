from __future__ import annotations

import json
import subprocess
import sys

from app.core.skill_registry import (
    load_bot_profiles,
    load_skill_claims,
    resolve_skills_for_bot,
    validate_registry,
)


def test_registry_validates_cleanly() -> None:
    assert validate_registry() == []


def test_every_claim_has_primary_and_limited_secondary_tags() -> None:
    claims = load_skill_claims()
    assert len(claims) >= 12
    for claim in claims.values():
        role_tags = claim["role_tags"]
        assert role_tags["primary"]
        assert len(role_tags.get("secondary") or []) <= 2


def test_bot_profiles_keep_implementation_separate_from_review_roles() -> None:
    profiles = load_bot_profiles()
    forbidden = {"validator", "reviewer", "security"}
    for profile in profiles.values():
        tags = set(profile["role_tags"])
        if "implementation" in tags:
            assert not tags.intersection(forbidden)
        if "orchestrator" in tags:
            assert profile["permission_ceiling"] == "task_create"


def test_lead_gets_planning_and_orchestration_skills_only() -> None:
    names = {item.name for item in resolve_skills_for_bot("lead")}
    assert "omh-ralplan" in names
    assert "omh-ralplan-driver" in names
    assert "omh-ralph-task" not in names
    assert "hermes-executor-verification" not in names


def test_builder_core_gets_implementation_but_not_validator_skills() -> None:
    names = {item.name for item in resolve_skills_for_bot("builder_core")}
    assert "omh-ralph" in names
    assert "omh-ralph-task" in names
    assert "hermes-executor-verification" not in names


def test_validator_gets_verification_without_implementation_skills() -> None:
    names = {item.name for item in resolve_skills_for_bot("validator")}
    assert "hermes-executor-verification" in names
    assert "omh-ralph" not in names
    assert "omh-ralph-task" not in names


def test_secondary_tags_do_not_grant_access() -> None:
    names = {item.name for item in resolve_skills_for_bot("sentinel")}
    assert "omh-triage" in names
    assert "omh-ralplan" not in names


def test_query_registry_cli_json() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/query_registry.py", "--bot", "lead", "--json"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["bot_id"] == "lead"
    assert any(item["name"] == "omh-ralplan" and item["allowed"] for item in payload["decisions"])
