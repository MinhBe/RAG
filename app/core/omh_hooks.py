
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.omh_registry import load_omh_registry, omh_status_text
from app.core.settings import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_MARKER_RE = re.compile(r"\[omh-role:([A-Za-z0-9_-]+)\]")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SHELL_METACHAR_RE = re.compile(r"[\n\r;&|`$<>(){}]")
MAX_EVIDENCE_TIMEOUT_SECONDS = 300
MAX_EVIDENCE_OUTPUT_CHARS = 50_000


@dataclass(frozen=True)
class OmhPreLlmResult:
    context: str | None
    user_message: str
    policy_notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OmhToolHookResult:
    allowed: bool
    context: str | None = None
    warnings: tuple[str, ...] = ()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        value = getattr(settings, name.lower(), default)
        return bool(value)
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def hooks_enabled() -> bool:
    return _env_bool("HERMES_OMH_HOOKS_ENABLED", False)


def evidence_enabled() -> bool:
    return _env_bool("HERMES_OMH_EVIDENCE_ENABLED", False)


def _resolve_repo_path(raw: str | None, default: str) -> Path:
    path = Path(raw or default)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def state_dir() -> Path:
    configured = os.environ.get("HERMES_OMH_STATE_DIR") or getattr(settings, "hermes_omh_state_dir", ".omh/state")
    path = _resolve_repo_path(configured, ".omh/state")
    path.mkdir(parents=True, exist_ok=True)
    _seed_dot_omh(path.parent)
    return path


def events_path() -> Path:
    configured = os.environ.get("HERMES_OMH_EVENTS_PATH") or getattr(settings, "hermes_omh_events_path", ".omh/events/hooks.jsonl")
    path = _resolve_repo_path(configured, ".omh/events/hooks.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    _seed_dot_omh(path.parent.parent if path.parent.name == "events" else REPO_ROOT / ".omh")
    return path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _seed_dot_omh(omh_dir: Path) -> None:
    omh_dir.mkdir(parents=True, exist_ok=True)
    readme = omh_dir / "README.md"
    gitignore = omh_dir / ".gitignore"
    if not readme.exists():
        readme.write_text(
            "# Hermes .omh\n\nRuntime state and telemetry for Oh My Hermes integration.\n",
            encoding="utf-8",
        )
    if not gitignore.exists():
        gitignore.write_text(
            "state/\nevents/\nresearch/\n*.tmp.*\n",
            encoding="utf-8",
        )


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _state_file(mode: str) -> Path:
    if not SAFE_NAME_RE.match(mode):
        raise ValueError("mode must match [A-Za-z0-9_-]+")
    return state_dir() / f"{mode}-state.json"


def omh_state_init() -> dict[str, Any]:
    sd = state_dir()
    ep = events_path()
    return {"success": True, "state_dir": str(sd), "events_path": str(ep)}


def omh_state_write(mode: str, data: dict[str, Any]) -> dict[str, Any]:
    path = _state_file(mode)
    payload = {"_meta": {"written_at": _now(), "mode": mode, "schema_version": 1, "written_by": "hermes-omh-hook-bridge"}}
    payload.update({k: v for k, v in data.items() if k != "_meta"})
    _atomic_json(path, payload)
    return {"success": True, "mode": mode, "path": str(path)}


def omh_state_read(mode: str) -> dict[str, Any]:
    path = _state_file(mode)
    if not path.exists():
        return {"exists": False, "mode": mode, "data": {}, "path": str(path)}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"exists": True, "mode": mode, "data": {}, "path": str(path), "error": f"parse_error:{exc}"}
    return {
        "exists": True,
        "mode": raw.get("_meta", {}).get("mode") or mode,
        "data": {k: v for k, v in raw.items() if k != "_meta"},
        "meta": raw.get("_meta", {}),
        "path": str(path),
    }


def omh_state_activate(mode: str, phase: str = "active", goal: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"active": True, "phase": phase, "started_at": _now()}
    if goal:
        data["goal"] = goal[:1000]
    return omh_state_write(mode, data)


