
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_OMH_SOURCE_PATH = Path(
    r"C:\Users\Admin\Downloads\Knowleage\Model Setup\skill_sources_v0_5\A12_oh-my-hermes"
)


@dataclass(frozen=True)
class OmhSkill:
    name: str
    local_path: str
    summary: str
    capability_tags: tuple[str, ...]


@dataclass(frozen=True)
class OmhRegistry:
    available: bool
    source_path: str
    head_sha: str | None
    default_branch: str | None
    plugin_tools: tuple[str, ...]
    plugin_hooks: tuple[str, ...]
    roles: tuple[str, ...]
    skills: tuple[OmhSkill, ...]
    mode: str
    integrity_state: str
    notes: tuple[str, ...]


def _source_path() -> Path:
    raw = os.environ.get("HERMES_OMH_SOURCE_PATH")
    return Path(raw) if raw else DEFAULT_OMH_SOURCE_PATH


def _run_git(path: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _yaml_list(text: str, key: str) -> tuple[str, ...]:
    lines = text.splitlines()
    out: list[str] = []
    in_block = False
    for line in lines:
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            in_block = True
            continue
        if in_block:
            if line and not line.startswith((" ", "\t", "-")):
                break
            match = re.match(r"\s*-\s*([A-Za-z0-9_\-]+)\s*$", line)
            if match:
                out.append(match.group(1))
    return tuple(out)


def _summary_from_skill(path: Path) -> str:
    text = _read_text(path / "SKILL.md")
    for line in text.splitlines():
        stripped = line.strip(" #\t")
        if stripped and not stripped.lower().startswith("skill"):
            return stripped[:220]
    readme = _read_text(path / "README.md")
    for line in readme.splitlines():
        stripped = line.strip(" #\t")
        if stripped:
            return stripped[:220]
    return "OMH skill; summary not declared in first lines."


def _tags_for_skill(name: str, summary: str) -> tuple[str, ...]:
    corpus = f"{name} {summary}".lower()
    tags: set[str] = {"omh", "skill"}
    mapping = {
        "research": "research",
        "verify": "verification",
        "verified": "verification",
        "evidence": "evidence",
        "plan": "planning",
        "planner": "planning",
        "architect": "architecture",
        "critic": "critique",
        "triage": "triage",
        "interview": "requirements",
        "executor": "execution",
        "ralph": "execution",
        "delegate": "delegation",
        "autopilot": "workflow",
        "consensus": "orchestration",
        "parallel": "parallel",
    }
    for needle, tag in mapping.items():
        if needle in corpus:
            tags.add(tag)
    return tuple(sorted(tags))


def _discover_roles(source: Path) -> tuple[str, ...]:
    ref_dir = source / "plugins" / "omh" / "references"
    if not ref_dir.exists():
        return ()
    roles: set[str] = set()
    for path in ref_dir.glob("role-*.md"):
        name = path.stem.removeprefix("role-")
        if name:
            roles.add(name)
    return tuple(sorted(roles))


def _discover_skills(source: Path) -> tuple[OmhSkill, ...]:
    skills_dir = source / "plugins" / "omh" / "skills"
    if not skills_dir.exists():
        return ()
    skills: list[OmhSkill] = []
    for path in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        summary = _summary_from_skill(path)
        skills.append(
            OmhSkill(
                name=path.name,
                local_path=str(path),
                summary=summary,
                capability_tags=_tags_for_skill(path.name, summary),
            )
        )
    return tuple(skills)


def load_omh_registry() -> OmhRegistry:
    source = _source_path()
    notes: list[str] = []
    if not source.exists():
        return OmhRegistry(
            available=False,
            source_path=str(source),
            head_sha=None,
            default_branch=None,
            plugin_tools=(),
            plugin_hooks=(),
            roles=(),
            skills=(),
            mode="unavailable",
            integrity_state="missing_source_path",
            notes=("Set HERMES_OMH_SOURCE_PATH or fetch A12 Oh My Hermes source.",),
        )
    if not (source / ".git").exists():
        notes.append("Source exists but is not a git repository; treat as evidence-only copy.")
    plugin_yaml = _read_text(source / "plugins" / "omh" / "plugin.yaml")
    skills = _discover_skills(source)
    roles = _discover_roles(source)
    tools = _yaml_list(plugin_yaml, "provides_tools")
    hooks = _yaml_list(plugin_yaml, "provides_hooks")
    head_sha = _run_git(source, "rev-parse", "HEAD")
    branch = _run_git(source, "branch", "--show-current")
    integrity = "available_git_source" if head_sha else "available_unverified_source"
    if hooks:
        notes.append("Plugin hooks are not auto-enabled; deployment mode is registry-controlled/reference-only.")
    if tools:
        notes.append("OMH tools are discovered but not directly exposed until Hermes wrapper contracts are added.")
    return OmhRegistry(
        available=bool(skills or tools or hooks),
        source_path=str(source),
        head_sha=head_sha,
        default_branch=branch,
        plugin_tools=tools,
        plugin_hooks=hooks,
        roles=roles,
        skills=skills,
        mode="registry_controlled_reference_only",
        integrity_state=integrity,
        notes=tuple(notes),
    )


def omh_status_text() -> str:
    registry = load_omh_registry()
    lines = ["Oh My Hermes deployment status"]
    lines.append(f"available: {str(registry.available).lower()}")
    lines.append(f"mode: {registry.mode}")
    lines.append(f"integrity_state: {registry.integrity_state}")
    lines.append(f"source_path: {registry.source_path}")
    lines.append(f"head_sha: {registry.head_sha or '-'}")
    lines.append(f"branch: {registry.default_branch or '-'}")
    lines.append(f"skills: {len(registry.skills)}")
    if registry.skills:
        lines.append("skill_names: " + ", ".join(skill.name for skill in registry.skills))
    lines.append(f"roles: {len(registry.roles)}")
    if registry.roles:
        lines.append("role_names: " + ", ".join(registry.roles[:20]))
    lines.append("plugin_tools: " + (", ".join(registry.plugin_tools) or "-"))
    lines.append("plugin_hooks: " + (", ".join(registry.plugin_hooks) or "-"))
    if registry.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in registry.notes)
    return "\n".join(lines)


def omh_capability_records() -> list[dict[str, Any]]:
    registry = load_omh_registry()
    records: list[dict[str, Any]] = []
    for skill in registry.skills:
        records.append(
            {
                "source": "oh-my-hermes",
                "name": skill.name,
                "local_path": skill.local_path,
                "summary": skill.summary,
                "capability_tags": list(skill.capability_tags),
                "mode": registry.mode,
                "parallel_safe": "unknown_until_runtime_observed",
                "side_effects": "prompt/reference only unless plugin hooks/tools are explicitly enabled",
            }
        )
    return records
