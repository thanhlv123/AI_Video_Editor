"""Read-only render readiness gate for automated Creator Studio exports.

This runs after timeline assembly and before the FFmpeg backend. It keeps
missing-media diagnostics actionable and prevents needless render attempts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from creator_studio.timeline_preflight import inspect_timeline


class RenderReadinessError(RuntimeError):
    """The timeline is not ready to render; no export was attempted."""


def require_render_ready(
    timeline_manifest_path: str | Path,
    project_root: str | Path,
) -> dict[str, Any]:
    """Validate the timeline without changing files or creating an export.

    Warnings (for example external media references) are not fatal.
    """
    report = inspect_timeline(
        Path(timeline_manifest_path),
        Path(project_root),
    )
    if report.get("status") == "ready":
        return report

    errors = [
        item
        for item in report.get("issues", ())
        if isinstance(item, dict) and item.get("severity") == "error"
    ]
    if not errors:
        raise RenderReadinessError(
            "Kiểm tra trước khi xuất video không đạt. "
            "Hãy tạo lại timeline và kiểm tra tư liệu."
        )

    details = []
    for item in errors[:5]:
        code = str(item.get("code") or "unknown_error")
        message = str(item.get("message") or "Render input is invalid.")
        action = str(item.get("action") or "").strip()
        details.append(
            f"{code}: {message}" + (f" Cách xử lý: {action}" if action else "")
        )
    remaining = len(errors) - len(details)
    if remaining:
        details.append(f"... và {remaining} lỗi khác.")

    raise RenderReadinessError(
        "Không thể xuất video vì dữ liệu chưa sẵn sàng:\n"
        + "\n".join(details)
    )
