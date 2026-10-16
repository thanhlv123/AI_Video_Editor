M119 - RUNTIME DOCTOR
=====================

Windows:
    start_creator_studio.cmd --doctor

Python:
    python run_creator_studio.py --doctor

This command checks local Python 3.12, PyQt6, production GUI source,
FFmpeg, ffprobe, libx264 and AAC encoding support. It also reports
optional Qt Multimedia and Piper Local readiness.

The command prints a JSON report. Exit code 0 means all required
local checks passed; exit code 1 means a required check failed.
Each failed check includes an action that can resolve the problem.

The diagnostic is read-only. It does not start the GUI or call
external services. It does not verify online providers, GPU/TTS
runtime health, or complete real-world video production.

M119 adds offline regression tests to the Windows CI full test suite.
