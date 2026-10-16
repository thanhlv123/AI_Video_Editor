M131 - ONE-TIME WINDOWS BOOTSTRAP
=================================

New setup entry point: setup_creator_studio.cmd
Existing launch entry point: start_creator_studio.cmd

On Windows with Python 3.12 installed, double-click
setup_creator_studio.cmd once. It creates the repository-local .venv
and installs the core GUI dependencies from requirements-runtime.txt.
It never installs into global Python, deletes a project, or overwrites
an incomplete existing .venv. If the local environment already exists,
it installs missing/updated requirements into that same environment.

FFmpeg and ffprobe must be installed separately and available on PATH.
This setup deliberately does not run package managers with admin
privileges or automatically download provider models, media, or voices.
Optional providers such as Piper Local and VoiceStudio Local still
require their own setup.

Read-only prerequisite report:
    python scripts/m131_bootstrap.py --check

Explicit environment installation:
    python scripts/m131_bootstrap.py --install

After setup, double-click start_creator_studio.cmd. It already prefers
the repository-local .venv interpreter.

Tests:
    python -m unittest tests.test_bootstrap_m131

The Windows release gate compiles the Python sources, imports all tests,
runs the real GUI smoke and FFmpeg acceptance, and executes the full
unittest suite. The setup script's network-install path is tested using
a subprocess stub and is not executed on CI.
