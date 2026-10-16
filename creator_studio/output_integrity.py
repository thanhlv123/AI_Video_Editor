"""Validate the actual MP4 streams before a production export is accepted.

FFprobe is run with an argument list (never a shell command) and a timeout.
This module only reads the output; callers own manifest state and cleanup.
"""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
import shutil
import subprocess


class OutputIntegrityError(RuntimeError):
    """The rendered MP4 is missing or does not match its timeline contract."""


def verify_rendered_output(
    output_path: str | Path,
    *,
    expected_width: int,
    expected_height: int,
    expected_duration: float,
    require_audio: bool = True,
    ffprobe: str | None = None,
) -> dict:
    """Return ffprobe metadata or reject a damaged/incomplete MP4."""
    path = Path(output_path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise OutputIntegrityError("Rendered MP4 is missing or empty.")

    probe_executable = ffprobe or shutil.which("ffprobe")
    if not probe_executable:
        raise OutputIntegrityError(
            "ffprobe is required to verify exported video. Install FFmpeg with ffprobe."
        )

    command = [
        probe_executable,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OutputIntegrityError(
            f"Unable to inspect rendered MP4: {type(exc).__name__}."
        ) from exc

    if result.returncode != 0:
        raise OutputIntegrityError(
            "ffprobe could not decode the rendered MP4 container."
        )
    try:
        metadata = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise OutputIntegrityError("ffprobe returned invalid JSON.") from exc
    if not isinstance(metadata, dict):
        raise OutputIntegrityError("ffprobe returned an invalid media document.")

    streams = metadata.get("streams")
    if not isinstance(streams, list):
        raise OutputIntegrityError("Rendered MP4 has no valid stream list.")
    video = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"),
        None,
    )
    audio = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
        None,
    )
    if not video or video.get("codec_name") != "h264":
        raise OutputIntegrityError("Rendered MP4 is missing its H.264 video stream.")
    if (video.get("width"), video.get("height")) != (
        int(expected_width), int(expected_height)
    ):
        raise OutputIntegrityError("Rendered MP4 resolution does not match the project.")
    if require_audio and (not audio or audio.get("codec_name") != "aac"):
        raise OutputIntegrityError("Rendered MP4 is missing its AAC audio stream.")

    format_data = metadata.get("format")
    if not isinstance(format_data, dict):
        raise OutputIntegrityError("Rendered MP4 has no duration metadata.")
    try:
        duration = float(format_data.get("duration"))
        expected = float(expected_duration)
    except (TypeError, ValueError) as exc:
        raise OutputIntegrityError("Rendered MP4 duration is invalid.") from exc
    if not isfinite(duration) or duration <= 0 or not isfinite(expected) or expected <= 0:
        raise OutputIntegrityError("Rendered MP4 duration is invalid.")
    tolerance = max(0.5, expected * 0.1)
    if abs(duration - expected) > tolerance:
        raise OutputIntegrityError(
            f"Rendered MP4 duration differs from timeline: {duration:.2f}s vs {expected:.2f}s."
        )
    return metadata
