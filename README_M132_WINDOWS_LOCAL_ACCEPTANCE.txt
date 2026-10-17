M132 - WINDOWS LOCAL ACCEPTANCE
================================

Purpose
-------
M132 adds the final local release-candidate acceptance checkpoint before the
user starts hands-on testing on the Windows workstation.

One-click Windows verification
------------------------------
1. Run setup_creator_studio.cmd once if the local .venv is not ready.
2. Double-click verify_creator_studio.cmd.
3. A passing run prints:

   CREATOR STUDIO WINDOWS LOCAL: READY FOR USER TESTING

4. Then double-click start_creator_studio.cmd.

The acceptance report is written to:

    .automation\windows_local_acceptance.json

What the acceptance gate checks
-------------------------------
- M131 repository-local Python environment and runtime packages.
- Production launcher prerequisites.
- Runtime Doctor required checks: Python, PyQt6, FFmpeg, ffprobe,
  libx264, AAC, and production GUI source.
- Real production Creator Studio window construction in offscreen smoke mode.

CI mode
-------
GitHub Actions runs:

    python scripts/m132_windows_local_acceptance.py --ci

CI mode validates the same runtime/GUI capability using the GitHub runner's
Python environment. It intentionally does not require a repository-local .venv
because M131 has separate tests for creation and preservation of that local
environment.

Scope
-----
M132 is a readiness checkpoint, not VPS deployment. VPS and multi-user work
must not begin until the Windows-local build has been tested by the user and
the user explicitly approves the next phase.
