
from __future__ import annotations

from typing import Any

from app.core.job_store import TaskRecord


class ProviderExecutionError(RuntimeError):
    pass


def _dependency_reports(task: TaskRecord) -> list[dict[str, Any]]:
    return list(task.input.get("dependency_reports", []))


def run_fake_provider(task: TaskRecord) -> dict[str, Any]:
    user_text = str(task.input.get("user_text", ""))
    if task.mission == "research.local_places":
        return {
            "ok": True,
            "mission": task.mission,
            "summary": "Provider gia da tra 3 quan cat toc mau quanh dia chi nguoi dung.",
            "places": [
                {"name": "Barber Mau 1", "distance_note": "gan 165 Cau Giay", "source": "fake_provider"},
                {"name": "Hair Studio Mau 2", "distance_note": "khu Cau Giay", "source": "fake_provider"},
                {"name": "Tiem Cat Toc Mau 3", "distance_note": "can kiem chung lai", "source": "fake_provider"},
            ],
            "limitations": ["chưa xác minh giờ mở cửa", "provider thật chưa bật"],
            "user_text": user_text,
        }
    if task.mission == "risk.critic":
        deps = _dependency_reports(task)
        return {
            "ok": True,
            "mission": task.mission,
            "summary": "Critic da kiem tra rui ro: du lieu dia diem la provider gia, chua duoc xac minh thuc dia.",
            "must_disclose": ["chưa xác minh giờ mở cửa", "chưa xác minh tồn tại bằng provider thật"],
            "dependency_count": len(deps),
        }
    if task.mission == "answer.verify":
        deps = _dependency_reports(task)
        return {
            "ok": True,
            "mission": task.mission,
            "summary": "Validator pass co dieu kien: cau tra loi phai ghi ro cac han che nguon.",
            "pass": True,
            "required_notice": "chưa xác minh giờ mở cửa",
            "dependency_count": len(deps),
        }
    if task.mission == "planning.generic":
        return {
            "ok": True,
            "mission": task.mission,
            "summary": "Lead tao plan generic vi case chua co provider cu the.",
            "user_text": user_text,
        }
    if task.mission == "research.question":
        return {
            "ok": True,
            "mission": task.mission,
            "summary": "Research provider gia da tao report nghien cuu mau.",
            "limitations": ["provider web thật chưa chạy trong lát A"],
            "user_text": user_text,
        }
    raise ProviderExecutionError(f"no fake provider for mission {task.mission}")
