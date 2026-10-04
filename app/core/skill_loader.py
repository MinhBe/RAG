from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class SkillLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedSkill:
    ref: str
    path: Path
    expected_hash: str
    actual_hash: str
    content: str


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_skill_from_provider(provider: dict) -> LoadedSkill:
    skill_path_raw = provider.get("skill_path")
    expected_hash = str(provider.get("skill_hash") or "")
    skill_ref = str(provider.get("skill_ref") or provider.get("skill_id") or "")
    if not skill_path_raw:
        raise SkillLoadError(f"provider {provider.get('id')} has no skill_path")
    if not expected_hash.startswith("sha256:"):
        raise SkillLoadError(f"provider {provider.get('id')} has no sha256 skill_hash")
    path = Path(str(skill_path_raw))
    if not path.exists():
        raise SkillLoadError(f"skill file not found: {path}")
    content = path.read_text(encoding="utf-8-sig")
    actual_hash = content_hash(content)
    if actual_hash != expected_hash:
        raise SkillLoadError(f"skill hash mismatch for {skill_ref}: expected {expected_hash}, got {actual_hash}")
    return LoadedSkill(ref=skill_ref, path=path, expected_hash=expected_hash, actual_hash=actual_hash, content=content)
