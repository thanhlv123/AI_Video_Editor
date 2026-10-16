M117 - PRODUCTION LAUNCHER AND GUI STARTUP READINESS
==================================================

The stable launch entry point now loads gui_creator_studio_m114.py, which
contains the complete Creator Studio automation and render/export GUI.
The original gui_creator_studio.py classes remain importable for older tests;
direct execution delegates to the same production launcher.

Windows launch:
    Double-click start_creator_studio.cmd
    Or: python run_creator_studio.py

Prerequisite check (no GUI or network requests):
    python run_creator_studio.py --check

Offscreen GUI startup smoke test (no event loop or provider API calls):
    python run_creator_studio.py --smoke

Required runtime: Python 3.12+, PyQt6 Widgets, FFmpeg on PATH. A real
production GUI smoke test also checks that automation, project, voice,
scene, media, timeline and export pages can be constructed.

M117 does not automatically install dependencies, download media, connect
to external providers, or write into a user project. This launcher is not
a guarantee that provider credentials, local TTS services, GPU drivers,
or all user media inputs are functional. Those require separate runtime
validation.

GitHub Actions runs the launcher prerequisite check and GUI smoke on
Windows before the full automatic regression suite.
