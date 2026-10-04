from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_DIR = REPO_ROOT / "taxonomy"
BOTS_DIR = REPO_ROOT / "bots"
REGISTRY_DIR = REPO_ROOT / "registry"


class RegistryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SkillDecision:
    skill_id: str
    name: str
    allowed: bool
    reason: str
    primary_tag: str
    secondary_tags: tuple[str, ...]
    required_permission: str
    discipline: tuple[str, ...]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RegistryValidationError(f"{path} must contain a YAML mapping")
    return data


def _entries(path: Path, key: str) -> list[dict[str, Any]]:
    data = _load_yaml(path)
    raw = data.get(key, [])
    if not isinstance(raw, list):
        raise RegistryValidationError(f"{path}:{key} must be a list")
    return [item for item in raw if isinstance(item, dict)]


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def role_tag_ids() -> set[str]:
    return {entry["id"] for entry in _entries(TAXONOMY_DIR / "role_tags.yaml", "role_tags")}


def discipline_ids() -> set[str]:
    return {entry["id"] for entry in _entries(TAXONOMY_DIR / "disciplines.yaml", "disciplines")}


def permission_ranks() -> dict[str, int]:
    return {entry["id"]: int(entry["rank"]) for entry in _entries(TAXONOMY_DIR / "permissions.yaml", "permissions")}


def load_bot_profiles() -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(BOTS_DIR.glob("*.yaml")):
        data = _load_yaml(path)
        bot_id = str(data.get("bot_id", "")).strip()
        if not bot_id:
            raise RegistryValidationError(f"{path} missing bot_id")
        data["_path"] = str(path)
        profiles[bot_id] = data
    return profiles


def load_skill_claims() -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    for path in [REGISTRY_DIR / "skill_claims.generated.yaml", REGISTRY_DIR / "skill_claims.curated.yaml"]:
        for claim in _entries(path, "claims"):
            skill_id = str(claim.get("skill_id", "")).strip()
            if not skill_id:
                raise RegistryValidationError(f"{path} has claim without skill_id")
            claim["_path"] = str(path)
            claims[skill_id] = claim
    return claims


def validate_registry() -> list[str]:
    errors: list[str] = []
    tags = role_tag_ids()
    disciplines = discipline_ids()
    ranks = permission_ranks()
    profiles = load_bot_profiles()
    claims = load_skill_claims()
    if not tags:
        errors.append("taxonomy/role_tags.yaml has no role_tags")
    if not profiles:
        errors.append("bots/*.yaml has no bot profiles")
    if not claims:
        errors.append("registry skill claims are empty")
    tag_coverage: set[str] = set()
    for bot_id, bot in profiles.items():
        bot_tags = set(_as_str_list(bot.get("role_tags")))
        tag_coverage.update(bot_tags)
        unknown = bot_tags - tags
        if unknown:
            errors.append(f"bot {bot_id} has unknown role_tags: {sorted(unknown)}")
        bot_disciplines = set(_as_str_list(bot.get("disciplines")))
        unknown_disciplines = bot_disciplines - disciplines
        if unknown_disciplines:
            errors.append(f"bot {bot_id} has unknown disciplines: {sorted(unknown_disciplines)}")
        ceiling = bot.get("permission_ceiling")
        if ceiling not in ranks:
            errors.append(f"bot {bot_id} has unknown permission_ceiling: {ceiling}")
        forbidden_self_review = {"validator", "reviewer", "security"}
        if "implementation" in bot_tags and bot_tags.intersection(forbidden_self_review):
            errors.append(f"bot {bot_id} violates segregation_of_duties: {sorted(bot_tags)}")
        if "orchestrator" in bot_tags and ceiling in ranks and ranks[str(ceiling)] > ranks["task_create"]:
            errors.append(f"bot {bot_id} violates orchestrator_no_write with ceiling={ceiling}")
    missing_bot_tags = tags - tag_coverage
    if missing_bot_tags:
        errors.append(f"role tags without any bot wearer: {sorted(missing_bot_tags)}")
    for skill_id, claim in claims.items():
        role_tags = claim.get("role_tags") or {}
        if not isinstance(role_tags, dict):
            errors.append(f"skill {skill_id} role_tags must be mapping")
            continue
        primary = role_tags.get("primary")
        secondary = _as_str_list(role_tags.get("secondary"))
        if not primary:
            errors.append(f"skill {skill_id} missing primary tag")
        elif primary not in tags:
            errors.append(f"skill {skill_id} has unknown primary tag: {primary}")
        if len(secondary) > 2:
            errors.append(f"skill {skill_id} has more than two secondary tags")
        unknown_secondary = set(secondary) - tags
        if unknown_secondary:
            errors.append(f"skill {skill_id} has unknown secondary tags: {sorted(unknown_secondary)}")
        if primary in secondary:
            errors.append(f"skill {skill_id} repeats primary tag in secondary tags")
        required_permission = claim.get("required_permission")
        if required_permission not in ranks:
            errors.append(f"skill {skill_id} has unknown required_permission: {required_permission}")
        claim_disciplines = set(_as_str_list(claim.get("discipline")))
        unknown_claim_disciplines = claim_disciplines - disciplines
        if unknown_claim_disciplines:
            errors.append(f"skill {skill_id} has unknown disciplines: {sorted(unknown_claim_disciplines)}")
        origin = claim.get("origin")
        if origin not in {"curated", "inferred"}:
            errors.append(f"skill {skill_id} has invalid origin: {origin}")
        confidence = claim.get("confidence")
        if not isinstance(confidence, int | float) or not (0 <= float(confidence) <= 1):
            errors.append(f"skill {skill_id} has invalid confidence: {confidence}")
        if bool(claim.get("composite")):
            if claim.get("must_delegate") is not True:
                errors.append(f"skill {skill_id} is composite but missing must_delegate=true")
            if required_permission in ranks and ranks[str(required_permission)] > ranks["task_create"]:
                errors.append(f"composite skill {skill_id} cannot require direct execution permission: {required_permission}")
            delegates = _as_str_list(claim.get("delegates_to"))
            if not delegates:
                errors.append(f"composite skill {skill_id} must declare delegates_to")
    return errors


