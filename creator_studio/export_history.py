"""Read-only list of successful Creator Studio video exports."""
from dataclasses import dataclass
from pathlib import Path
import json

@dataclass(frozen=True)
class CompletedExport:
    output_path: Path
    manifest_path: Path

def find_completed_exports(project_root, limit=100):
    root = Path(project_root).resolve()
    work = root / "work" / "automation"
    outputs = root / "exports"
    if not work.is_dir() or not outputs.is_dir():
        return []
    entries = []
    for manifest in work.glob("run_*/render_export_manifest*.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("status") != "completed":
                continue
            video = Path(data["output_path"]).resolve()
            if video.parent == outputs and video.is_file() and video.stat().st_size:
                entries.append(CompletedExport(video, manifest))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return entries[:limit]
