"""M117 canonical, dependency-light Creator Studio entry point.

Keep GUI imports lazy so --check can diagnose a broken Python/Qt installation.
Do not launch providers, contact the network, or mutate project data here.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


GUI_MODULE = "gui_creator_studio_m114"
GUI_FILENAME = GUI_MODULE + ".py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def inspect_runtime() -> dict:
    """Report startup prerequisites without importing the application GUI."""
    try:
        qt_found = importlib.util.find_spec("PyQt6.QtWidgets") is not None
    except (ImportError, ValueError, AttributeError):
        qt_found = False

    ffmpeg_path = shutil.which("ffmpeg")
    checks = {
        "python_3_12_or_newer": sys.version_info >= (3, 12),
        "pyqt6_widgets": qt_found,
        "ffmpeg_on_path": bool(ffmpeg_path),
        "production_gui_present": (PROJECT_ROOT / GUI_FILENAME).is_file(),
    }
    return {
        "status": "ready" if all(checks.values()) else "blocked",
        "gui_module": GUI_MODULE,
        "python": sys.version.split()[0],
        "checks": checks,
        "ffmpeg_path": ffmpeg_path,
    }


def smoke_gui() -> dict:
    """Construct the real production window without entering the event loop."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    gui = importlib.import_module(GUI_MODULE)
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication([])

    window = None
    try:
        window = gui.CreatorStudioWindow()
        pages = getattr(window, "page_indexes", {})
        required_pages = {"automation", "project", "voice", "scenes", "media", "timeline", "export"}
        missing = sorted(required_pages.difference(pages))
        if missing:
            raise RuntimeError("Missing production GUI pages: " + ", ".join(missing))
        if not hasattr(window, "render_export_worker"):
            raise RuntimeError("Render/export integration is missing from the GUI")
        if not hasattr(window, "automation_page"):
            raise RuntimeError("Automation workspace is missing from the GUI")
        return {
            "status": "passed",
            "gui_module": GUI_MODULE,
            "pages": sorted(pages),
            "window_created": True,
        }
    finally:
        if window is not None:
            window.close()
            window.deleteLater()
        if owns_app and app is not None:
            app.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the latest production Creator Studio GUI.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Print a JSON prerequisite report.")
    group.add_argument("--smoke", action="store_true", help="Instantiate the GUI without showing it.")
    group.add_argument("--doctor", action="store_true", help="Diagnose local render and GUI readiness.")
    args = parser.parse_args(argv)

    if args.doctor:
        from creator_studio.runtime_doctor import diagnose
        report = diagnose()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "ready" else 1

    if args.check:
        report = inspect_runtime()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "ready" else 1

    if args.smoke:
        report = inspect_runtime()
        if report["status"] != "ready":
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1
        try:
            result = smoke_gui()
        except Exception as exc:
            print(
                json.dumps(
                    {"status": "failed", "gui_module": GUI_MODULE,
                     "error": f"{type(exc).__name__}: {exc}"},
                    ensure_ascii=False, indent=2,
                ),
                file=sys.stderr,
            )
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    try:
        gui = importlib.import_module(GUI_MODULE)
    except (ImportError, OSError) as exc:
        print(
            f"Creator Studio could not import {GUI_MODULE}: {type(exc).__name__}: {exc}\n"
            "Run: python run_creator_studio.py --check",
            file=sys.stderr,
        )
        return 1

    # gui.main() owns the QApplication and its event loop. It may raise
    # SystemExit with the Qt exit code; do not swallow that exit status.
    result = gui.main()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