def _permission_allows(required: str, ceiling: str, ranks: dict[str, int]) -> bool:
    return ranks[required] <= ranks[ceiling]


def resolve_skills_for_bot(bot_id: str, include_denied: bool = False) -> list[SkillDecision]:
    errors = validate_registry()
    if errors:
        raise RegistryValidationError("registry validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    profiles = load_bot_profiles()
    if bot_id not in profiles:
        raise RegistryValidationError(f"unknown bot_id: {bot_id}")
    bot = profiles[bot_id]
    bot_tags = set(_as_str_list(bot.get("role_tags")))
    bot_disciplines = set(_as_str_list(bot.get("disciplines")))
    ceiling = str(bot["permission_ceiling"])
    ranks = permission_ranks()
    decisions: list[SkillDecision] = []
    for skill_id, claim in sorted(load_skill_claims().items()):
        role_tags = claim["role_tags"]
        primary = str(role_tags["primary"])
        secondary = tuple(_as_str_list(role_tags.get("secondary")))
        required_permission = str(claim["required_permission"])
        skill_disciplines = tuple(_as_str_list(claim.get("discipline")))
        allowed = True
        reasons: list[str] = []
        if primary not in bot_tags:
            allowed = False
            reasons.append(f"primary tag {primary!r} not worn by bot")
        if not _permission_allows(required_permission, ceiling, ranks):
            allowed = False
            reasons.append(f"permission {required_permission!r} exceeds ceiling {ceiling!r}")
        if (
            primary == "implementation"
            and bot_disciplines
            and skill_disciplines
            and not bot_disciplines.intersection(skill_disciplines)
        ):
            allowed = False
            reasons.append("implementation discipline does not intersect bot disciplines")
        if allowed or include_denied:
            decisions.append(
                SkillDecision(
                    skill_id=skill_id,
                    name=str(claim.get("name") or skill_id),
                    allowed=allowed,
                    reason="allowed" if allowed else "; ".join(reasons),
                    primary_tag=primary,
                    secondary_tags=secondary,
                    required_permission=required_permission,
                    discipline=skill_disciplines,
                )
            )
    return decisions


def decisions_as_dicts(decisions: list[SkillDecision]) -> list[dict[str, Any]]:
    return [
        {
            "skill_id": item.skill_id,
            "name": item.name,
            "allowed": item.allowed,
            "reason": item.reason,
            "primary_tag": item.primary_tag,
            "secondary_tags": list(item.secondary_tags),
            "required_permission": item.required_permission,
            "discipline": list(item.discipline),
        }
        for item in decisions
    ]


def format_skill_resolution(bot_id: str, include_denied: bool = False) -> str:
    bot = load_bot_profiles()[bot_id]
    decisions = resolve_skills_for_bot(bot_id, include_denied=include_denied)
    allowed = [item for item in decisions if item.allowed]
    denied = [item for item in decisions if not item.allowed]
    lines = [
        f"Bot skill resolution: {bot_id}",
        f"display_name: {bot.get('display_name')}",
        "role_tags: " + ", ".join(_as_str_list(bot.get("role_tags"))),
        f"permission_ceiling: {bot.get('permission_ceiling')}",
        f"allowed_skills: {len(allowed)}",
    ]
    for item in allowed:
        disciplines = ",".join(item.discipline) or "-"
        secondary = ",".join(item.secondary_tags) or "-"
        lines.append(
            f"- {item.name} [{item.primary_tag}; secondary={secondary}; permission={item.required_permission}; discipline={disciplines}]"
        )
    if include_denied:
        lines.append(f"denied_skills: {len(denied)}")
        for item in denied:
            lines.append(f"- {item.name}: {item.reason}")
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve Hermes skills available to a bot profile.")
    parser.add_argument("--bot", required=True, help="bot_id such as lead, builder_core, validator")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--include-denied", action="store_true", help="Include denied skills with reasons")
    args = parser.parse_args(argv)
    decisions = resolve_skills_for_bot(args.bot, include_denied=args.include_denied)
    if args.json:
        payload = {"bot_id": args.bot, "decisions": decisions_as_dicts(decisions)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_skill_resolution(args.bot, include_denied=args.include_denied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



def bot_id_for_telegram_username(username: str | None) -> str | None:
    if not username:
        return None
    normalized = username.strip().lstrip("@").lower()
    for bot_id, profile in load_bot_profiles().items():
        telegram = str(profile.get("telegram_username") or "").strip().lstrip("@").lower()
        if telegram == normalized:
            return bot_id
    return None


def load_bot_profile(bot_id: str) -> dict[str, Any]:
    profiles = load_bot_profiles()
    if bot_id not in profiles:
        raise RegistryValidationError(f"unknown bot_id: {bot_id}")
    return profiles[bot_id]


def format_bot_identity(bot_id: str) -> str:
    bot = load_bot_profile(bot_id)
    return "\n".join(
        [
            f"Bot profile: {bot_id}",
            f"display_name: {bot.get('display_name')}",
            f"telegram_username: {bot.get('telegram_username')}",
            "role_tags: " + ", ".join(_as_str_list(bot.get("role_tags"))),
            "disciplines: " + ", ".join(_as_str_list(bot.get("disciplines"))),
            f"permission_ceiling: {bot.get('permission_ceiling')}",
            f"model_policy.preferred: {(bot.get('model_policy') or {}).get('preferred')}",
            f"model_policy.may_delegate: {str((bot.get('model_policy') or {}).get('may_delegate')).lower()}",
            f"notes: {bot.get('notes')}",
        ]
    )


def format_skill_resolution_for_username(username: str | None, include_denied: bool = False) -> str:
    bot_id = bot_id_for_telegram_username(username)
    if bot_id is None:
        return "BLOCKED by Hermes runtime profile guard: no bot profile is mapped to this Telegram username."
    return format_skill_resolution(bot_id, include_denied=include_denied)


def allowed_skill_context_for_bot(bot_id: str | None) -> str | None:
    if not bot_id:
        return None
    bot = load_bot_profile(bot_id)
    allowed = [item for item in resolve_skills_for_bot(bot_id) if item.allowed]
    lines = [
        "[Hermes Skill Access Control]",
        f"bot_id: {bot_id}",
        f"display_name: {bot.get('display_name')}",
        "role_tags: " + ", ".join(_as_str_list(bot.get("role_tags"))),
        f"permission_ceiling: {bot.get('permission_ceiling')}",
        "Rule: you may reference or use only skills listed under allowed_skills. Secondary tags do not grant access.",
        "allowed_skills:",
    ]
    if not allowed:
        lines.append("- none")
    claims = load_skill_claims()
    for item in allowed:
        secondary = ",".join(item.secondary_tags) or "-"
        disciplines = ",".join(item.discipline) or "-"
        claim = claims.get(item.skill_id, {})
        composite_note = "; composite=must_delegate" if claim.get("composite") and claim.get("must_delegate") else ""
        lines.append(
            f"- {item.name}: primary={item.primary_tag}; secondary={secondary}; "
            f"permission={item.required_permission}; discipline={disciplines}{composite_note}"
        )
    return "\n".join(lines)


def format_all_bot_skill_matrix() -> str:
    lines = ["Hermes bot/skill access matrix"]
    for bot_id in sorted(load_bot_profiles()):
        allowed = [item for item in resolve_skills_for_bot(bot_id) if item.allowed]
        names = ", ".join(item.name for item in allowed) or "-"
        profile = load_bot_profile(bot_id)
        lines.append(
            f"- {bot_id} ({profile.get('display_name')}): {len(allowed)} skills -> {names}"
        )
    return "\n".join(lines)
