
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.skill_registry import (
    bot_id_for_telegram_username,
    load_bot_profile,
    load_skill_claims,
    permission_ranks,
    resolve_skills_for_bot,
)

SKILL_REQUEST_RE = re.compile(
    r"(?:/use-skill|/run-skill|/skill|run skill|use skill|cháº¡y skill|chay skill|dÃ¹ng skill|dung skill|cháº¡y|chay|dÃ¹ng|dung)\s+([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
WRITE_REQUEST_RE = re.compile(
    r"\b(?:write|ghi|sá»­a|sua|edit|modify|commit|táº¡o file|tao file|xÃ³a file|xoa file)\b.*\b(?:file|repo|code|repository|mÃ£|ma)\b|\b(?:ghi file|write file|commit code)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeGuardResult:
    action: str
    allowed: bool
    bot_id: str | None
    message: str
    reason: str


def _skill_aliases(skill_id: str, claim: dict[str, Any]) -> set[str]:
    aliases = {skill_id.lower(), skill_id.split(".")[-1].lower()}
    name = str(claim.get("name") or "").strip().lower()
    if name:
        aliases.add(name)
    return aliases


def find_skill_claim(skill_name: str) -> tuple[str, dict[str, Any]] | None:
    needle = skill_name.strip().lstrip("@").lower()
    for skill_id, claim in load_skill_claims().items():
        if needle in _skill_aliases(skill_id, claim):
            return skill_id, claim
    return None


def detect_skill_invocation(text: str) -> str | None:
    match = SKILL_REQUEST_RE.search(text)
    if not match:
        return None
    return match.group(1).strip().strip(".,:;`'")


def detects_repo_write_request(text: str) -> bool:
    return bool(WRITE_REQUEST_RE.search(text))


def guard_skill_invocation_for_username(username: str | None, skill_name: str) -> RuntimeGuardResult:
    bot_id = bot_id_for_telegram_username(username)
    if bot_id is None:
        return RuntimeGuardResult(
            action="skill_invoke",
            allowed=False,
            bot_id=None,
            reason="unmapped_bot",
            message="BLOCKED by Hermes runtime: no bot profile is mapped to this Telegram username.",
        )
    found = find_skill_claim(skill_name)
    if found is None:
        return RuntimeGuardResult(
            action="skill_invoke",
            allowed=False,
            bot_id=bot_id,
            reason="unknown_skill",
            message=f"BLOCKED by Hermes runtime: unknown skill {skill_name!r}.",
        )
    skill_id, claim = found
    decisions = resolve_skills_for_bot(bot_id, include_denied=True)
    decision = next((item for item in decisions if item.skill_id == skill_id), None)
    if decision is None or not decision.allowed:
        reason = decision.reason if decision is not None else "skill not resolvable for bot"
        return RuntimeGuardResult(
            action="skill_invoke",
            allowed=False,
            bot_id=bot_id,
            reason=reason,
            message=(
                "BLOCKED by Hermes runtime access control\n"
                f"bot_id: {bot_id}\n"
                f"requested_skill: {claim.get('name') or skill_id}\n"
                f"reason: {reason}"
            ),
        )
    if bool(claim.get("composite")) and bool(claim.get("must_delegate")):
        delegates = ", ".join(str(item) for item in claim.get("delegates_to", [])) or "declared sub-steps"
        return RuntimeGuardResult(
            action="skill_invoke",
            allowed=False,
            bot_id=bot_id,
            reason="composite_must_delegate",
            message=(
                "BLOCKED as direct execution by Hermes runtime\n"
                f"bot_id: {bot_id}\n"
                f"requested_skill: {claim.get('name') or skill_id}\n"
                "reason: composite skill must delegate; it may orchestrate but not self-execute.\n"
                f"delegates_to: {delegates}"
            ),
        )
    return RuntimeGuardResult(
        action="skill_invoke",
        allowed=True,
        bot_id=bot_id,
        reason="allowed_by_resolver",
        message=(
            "ALLOWED by Hermes runtime access control\n"
            f"bot_id: {bot_id}\n"
            f"skill: {claim.get('name') or skill_id}\n"
            "note: direct execution bridge is guarded; execution still requires a supported mission/case runner."
        ),
    )


def guard_repo_write_for_username(username: str | None, requested_action: str = "repo_write") -> RuntimeGuardResult:
    bot_id = bot_id_for_telegram_username(username)
    if bot_id is None:
        return RuntimeGuardResult(
            action=requested_action,
            allowed=False,
            bot_id=None,
            reason="unmapped_bot",
            message="BLOCKED by Hermes runtime: no bot profile is mapped to this Telegram username.",
        )
    bot = load_bot_profile(bot_id)
    ranks = permission_ranks()
    ceiling = str(bot.get("permission_ceiling"))
    required = "repo_write"
    if ranks[ceiling] < ranks[required]:
        return RuntimeGuardResult(
            action=requested_action,
            allowed=False,
            bot_id=bot_id,
            reason=f"permission {required!r} exceeds ceiling {ceiling!r}",
            message=(
                "BLOCKED by Hermes runtime permission ceiling\n"
                f"bot_id: {bot_id}\n"
                f"requested_permission: {required}\n"
                f"permission_ceiling: {ceiling}\n"
                "reason: this bot may not write files/repo code directly."
            ),
        )
    return RuntimeGuardResult(
        action=requested_action,
        allowed=True,
        bot_id=bot_id,
        reason="permission_ceiling_allows_repo_write",
        message=(
            "Repo-write permission ceiling allows this bot, but chat text alone does not execute writes. "
            "Use a supported implementation mission/task runner with traceable inputs."
        ),
    )


def evaluate_runtime_request_for_username(username: str | None, text: str) -> RuntimeGuardResult | None:
    skill_name = detect_skill_invocation(text)
    if skill_name:
        return guard_skill_invocation_for_username(username, skill_name)
    if detects_repo_write_request(text):
        return guard_repo_write_for_username(username)
    return None
