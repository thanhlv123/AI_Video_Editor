"""M125: real FFmpeg failure/cancel/retry in a disposable offline project."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m118_render_acceptance import build_fixture, _probe_video, _write_json


def run_acceptance() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe must be available on PATH.")

    from creator_studio.render_backend import RenderBackendCancelled
    from creator_studio.render_export import RenderExportError, RenderExportService

    with TemporaryDirectory(prefix="m125_failure_recovery_") as temporary:
        root = Path(temporary) / "Dự án phục hồi"
        timeline = build_fixture(root, ffmpeg)
        service = RenderExportService(
            default_width=320, default_height=180, default_fps=12.0
        )
        first = service.export(timeline, root)
        first_digest = hashlib.sha256(first.output_path.read_bytes()).hexdigest()
        next_output = root / "exports" / "final_video_002.mp4"

        source_video = root / "assets/videos/downloaded/green.mp4"
        original_media = source_video.read_bytes()
        source_video.write_bytes(b"invalid-video-data")

        try:
            service.export(timeline, root)
        except RenderExportError:
            pass
        else:
            raise AssertionError("Corrupted source media unexpectedly rendered.")

        failed_manifest = timeline.parent / "render_export_manifest_002.json"
        if not failed_manifest.is_file():
            raise AssertionError("Failure did not persist an export manifest.")
        failed = json.loads(failed_manifest.read_text(encoding="utf-8"))
        if failed.get("status") != "failed" or not failed.get("error"):
            raise AssertionError("Corrupted media was not reported as failed.")
        if next_output.exists():
            raise AssertionError("Failed render left a partial MP4 output.")

        source_video.write_bytes(original_media)

        def cancel_at_prepared(progress):
            if progress.phase == "prepared":
                raise RenderBackendCancelled("Cancelled during preparation.")

        try:
            service.export(timeline, root, progress_callback=cancel_at_prepared)
        except RenderBackendCancelled:
            pass
        else:
            raise AssertionError("Prepared callback cancellation was ignored.")

        cancelled_manifest = timeline.parent / "render_export_manifest_003.json"
        if not cancelled_manifest.is_file():
            raise AssertionError("Cancellation did not persist an export manifest.")
        cancelled = json.loads(cancelled_manifest.read_text(encoding="utf-8"))
        if cancelled.get("status") != "cancelled":
            raise AssertionError("Cancellation did not produce cancelled status.")
        if next_output.exists():
            raise AssertionError("Cancelled render left a partial MP4 output.")

        recovered = service.export(timeline, root)
        if recovered.output_path != next_output:
            raise AssertionError("Retry did not reuse the next safe output filename.")
        if hashlib.sha256(first.output_path.read_bytes()).hexdigest() != first_digest:
            raise AssertionError("Failure/retry modified a previous successful MP4.")

        probe = _probe_video(ffprobe, recovered.output_path)
        streams = probe.get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in streams):
            raise AssertionError("Recovered MP4 has no video stream.")
        if not any(stream.get("codec_type") == "audio" for stream in streams):
            raise AssertionError("Recovered MP4 has no audio stream.")

        return {
            "status": "passed",
            "checks": [
                "corrupted_source_failure",
                "failed_manifest_persisted",
                "partial_mp4_cleanup",
                "prepared_callback_cancel",
                "cancelled_manifest_persisted",
                "safe_retry_after_failure",
                "previous_export_preserved",
                "recovered_mp4_audio_video",
            ],
            "first_output": first.output_path.name,
            "recovered_output": recovered.output_path.name,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M125 FFmpeg failure recovery.")
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
