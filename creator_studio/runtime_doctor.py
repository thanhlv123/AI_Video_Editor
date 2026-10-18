"""Read-only local runtime diagnosis for production Creator Studio."""
from __future__ import annotations
import importlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
CREDENTIAL_NAMES = ("PEXELS_API_KEY", "PIXABAY_API_KEY", "YOUTUBE_API_KEY", "KIE_API_KEY", "OPENAI_API_KEY")

def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False

def _encoders(ffmpeg_path: str) -> tuple[bool, bool, str]:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, False, type(exc).__name__
    if result.returncode:
        return False, False, f"ffmpeg returned exit code {result.returncode}"
    output = result.stdout + "\n" + result.stderr
    h264 = bool(re.search(r"(?m)^\s*V\S*\s+libx264(?:\s|$)", output))
    aac = bool(re.search(r"(?m)^\s*A\S*\s+aac(?:\s|$)", output))
    return h264, aac, "encoders inspected"

def diagnose(*, project_root: Path | None = None, environ: Mapping[str, str] | None = None) -> dict:
    """Inspect required runtime and optional integrations without writes."""
    env = os.environ if environ is None else environ
    checks: list[dict] = []

    def add(name: str, required: bool, ok: bool, detail: str, action: str = "") -> None:
        checks.append({"name": name, "required": required, "ok": bool(ok),
                       "detail": detail, "action": action if not ok else ""})

    add("python_3_12", True, sys.version_info >= (3, 12),
        f"Python {sys.version_info.major}.{sys.version_info.minor}", "Install Python 3.12 or newer.")
    widgets = _module_available("PyQt6.QtWidgets")
    add("pyqt6_widgets", True, widgets, "Qt Widgets available" if widgets else "Qt Widgets unavailable",
        "Install PyQt6 in the Python environment used to launch Creator Studio.")
    faster_whisper = _module_available("faster_whisper")
    add(
        "faster_whisper",
        True,
        faster_whisper,
        "faster-whisper available" if faster_whisper else "faster-whisper unavailable",
        "Install runtime dependencies with setup_creator_studio.cmd.",
    )
    multimedia = _module_available("PyQt6.QtMultimedia")
    add("pyqt6_multimedia", False, multimedia,
        "Qt Multimedia available" if multimedia else "Audio/video preview may be unavailable",
        "Install a compatible PyQt6 multimedia package.")
    gui_present = (ROOT / "gui_creator_studio_m114.py").is_file()
    add("production_gui", True, gui_present,
        "Production GUI source present" if gui_present else "Production GUI source missing",
        "Restore gui_creator_studio_m114.py from the project repository.")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    add("ffmpeg", True, bool(ffmpeg), "FFmpeg found" if ffmpeg else "FFmpeg not found on PATH",
        "Install FFmpeg and add its bin folder to PATH.")
    add("ffprobe", True, bool(ffprobe), "ffprobe found" if ffprobe else "ffprobe not found on PATH",
        "Install FFmpeg including ffprobe and add its bin folder to PATH.")
    h264, aac, note = _encoders(ffmpeg) if ffmpeg else (False, False, "FFmpeg unavailable")
    add("h264_encoder", True, h264, "libx264 available" if h264 else f"libx264 unavailable ({note})",
        "Use an FFmpeg build with libx264.")
    add("aac_encoder", True, aac, "AAC available" if aac else f"AAC unavailable ({note})",
        "Use an FFmpeg build with AAC encoding support.")

    piper = ROOT / "runtime" / "piper"
    piper_exe = any((piper / name / "Scripts" / "python.exe").is_file() for name in (".venv", "venv"))
    voices = piper / "voices"
    piper_ready = piper_exe and voices.is_dir() and any(voices.rglob("*.onnx"))
    add("piper_local", False, piper_ready,
        "Piper runtime and voice model found" if piper_ready else "Piper Local not configured",
        "Configure Piper Local and import an ONNX voice model if offline TTS is needed.")

    # Report only how many environment variables are configured; never their values.
    count = sum(bool(env.get(name, "").strip()) for name in CREDENTIAL_NAMES)
    add("provider_environment", False, count > 0,
        f"{count} of {len(CREDENTIAL_NAMES)} provider environment variables set (keyring not inspected)",
        "Configure desired providers in Creator Studio settings.")
    if project_root is not None:
        exists = Path(project_root).expanduser().is_dir()
        add("project_directory", True, exists,
            "Selected project directory exists" if exists else "Selected project directory missing",
            "Select an existing project directory. No files were changed.")

    failures = [item["name"] for item in checks if item["required"] and not item["ok"]]
    warnings = [item["name"] for item in checks if not item["required"] and not item["ok"]]
    return {"format": "creator_studio.runtime_doctor.v1",
            "status": "ready" if not failures else "blocked",
            "required_failures": failures, "optional_warnings": warnings, "checks": checks}
