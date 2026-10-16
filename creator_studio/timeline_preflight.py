"""Read-only M120 preflight for M113 timeline manifests before FFmpeg export."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from creator_studio.render_export import RenderExportError, RenderExportService

MAX_MANIFEST_BYTES = 8 * 1024 * 1024


def inspect_timeline(manifest_path: Path, project_root: Path) -> dict:
    """Return actionable render readiness without changing project files."""
    timeline = Path(manifest_path).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()
    issues = []
    references = []

    def issue(code: str, message: str, action: str, *, warning=False):
        issues.append({
            "severity": "warning" if warning else "error",
            "code": code, "message": message, "action": action,
        })

    def result():
        errors = [x for x in issues if x["severity"] == "error"]
        return {
            "format": "creator_studio.timeline_preflight.v1",
            "status": "blocked" if errors else "ready",
            "project_root": str(root),
            "timeline_manifest": str(timeline),
            "references": references,
            "issues": issues,
            "summary": {
                "reference_count": len(references),
                "error_count": len(errors),
                "warning_count": len(issues) - len(errors),
            },
        }

    if not root.is_dir():
        issue("project_missing", "Project directory does not exist.",
              "Select an existing Creator Studio project directory.")
        return result()
    if not timeline.is_file():
        issue("timeline_missing", "Timeline manifest does not exist.",
              "Complete automatic timeline assembly before exporting.")
        return result()
    try:
        if timeline.stat().st_size > MAX_MANIFEST_BYTES:
            issue("timeline_too_large", "Timeline manifest exceeds 8 MiB.",
                  "Inspect the manifest for unexpectedly large content.")
            return result()
        payload = json.loads(timeline.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        issue("invalid_json", f"Cannot read timeline manifest: {type(exc).__name__}.",
              "Regenerate the timeline manifest from Creator Studio.")
        return result()
    if not isinstance(payload, dict):
        issue("invalid_document", "Timeline manifest must be a JSON object.",
              "Regenerate the timeline manifest.")
        return result()

    if payload.get("status") != "ready":
        issue("timeline_not_ready", "Timeline manifest is not marked ready.",
              "Resolve timeline assembly issues before exporting.")
    duration = payload.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        issue("invalid_duration", "Timeline duration must be finite and positive.",
              "Regenerate scene timing and timeline assembly.")

    tracks = payload.get("tracks")
    if not isinstance(tracks, dict):
        issue("invalid_tracks", "Timeline tracks must be an object.",
              "Regenerate the timeline manifest.")
        return result()
    visuals = tracks.get("visuals")
    if not isinstance(visuals, list) or not visuals:
        issue("missing_visuals", "Timeline has no visual clips.",
              "Assign valid visual assets and rebuild the timeline.")
        visuals = []

    def check_ref(role: str, data):
        if not isinstance(data, dict):
            issue("invalid_reference", f"{role} reference must be an object.",
                  "Regenerate the timeline manifest.")
            return
        raw = data.get("path")
        if not isinstance(raw, str) or not raw.strip():
            issue("missing_path", f"{role} has no media path.",
                  "Reassign the missing asset and rebuild the timeline.")
            return
        try:
            path = Path(raw).expanduser()
            resolved = (path if path.is_absolute() else root / path).resolve()
            exists = resolved.is_file()
            size = resolved.stat().st_size if exists else 0
            external = not resolved.is_relative_to(root)
        except (OSError, ValueError) as exc:
            issue("invalid_path", f"{role} has an invalid media path: {type(exc).__name__}.",
                  "Reassign the asset from the project media library.")
            return
        references.append({
            "role": role, "path": raw, "resolved_path": str(resolved),
            "exists": exists, "size_bytes": size,
        })
        if not exists:
            issue("missing_media", f"{role} media file is missing: {raw}",
                  "Restore or reassign this media asset before exporting.")
        elif size <= 0:
            issue("empty_media", f"{role} media file is empty: {raw}",
                  "Replace the empty asset with a valid media file.")
        if external:
            issue("external_media", f"{role} references media outside the project.",
                  "Import the asset into the project for portability.", warning=True)

    for index, clip in enumerate(visuals):
        if not isinstance(clip, dict):
            issue("invalid_clip", f"Visual clip {index + 1} is not an object.",
                  "Rebuild the timeline.")
            continue
        check_ref(f"visual[{index}]", clip.get("asset"))
    check_ref("narration", tracks.get("narration"))
    music = tracks.get("music")
    state = payload.get("music_state")
    included = state.get("included", music is not None) if isinstance(state, dict) else music is not None
    if included:
        check_ref("music", music)

    if not any(x["severity"] == "error" for x in issues):
        try:
            RenderExportService()._prepare_render(manifest=payload, project_root=root)
        except (RenderExportError, ValueError, TypeError, OSError) as exc:
            issue("render_contract", f"Render validation failed: {exc}",
                  "Check source durations, clip timing, media metadata and timeline structure.")
    return result()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only timeline render preflight.")
    parser.add_argument("timeline_manifest", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    report = inspect_timeline(args.timeline_manifest, args.project_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
