"""M131 Windows bootstrap: explicit, non-destructive local venv setup.

No network, installs, or project writes occur in --check mode.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_IMPORTS = (
    "PyQt6.QtWidgets", "requests", "PIL", "docx",
    "keyring", "numpy", "psutil", "aiohttp", "faster_whisper",
)


def environment_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def probe_runtime_packages(executable: Path) -> bool:
    imports = "; ".join(f"import {name}" for name in RUNTIME_IMPORTS)
    try:
        completed = subprocess.run(
            [str(executable), "-c", imports],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=25, check=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def inspect_environment(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    environment = root / ".venv"
    python = environment_python(root)
    valid_environment = (
        environment.is_dir() and not environment.is_symlink()
        and python.is_file() and not python.is_symlink()
    )
    packages = probe_runtime_packages(python) if valid_environment else False
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    checks = {
        "python_3_12_or_newer": sys.version_info >= (3, 12),
        "local_environment": valid_environment,
        "runtime_packages": packages,
        "ffmpeg": bool(ffmpeg),
        "ffprobe": bool(ffprobe),
    }
    return {
        "format": "creator_studio.bootstrap.v1",
        "status": "ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "python": str(python),
        "next_steps": [
            "Run setup_creator_studio.cmd to install local Python dependencies."
            if not valid_environment or not packages else "",
            "Install FFmpeg with ffprobe and add its bin directory to PATH."
            if not ffmpeg or not ffprobe else "",
        ],
    }


def install_environment(root: Path = ROOT) -> int:
    root = Path(root).resolve()
    environment = root / ".venv"
    python = environment_python(root)
    requirements = root / "requirements-runtime.txt"
    if sys.version_info < (3, 12):
        print("Python 3.12 or newer is required.", file=sys.stderr)
        return 1
    if not requirements.is_file():
        print("Runtime requirements file is missing.", file=sys.stderr)
        return 1
    if environment.is_symlink() or python.is_symlink():
        print("Refusing to modify a linked Python environment.", file=sys.stderr)
        return 1
    if environment.exists() and not python.is_file():
        print("Existing .venv is incomplete; refusing to overwrite it.", file=sys.stderr)
        return 1
    if not environment.exists():
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(environment)],
            cwd=root, check=False,
        )
        if result.returncode:
            return result.returncode
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "--no-input", "-r", str(requirements)],
        cwd=root, check=False,
    )
    return result.returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Set up local Creator Studio runtime.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Read-only readiness report.")
    action.add_argument("--install", action="store_true", help="Create/update local .venv.")
    args = parser.parse_args(argv)

    if args.install:
        code = install_environment()
        if code:
            return code
    report = inspect_environment()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
