"""M127: offline real FFmpeg retry after simulated interrupted export."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.m118_render_acceptance import build_fixture, _probe_video, _write_json
from creator_studio.render_export import RenderExportService


def run_acceptance():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe must be on PATH.")
    with TemporaryDirectory(prefix="m127_recovery_") as tmp:
        root = Path(tmp) / "Dự án sau sự cố"
        timeline = build_fixture(root, ffmpeg)
        old = root / "exports/final_video_001.mp4"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"previous-user-output")
        old_digest = hashlib.sha256(old.read_bytes()).hexdigest()
        stale = timeline.parent / "render_export_manifest.json"
        _write_json(stale, {
            "format": "creator_studio.render_export.v1",
            "status": "rendering",
            "project_root": str(root),
            "output_path": str(old),
            "issues": [],
        })
        result = RenderExportService(
            default_width=320, default_height=180, default_fps=12.0,
        ).export(timeline, root)
        previous = json.loads(stale.read_text(encoding="utf-8"))
        current = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        if previous.get("status") != "failed":
            raise AssertionError("Interrupted manifest was not recovered.")
        if "render_interrupted" not in previous.get("issues", []):
            raise AssertionError("Recovery reason was not persisted.")
        if current.get("status") != "completed":
            raise AssertionError("New export did not complete.")
        if result.output_path.name != "final_video_002.mp4":
            raise AssertionError("Occupied MP4 path was reused.")
        if hashlib.sha256(old.read_bytes()).hexdigest() != old_digest:
            raise AssertionError("Previous output was modified.")
        probe = _probe_video(ffprobe, result.output_path)
        stream_types = {s.get("codec_type") for s in probe.get("streams", [])}
        if not {"video", "audio"}.issubset(stream_types):
            raise AssertionError("New MP4 lacks video or audio.")
        return {"status": "passed", "checks": [
            "stale_manifest_recovered", "old_mp4_preserved",
            "unique_output_filename", "new_manifest_completed",
            "real_ffmpeg_audio_video",
        ]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_acceptance()
        code = 0
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2),
          file=sys.stdout if code == 0 else sys.stderr)
    if args.report:
        _write_json(args.report, result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
