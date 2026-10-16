"""Read-only discovery of completed MP4 exports belonging to one project."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CompletedExport:
    output_path: Path
    manifest_path: Path


def find_completed_exports(project_root, limit=100) -> list[CompletedExport]:
    """Return newest completed exports without following project-run symlinks."""
    root = Path(project_root).expanduser().resolve()
    work = root / "work" / "automation"
    outputs = root / "exports"
    if (
        not work.is_dir() or not outputs.is_dir()
        or work.is_symlink() or outputs.is_symlink()
    ):
        return []

    entries: list[tuple[int, str, CompletedExport]] = []
    for manifest in work.glob("run_*/render_export_manifest*.json"):
        if manifest.is_symlink() or manifest.parent.is_symlink():
            continue
        try:
            if not manifest.is_file():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("status") != "completed":
                continue
            raw = Path(data["output_path"])
            if not raw.is_absolute() or raw.is_symlink():
                continue
            video = raw.resolve(strict=True)
            if (
                not video.is_file() or video.suffix.lower() != ".mp4"
                or video.stat().st_size <= 0
                or not video.parent.samefile(outputs)
            ):
                continue
            modified = manifest.stat().st_mtime_ns
            entries.append((modified, manifest.name, CompletedExport(video, manifest.resolve(strict=True))))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue

    entries.sort(key=lambda item: (item[0], item[1]), reverse=True)
    seen: set[Path] = set()
    result: list[CompletedExport] = []
    for _, _, entry in entries:
        if entry.output_path in seen:
            continue
        seen.add(entry.output_path)
        result.append(entry)
        if len(result) >= max(0, limit):
            break
    return result[:max(0, limit)]
