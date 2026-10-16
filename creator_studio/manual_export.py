"""Find finished M113 timelines for manual export."""
from __future__ import annotations
import json
from pathlib import Path
from creator_studio.timeline_assembly import TIMELINE_FILENAME, TIMELINE_FORMAT

def find_ready_timelines(project_root: str | Path) -> list[Path]:
    root = Path(project_root).expanduser().resolve()
    automation = root / "work" / "automation"
    if not automation.is_dir() or automation.is_symlink():
        return []
    found: list[tuple[int, str, Path]] = []
    for path in automation.glob("run_*/" + TIMELINE_FILENAME):
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            continue
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(automation):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != TIMELINE_FORMAT or data.get("status") != "ready":
                continue
            modified = path.stat().st_mtime_ns
        except (OSError, UnicodeError, ValueError):
            continue
        found.append((modified, path.parent.name, resolved))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in found]
