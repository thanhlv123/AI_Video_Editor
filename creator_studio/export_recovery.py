"""Reconcile crashed exports while the project export lock is held."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

_NAME = re.compile(r"render_export_manifest(?:_[0-9]{3,})?\.json\Z")


def recover_interrupted_exports(run_directory: str | Path, project_root: str | Path) -> list[Path]:
    directory = Path(run_directory).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()
    if not directory.is_dir():
        return []
    recovered: list[Path] = []
    for path in sorted(directory.glob("render_export_manifest*.json")):
        if path.is_symlink() or not _NAME.fullmatch(path.name):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("format") != "creator_studio.render_export.v1" or data.get("status") != "rendering":
            continue
        try:
            recorded_root = Path(data["project_root"]).expanduser().resolve()
        except (KeyError, TypeError, ValueError, OSError):
            continue
        if recorded_root != root:
            continue
        updated = dict(data)
        updated["status"] = "failed"
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated["error"] = "Previous export was interrupted. Any existing MP4 was preserved."
        issues = data.get("issues")
        issues = list(issues) if isinstance(issues, list) else []
        if "render_interrupted" not in issues:
            issues.append("render_interrupted")
        updated["issues"] = issues
        temp = path.with_name(path.name + ".recovery.tmp")
        try:
            temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(path)
        except OSError:
            continue
        recovered.append(path)
    return recovered
