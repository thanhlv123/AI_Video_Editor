"""M126 offline acceptance: real MP4 passes postcondition; corrupt MP4 fails."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m118_render_acceptance import build_fixture, _write_json


def run_acceptance() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe must be on PATH.")
    from creator_studio.output_integrity import (
        OutputIntegrityError, verify_rendered_output,
    )
    from creator_studio.render_export import RenderExportService

    with TemporaryDirectory(prefix="m126_integrity_") as directory:
        root = Path(directory) / "Dự án kiểm tra"
        timeline = build_fixture(root, ffmpeg)
        service = RenderExportService(
            default_width=320, default_height=180, default_fps=12.0
        )
        if not service.verify_output:
            raise AssertionError("Production export integrity verification is disabled.")
        result = service.export(timeline, root)
        verify_rendered_output(
            result.output_path,
            expected_width=320,
            expected_height=180,
            expected_duration=2.0,
        )

        invalid = root / "exports" / "corrupted_sample.mp4"
        invalid.write_bytes(b"not-a-playable-mp4")
        try:
            verify_rendered_output(
                invalid, expected_width=320,
                expected_height=180, expected_duration=2.0,
            )
        except OutputIntegrityError:
            pass
        else:
            raise AssertionError("Corrupted MP4 unexpectedly passed ffprobe.")

        if not result.output_path.is_file():
            raise AssertionError("Valid export was altered during negative verification.")
        return {
            "status": "passed",
            "checks": [
                "real_ffprobe_postcondition",
                "h264_aac_resolution_duration",
                "corrupted_mp4_rejected",
                "valid_export_preserved",
            ],
            "output": result.output_path.name,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M126 output integrity acceptance.")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_acceptance()
        exit_code = 0
    except Exception as exc:
        report = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        exit_code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2),
          file=sys.stdout if exit_code == 0 else sys.stderr)
    if args.report:
        _write_json(args.report, report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
