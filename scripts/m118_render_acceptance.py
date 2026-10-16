"""M118 offline acceptance: real FFmpeg MP4 from a Creator Studio timeline.

Synthetic inputs only. Never uses provider credentials or a user's project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


# Support both `python -m scripts.m118_render_acceptance` and direct
# `python scripts/m118_render_acceptance.py` on Windows.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run_command(command: list[str], *, timeout: int = 60) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {Path(command[0]).name}; "
            f"{completed.stderr[-1600:]}"
        )
    return completed.stdout


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_manifest() -> dict:
    """A minimal ready M113 manifest with narration, two visuals and music."""
    visuals = []
    for index, color in enumerate(("blue", "green")):
        start = float(index)
        end = start + 1.0
        visuals.append({
            "clip_id": f"visual_{index + 1:04d}",
            "kind": "scene",
            "scene_id": f"scene_{index + 1:03d}",
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": 1.0,
            "asset": {
                "asset_id": f"video_{index + 1}",
                "media_type": "video",
                "path": f"assets/videos/downloaded/{color}.mp4",
                "duration_seconds": 1.25,
                "width": 320,
                "height": 180,
                "origin": "downloaded",
            },
            "operation": {
                "mode": "trim",
                "source_in_seconds": 0.0,
                "source_out_seconds": 1.0,
                "playback_rate": 1.0,
                "loop": False,
                "speed_change": False,
            },
            "fit": {"mode": "cover", "position": "center"},
        })

    return {
        "format": "creator_studio.automatic_timeline.v1",
        "status": "ready",
        "duration_seconds": 2.0,
        "summary": {
            "scene_count": 2,
            "visual_clip_count": 2,
            "gap_fill_count": 0,
            "music_included": True,
            "unresolved_count": 0,
        },
        "source": {},
        "tracks": {
            "narration": {
                "asset_id": "voice_test",
                "path": "assets/voice/generated/narration.wav",
                "start_seconds": 0.0,
                "end_seconds": 2.0,
                "timeline_duration_seconds": 2.0,
                "source_duration_seconds": 2.0,
                "gain_db": 0.0,
                "primary": True,
                "time_stretch": False,
            },
            "visuals": visuals,
            "music": {
                "path": "assets/music/imported/bed.wav",
                "start_seconds": 0.0,
                "end_seconds": 2.0,
                "target_duration_seconds": 2.0,
                "source_duration_seconds": 2.0,
                "operation": {
                    "loop_required": False,
                    "trim_to_target": True,
                    "playback_rate": 1.0,
                },
                "mix": {
                    "gain_db": -24.0,
                    "fade_in_seconds": 0.2,
                    "fade_out_seconds": 0.2,
                    "ducking_enabled": True,
                    "ducking_reduction_db": 6.0,
                    "voice_is_primary": True,
                },
            },
        },
        "music_state": {"status": "selected", "included": True},
        "policy": {},
        "issues": [],
    }


def build_fixture(root: Path, ffmpeg: str) -> Path:
    """Generate tiny, valid local media under a disposable Unicode project."""
    root.mkdir(parents=True, exist_ok=True)
    for color in ("blue", "green"):
        video = root / f"assets/videos/downloaded/{color}.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        _run_command([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x180:r=12:d=1.25",
            "-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p",
            str(video),
        ])

    for frequency, relative in (
        (440, "assets/voice/generated/narration.wav"),
        (220, "assets/music/imported/bed.wav"),
    ):
        audio = root / relative
        audio.parent.mkdir(parents=True, exist_ok=True)
        _run_command([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=2",
            "-c:a", "pcm_s16le", str(audio),
        ])

    return _write_json(
        root / "work/automation/run_acceptance/timeline_manifest.json",
        build_manifest(),
    )


def _probe_video(ffprobe: str, path: Path) -> dict:
    output = _run_command([
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of", "json", str(path),
    ])
    return json.loads(output)


def run_acceptance() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe must both be available on PATH.")

    from creator_studio.render_export import RenderExportService

    with TemporaryDirectory(prefix="m118_render_acceptance_") as temp:
        root = Path(temp) / "Dự án thử nghiệm"
        timeline = build_fixture(root, ffmpeg)
        service = RenderExportService(
            default_width=320,
            default_height=180,
            default_fps=12.0,
        )
        phases = []
        first = service.export(
            timeline_manifest_path=timeline,
            project_root=root,
            progress_callback=lambda event: phases.append(event.phase),
        )
        if not first.output_path.is_file() or not first.manifest_path.is_file():
            raise AssertionError("Render/export did not produce MP4 and manifest.")
        original_digest = hashlib.sha256(first.output_path.read_bytes()).hexdigest()

        second = service.export(timeline_manifest_path=timeline, project_root=root)
        if first.output_path == second.output_path:
            raise AssertionError("Repeated export overwrote the original output.")
        if hashlib.sha256(first.output_path.read_bytes()).hexdigest() != original_digest:
            raise AssertionError("Repeated export modified the original MP4.")

        probe = _probe_video(ffprobe, first.output_path)
        streams = probe.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        duration = float(probe.get("format", {}).get("duration", 0.0))
        if not video or video.get("width") != 320 or video.get("height") != 180:
            raise AssertionError(f"Unexpected video stream: {video}")
        if not audio:
            raise AssertionError("The rendered MP4 is missing an audio stream.")
        if not (1.5 <= duration <= 3.5):
            raise AssertionError(f"Unexpected MP4 duration: {duration}")
        if "rendering" not in phases:
            raise AssertionError(f"Render progress did not report encoding: {phases}")

        return {
            "status": "passed",
            "checks": [
                "unicode_project_path",
                "m113_timeline_manifest",
                "real_ffmpeg_video_and_audio",
                "ffprobe_duration_resolution",
                "export_manifest",
                "non_overwriting_repeat_export",
                "render_progress",
            ],
            "duration_seconds": duration,
            "resolution": "320x180",
            "output_names": [first.output_path.name, second.output_path.name],
            "first_mp4_bytes": first.output_path.stat().st_size,
            "second_mp4_bytes": second.output_path.stat().st_size,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run real, offline M118 render acceptance.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    args = parser.parse_args(argv)
    try:
        result = run_acceptance()
        code = 0
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        code = 1

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="", file=sys.stdout if code == 0 else sys.stderr)
    if args.report:
        _write_json(args.report, result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
