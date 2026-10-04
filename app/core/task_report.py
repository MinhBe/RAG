from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALID_STATUS = {"ok", "partial", "failed"}


@dataclass(frozen=True)
class ReportValidationResult:
    ok: bool
    errors: tuple[str, ...]
    report: dict[str, Any] | None = None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def validate_task_report(payload: Any) -> ReportValidationResult:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ReportValidationResult(False, ("report must be object",), None)
    status = payload.get("status")
    if status not in VALID_STATUS:
        errors.append("status must be ok|partial|failed")
    if not isinstance(payload.get("summary"), str):
        errors.append("summary must be string")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be list")
    else:
        for idx, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"findings[{idx}] must be object")
                continue
            if not isinstance(finding.get("claim"), str):
                errors.append(f"findings[{idx}].claim must be string")
            urls = finding.get("source_urls")
            if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
                errors.append(f"findings[{idx}].source_urls must be list[str]")
            confidence = finding.get("confidence")
            if not _is_number(confidence) or not (0 <= float(confidence) <= 1):
                errors.append(f"findings[{idx}].confidence must be number in [0,1]")
    if not isinstance(payload.get("gaps"), list):
        errors.append("gaps must be list")
    skill_applied = payload.get("skill_applied")
    if not isinstance(skill_applied, dict):
        errors.append("skill_applied must be object")
    else:
        if not isinstance(skill_applied.get("ref"), str):
            errors.append("skill_applied.ref must be string")
        if not str(skill_applied.get("hash", "")).startswith("sha256:"):
            errors.append("skill_applied.hash must be sha256")
    tools_called = payload.get("tools_called")
    if not isinstance(tools_called, list):
        errors.append("tools_called must be list")
    else:
        for idx, tool in enumerate(tools_called):
            if not isinstance(tool, dict):
                errors.append(f"tools_called[{idx}] must be object")
                continue
            if not isinstance(tool.get("name"), str):
                errors.append(f"tools_called[{idx}].name must be string")
            if not _is_number(tool.get("ms")):
                errors.append(f"tools_called[{idx}].ms must be number")
            if not isinstance(tool.get("bytes"), int):
                errors.append(f"tools_called[{idx}].bytes must be integer")
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        errors.append("usage must be object")
    else:
        if not isinstance(usage.get("llm_calls"), int):
            errors.append("usage.llm_calls must be integer")
        if not isinstance(usage.get("tokens"), int):
            errors.append("usage.tokens must be integer")
        if not _is_number(usage.get("ms")):
            errors.append("usage.ms must be number")
    return ReportValidationResult(not errors, tuple(errors), payload if not errors else None)


def source_urls_in_report(report: dict[str, Any]) -> set[str]:
    urls: set[str] = set()
    for finding in report.get("findings", []) or []:
        for url in finding.get("source_urls", []) or []:
            if isinstance(url, str):
                urls.add(url)
    return urls


def check_traceable_sources(report: dict[str, Any], observed_urls: set[str]) -> list[str]:
    errors: list[str] = []
    for url in sorted(source_urls_in_report(report)):
        if url not in observed_urls:
            errors.append(f"source not traceable to this task's tool output: {url}")
    return errors