def omh_state_cancel(mode: str, reason: str = "user_requested") -> dict[str, Any]:
    current = omh_state_read(mode)
    data = dict(current.get("data") or {})
    data.update(
        {
            "active": False,
            "cancel_requested": True,
            "cancel_reason": reason[:500],
            "cancel_at": _now(),
        }
    )
    return omh_state_write(mode, data)


def list_active_modes() -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    sd = state_dir()
    for path in sorted(sd.glob("*-state.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        data = {k: v for k, v in raw.items() if k != "_meta"}
        if data.get("active"):
            meta = raw.get("_meta", {})
            active.append(
                {
                    "mode": meta.get("mode") or path.stem.removesuffix("-state"),
                    "phase": data.get("phase"),
                    "written_at": meta.get("written_at"),
                    "path": str(path),
                }
            )
    return active


def _role_dir() -> Path:
    registry = load_omh_registry()
    return Path(registry.source_path) / "plugins" / "omh" / "references"


def role_catalog() -> dict[str, Path]:
    root = _role_dir()
    if not root.exists():
        return {}
    return {p.stem.removeprefix("role-"): p for p in sorted(root.glob("role-*.md"))}


def load_role_prompt(role_name: str) -> str | None:
    if not SAFE_NAME_RE.match(role_name):
        return None
    path = role_catalog().get(role_name)
    if not path or not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")[:8000]


def strip_role_markers(text: str) -> str:
    return ROLE_MARKER_RE.sub("", text).strip()


def extract_role_marker(text: str) -> str | None:
    match = ROLE_MARKER_RE.search(text)
    return match.group(1) if match else None


def pre_llm_call(
    *,
    user_message: str,
    is_first_turn: bool,
    assistant_name: str,
    peer_names: tuple[str, ...] = (),
) -> OmhPreLlmResult:
    if not hooks_enabled():
        return OmhPreLlmResult(context=None, user_message=user_message, policy_notes=("omh_hooks_disabled",))
    context_parts: list[str] = []
    warnings: list[str] = []
    notes: list[str] = ["omh_pre_llm_call"]
    role_name = extract_role_marker(user_message)
    if is_first_turn and role_name:
        role_prompt = load_role_prompt(role_name)
        if role_prompt:
            context_parts.append(f"[OMH Role: {role_name}]\n{role_prompt}")
            notes.append(f"omh_role:{role_name}")
        else:
            available = ", ".join(sorted(role_catalog())) or "(none)"
            warning = f"Unknown OMH role '{role_name}'. Available roles: {available}."
            warnings.append(warning)
            context_parts.append(f"[OMH WARNING] {warning}")
    modes = list_active_modes()
    if modes:
        if is_first_turn:
            lines = ["[OMH] Active modes detected. Read state before proceeding:"]
            lines.extend(f"- {m['mode']}: phase={m.get('phase') or '?'}" for m in modes)
            lines.append("Use OMH state context; preserve phase continuity and cancellation awareness.")
        else:
            mode_str = ", ".join(f"{m['mode']}:{m.get('phase') or '?'}" for m in modes)
            lines = [f"[OMH] Active: {mode_str}. Check cancellation/state before continuing."]
        context_parts.append("\n".join(lines))
        notes.append("omh_active_modes")
    record_hook_event(
        "pre_llm_call",
        {
            "assistant_name": assistant_name,
            "peer_names": list(peer_names),
            "role_marker": role_name,
            "context_injected": bool(context_parts),
            "active_mode_count": len(modes),
        },
    )
    return OmhPreLlmResult(
        context="\n\n".join(context_parts) if context_parts else None,
        user_message=strip_role_markers(user_message),
        policy_notes=tuple(notes),
        warnings=tuple(warnings),
    )


def pre_tool_call(*, tool_name: str, tool_input: dict[str, Any] | str | None = None) -> OmhToolHookResult:
    if not hooks_enabled():
        return OmhToolHookResult(allowed=True, warnings=("omh_hooks_disabled",))
    parsed: dict[str, Any] = {}
    if isinstance(tool_input, dict):
        parsed = tool_input
    elif isinstance(tool_input, str) and tool_input.strip():
        try:
            parsed = json.loads(tool_input)
        except json.JSONDecodeError:
            parsed = {"raw": tool_input}
    warnings: list[str] = []
    context: str | None = None
    if tool_name == "delegate_task":
        goal = str(parsed.get("goal") or parsed.get("raw") or "")
        role_name = extract_role_marker(goal)
        if role_name and role_name not in role_catalog():
            available = ", ".join(sorted(role_catalog())) or "(none)"
            context = f"[OMH WARNING] Unknown role '{role_name}' in delegate_task. Available roles: {available}."
            warnings.append(context)
    if tool_name == "omh_gather_evidence" and not evidence_enabled():
        context = "[OMH BLOCKED] omh_gather_evidence is disabled by HERMES_OMH_EVIDENCE_ENABLED."
        warnings.append(context)
        record_hook_event("pre_tool_call", {"tool_name": tool_name, "allowed": False, "reason": "evidence_disabled"})
        return OmhToolHookResult(allowed=False, context=context, warnings=tuple(warnings))
    record_hook_event("pre_tool_call", {"tool_name": tool_name, "allowed": True, "warning_count": len(warnings)})
    return OmhToolHookResult(allowed=True, context=context, warnings=tuple(warnings))


def record_hook_event(event_type: str, payload: dict[str, Any]) -> None:
    if not hooks_enabled() and event_type != "status":
        return
    event = {"ts": _now(), "event_type": event_type, "payload": payload}
    path = events_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def on_session_end(*, session_kind: str, reason: str = "turn_complete", mark_interrupted: bool = False) -> None:
    if not hooks_enabled():
        return
    modes = list_active_modes()
    interrupted_at = _now()
    if mark_interrupted:
        for mode in modes:
            current = omh_state_read(mode["mode"])
            data = dict(current.get("data") or {})
            data["_interrupted_at"] = interrupted_at
            omh_state_write(mode["mode"], data)
    record_hook_event(
        "on_session_end",
        {
            "session_kind": session_kind,
            "reason": reason,
            "mark_interrupted": mark_interrupted,
            "active_modes": [m["mode"] for m in modes],
        },
    )


def _allowlist_prefixes() -> list[str]:
    return [
        "uv run pytest",
        "uv run ruff check",
        "uv run python -m compileall",
        "python -m pytest",
        "python -m mypy",
        "python -m compileall",
        "python3 -m pytest",
        "ruff check",
        "ruff format --check",
        "pytest",
        "npm test",
        "npm run test",
        "npm run build",
        "npm run lint",
        "pnpm test",
        "pnpm build",
        "pnpm lint",
        "cargo test",
        "cargo check",
        "go test",
        "go build",
    ]


def _matches_prefix(tokens: list[str], prefix: str) -> bool:
    prefix_tokens = prefix.split()
    return len(tokens) >= len(prefix_tokens) and tokens[: len(prefix_tokens)] == prefix_tokens


def gather_evidence(commands: list[str], timeout: int = 120, truncate: int = 4000) -> dict[str, Any]:
    hook = pre_tool_call(tool_name="omh_gather_evidence", tool_input={"commands": commands})
    if not hook.allowed:
        return {"error": hook.context or "omh_gather_evidence blocked", "results": [], "all_pass": False}
    timeout = min(max(timeout, 1), MAX_EVIDENCE_TIMEOUT_SECONDS)
    truncate = min(max(truncate, 500), MAX_EVIDENCE_OUTPUT_CHARS)
    if not commands:
        return {"error": "commands list is empty", "results": [], "all_pass": False}
    if len(commands) > 10:
        return {"error": "too many commands", "results": [], "all_pass": False}
    results: list[dict[str, Any]] = []
    for command in commands:
        if SHELL_METACHAR_RE.search(command):
            results.append({"command": command, "passed": False, "exit_code": -1, "output": "Rejected shell metacharacter"})
            continue
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            results.append({"command": command, "passed": False, "exit_code": -1, "output": f"Parse error: {exc}"})
            continue
        if not any(_matches_prefix(tokens, prefix) for prefix in _allowlist_prefixes()):
            results.append({"command": command, "passed": False, "exit_code": -1, "output": "Command not in OMH allowlist"})
            continue
        try:
            proc = subprocess.run(tokens, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, shell=False, check=False)
            combined = (proc.stdout or "") + (proc.stderr or "")
            results.append(
                {
                    "command": command,
                    "passed": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "output": combined[-truncate:],
                    "truncated": len(combined) > truncate,
                }
            )
        except subprocess.TimeoutExpired:
            results.append({"command": command, "passed": False, "exit_code": -1, "output": f"TIMEOUT after {timeout}s"})
        except OSError as exc:
            results.append({"command": command, "passed": False, "exit_code": -1, "output": f"OS error: {exc}"})
    all_pass = bool(results) and all(result.get("passed") for result in results)
    record_hook_event("omh_gather_evidence", {"commands": commands, "all_pass": all_pass})
    return {"results": results, "all_pass": all_pass, "summary": f"{sum(1 for r in results if r.get('passed'))}/{len(results)} passed"}


def omh_runtime_status_text() -> str:
    base = omh_status_text()
    active = list_active_modes() if hooks_enabled() else []
    lines = [base, "", "OMH hook bridge"]
    lines.append(f"hooks_enabled: {str(hooks_enabled()).lower()}")
    lines.append(f"evidence_enabled: {str(evidence_enabled()).lower()}")
    lines.append(f"state_dir: {state_dir()}")
    lines.append(f"events_path: {events_path()}")
    lines.append(f"active_modes: {len(active)}")
    if active:
        lines.append("active_mode_names: " + ", ".join(m["mode"] for m in active))
    return "\n".join(lines)


def _compact_json(data: Any, limit: int = 2400) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text if len(text) <= limit else text[:limit] + "\n...truncated"


def handle_omh_command(command: str) -> str:
    normalized = command.strip()
    parts = normalized.split()
    if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() == "status"):
        record_hook_event("status", {"source": "telegram_command"})
        return omh_runtime_status_text()
    sub = parts[1].lower()
    if sub == "init":
        return _compact_json(omh_state_init())
    if sub == "roles":
        return "OMH roles:\n" + ", ".join(sorted(role_catalog()))
    if sub == "role":
        if len(parts) < 3:
            return "Usage: /omh role <role-name>"
        prompt = load_role_prompt(parts[2])
        return prompt[:2800] if prompt else f"Unknown role: {parts[2]}"
    if sub in {"mode", "activate"}:
        if len(parts) < 3:
            return "Usage: /omh mode <mode> [phase] [goal...]"
        mode = parts[2]
        phase = parts[3] if len(parts) >= 4 else "active"
        goal = " ".join(parts[4:]) if len(parts) >= 5 else None
        return _compact_json(omh_state_activate(mode, phase=phase, goal=goal))
    if sub == "read":
        if len(parts) < 3:
            return "Usage: /omh read <mode>"
        return _compact_json(omh_state_read(parts[2]))
    if sub == "cancel":
        if len(parts) < 3:
            return "Usage: /omh cancel <mode> [reason]"
        reason = " ".join(parts[3:]) if len(parts) >= 4 else "user_requested"
        return _compact_json(omh_state_cancel(parts[2], reason=reason))
    if sub == "evidence":
        if len(parts) < 3:
            return "Usage: /omh evidence <allowlisted command>"
        result = gather_evidence([" ".join(parts[2:])])
        return _compact_json(result, limit=3200)
    return "Unknown /omh subcommand. Use: /omh status|init|roles|role|mode|read|cancel|evidence"
