
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml

from app.core.skill_registry import (
    REPO_ROOT,
    _as_str_list,
    load_bot_profile,
    permission_ranks,
    resolve_skills_for_bot,
)

MISSIONS_PATH = REPO_ROOT / "registry" / "missions.yaml"
PROVIDERS_PATH = REPO_ROOT / "registry" / "providers.yaml"


@dataclass(frozen=True)
class ProviderResolution:
    mission_id: str
    bot_id: str
    tier: str
    provider_id: str | None
    allowed: bool
    reason: str


def _load_list(path, key: str) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get(key, [])
    return [item for item in raw if isinstance(item, dict)]


def load_missions() -> dict[str, dict]:
    return {str(item["id"]): item for item in _load_list(MISSIONS_PATH, "missions")}


def load_providers() -> list[dict]:
    return _load_list(PROVIDERS_PATH, "providers")


def _permission_allows(required: str, ceiling: str) -> bool:
    ranks = permission_ranks()
    return ranks[required] <= ranks[ceiling]


def resolve_provider(mission_id: str, bot_id: str, tier: Literal["common", "specific"] = "specific") -> ProviderResolution:
    missions = load_missions()
    if mission_id not in missions:
        return ProviderResolution(mission_id, bot_id, tier, None, False, "unknown mission")
    candidates = [p for p in load_providers() if p.get("mission_id") == mission_id and p.get("tier") == tier]
    if not candidates:
        return ProviderResolution(mission_id, bot_id, tier, None, False, "no provider for tier")
    bot = load_bot_profile(bot_id)
    bot_tags = set(_as_str_list(bot.get("role_tags")))
    ceiling = str(bot.get("permission_ceiling"))
    allowed_skill_ids = {item.skill_id for item in resolve_skills_for_bot(bot_id)}
    allowed_skill_names = {item.name for item in resolve_skills_for_bot(bot_id)}
    denied_reasons: list[str] = []
    for provider in candidates:
        provider_id = str(provider.get("id"))
        if provider.get("enabled") is False:
            denied_reasons.append(f"{provider_id}: provider disabled/not configured")
            continue
        required_role = provider.get("required_role_tag")
        required_permission = str(provider.get("required_permission", "read"))
        skill_id = provider.get("skill_id")
        if required_role and required_role not in bot_tags:
            denied_reasons.append(f"{provider_id}: required role {required_role!r} not worn")
            continue
        if not _permission_allows(required_permission, ceiling):
            denied_reasons.append(f"{provider_id}: permission {required_permission!r} exceeds {ceiling!r}")
            continue
        if skill_id and skill_id not in allowed_skill_ids and str(skill_id).split(".")[-1] not in allowed_skill_names:
            denied_reasons.append(f"{provider_id}: skill {skill_id!r} not allowed by resolver")
            continue
        return ProviderResolution(mission_id, bot_id, tier, provider_id, True, "allowed")
    return ProviderResolution(mission_id, bot_id, tier, None, False, "; ".join(denied_reasons) or "no provider allowed")
